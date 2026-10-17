# Double dummy solver and dataset

The double dummy solver (`bridge/solver/`, the Rust port in `research/solver-rs/`) and the dataset built with it for fitting bidding.

Moved verbatim from `CLAUDE.md` on 2026-10-13, so it is read when the work needs it instead of loading into every session. [CLAUDE.md](../CLAUDE.md) keeps the guardrails and links here.

## Commands

```bash
# Double dummy solver
python tests/test_solver_core.py    # packed-int core vs bridge/trick.py, the rules oracle
python tests/test_solver_exact.py   # exhaustive enumeration vs the frozen fixture
python tests/test_solver_search.py  # optimised search vs exhaustive enumeration
python tests/test_solver_api.py     # domain-facing analysis layer + validation
python tests/test_dd_dataset.py      # dataset generator: strains, pairing, resume
python tests/test_solver_rust.py     # Rust engine vs trusted Python search, beyond the fixture

# Heavier sweeps (all optional, all default to a quick setting)
SOLVER_TEST_SAMPLES=1000000 python tests/test_solver_core.py
SOLVER_EXACT_MAX_CARDS=5 python tests/test_solver_exact.py
SOLVER_RUST_DEEP=1 python tests/test_solver_rust.py

# Rebuild the frozen ground-truth fixture (~70s, only when it must change)
python tests/fixtures/generate_endings.py

# Build the Rust engine once (see Solver invariants below for why it exists)
cd research/solver-rs && cargo build --release && cargo test --release && cd ../..

# Double dummy dataset for fitting bidding (resumable, just rerun to continue)
python research/dd_dataset.py --deals 25                            # pure Python
python research/dd_dataset.py --deals 300 --engine rust --workers 6  # ~67x faster per solve

# Fit hand evaluation + bidding policy to that dataset (seconds; prints the report)
python research/hand_value.py
```

## Solver invariants

- `bridge/trick.py` is the rules oracle. The solver never redefines the rules; it is property-tested against it.
- A change to `ns_tricks` in `tests/fixtures/endings.json` means a rules change or a bug — **never** a speedup. Optimisations must reproduce it exactly.
- Rank equivalence is only valid when "live" counts unplayed cards **plus** cards face-up on the current trick. Move reduction accounts for the table; the transposition key does not need to, because it is only probed at trick boundaries where the table is empty.
- Seat rotation by two (N↔S, E↔W) leaves a position's value unchanged; rotation by one complements it. Both are asserted in `tests/test_solver_exact.py` and are the sharpest check on seat indexing.
- Enumeration costs ~115x per additional card; the optimised search ~4x. Don't run `brute.py` on more than 5 cards per hand.
- Measured search cost per position: 8 cards ~0.45s median over random endings but ~1.0s for real mid-play positions, 10 cards ~11s, a full 13-card deal ~600s and 3.6M transposition entries (gigabytes). Anything that solves many deals should work from mid-play, not from the opening lead: 100 single-dummy samples from 8 cards each is ~1.7 minutes, from the opening lead it would be ~17 hours.
- `api.card_values` shares one `Search` across all candidate cards. Measured 2.2-2.4x fewer nodes and 2.1-2.4x faster than a fresh table per card, rising slowly with depth. Worth keeping, so don't 'simplify' it into independent solves — but it is a ~2x win, not an order of magnitude.
- Per-card analysis cost is NOT the same as one solve; child positions differ in difficulty from the root. Measured: 8 cards 1.4s, 9 cards 4.1s, 10 cards 38s. Interactive per-card analysis is viable for roughly the last six tricks of a hand, not the whole hand.
- `research/solver-rs`'s `Search::card_values` solves each card with `value_from`, stepping out from the previous card's answer, rather than binary searching each one. Measured with `cargo run --release --example bench_cards` (10 challenge deals, every card of tricks 1-3, one `Search` kept through the hand): identical values, 1.15x fewer nodes median (1.03x-1.80x). A small win, smallest on the hardest deals: the shared table already makes repeat probes cheap, so the cost is in the first probe per card. The same benchmark measured the per-card display's cost: the opening lead takes 6.5s median and up to 168s natively, with a 3.2 GB process peak; with the `Search` kept, the rest of trick 1 is ~0.3s and trick 3 ~0.1s. A fresh `Search` per decision is 2-3x slower per trick.
- **Solo-suit cutoff, measured and rejected.** A card wins outright when it is the only card of the winning suit, so the leader's suits that no other seat holds (and nobody can ruff) are certain tricks, low cards included, and a probe can stop when they decide it. Sound, and it passed the fixture, but it fires only once a suit has gone from every other hand, which is the last trick or two where the search is already cheap: millions of cutoffs saved 1.0-1.6% of nodes (deals 0-2 of `bench_cards`, tricks 1-3). Don't re-add it; a bound worth having must fire early in the hand.
- Move ordering is sound by construction (it reorders, never filters), so it is judged purely on nodes and wall time. Two ordering ideas were measured and rejected — ranking leads by distance from the second-highest outstanding card, and killer moves. Don't re-add them without new evidence; see the docstring in `search.py`.
- `research/solver-rs/` is a straight Rust port, verified against the same `tests/fixtures/endings.json` (its own `cargo test`) and, past the fixture's 5-card ceiling, against `bridge/solver/search.py` directly (`tests/test_solver_rust.py`). On the full 13-card deal already benchmarked in Python (seed 0): identical node count (55,633,842), identical table size (3,620,453 entries), identical answer (N/S=2/13), **603.9s → 9.0s (67.0x)**. Across 50 random endings at 6-10 cards: 63-72x, zero mismatches. This is real and reproducible, not a bitboard-style overestimate — but it took two real bugs to get there, both worth knowing before touching `search.rs`'s `key()`:
  - **Fixed-width overflow.** `search.py`'s `_key` builds a table key with 16 left-shifts of 13 bits (four per suit, one per seat) — around 210 bits. Python's ints are arbitrary-precision, so this is harmless there; translated literally into a 64-bit integer it silently wraps, producing real transposition-table collisions. `search.rs`'s `key()` is NOT a literal port for this reason — it repacks the same *information* (which seat holds each rank-compressed live card, 2 bits each) into a dense `u128` instead, and is not required to be bit-compatible with Python's key, only to preserve the same equivalence classes.
  - **A card position isn't its own witness.** The first fix still collided: a single live card held by seat 0 (2-bit code `00`) is bit-identical to zero live cards in that suit, since both produce an all-zero contribution. The count of live cards per suit has to be packed in explicitly, not inferred from the pattern. Both bugs were caught by `tests/fixture.rs` disagreeing with the frozen fixture — reinforcing why that fixture exists and why every port must be checked against it before being trusted, not just checked to compile.
  - Every ablation flag (`use_table`/`normalise_key`/`reduce_moves`/`ordering`) in `search.py` is hard-coded to its winning setting in `search.rs`, not re-ported. That work is done and recorded above; add the flags back only if a fifth optimisation needs the same kind of isolated measurement.

