//! Benchmark: what would a BBO-style per-card display cost from trick 1?
//!
//! For each of the first N challenge deals (data/solved_deals.json), play the
//! deal's best contract (the strain and side taking the most tricks; South or
//! East declares) and, at every card of the first T tricks, score every legal
//! card the way `api.card_values` does: play it, then solve the rest. The
//! best card (ties to the lowest index) is played and the walk goes on.
//!
//! Modes, each over the same walk:
//!   fresh       a new Search for every decision, as `api.card_values` does
//!   persistent  one Search kept for the whole deal, as a live display could
//!   guided      persistent, but each card is solved with `value_from`,
//!               starting from the last answer instead of a binary search
//!
//! One JSON line per decision goes to stdout, with every card's value so the
//! modes can be checked against each other; a summary goes to stderr.
//!
//!   cargo run --release --example bench_cards -- [deals=10] [tricks=3] [modes=fresh,persistent,guided]
//!
//! Memory is an estimate: the transposition table's slots (a power of two,
//! at least 2^16, doubled before they're 3/4 full) times 24 bytes. Process
//! overhead is extra.

use serde_json::Value;
use solver_rs::bitstate::{cards_in, Position, SecondHighest, NS_SEATS};
use solver_rs::convert::{text_to_mask, trump_to_index};
use solver_rs::search::Search;
use std::time::Instant;

const SEATS: [&str; 4] = ["North", "East", "South", "West"];

fn table_bytes(entries: usize) -> usize {
    if entries == 0 {
        return 0;
    }
    let mut slots = 1usize << 16;
    while entries * 4 > slots * 3 {
        slots *= 2;
    }
    slots * 24
}

/// Every legal card for the seat to act, mapped to N/S tricks for the hand.
/// `guided` uses `Search::card_values`; otherwise every card is binary
/// searched, the way `api.card_values` does it, as the baseline.
fn card_values(engine: &mut Search, position: &Position, sh: &SecondHighest, guided: bool, guess: Option<i32>) -> Vec<(u32, i32)> {
    if guided {
        return engine.card_values(position, guess);
    }
    let mut out = Vec::new();
    for card in cards_in(position.moves()) {
        let (after, winner) = position.play(card, sh);
        let gained = match winner {
            Some(w) if NS_SEATS.contains(&w) => 1,
            _ => 0,
        };
        out.push((card, gained + engine.value(&after)));
    }
    out
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let deals: usize = args.get(1).map_or(10, |s| s.parse().expect("deals"));
    let tricks: u32 = args.get(2).map_or(3, |s| s.parse().expect("tricks"));
    let modes: Vec<String> = args.get(3).map_or("fresh,persistent,guided", |s| s.as_str()).split(',').map(String::from).collect();

    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../data/solved_deals.json");
    let data: Value = serde_json::from_str(&std::fs::read_to_string(path).expect("read deals")).expect("parse deals");
    let sh = SecondHighest::build();

    for deal in data["deals"].as_array().expect("deals array").iter().take(deals) {
        let id = deal["id"].as_u64().unwrap();
        let mut hands = [0u64; 4];
        for (i, seat) in SEATS.iter().enumerate() {
            hands[i] = text_to_mask(deal["hands"][*seat].as_str().unwrap());
        }
        // Best contract: most tricks for the declaring side, first found on ties.
        let (mut best_key, mut best_tricks) = (String::new(), -1i64);
        for strain in ["NT", "S", "H", "D", "C"] {
            for side in ["N/S", "E/W"] {
                let key = format!("{strain}:{side}");
                let t = deal["tricks"][&key].as_i64().unwrap();
                if t > best_tricks {
                    best_tricks = t;
                    best_key = key;
                }
            }
        }
        let (strain, side) = best_key.split_once(':').unwrap();
        let trump = if strain == "NT" { None } else { trump_to_index(strain) };
        // South declares for N/S (West leads), East for E/W (South leads).
        let leader = if side == "N/S" { 3 } else { 2 };

        for mode in modes.iter().map(String::as_str) {
            let mut position = Position::new(hands, leader, trump);
            let mut kept = Search::new(trump, &sh);
            // No first guess: a live game on a random deal wouldn't have one.
            let mut last_best: Option<i32> = None;
            let deal_start = Instant::now();
            for step in 0..(tricks * 4) {
                let mut fresh = Search::new(trump, &sh);
                let engine = if mode == "fresh" { &mut fresh } else { &mut kept };
                let nodes_before = engine.nodes;
                let started = Instant::now();
                let values = card_values(engine, &position, &sh, mode == "guided", last_best);
                let seconds = started.elapsed().as_secs_f64();
                let actor = position.to_act();
                let ns = NS_SEATS.contains(&actor);
                let target = if ns {
                    values.iter().map(|v| v.1).max().unwrap()
                } else {
                    values.iter().map(|v| v.1).min().unwrap()
                };
                let pick = values.iter().filter(|v| v.1 == target).map(|v| v.0).min().unwrap();
                last_best = Some(target);
                let entries = engine.table_len();
                let listed: Vec<String> = values.iter().map(|v| format!("[{},{}]", v.0, v.1)).collect();
                println!(
                    "{{\"deal\":{id},\"contract\":\"{best_key}\",\"dd\":{best_tricks},\"mode\":\"{mode}\",\"trick\":{},\"card\":{},\"seat\":\"{}\",\"cards_left\":{},\"choices\":{},\"seconds\":{seconds:.4},\"nodes\":{},\"table_entries\":{entries},\"table_mb\":{:.1},\"ns_best\":{target},\"values\":[{}]}}",
                    step / 4 + 1,
                    step % 4 + 1,
                    SEATS[actor as usize],
                    position.cards_left(),
                    values.len(),
                    engine.nodes - nodes_before,
                    table_bytes(entries) as f64 / 1e6,
                    listed.join(","),
                );
                position = position.play(pick, &sh).0;
            }
            eprintln!("deal {id} {best_key} {mode}: {:.1}s for {tricks} tricks", deal_start.elapsed().as_secs_f64());
        }
    }
}
