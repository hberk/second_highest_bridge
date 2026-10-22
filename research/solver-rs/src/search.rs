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

/// The most transposition-table slots a `Search` keeps.
///
/// The table had no bound, and it grows by doubling: on challenge deal 197
/// (2NT by South, every card of the hand scored by `line_values`) it reached
/// 206 million entries and 8.9 GB, and two such deals at once swapped a 16 GB
/// machine to a standstill. 2^26 slots of 24 bytes are 1.6 GB, so the table
/// never grows past that (2.4 GB for the moment the last doubling copies).
///
/// Once it is full, a new position overwrites the shallowest of the four in
/// its bucket (`Table`): a deep position is the expensive one to search
/// again. Sound for any size: an entry only caches bounds on a position's
/// value, so losing one costs search time, never a different answer --
/// `tests/fixture.rs` re-checks the fixture with tiny limits.
pub const MAX_TABLE_ENTRIES: usize = 1 << 26;

/// Slots in one bucket: where a position may be stored.
const WAYS: usize = 4;

/// The slots a table starts with, and grows from by doubling.
const FIRST_SLOTS: usize = 1 << 16;

/// The transposition table: bounds on N/S's tricks from a position, and its
/// tricks left, at most `limit` slots in buckets of `WAYS`.
///
/// It replaced a hash map that, when full, dropped its shallow half
/// (2026-10-22). In the History replayer's order (last trick first, one
/// `Search` per board) on 10 stored robot lines, tricks 1-2 took 39 s median
/// and 403 s at worst with 4M slots (100 MB), against 139 s and 906 s for the
/// map capped at 1M entries (~130 MB), every card's value identical. The map
/// emptied half of itself over 100 times on a hard board and rebuilt the
/// rest each time; a full bucket here loses one shallow entry.
///
/// A slot is three words: the key's two halves, then the low bound, high
/// bound and tricks left a byte each. Tricks left 0 marks an empty slot,
/// since a stored position always has a trick to play, so a new table is
/// zeroed memory.
struct Table {
    slots: Vec<[u64; 3]>,
    limit: usize,
    len: usize,
}

impl Table {
    fn new(limit: usize, first: usize) -> Self {
        let limit = limit.max(WAYS).next_power_of_two();
        Table { slots: vec![[0; 3]; first.clamp(WAYS, limit).next_power_of_two()], limit, len: 0 }
    }

    /// The first slot of a key's bucket. The key's bits are packed by suit,
    /// so they're mixed (MurmurHash3's finaliser) before any are taken: an
    /// unmixed multiply left whole suits out of the index, and the search was
    /// 3.6x slower for the collisions.
    #[inline(always)]
    fn bucket(&self, k0: u64, k1: u64) -> usize {
        let mut h = k0 ^ k1.wrapping_mul(0xC2B2_AE3D_27D4_EB4F);
        h ^= h >> 33;
        h = h.wrapping_mul(0xFF51_AFD7_ED55_8CCD);
        h ^= h >> 33;
        h = h.wrapping_mul(0xC4CE_B9FE_1A85_EC53);
        h ^= h >> 33;
        (h as usize) & (self.slots.len() - WAYS)
    }

    /// The low and high bounds stored for a key.
    #[inline(always)]
    fn get(&self, key: u128) -> Option<(i32, i32)> {
        let (k0, k1) = (key as u64, (key >> 64) as u64);
        let b = self.bucket(k0, k1);
        for slot in &self.slots[b..b + WAYS] {
            if slot[0] == k0 && slot[1] == k1 && slot[2] >> 16 != 0 {
                return Some(((slot[2] & 0xFF) as i32, (slot[2] >> 8 & 0xFF) as i32));
            }
        }
        None
    }