## Dataset invariants

- The dataset stores **raw hands and trick counts, never features**, so it outlives any feature design. Strain and declarer choice use only suit lengths and HCP, never `ai.py`, so the data does not depend on the evaluation it exists to replace.
- Slow deals are **never skipped or timed out**: that would bias the data towards easy deals.
- Both declaring sides of a strain share one `Search`, and the second solve starts from the first's answer via `Search.value_from`. Measured 1.45x cheaper than two separate solves, with identical results. `value_from` alone is 1.3-1.4x cheaper than `value` with an exact guess, ~1.1x when off by two.
- Workers are sized from free RAM at ~1.2 GB each (one full-deal table measured ~0.54 GB of Python allocations) and replaced after every task, because Python does not reliably return a large table's memory to the OS. On this 16 GB machine that allows about 3-8 workers, not 12. The budget was calibrated for the Python engine, and the Rust engine has now been **measured against it rather than assumed**: sampling live `solver-rs.exe` processes through a real `--engine rust` run gave peak working sets of 270 MB, 270, 534, 1062, 1062 and 1062 across six worker processes — a peak of about **1.06 GB**, only slightly under the 1.2 GB budget. That refutes the natural guess (recorded here previously) that native structs and a flat 24-byte table entry would make Rust workers 3-5x cheaper than Python's; they are not. Worse, that sample only caught whichever deals ran inside one 60-second window, and a hard deal reaching 77M table entries needs far more. So `--engine rust` keeps the same `safe_workers()` estimate **deliberately**, not for want of a measurement: raising the worker count because "native code is cheap" would thrash this machine.
- Records are appended and fsynced one at a time; rerunning skips finished (deal, strain) pairs and repairs a line cut off by a hard kill. This applies identically to both engines — `solve_strain_rust` returns the same record shape as `solve_strain` (an added `'engine'` field says which one produced a row), so a `.jsonl` file can mix engines across runs without special-casing.
- `--engine rust` fails fast with a clear message (naming the exact `cargo build --release` command) if the binary is missing, both at the CLI (`main()`) and inside `solve_strain_rust` itself — never silently falls back to Python, which would make a dataset's provenance ambiguous.
