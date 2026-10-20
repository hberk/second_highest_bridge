//! Exact double dummy search: zero-window alpha-beta, transposition table,
//! rank-equivalence reduction, trick-first move ordering.
//!
//! Direct port of `bridge/solver/search.py`'s PRODUCTION configuration only.
//! The Python version keeps four independently-switchable flags
//! (use_table / normalise_key / reduce_moves / ordering) so each optimisation
//! could be measured in isolation during development — that ablation work is
//! done and recorded in docs/SOLVER.md, so this port hard-codes the winning
//! configuration (all four on, ordering="trick") rather than re-porting the
//! switches. If a fifth optimisation ever needs the same kind of ablation,
//! add the flags back here first.
//!
//! Every idea below is explained at length in search.py; comments here are
//! kept short and point back there rather than repeating the reasoning.

use crate::bitstate::{
    cards_in, legal_moves, resolve, suit_of, tricks_available, Position, SecondHighest,
    NS_SEATS, RANKS_PER_SUIT, SEAT_COUNT, SUIT_MASK,
};
use rustc_hash::FxHashMap;

/// The most transposition-table entries a `Search` keeps.
///
/// The table had no bound, and it grows by doubling: on challenge deal 197
/// (2NT by South, every card of the hand scored by `line_values`) it reached
/// 206 million entries and 8.9 GB, and two such deals at once swapped a 16 GB
/// machine to a standstill. 50 million entries fit in 2^26 buckets, about
/// 2.2 GB, so the table never grows past that (3.3 GB for the moment the
/// last doubling copies). An entry holds a 16-byte key and its bounds, 32
/// bytes with alignment, so storing tricks-left beside them costs nothing.
///
/// When full, the shallow entries go and the deep ones stay (`evict`).
/// Clearing the whole table instead made deal 197 more than six times slower:
/// a deep position is expensive to search again, and the shallow ones are
/// both the most numerous and the cheapest. Keeping the deep half, deal 197
/// took 2,174s against 1,049s uncapped at a 3.1 GB peak (24 evictions); the
/// next three largest lines (62-68M entries) 13-25% longer; lines under the
/// limit, unchanged. Values identical on all 15 lines re-solved (2026-10-19). Either is sound: an entry only
/// caches bounds on a position's value, so losing one costs search time,
/// never a different answer -- `tests/fixture.rs` re-checks the fixture with
/// tiny limits.
pub const MAX_TABLE_ENTRIES: usize = 50_000_000;

pub struct Search<'a> {
    trump: Option<u32>,
    sh: &'a SecondHighest,
    /// Bounds on N/S's tricks from a position, and its tricks left.
    table: FxHashMap<u128, (i32, i32, i32)>,
    limit: usize,
    pub nodes: u64,
    pub probes: u64,
    pub hits: u64,
    /// Times the table reached `limit` and shed its shallow entries.
    pub clears: u64,
}

impl<'a> Search<'a> {
    pub fn new(trump: Option<u32>, sh: &'a SecondHighest) -> Self {
        Self::with_limit(trump, sh, MAX_TABLE_ENTRIES)
    }

    /// A search whose table is cleared once it holds `limit` entries.
    pub fn with_limit(trump: Option<u32>, sh: &'a SecondHighest, limit: usize) -> Self {
        Search {
            trump,
            sh,
            table: FxHashMap::default(),
            limit: limit.max(1),
            nodes: 0,
            probes: 0,
            hits: 0,
            clears: 0,
        }
    }

    pub fn table_len(&self) -> usize {
        self.table.len()
    }

    // ── Rank equivalence ────────────────────────────────────────────────