    /// Store a key's bounds: in its own slot if it has one, else an empty
    /// one, else over the bucket's shallowest. True when that overwrote
    /// another position.
    fn put(&mut self, key: u128, low: i32, high: i32, tricks_left: i32) -> bool {
        if self.len * 4 >= self.slots.len() * 3 && self.slots.len() < self.limit {
            self.grow();
        }
        let (k0, k1) = (key as u64, (key >> 64) as u64);
        let b = self.bucket(k0, k1);
        let mut target = b;
        for i in b..b + WAYS {
            let slot = &self.slots[i];
            if slot[0] == k0 && slot[1] == k1 && slot[2] >> 16 != 0 {
                target = i;
                break;
            }
            if slot[2] >> 16 < self.slots[target][2] >> 16 {
                target = i;
            }
        }
        let old = self.slots[target];
        let replaced = old[2] >> 16 != 0 && (old[0] != k0 || old[1] != k1);
        if old[2] >> 16 == 0 {
            self.len += 1;
        }
        self.slots[target] = [k0, k1, low as u64 | (high as u64) << 8 | (tricks_left as u64) << 16];
        replaced
    }

    /// Double the slots and put every entry back.
    fn grow(&mut self) {
        let doubled = vec![[0; 3]; self.slots.len() * 2];
        let old = std::mem::replace(&mut self.slots, doubled);
        self.len = 0;
        for slot in old {
            if slot[2] >> 16 != 0 {
                let key = slot[0] as u128 | (slot[1] as u128) << 64;
                let depth = (slot[2] >> 16) as i32;
                self.put(key, (slot[2] & 0xFF) as i32, (slot[2] >> 8 & 0xFF) as i32, depth);
            }
        }
    }
}

pub struct Search<'a> {
    trump: Option<u32>,
    sh: &'a SecondHighest,
    table: Table,
    pub nodes: u64,
    pub probes: u64,
    pub hits: u64,
    /// Times a full bucket lost a position to a new one.
    pub clears: u64,
}

impl<'a> Search<'a> {
    pub fn new(trump: Option<u32>, sh: &'a SecondHighest) -> Self {
        Self::with_limit(trump, sh, MAX_TABLE_ENTRIES)
    }

    /// A search whose table holds at most `limit` slots (rounded up to a
    /// power of two, at least 4). It starts small and doubles as it fills.
    pub fn with_limit(trump: Option<u32>, sh: &'a SecondHighest, limit: usize) -> Self {
        Self::with_table(trump, sh, limit, FIRST_SLOTS)
    }

    /// As `with_limit`, but every slot is allocated at once, so memory never
    /// passes the final size: growing copies the table, and for that moment
    /// holds one and a half times it. For the browser, where memory is the
    /// limit and a whole board fills the table anyway.
    pub fn preallocated(trump: Option<u32>, sh: &'a SecondHighest, limit: usize) -> Self {
        Self::with_table(trump, sh, limit, limit)
    }

    fn with_table(trump: Option<u32>, sh: &'a SecondHighest, limit: usize, first: usize) -> Self {
        Search {
            trump,
            sh,
            table: Table::new(limit, first),
            nodes: 0,
            probes: 0,
            hits: 0,
            clears: 0,
        }
    }

    /// Positions in the table.
    pub fn table_len(&self) -> usize {
        self.table.len
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

    /// search.py's `_ordered` with ordering="trick": the cards that win the
    /// trick for the seat's side so far first, each group low to high. Into
    /// an array, not a Vec: allocating two per node was 15% of the search
    /// (2026-10-22, same nodes).
    fn ordered(&self, moves: u64, seat: u32, leader: u32, trick: &[u32]) -> ([u32; 13], usize) {
        let mut out = [0u32; 13];
        let mut n = 0;
        if trick.is_empty() || moves.count_ones() < 2 {
            for card in cards_in(moves) {
                out[n] = card;
                n += 1;
            }
            return (out, n);
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

        let mut losing = [0u32; 13];
        let mut lost = 0;
        for card in cards_in(moves) {
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
            if (winner & 1) == side {
                out[n] = card;
                n += 1;
            } else {
                losing[lost] = card;
                lost += 1;
            }
        }
        out[n..n + lost].copy_from_slice(&losing[..lost]);
        (out, n + lost)
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
        if let Some((l, h)) = self.table.get(key) {
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
        if self.table.put(key, low, high, tricks_left) {
            self.clears += 1;
        }
        result
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
        let (ordered, count) = self.ordered(moves, seat, leader, &trick[..trick_len]);

        for &card in &ordered[..count] {
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
