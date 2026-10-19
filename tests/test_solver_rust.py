"""Cross-validates the Rust engine (research/solver-rs/) against the trusted
Python search on positions well past the frozen fixture's 5-card ceiling.

The fixture itself is checked by `cargo test --release` inside
research/solver-rs/ (its tests/fixture.rs reads the same
tests/fixtures/endings.json this project's Python tests use) — that is the
first and most important gate, and it is not repeated here. What this file
adds is the boundary `cargo test` cannot see on its own: does the compiled CLI,
called exactly as research/dd_dataset.py calls it, agree with bridge/solver's
own Python search at depths the fixture has never reached (6-10 cards), and
does the dd_dataset.py wiring (solve_strain_rust) reproduce solve_strain
exactly on real generated deals?

Two real bugs were caught this way during development — both transposition-key
encoding errors invisible to a shallow check (an unbounded bit-shift that
silently wraps in Rust's fixed-width integers where Python's arbitrary-
precision ints just kept growing, and a follow-up where the fix didn't encode
*how many* cards were live in a suit, so a single card held by seat 0 collided
with zero live cards) — which is why this suite pushes past the fixture's own
depth rather than trusting a build that merely compiles.

The Rust engine is optional (research/dd_dataset.py defaults to
--engine python; the app never touches it), so a missing build is not this
suite's problem to fail on — every test here raises SkipTest when the binary
is not built, which tests/run_all.py reports as SKIP: neither a false failure
nor a pass. Build it with `cargo build --release` in research/solver-rs/ to
actually exercise this file.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import SkipTest

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from game import PLAYERS
from bridge.solver import search as py_search
from bridge.solver.convert import mask_to_cards, mask_to_text
from research import dd_dataset as ds
from tests.fixtures.generate_endings import random_ending

RUST_EXE = ds.RUST_EXE

#: Depths and sample counts for the default (quick) cross-check. Heavier:
#!   SOLVER_RUST_DEEP=1 python tests/test_solver_rust.py
DEFAULT_DEPTHS = [(6, 4), (8, 3), (10, 2)]
DEEP_DEPTHS = [(6, 15), (7, 12), (8, 10), (9, 8), (10, 5)]


def _built() -> bool:
    """True if there is something to test; otherwise the test is skipped."""
    if RUST_EXE.exists():
        return True
    raise SkipTest(f"solver-rs not built at {RUST_EXE} — "
                   f"cd research/solver-rs && cargo build --release")


def _solve_via_cli(hands_text, strain, leader) -> tuple:
    """Returns (ns_tricks, nodes, reported_seconds) from one CLI call."""
    payload = {"hands": hands_text, "strain": strain,
              "queries": [{"leader": leader, "trick": []}]}
    proc = subprocess.run([str(RUST_EXE)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=1200)
    assert proc.returncode == 0, f"solver-rs.exe failed: {proc.stderr}"
    out = json.loads(proc.stdout)
    result = out['results'][0]
    return result['ns_tricks'], result['nodes'], out['seconds']


# ── Cross-validation against the trusted Python search ──────────────────────

def test_rust_cli_matches_python_search_beyond_the_fixture():
    """The core correctness gate for anything past 5 cards per hand."""
    if not _built():
        return
    depths = DEEP_DEPTHS if os.environ.get('SOLVER_RUST_DEEP') else DEFAULT_DEPTHS
    checked = 0

    for cards_each, samples in depths:
        for seed in range(samples):
            pos = random_ending(seed, cards_each)
            strain = 'NT' if pos.trump is None else 'CDHS'[pos.trump]
            leader = PLAYERS[pos.leader]
            hands_text = {PLAYERS[i]: mask_to_text(h) for i, h in enumerate(pos.hands)}

            expected = py_search.solve(pos)
            actual, _, _ = _solve_via_cli(hands_text, strain, leader)
            assert actual == expected, (
                f"cards={cards_each} seed={seed}: python={expected} rust={actual}"
            )
            checked += 1

    assert checked >= 9, f"only checked {checked} positions"


def test_rust_cli_agrees_on_a_slice_of_the_measured_full_deal():
    """A 10-card ending, the deepest this suite checks. It is random_ending's
    seed 0, NOT the 13-card deal the engines were benchmarked on (N/S=2/13,
    55,633,842 nodes, 603.9s in Python, 9.0s in Rust): re-solving that is slow
    even in Rust, so its numbers are recorded in docs/SOLVER.md, not
    re-verified on every test run.
    """
    if not _built():
        return
    pos = random_ending(0, 10)  # first 10 cards of the same seed-0 deal shape
    strain = 'NT' if pos.trump is None else 'CDHS'[pos.trump]
    leader = PLAYERS[pos.leader]
    hands_text = {PLAYERS[i]: mask_to_text(h) for i, h in enumerate(pos.hands)}

    expected = py_search.solve(pos)
    actual, _, _ = _solve_via_cli(hands_text, strain, leader)
    assert actual == expected


# ── The dd_dataset.py wiring itself ──────────────────────────────────────────

def test_solve_strain_rust_matches_solve_strain_on_generated_deals():
    """Exercises exactly what --engine rust runs in production: the same
    strain-and-declarer selection (strains_to_solve/declarer_for/leader_for),
    the same paired-solve call shape as solve_strain.

    Deliberately NOT run on full 13-card deals: comparing against the pure-
    Python solve_strain there costs minutes per pair (that's the whole reason
    the Rust engine exists), which would make this "quick" cross-check as slow
    as the pilot run it's meant to guard against regressing. Small endings
    exercise the identical wiring — dd_dataset.py's Hands type is a plain
    Dict[str, List[Card]] regardless of how many cards are in it — for a cost
    measured in milliseconds. Full-deal agreement is checked separately, once,
    against real saved answers, in test_solve_strain_rust_reproduces_the_original_pilot_data.
    """
    if not _built():
        return
    for cards_each, deal_id in ((5, 0), (6, 1), (6, 2)):
        pos = random_ending(deal_id, cards_each)
        hands = {PLAYERS[i]: mask_to_cards(h) for i, h in enumerate(pos.hands)}
        for strain, _why in ds.strains_to_solve(hands):
            expected = ds.solve_strain(hands, strain)
            actual = ds.solve_strain_rust(hands, strain)

            expected_tricks = [(r['declaring_side'], r['ns_tricks']) for r in expected['results']]
            actual_tricks = [(r['declaring_side'], r['ns_tricks']) for r in actual['results']]
            assert actual_tricks == expected_tricks, (deal_id, strain)
            assert actual['table_entries'] == expected['table_entries'], (deal_id, strain)
            assert actual['engine'] == 'rust'
            assert expected['engine'] == 'python'


def test_solve_strain_rust_reproduces_the_original_pilot_data():
    """The strongest available check: re-solves the deals already saved in
    research/data/dd_pilot.jsonl from the original (pure-Python) pilot run,
    and requires an exact match against real, previously-computed answers —
    not just answers this session generated on both sides.
    """
    if not _built():
        return
    pilot_path = root_dir / 'research' / 'data' / 'dd_pilot.jsonl'
    if not pilot_path.exists():
        raise SkipTest(f"no pilot data at {pilot_path}")
    saved = [json.loads(line) for line in pilot_path.read_text(encoding='utf-8').splitlines()
             if line.strip()]

    checked = 0
    for record in saved[:9]:  # the original pilot's first batch; keep this test quick
        hands = ds.deal_for(record['deal_id'])
        actual = ds.solve_strain_rust(hands, record['strain'])
        actual_tricks = [(r['declaring_side'], r['ns_tricks']) for r in actual['results']]
        expected_tricks = [(r['declaring_side'], r['ns_tricks']) for r in record['results']]
        assert actual_tricks == expected_tricks, (record['deal_id'], record['strain'])
        checked += 1
    assert checked > 0


def test_missing_binary_fails_clearly_not_silently():
    """solve_strain_rust must refuse rather than pretend to answer, regardless
    of whether the real binary happens to be built on this machine."""
    real = ds.RUST_EXE
    try:
        ds.RUST_EXE = root_dir / 'research' / 'solver-rs' / 'target' / 'release' / 'does-not-exist.exe'
        try:
            ds.solve_strain_rust(ds.deal_for(0), 'NT')
            raise AssertionError("expected FileNotFoundError")
        except FileNotFoundError as error:
            assert 'cargo build --release' in str(error)
    finally:
        ds.RUST_EXE = real


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except SkipTest as why:
                print(f"SKIP {name} ({why})")
    print("\nRust engine verified against the trusted Python search"
          if RUST_EXE.exists() else
          "\nRust engine not built — nothing was actually checked; see notices above.")
