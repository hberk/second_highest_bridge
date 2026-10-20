//! Per-card double dummy values along one played line: what every legal card
//! was worth at every decision of a hand that was actually played.
//!
//! `research/presolve_robot_lines.py` shells out to this once per robot line;
//! nothing else calls it. One process per line, so a hard deal's table is
//! handed back to the OS when the line is done.
//!
//! Input (stdin):
//!   {"hands": {"North": "AS KS ...", ...}, "strain": "NT",
//!    "leader": "West", "plays": ["2C", "3C", ...]}
//!
//! `plays` is the line in play order, up to 52 cards. Each decision is scored
//! with `Search::card_values` on ONE Search kept through the hand, then the
//! card actually played is played. A card in `plays` that isn't legal for the
//! seat to act is an error, never skipped.
//!
//! Output (stdout):
//!   {"decisions": [{"seat": "West", "played": "2C",
//!                   "values": [["2C", 7], ["5D", 6], ...]}, ...],
//!    "nodes": 123, "table_entries": 456, "table_clears": 0, "seconds": 7.8}
//!
//! Each value is N/S's tricks for the WHOLE hand if that card is played and
//! everyone plays perfectly after it: tricks already won plus the rest.

use serde::Deserialize;
use solver_rs::bitstate::{Position, SecondHighest, NS_SEATS};
use solver_rs::convert::{index_to_text, text_to_index, text_to_mask, trump_to_index};
use solver_rs::search::Search;
use std::io::{self, Read, Write};
use std::time::Instant;

const SEATS: [&str; 4] = ["North", "East", "South", "West"];

#[derive(Deserialize)]
struct Input {
    hands: std::collections::HashMap<String, String>,
    strain: String,
    leader: String,
    plays: Vec<String>,
}

fn seat_index(name: &str) -> Result<u32, String> {
    SEATS
        .iter()
        .position(|s| *s == name)
        .map(|i| i as u32)
        .ok_or_else(|| format!("{name:?} is not a seat (expected North/East/South/West)"))
}

fn run(input: Input) -> Result<String, String> {
    let mut hands = [0u64; 4];
    let mut seen = 0u64;
    for (i, seat) in SEATS.iter().enumerate() {
        let text = input.hands.get(*seat).ok_or_else(|| format!("missing hand for {seat}"))?;
        let mask = text_to_mask(text);
        if mask & seen != 0 {
            return Err(format!("a card appears in more than one hand (near {seat})"));
        }
        seen |= mask;
        hands[i] = mask;
    }
    let trump = if input.strain == "NT" {
        None
    } else {
        Some(trump_to_index(&input.strain).ok_or_else(|| format!("{:?} is not a strain", input.strain))?)
    };

    let sh = SecondHighest::build();
    let mut engine = Search::new(trump, &sh);
    let mut position = Position::new(hands, seat_index(&input.leader)?, trump);
    let mut won: i32 = 0;
    let mut last_best: Option<i32> = None;
    let mut decisions = Vec::with_capacity(input.plays.len());
    let started = Instant::now();

    for token in &input.plays {
        let card = text_to_index(token);
        let seat = position.to_act();
        if position.moves() & (1u64 << card) == 0 {
            return Err(format!("{token} is not a legal card for {} here", SEATS[seat as usize]));
        }
        // card_values counts the rest of the hand; add what N/S already won.
        let rest = engine.card_values(&position, last_best.map(|b| b - won));
        let best = if NS_SEATS.contains(&seat) {
            rest.iter().map(|v| v.1).max()
        } else {
            rest.iter().map(|v| v.1).min()
        };
        last_best = best.map(|b| b + won);
        let values: Vec<String> = rest
            .iter()
            .map(|(c, v)| format!("[\"{}\",{}]", index_to_text(*c), v + won))
            .collect();
        decisions.push(format!(
            "{{\"seat\":\"{}\",\"played\":\"{}\",\"values\":[{}]}}",
            SEATS[seat as usize],
            token,
            values.join(",")
        ));

        let (after, winner) = position.play(card, &sh);
        if let Some(w) = winner {
            if NS_SEATS.contains(&w) {
                won += 1;
            }
        }
        position = after;
    }

    Ok(format!(
        "{{\"decisions\":[{}],\"nodes\":{},\"table_entries\":{},\"table_clears\":{},\"seconds\":{:.3}}}",
        decisions.join(","),
        engine.nodes,
        engine.table_len(),
        engine.clears,
        started.elapsed().as_secs_f64()
    ))
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
        Ok(text) => {
            let mut out = io::stdout().lock();
            let _ = out.write_all(text.as_bytes());
            let _ = out.write_all(b"\n");
        }
        Err(message) => {
            eprintln!("{message}");
            std::process::exit(1);
        }
    }
}