    /// Position key with ranks compressed to their order among live cards.
    /// Only valid at a trick boundary (search.py's `_key`, normalise_key=True path).
    ///
    /// Not a literal port of the bit-shift scheme in search.py's `_key`: that
    /// version builds the key with four 13-bit left-shifts per suit (one per
    /// seat), which is fine for Python's arbitrary-precision ints but silently
    /// wraps in any fixed-width Rust integer — the ~210-bit result overflowed
    /// u64 and caused real transposition-table collisions, caught by
    /// tests/fixture.rs disagreeing with the frozen fixture on two positions.
    ///
    /// This computes the same INFORMATION (which of 4 seats holds each live,
    /// rank-compressed position — a 2-bit code per position) but packs it
    /// densely: up to 13 live positions per suit * 2 bits = 26 bits per suit,
    /// 4 suits + 2 bits for leader = 106 bits, well inside u128. The two
    /// encodings are not byte-compatible, and don't need to be — only that
    /// positions in the same rank-equivalence class map to the same key here,
    /// which this preserves exactly (same compression logic, same leader).
    fn key(&self, hands: &[u64; 4], leader: u32) -> u128 {
        let mut key: u128 = leader as u128;
        for suit in 0..4u32 {
            let base = suit * RANKS_PER_SUIT;
            let h: [u64; 4] = [
                (hands[0] >> base) & SUIT_MASK,
                (hands[1] >> base) & SUIT_MASK,
                (hands[2] >> base) & SUIT_MASK,
                (hands[3] >> base) & SUIT_MASK,
            ];

            let mut suit_code: u128 = 0;
            let mut position = 0u32;
            let mut live = h[0] | h[1] | h[2] | h[3];
            while live != 0 {
                let low = live & live.wrapping_neg();
                let seat_code: u128 = if h[0] & low != 0 {
                    0
                } else if h[1] & low != 0 {
                    1
                } else if h[2] & low != 0 {
                    2
                } else {
                    3
                };
                suit_code |= seat_code << (2 * position);
                position += 1;
                live ^= low;
            }
            // `position` is now the live count for this suit (0-13). It must be
            // packed in too, not just the per-position seat codes: a single
            // card held by seat 0 (code 0b00) is bit-identical to zero live
            // cards, and more generally any all-seat-0 prefix collides with a
            // shorter or empty suit. A real collision from exactly this hole
            // was caught by tests/fixture.rs on random-3-04 (disagreed with
            // the frozen fixture) — 4 bits for the count plus 26 for up to 13
            // two-bit codes is 30 bits per suit, 122 total with the 2-bit
            // leader, comfortably inside u128.
            key = (key << 30) | ((position as u128) << 26) | suit_code;
        }
        key
    }

    /// Drop moves interchangeable with a lower card of the same run.
    /// search.py's `_distinct_moves`.
    fn distinct_moves(&self, hands: &[u64; 4], seat: usize, moves: u64, table: u64) -> u64 {
        let elsewhere = ((hands[0] | hands[1] | hands[2] | hands[3]) & !hands[seat]) | table;
        let mut keep: u64 = 0;

        for suit in 0..4u32 {
            let base = suit * RANKS_PER_SUIT;
            let mut mine = (moves >> base) & SUIT_MASK;
            if mine == 0 {
                continue;
            }
            let others = (elsewhere >> base) & SUIT_MASK;

            let mut previous: i32 = -1;
            while mine != 0 {
                let low = mine & mine.wrapping_neg();
                let rank = low.trailing_zeros() as i32;
                let gap: u64 = ((1u64 << rank) - 1) & !((1u64 << (previous + 1)) - 1);
                if previous < 0 || (others & gap) != 0 {
                    keep |= low << base;
                }
                previous = rank;
                mine ^= low;
            }
        }
        keep
    }

    // ── Move ordering ───────────────────────────────────────────────────

