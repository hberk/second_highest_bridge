//! The solver for the browser: one played board, analysed decision by
//! decision, with one `Search` kept through the board.
//!
//! wasm32-unknown-unknown has no OS, so everything goes through two buffers
//! of u32 in this module's memory. JS writes a board into the input buffer,
//! calls `load`, then `analyse(i)` for the decisions it wants, latest first:
//! the endgame is cheap and fills the table the earlier tricks reuse.
//!
//! Input words: [leader seat, trump (0-3 = C D H S, 4 = notrump), table limit,
//! play count, then each seat's hand as two words (low 32 bits, high 20),
//! North East South West, then the plays as card numbers (13 * suit + rank,
//! rank 0 = the 2), in play order]. Seats are 0-3 = North East South West.
//!
//! `analyse` writes [card, tricks]* to the output buffer: each legal card's
//! N/S tricks for the REST of the hand after it, both sides perfect, the
//! same number `bridge/solver/api.card_values` gives. JS adds the tricks
//! already won.

use solver_rs::bitstate::{Position, SecondHighest};
use solver_rs::search::Search;
use std::cell::RefCell;

struct Board {
    engine: Search<'static>,
    /// The position before each play.
    positions: Vec<Position>,
}

thread_local! {
    static SH: &'static SecondHighest = Box::leak(Box::new(SecondHighest::build()));
    static BOARD: RefCell<Option<Board>> = const { RefCell::new(None) };
    static INPUT: RefCell<Vec<u32>> = const { RefCell::new(Vec::new()) };
    static OUTPUT: RefCell<Vec<u32>> = const { RefCell::new(Vec::new()) };
}

/// Room for `words` u32 of input; returns where to write them.
#[unsafe(no_mangle)]
pub extern "C" fn input(words: usize) -> *mut u32 {
    INPUT.with(|b| {
        let mut b = b.borrow_mut();
        b.clear();
        b.resize(words, 0);
        b.as_mut_ptr()
    })
}

/// Where `analyse` left its answer.
#[unsafe(no_mangle)]
pub extern "C" fn output() -> *const u32 {
    OUTPUT.with(|b| b.borrow().as_ptr())
}

/// Read the board in the input buffer. 0 when it loaded; otherwise
/// -1 malformed input, -2 hands that overlap or differ in size,
/// -(100 + i) when play i isn't legal for the seat to act.
#[unsafe(no_mangle)]
pub extern "C" fn load() -> i32 {
    let words = INPUT.with(|b| b.borrow().clone());
    BOARD.with(|b| *b.borrow_mut() = None);
    if words.len() < 12 {
        return -1;
    }
    let (leader, trump_word, limit, count) = (words[0], words[1], words[2], words[3] as usize);
    if leader > 3 || trump_word > 4 || words.len() != 12 + count || count > 52 {
        return -1;
    }
    let trump = if trump_word == 4 { None } else { Some(trump_word) };
    let mut hands = [0u64; 4];
    let mut seen = 0u64;
    for (seat, hand) in hands.iter_mut().enumerate() {
        *hand = words[4 + 2 * seat] as u64 | (words[5 + 2 * seat] as u64) << 32;
        if *hand >> 52 != 0 || *hand & seen != 0 {
            return -2;
        }
        seen |= *hand;
    }
    let size = hands[0].count_ones();
    if hands.iter().any(|h| h.count_ones() != size) || count > 4 * size as usize {
        return -2;
    }
    let sh = SH.with(|s| *s);
    let mut position = Position::new(hands, leader, trump);
    let mut positions = Vec::with_capacity(count);
    for (i, &card) in words[12..].iter().enumerate() {
        if card >= 52 || position.moves() & (1u64 << card) == 0 {
            return -(100 + i as i32);
        }
        positions.push(position.clone());
        position = position.play(card, sh).0;
    }
    BOARD.with(|b| {
        *b.borrow_mut() = Some(Board {
            engine: Search::with_limit(trump, sh, limit.max(1) as usize),
            positions,
        })
    });
    0
}

/// Score every legal card before play `i`; returns how many, or -1 when no
/// board is loaded or `i` is past its plays.
#[unsafe(no_mangle)]
pub extern "C" fn analyse(i: usize) -> i32 {
    BOARD.with(|b| {
        let mut b = b.borrow_mut();
        let Some(board) = b.as_mut() else { return -1 };
        let Some(position) = board.positions.get(i).cloned() else { return -1 };
        let values = board.engine.card_values(&position, None);
        OUTPUT.with(|o| {
            let mut o = o.borrow_mut();
            o.clear();
            for (card, tricks) in &values {
                o.push(*card);
                o.push(*tricks as u32);
            }
        });
        values.len() as i32
    })
}

/// Entries in the loaded board's table, for measuring memory.
#[unsafe(no_mangle)]
pub extern "C" fn table_entries() -> usize {
    BOARD.with(|b| b.borrow().as_ref().map_or(0, |board| board.engine.table_len()))
}

/// Drop the board and its table.
#[unsafe(no_mangle)]
pub extern "C" fn unload() {
    BOARD.with(|b| *b.borrow_mut() = None);
}
