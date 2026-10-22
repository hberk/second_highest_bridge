//! Verifies this port against the SAME frozen fixture the Python solver is
//! checked against — `tests/fixtures/endings.json`, produced by exhaustive
//! enumeration (`bridge/solver/brute.py`) and never hand-edited. A disagreement
//! here means a bug in this port, exactly like a disagreement in
//! tests/test_solver_search.py means a bug in search.py: never a speedup.
//!
//! This is the load-bearing test in this crate. Everything else is a detail;
//! this is the guarantee that the Rust port computes the same answers as the
//! rest of the project's double dummy work.

use serde::Deserialize;
use serde_json::Value;
use solver_rs::bitstate::{cards_in, Position, SecondHighest, NS_SEATS};
use solver_rs::convert::{text_to_index, text_to_mask, trump_to_index};
use solver_rs::search::Search;
use std::collections::HashMap;
use std::path::PathBuf;

#[derive(Deserialize)]
struct FixtureFile {
    positions: Vec<FixtureEntry>,
}

#[derive(Deserialize)]
struct FixtureEntry {
    id: String,
    cards_each: u32,
    strain: String,
    leader: String,
    hands: HashMap<String, String>,
    trick: String,
    ns_tricks: i32,
}

fn fixture_path() -> PathBuf {
    // research/solver-rs/tests/fixture.rs -> ../../../tests/fixtures/endings.json
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("endings.json")
}

fn load_fixture() -> Vec<FixtureEntry> {
    let text = std::fs::read_to_string(fixture_path())
        .expect("tests/fixtures/endings.json must exist — run tests/fixtures/generate_endings.py");
    let parsed: FixtureFile = serde_json::from_str(&text).expect("fixture must be valid JSON");
    parsed.positions
}

fn seat_index(name: &str) -> u32 {
    match name {
        "North" => 0,
        "East" => 1,
        "South" => 2,
        "West" => 3,
        other => panic!("not a seat: {other}"),
    }
}

fn position_of(entry: &FixtureEntry) -> Position {
    let mut hands = [0u64; 4];
    for seat_name in ["North", "East", "South", "West"] {
        hands[seat_index(seat_name) as usize] = text_to_mask(&entry.hands[seat_name]);
    }
    let mut trick = [0u32; 4];
    let mut trick_len = 0u32;
    for token in entry.trick.split_whitespace() {
        trick[trick_len as usize] = text_to_index(token);
        trick_len += 1;
    }
    let trump = if entry.strain == "NT" {
        None
    } else {
        trump_to_index(&entry.strain)
    };
    Position {
        hands,
        leader: seat_index(&entry.leader),
        trick,
        trick_len,
        trump,
    }
}

#[test]
fn fixture_file_is_readable_and_nonempty() {
    let positions = load_fixture();
    assert!(!positions.is_empty(), "fixture is empty");
    assert!(positions.len() >= 100, "fixture looks truncated: {} entries", positions.len());
}

