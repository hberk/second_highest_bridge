//! Command-line entry point: reads one JSON object from stdin, writes one back
//! to stdout. `research/dd_dataset.py` shells out to this binary per (deal,
//! strain) task; nothing else in the project calls it.
//!
//! Input:
//!   {
//!     "hands": {"North": "AS KS ...", "East": "...", "South": "...", "West": "..."},
//!     "strain": "S" | "NT" | ...,
//!     "queries": [
//!       {"leader": "East", "trick": []},
//!       {"leader": "South", "trick": []}
//!     ]
//!   }
//!
//! All queries in one call share ONE Search (one transposition table, keyed
//! only on hands + leader, which is safe across leaders because the table key
//! never encodes who leads a position other than as part of its own state).
//! The first query is solved with `value`; every later query starts from the
//! immediately-preceding query's answer via `value_from` — this is the exact
//! shape of `solve_strain` in dd_dataset.py, and is where the measured 1.45x
//! pairing win comes from (see CLAUDE.md, Dataset invariants).
//!
//! Output:
//!   {
//!     "results": [
//!       {"leader": "East", "ns_tricks": 7, "nodes": 123456},
//!       {"leader": "South", "ns_tricks": 6, "nodes": 54321}
//!     ],
//!     "table_entries": 78901,
//!     "nodes_total": 177777,
//!     "seconds": 12.34
//!   }
//!
//! Errors go to stderr as plain text and the process exits non-zero; the
//! caller treats that as a solve failure the same way it would a Python
//! exception, not as a malformed-but-parseable result.

use solver_rs::bitstate::{Position, SecondHighest};
use solver_rs::convert::{self, text_to_mask, trump_to_index};
use solver_rs::search::Search;
use serde::{Deserialize, Serialize};
use std::io::{self, Read, Write};
use std::time::Instant;

#[derive(Deserialize)]
struct Query {
    leader: String,
    #[serde(default)]
    trick: Vec<String>,
}

#[derive(Deserialize)]
struct Input {
    hands: std::collections::HashMap<String, String>,
    strain: String,
    queries: Vec<Query>,
}

#[derive(Serialize)]
struct QueryResult {
    leader: String,
    ns_tricks: i32,
    nodes: u64,
}

#[derive(Serialize)]
struct Output {
    results: Vec<QueryResult>,
    table_entries: usize,
    nodes_total: u64,
    seconds: f64,
}

/// N/E/S/W -> 0/1/2/3, matching bridge.auction.PLAYERS exactly.
fn seat_index(name: &str) -> Result<u32, String> {
    match name {
        "North" => Ok(0),
        "East" => Ok(1),
        "South" => Ok(2),
        "West" => Ok(3),
        other => Err(format!("{other:?} is not a seat (expected North/East/South/West)")),
    }
}

fn run(input: Input) -> Result<Output, String> {
    if input.hands.len() != 4 {
        return Err(format!(
            "hands must name all four seats; got {:?}",
            input.hands.keys().collect::<Vec<_>>()
        ));
    }
    let mut hands = [0u64; 4];
    let mut seen: u64 = 0;
    for seat_name in ["North", "East", "South", "West"] {
        let text = input
            .hands
            .get(seat_name)
            .ok_or_else(|| format!("missing hand for {seat_name}"))?;
        let mask = text_to_mask(text);
        if mask & seen != 0 {
            return Err(format!("a card appears in more than one hand (near {seat_name})"));
        }
        seen |= mask;
        hands[seat_index(seat_name)? as usize] = mask;
    }

    let trump = if input.strain == "NT" {
        None
    } else {
        Some(trump_to_index(&input.strain).ok_or_else(|| {
            format!("{:?} is not a strain; use C/D/H/S/NT", input.strain)
        })?)
    };

    if input.queries.is_empty() {
        return Err("queries must not be empty".to_string());
    }

    let sh = SecondHighest::build();
    let mut engine = Search::new(trump, &sh);
    let mut results = Vec::with_capacity(input.queries.len());
    let mut previous_answer: Option<i32> = None;
    let started = Instant::now();

    for query in &input.queries {
        let leader = seat_index(&query.leader)?;

        let mut trick_hands = hands;
        let mut trick_cards = [0u32; 4];
        let mut trick_len = 0u32;
        let mut trick_seen: u64 = 0;
        for token in &query.trick {
            let idx = convert::text_to_index(token);
            let bit = 1u64 << idx;
            if bit & trick_seen != 0 || bit & seen != 0 {
                return Err(format!(
                    "{token} is both on the trick and already held in a hand"
                ));
            }
            trick_seen |= bit;
            let seat = (leader + trick_len) % 4;
            if trick_hands[seat as usize] & bit != 0 {
                // Card is already excluded from `hands` by construction in the
                // dataset generator; this branch only matters for ad-hoc/manual
                // input where a trick card was left inside a hand by mistake.
                trick_hands[seat as usize] &= !bit;
            }
            trick_cards[trick_len as usize] = idx;
            trick_len += 1;
        }

        let position = Position {
            hands: trick_hands,
            leader,
            trick: trick_cards,
            trick_len,
            trump,
        };

        let nodes_before = engine.nodes;
        let answer = match previous_answer {
            None => engine.value(&position),
            Some(guess) => engine.value_from(&position, guess),
        };
        previous_answer = Some(answer);

        results.push(QueryResult {
            leader: query.leader.clone(),
            ns_tricks: answer,
            nodes: engine.nodes - nodes_before,
        });
    }

    Ok(Output {
        results,
        table_entries: engine.table_len(),
        nodes_total: engine.nodes,
        seconds: started.elapsed().as_secs_f64(),
    })
}

fn main() {
    let mut raw = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut raw) {
        eprintln!("failed to read stdin: {e}");
        std::process::exit(1);
    }

    let input: Input = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("invalid input JSON: {e}");
            std::process::exit(1);
        }
    };

    match run(input) {
        Ok(output) => {
            let text = serde_json::to_string(&output).expect("Output always serialises");
            let stdout = io::stdout();
            let mut handle = stdout.lock();
            let _ = handle.write_all(text.as_bytes());
            let _ = handle.write_all(b"\n");
        }
        Err(message) => {
            eprintln!("{message}");
            std::process::exit(1);
        }
    }
}