    /// search.py's `_ordered` with ordering="trick".
    fn ordered(&self, moves: u64, seat: u32, leader: u32, trick: &[u32]) -> Vec<u32> {
        let cards: Vec<u32> = cards_in(moves).collect();
        if cards.len() < 2 || trick.is_empty() {
            return cards;
        }

        let trump = self.trump;
        let mut winning_suit = suit_of(trick[0]);
        if let Some(t) = trump {
            if trick.iter().any(|&c| suit_of(c) == t) {
                winning_suit = t;
            }
        }

        let base = winning_suit * RANKS_PER_SUIT;
        let ceiling = base + RANKS_PER_SUIT;
        let mut ranks: u64 = 0;
        let mut holder = [u32::MAX; 13];
        for (offset, &played) in trick.iter().enumerate() {
            if played >= base && played < ceiling {
                let rank = (played - base) as usize;
                ranks |= 1u64 << rank;
                holder[rank] = (leader + offset as u32) % SEAT_COUNT;
            }
        }

        let side = seat & 1;
        let standing = holder[self.sh.get(ranks) as usize];
        // Mirrors Python's `can_ruff = trump is not None and winning_suit != trump`
        let can_ruff = trump.is_some() && trump != Some(winning_suit);

        let mut scored: Vec<(u32, u32)> = Vec::with_capacity(cards.len());
        for &card in &cards {
            let winner = if can_ruff && suit_of(card) == trump.unwrap() {
                seat
            } else if card >= base && card < ceiling {
                let rank = (card - base) as usize;
                let second = self.sh.get(ranks | (1u64 << rank)) as usize;
                if second == rank {
                    seat
                } else {
                    holder[second]
                }
            } else {
                standing
            };
            let priority = if (winner & 1) == side { 0 } else { 1 };
            scored.push((priority, card));
        }
        scored.sort_unstable();
        scored.into_iter().map(|(_, card)| card).collect()
    }

    // ── Zero-window search ──────────────────────────────────────────────

    /// Can N/S still take at least `need` tricks? Called at trick boundaries.
    fn reach(&mut self, hands: [u64; 4], leader: u32, need: i32, tricks_left: i32) -> bool {
        if need <= 0 {
            return true;
        }
        if need > tricks_left {
            return false;
        }

        self.probes += 1;
        let key = self.key(&hands, leader);
        let mut low = 0i32;
        let mut high = tricks_left;
        if let Some(&(l, h, _)) = self.table.get(&key) {
            low = l;
            high = h;
            if need <= low {
                self.hits += 1;
                return true;
            }
            if need > high {
                self.hits += 1;
                return false;
            }
        }

        let result = self.in_trick(hands, leader, [0; 4], 0, 0, need, tricks_left);

        if result {
            if need > low {
                low = need;
            }
        } else if need - 1 < high {
            high = need - 1;
        }
        if self.table.len() >= self.limit && !self.table.contains_key(&key) {
            self.evict();
        }
        self.table.insert(key, (low, high, tricks_left));
        result
    }

    /// Make room in a full table: keep the deepest entries, at most half the
    /// limit, and drop the rest. Keeps the allocation, so there's no regrowth.
    fn evict(&mut self) {
        let mut at_depth = [0usize; 14];
        for &(_, _, depth) in self.table.values() {
            at_depth[depth.clamp(0, 13) as usize] += 1;
        }
        // The shallowest depth whose entries and everything deeper fit in half.
        let mut keep_from = 14;
        let mut kept = 0;
        while keep_from > 0 && kept + at_depth[keep_from - 1] <= self.limit / 2 {
            keep_from -= 1;
            kept += at_depth[keep_from];
        }
        let keep_from = keep_from as i32;
        // Drained and refilled, not `retain`ed: removing in place leaves
        // deleted markers that count towards the table's load, so it doubled
        // long before reaching the limit (6.2 GB measured on deal 197).
        // `drain` keeps the allocation and resets every slot; the kept half
        // waits in a Vec meanwhile (about 0.8 GB at the default limit).
        let kept: Vec<(u128, (i32, i32, i32))> = self
            .table
            .drain()
            .filter(|&(_, (_, _, depth))| depth >= keep_from)
            .collect();
        self.table.extend(kept);
        self.clears += 1;
    }