/// The whole fixture, by default up to 4 cards per hand (fast: well under a
/// second). Set SOLVER_RS_MAX_CARDS to re-check deeper positions, e.g.
///   SOLVER_RS_MAX_CARDS=5 cargo test --release -- --nocapture
#[test]
fn reproduces_the_whole_fixture() {
    let max_cards: u32 = std::env::var("SOLVER_RS_MAX_CARDS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(4);

    let sh = SecondHighest::build();
    let mut checked = 0;
    for entry in load_fixture() {
        if entry.cards_each > max_cards {
            continue;
        }
        let position = position_of(&entry);
        let mut engine = Search::new(position.trump, &sh);
        let actual = engine.value(&position);
        assert_eq!(
            actual, entry.ns_tricks,
            "{}: fixture says {}, Rust solver says {}",
            entry.id, entry.ns_tricks, actual
        );
        checked += 1;
    }
    assert!(checked >= 100, "only checked {checked} positions");
    eprintln!("reproduced {checked} fixture positions up to {max_cards} cards each");
}

/// A full table overwrites positions, never trusts one past its limit: with
/// the table holding a handful of slots the whole fixture must come out the
/// same, both as one value and as every card's value.
#[test]
fn a_cleared_table_changes_no_answer() {
    let sh = SecondHighest::build();
    let mut checked = 0;
    let mut clears = 0;
    for entry in load_fixture() {
        if entry.cards_each > 4 {
            continue;
        }
        let position = position_of(&entry);
        for limit in [1usize, 7, 64] {
            let mut engine = Search::with_limit(position.trump, &sh, limit);
            assert_eq!(engine.value(&position), entry.ns_tricks,
                       "{}: wrong with the table capped at {limit}", entry.id);
            let capped = Search::with_limit(position.trump, &sh, limit).card_values(&position, None);
            let free = Search::new(position.trump, &sh).card_values(&position, None);
            assert_eq!(capped, free, "{}: card values differ capped at {limit}", entry.id);
            clears += engine.clears;
        }
        checked += 1;
    }
    assert!(checked >= 100, "only checked {checked} positions");
    assert!(clears > 0, "the limit never overwrote a position, so this tested nothing");
}

/// Every hand-crafted worst case by name, regardless of the depth cutoff above
/// — these are exactly the shapes most likely to expose an equivalence or
/// trump-handling bug, and skipping them silently would defeat the point.
#[test]
fn reproduces_every_crafted_worst_case() {
    let sh = SecondHighest::build();
    let mut seen_ids = Vec::new();
    for entry in load_fixture() {
        if !entry.id.starts_with("crafted-") {
            continue;
        }
        let position = position_of(&entry);
        let mut engine = Search::new(position.trump, &sh);
        let actual = engine.value(&position);
        assert_eq!(actual, entry.ns_tricks, "{}: mismatch", entry.id);
        seen_ids.push(entry.id);
    }
    for required in [
        "crafted-single-suit-nt",
        "crafted-single-suit-trump",
        "crafted-mutual-voids",
        "crafted-stranded-ace",
        "crafted-two-suit",
        "crafted-ruff-race",
    ] {
        assert!(
            seen_ids.iter().any(|id| id == required),
            "fixture lost coverage of {required}"
        );
    }
}

/// The result Stage 1 of this project is built around: A-K-Q of one suit,
/// nothing else, takes zero tricks. Kept as its own test — independent of the
/// fixture file — because it is the single most important behavioural claim
/// this whole solver makes, and it should never depend on the fixture being
/// intact to be checked.
#[test]
fn top_three_cards_of_a_suit_take_no_tricks() {
    let sh = SecondHighest::build();
    let hands: [&str; 4] = ["AS KS QS", "JS 10S 9S", "8S 7S 6S", "5S 4S 3S"];
    let mut masks = [0u64; 4];
    for (i, h) in hands.iter().enumerate() {
        masks[i] = text_to_mask(h);
    }
    let position = Position {
        hands: masks,
        leader: 0,
        trick: [0; 4],
        trick_len: 0,
        trump: None,
    };
    let mut engine = Search::new(None, &sh);
    assert_eq!(engine.value(&position), 0);
}

/// Cross-checks the CLI binary itself (not just the library) against the same
/// fixture, on a handful of entries — the JSON parsing/output path has its own
/// bugs a library-only test cannot see (seat name typos, trump/strain mixups,
/// off-by-one in the query loop).
#[test]
fn cli_binary_matches_the_fixture() {
    let exe = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target")
        .join(if cfg!(debug_assertions) { "debug" } else { "release" })
        .join("solver-rs.exe");
    if !exe.exists() {
        panic!("solver-rs.exe not built at {exe:?} — run `cargo build` first");
    }

    let mut checked = 0;
    for entry in load_fixture() {
        if entry.cards_each > 3 || !entry.trick.is_empty() {
            continue; // keep this test fast; the library test covers depth
        }
        let input = serde_json::json!({
            "hands": entry.hands,
            "strain": entry.strain,
            "queries": [{"leader": entry.leader, "trick": []}],
        });

        use std::io::Write;
        use std::process::{Command, Stdio};
        let mut child = Command::new(&exe)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("failed to launch solver-rs.exe");
        child
            .stdin
            .as_mut()
            .unwrap()
            .write_all(input.to_string().as_bytes())
            .unwrap();
        let output = child.wait_with_output().expect("solver-rs.exe did not run");
        assert!(
            output.status.success(),
            "{}: solver-rs.exe failed: {}",
            entry.id,
            String::from_utf8_lossy(&output.stderr)
        );

        let parsed: Value = serde_json::from_slice(&output.stdout).expect("CLI must emit JSON");
        let ns_tricks = parsed["results"][0]["ns_tricks"].as_i64().unwrap() as i32;
        assert_eq!(ns_tricks, entry.ns_tricks, "{}: CLI mismatch", entry.id);
        checked += 1;
    }
    assert!(checked >= 20, "only checked {checked} positions via the CLI");
}

/// `card_values` against the fixture: for every position up to 4 cards each,
/// the best card's value is the fixture's answer, and every card's value is
/// the same whatever the first guess (none, too low, too high) and matches
/// playing the card and solving the rest from scratch.
#[test]
fn card_values_agree_with_the_fixture_whatever_the_guess() {
    let sh = SecondHighest::build();
    let mut checked = 0;
    for entry in load_fixture() {
        if entry.cards_each > 4 {
            continue;
        }
        let position = position_of(&entry);
        let mut reference = Vec::new();
        for card in cards_in(position.moves()) {
            let (after, winner) = position.play(card, &sh);
            let gained = match winner {
                Some(w) if NS_SEATS.contains(&w) => 1,
                _ => 0,
            };
            reference.push((card, gained + Search::new(position.trump, &sh).value(&after)));
        }
        for guess in [None, Some(0), Some(13)] {
            let values = Search::new(position.trump, &sh).card_values(&position, guess);
            assert_eq!(values, reference, "{}: card_values with guess {guess:?}", entry.id);
        }
        let ns_to_act = NS_SEATS.contains(&position.to_act());
        let best = if ns_to_act {
            reference.iter().map(|v| v.1).max()
        } else {
            reference.iter().map(|v| v.1).min()
        };
        assert_eq!(best, Some(entry.ns_tricks), "{}: best card vs fixture", entry.id);
        checked += 1;
    }
    assert!(checked >= 100, "only checked {checked} positions");
    eprintln!("card_values matched {checked} fixture positions");
}
