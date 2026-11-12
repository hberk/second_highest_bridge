//! Sampled look-ahead for the robots' middle game (experiment).
//!
//! Input (stdin): {"strain":"NT","leader":"West","trick":["2C","3C"],
//!   "layouts":[{"North":"AS KS ...","East":"...","South":"...","West":"..."}, ...]}
//! `hands` are the hands at the START of the current trick; `trick` is the cards
//! already on the table. For each layout the position after `trick` is solved and every legal
//! card of the seat to act is valued (N/S tricks from here). Output: the sum over
//! layouts per card: {"sums":[["2C",17],...],"layouts":n}
use serde::Deserialize;
use solver_rs::bitstate::{Position, SecondHighest};
use solver_rs::convert::{index_to_text, text_to_index, text_to_mask, trump_to_index};
use solver_rs::search::Search;
use std::collections::HashMap;
use std::io::{self, Read};

const SEATS: [&str; 4] = ["North", "East", "South", "West"];

#[derive(Deserialize)]
struct Input {
    strain: String,
    leader: String,
    trick: Vec<String>,
    layouts: Vec<HashMap<String, String>>,
}

fn main() {
    let mut raw = String::new();
    io::stdin().read_to_string(&mut raw).unwrap();
    let input: Input = serde_json::from_str(&raw).expect("bad json");
    let trump = if input.strain == "NT" { None } else { Some(trump_to_index(&input.strain).expect("strain")) };
    let leader = SEATS.iter().position(|s| *s == input.leader).expect("leader") as u32;
    let sh = SecondHighest::build();
    let mut engine = Search::new(trump, &sh);
    let mut sums: Vec<(u32, i64)> = Vec::new();
    for layout in &input.layouts {
        let mut hands = [0u64; 4];
        for (i, s) in SEATS.iter().enumerate() {
            hands[i] = text_to_mask(layout.get(*s).expect("hand"));
        }
        let mut position = Position::new(hands, leader, trump);
        for t in &input.trick {
            let (after, _) = position.play(text_to_index(t), &sh);
            position = after;
        }
        for (c, v) in engine.card_values(&position, None) {
            match sums.iter_mut().find(|e| e.0 == c) {
                Some(e) => e.1 += v as i64,
                None => sums.push((c, v as i64)),
            }
        }
    }
    let parts: Vec<String> = sums.iter().map(|(c, v)| format!("[\"{}\",{}]", index_to_text(*c), v)).collect();
    println!("{{\"sums\":[{}],\"layouts\":{}}}", parts.join(","), input.layouts.len());
}
