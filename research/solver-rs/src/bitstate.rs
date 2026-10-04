//! Packed-integer core for the Second-Highest double dummy solver.
//!
//! Direct port of `bridge/solver/bitstate.py`. Keep the two in sync: this file
//! is the specification, and every function here has a matching entry in
//! `tests/fixture.rs`, which is checked against the SAME
//! `tests/fixtures/endings.json` the Python solver uses.
//!
//! Encoding (identical to the Python core):
//!   card  suit * 13 + rank  — clubs 0-12, diamonds 13-25, hearts 26-38, spades 39-51
//!   rank  0 = deuce, 12 = ace, matching card.RANK_VALUE
//!   suit  0-3 for C/D/H/S, matching card.SUITS
//!   seat  0-3 for North/East/South/West, matching bridge.auction.PLAYERS
//!   hand  a 52-bit mask (u64), one bit per card held
//!   trump Some(0..=3) for a suit contract, None for No-Trump

pub const RANKS_PER_SUIT: u32 = 13;
pub const SUIT_COUNT: u32 = 4;
pub const SEAT_COUNT: u32 = 4;
pub const DECK_SIZE: u32 = RANKS_PER_SUIT * SUIT_COUNT;

/// North and South, matching bridge.auction.PLAYERS ordering.
pub const NS_SEATS: [u32; 2] = [0, 2];

pub const SUIT_MASK: u64 = (1u64 << RANKS_PER_SUIT) - 1;
pub const FULL_DECK: u64 = (1u64 << DECK_SIZE) - 1;

/// One 52-bit mask per suit, indexed by suit.
pub fn suit_mask(suit: u32) -> u64 {
    SUIT_MASK << (suit * RANKS_PER_SUIT)
}

pub fn suit_of(card: u32) -> u32 {
    card / RANKS_PER_SUIT
}

/// Rank of the second-highest set bit of every 13-bit mask, precomputed.
///
/// This is *the* primitive of the variant. A mask with one bit set answers
/// with that bit, which is the lone-card-wins rule falling out for free.
/// Index 0 is never a legal query and answers 0 (matches the Python table).
pub struct SecondHighest {
    table: Vec<u8>,
}

impl SecondHighest {
    pub fn build() -> Self {
        let size = 1usize << RANKS_PER_SUIT;
        let mut table = vec![0u8; size];
        for mask in 1..size {
            let top = 63 - (mask as u64).leading_zeros();
            let rest = (mask as u64) ^ (1u64 << top);
            table[mask] = if rest != 0 {
                (63 - rest.leading_zeros()) as u8
            } else {
                top as u8
            };
        }
        SecondHighest { table }
    }

    #[inline(always)]
    pub fn get(&self, mask: u64) -> u32 {
        self.table[mask as usize] as u32
    }
}

#[inline(always)]
pub fn cards_in(mask: u64) -> impl Iterator<Item = u32> {
    let mut m = mask;
    std::iter::from_fn(move || {
        if m == 0 {
            None
        } else {
            let low = m & m.wrapping_neg();
            m ^= low;
            Some(low.trailing_zeros())
        }
    })
}

#[inline(always)]
pub fn count(mask: u64) -> u32 {
    mask.count_ones()
}

/// Mask of cards that may legally be played. Mirrors `legal_plays`.
#[inline(always)]
pub fn legal_moves(hand: u64, led_suit: Option<u32>) -> u64 {
    match led_suit {
        None => hand,
        Some(suit) => {
            let follow = hand & suit_mask(suit);
            if follow != 0 { follow } else { hand }
        }
    }
}

/// Seat that wins the trick under the Second-Highest rule.
///
/// `plays` holds up to 4 card indices in play order, `plays[0]` played by
/// `leader`. Mirrors `bridge.trick.resolve_trick`: the winning suit is trump
/// when any trump was played, otherwise the led suit; the second-highest card
/// of that suit takes the trick, or the only card when just one was played.
#[inline(always)]
pub fn resolve(plays: &[u32], leader: u32, trump: Option<u32>, sh: &SecondHighest) -> u32 {
    let mut winning_suit = suit_of(plays[0]);
    if let Some(t) = trump {
        if plays.iter().any(|&idx| suit_of(idx) == t) {
            winning_suit = t;
        }
    }

    let base = winning_suit * RANKS_PER_SUIT;
    let ceiling = base + RANKS_PER_SUIT;
    let mut ranks: u64 = 0;
    for &idx in plays {
        if idx >= base && idx < ceiling {
            ranks |= 1u64 << (idx - base);
        }
    }

    let winner_card = base + sh.get(ranks);
    let offset = plays.iter().position(|&c| c == winner_card).unwrap() as u32;
    (leader + offset) % SEAT_COUNT
}

/// A point in the play, mid-trick or between tricks.
#[derive(Clone, Copy, Debug)]
pub struct Position {
    pub hands: [u64; 4],   // one mask per seat
    pub leader: u32,       // seat that led the current trick
    pub trick: [u32; 4],   // cards played to it so far, in play order
    pub trick_len: u32,
    pub trump: Option<u32>,
}

impl Position {
    pub fn new(hands: [u64; 4], leader: u32, trump: Option<u32>) -> Self {
        Position { hands, leader, trick: [0; 4], trick_len: 0, trump }
    }

    #[inline(always)]
    pub fn to_act(&self) -> u32 {
        (self.leader + self.trick_len) % SEAT_COUNT
    }

    #[inline(always)]
    pub fn led_suit(&self) -> Option<u32> {
        if self.trick_len == 0 { None } else { Some(suit_of(self.trick[0])) }
    }

    pub fn cards_left(&self) -> u32 {
        self.hands.iter().map(|&h| count(h)).sum()
    }

    #[inline(always)]
    pub fn moves(&self) -> u64 {
        legal_moves(self.hands[self.to_act() as usize], self.led_suit())
    }

    /// Play `card` for the seat to act. Returns the new position and, when the
    /// card completed a trick, the seat that won it (also the new leader).
    pub fn play(&self, card: u32, sh: &SecondHighest) -> (Position, Option<u32>) {
        let mut hands = self.hands;
        let actor = self.to_act() as usize;
        hands[actor] &= !(1u64 << card);

        let mut trick = self.trick;
        trick[self.trick_len as usize] = card;
        let trick_len = self.trick_len + 1;

        if trick_len < SEAT_COUNT {
            return (
                Position { hands, leader: self.leader, trick, trick_len, trump: self.trump },
                None,
            );
        }
        let winner = resolve(&trick[..4], self.leader, self.trump, sh);
        (Position::new(hands, winner, self.trump), Some(winner))
    }
}

/// Tricks still to be played from a position, counting the one in progress.
pub fn tricks_available(position: &Position) -> u32 {
    (position.cards_left() + position.trick_len) / SEAT_COUNT
}