    /// Play out the trick in progress. No table probes: mid-trick only.
    /// search.py's `_in_trick`.
    #[allow(clippy::too_many_arguments)]
    fn in_trick(
        &mut self,
        hands: [u64; 4],
        leader: u32,
        trick: [u32; 4],
        trick_len: usize,
        table: u64,
        need: i32,
        tricks_left: i32,
    ) -> bool {
        self.nodes += 1;

        let seat = (leader + trick_len as u32) % SEAT_COUNT;
        let led = if trick_len == 0 {
            None
        } else {
            Some(suit_of(trick[0]))
        };
        let moves = legal_moves(hands[seat as usize], led);
        let moves = self.distinct_moves(&hands, seat as usize, moves, table);

        let maximizing = NS_SEATS.contains(&seat);
        let ordered = self.ordered(moves, seat, leader, &trick[..trick_len]);

        for card in ordered {
            let mut rest = hands;
            rest[seat as usize] &= !(1u64 << card);
            let mut buf = trick;
            buf[trick_len] = card;
            let new_len = trick_len + 1;

            let ok = if new_len == SEAT_COUNT as usize {
                let winner = resolve(&buf[..4], leader, self.trump, self.sh);
                let gained = if NS_SEATS.contains(&winner) { 1 } else { 0 };
                self.reach(rest, winner, need - gained, tricks_left - 1)
            } else {
                self.in_trick(
                    rest,
                    leader,
                    buf,
                    new_len,
                    table | (1u64 << card),
                    need,
                    tricks_left,
                )
            };

            if maximizing {
                if ok {
                    return true;
                }
            } else if !ok {
                return false;
            }
        }
        !maximizing
    }

    // ── Entry points ─────────────────────────────────────────────────────

    /// Can N/S take at least `need` tricks from this position?
    pub fn reaches(&mut self, position: &Position, need: i32) -> bool {
        let tricks = tricks_available(position) as i32;
        if position.trick_len > 0 {
            let mut table: u64 = 0;
            for i in 0..position.trick_len as usize {
                table |= 1u64 << position.trick[i];
            }
            self.in_trick(
                position.hands,
                position.leader,
                position.trick,
                position.trick_len as usize,
                table,
                need,
                tricks,
            )
        } else {
            self.reach(position.hands, position.leader, need, tricks)
        }
    }

    /// Tricks N/S take with optimal play, by binary search on `reaches`.
    pub fn value(&mut self, position: &Position) -> i32 {
        let mut low = 0i32;
        let mut high = tricks_available(position) as i32;
        while low < high {
            let mid = (low + high + 1) / 2;
            if self.reaches(position, mid) {
                low = mid;
            } else {
                high = mid - 1;
            }
        }
        low
    }

    /// Tricks N/S take, found by stepping outward from a first guess.
    /// search.py's `value_from`.
    pub fn value_from(&mut self, position: &Position, guess: i32) -> i32 {
        let total = tricks_available(position) as i32;
        let mut estimate = guess.clamp(0, total);
        if self.reaches(position, estimate) {
            while estimate < total && self.reaches(position, estimate + 1) {
                estimate += 1;
            }
            return estimate;
        }
        estimate -= 1;
        while estimate > 0 && !self.reaches(position, estimate) {
            estimate -= 1;
        }
        estimate
    }

    /// Every legal card for the seat to act, mapped to the N/S tricks for the
    /// rest of the hand (counting the trick in progress) after playing it.
    /// The per-card display: what each card is worth.
    ///
    /// Each card is solved with `value_from`, stepping out from the previous
    /// card's answer, since sibling cards usually land on the same total or
    /// one off. `guess` seeds the first card (say, the last decision's best);
    /// with none, the first card is binary searched. A guess only changes the
    /// order of the zero-window probes, never an answer. Measured against a
    /// binary search per card (bench_cards, 10 deals, tricks 1-3, one Search
    /// kept through the hand): identical values, 1.15x fewer nodes median
    /// (1.03x-1.80x), 1.14x less time.
    pub fn card_values(&mut self, position: &Position, mut guess: Option<i32>) -> Vec<(u32, i32)> {
        let mut out = Vec::new();
        for card in cards_in(position.moves()) {
            let (after, winner) = position.play(card, self.sh);
            let gained = match winner {
                Some(w) if NS_SEATS.contains(&w) => 1,
                _ => 0,
            };
            let rest = match guess {
                Some(g) => self.value_from(&after, g - gained),
                None => self.value(&after),
            };
            out.push((card, gained + rest));
            guess = Some(gained + rest);
        }
        out
    }
}
