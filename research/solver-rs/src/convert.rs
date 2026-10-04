//! Card-text parsing, matching `bridge/solver/convert.py`'s format exactly:
//! `{rank}{suit}` tokens, space-separated (e.g. "AS KS QS 10H"), the same
//! text `mask_to_text`/`text_to_mask` produce and consume on the Python side.
//! This is the only module that touches card text — bitstate.rs and search.rs
//! stay pure ints, same separation as the Python solver.

use crate::bitstate::RANKS_PER_SUIT;

// Matches card.SUITS and card.RANKS exactly, including order.
const SUITS: [char; 4] = ['C', 'D', 'H', 'S'];
const RANKS: [&str; 13] = [
    "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A",
];

fn suit_index(c: char) -> Option<u32> {
    SUITS.iter().position(|&s| s == c).map(|i| i as u32)
}

fn rank_index(text: &str) -> Option<u32> {
    RANKS.iter().position(|&r| r == text).map(|i| i as u32)
}

/// "AS" -> 51, "2C" -> 0, "10H" -> 33. Panics on malformed input, since a bad
/// card text means a bug in the caller (this tool has no untrusted input).
pub fn text_to_index(token: &str) -> u32 {
    let suit_char = token.chars().last().expect("empty card token");
    let rank_text = &token[..token.len() - 1];
    let suit = suit_index(suit_char).unwrap_or_else(|| panic!("bad suit in {token:?}"));
    let rank = rank_index(rank_text).unwrap_or_else(|| panic!("bad rank in {token:?}"));
    suit * RANKS_PER_SUIT + rank
}

/// "AS KS QS" -> a 52-bit mask with those three bits set.
pub fn text_to_mask(text: &str) -> u64 {
    let mut mask: u64 = 0;
    for token in text.split_whitespace() {
        mask |= 1u64 << text_to_index(token);
    }
    mask
}

pub fn index_to_text(index: u32) -> String {
    let suit = SUITS[(index / RANKS_PER_SUIT) as usize];
    let rank = RANKS[(index % RANKS_PER_SUIT) as usize];
    format!("{rank}{suit}")
}

/// The strain letter maps to a trump suit index, or None for notrump.
/// Matches `trump_to_index`: any of "C","D","H","S" is a trump suit; "NT" is not.
pub fn trump_to_index(strain: &str) -> Option<u32> {
    match strain {
        "C" => Some(0),
        "D" => Some(1),
        "H" => Some(2),
        "S" => Some(3),
        _ => None, // "NT", or anything else — validated by the caller
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips_every_card() {
        for suit in 0..4u32 {
            for rank in 0..13u32 {
                let idx = suit * RANKS_PER_SUIT + rank;
                let text = index_to_text(idx);
                assert_eq!(text_to_index(&text), idx, "round trip failed for {text}");
            }
        }
    }

    #[test]
    fn matches_known_python_outputs() {
        // mask_to_text("AS") style tokens: rank first, then suit letter
        assert_eq!(text_to_index("AS"), 3 * RANKS_PER_SUIT + 12);
        assert_eq!(text_to_index("2C"), 0);
        assert_eq!(text_to_index("10H"), 2 * RANKS_PER_SUIT + 8);
        assert_eq!(index_to_text(0), "2C");
        assert_eq!(index_to_text(51), "AS");
    }

    #[test]
    fn trump_mapping_matches_suits_order() {
        assert_eq!(trump_to_index("C"), Some(0));
        assert_eq!(trump_to_index("D"), Some(1));
        assert_eq!(trump_to_index("H"), Some(2));
        assert_eq!(trump_to_index("S"), Some(3));
        assert_eq!(trump_to_index("NT"), None);
    }
}
