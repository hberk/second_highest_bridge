"""Solve every challenge deal for all four declarers, not one per side.

`data/solved_deals.json` was solved with one declarer per strain and side
(`dd_dataset.declarer_for`), and the challenge grade looked the count up by
side, whoever actually declared. This solves each strain of each library deal
from all four opening leaders in one Rust call (one shared table, so the two
new leaders cost little over re-solving the two already known), checks the
known two against the library, and appends one line per (deal, strain) to
`research/data/declarer_tricks.jsonl`. Resumable: rerun to continue.

    cargo build --release   # in research/solver-rs, once
    python research/solve_declarers.py --workers 4
    python research/export_challenge_deals.py

Slow deals are never skipped or timed out (the dataset rule), and there is no
Python fallback: the Rust binary must be built.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.dd_dataset import RUST_EXE, declarer_for, leader_for  # noqa: E402
from challenge import hands_for  # noqa: E402

LIBRARY = ROOT / 'data' / 'solved_deals.json'
TARGET = ROOT / 'research' / 'data' / 'declarer_tricks.jsonl'
STRAINS = ('C', 'D', 'H', 'S', 'NT')
#: Opening leader -> declarer: the lead comes from declarer's left.
LEADERS = ('East', 'South', 'West', 'North')
DECLARER_OF = {'East': 'North', 'South': 'East', 'West': 'South', 'North': 'West'}
SIDE_OF = {'North': 'N/S', 'South': 'N/S', 'East': 'E/W', 'West': 'E/W'}


def solve(deal: dict, strain: str) -> dict:
    payload = {
        'hands': deal['hands'],
        'strain': strain,
        'queries': [{'leader': leader, 'trick': []} for leader in LEADERS],
    }
    started = time.perf_counter()
    proc = subprocess.run([str(RUST_EXE)], input=json.dumps(payload),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"deal {deal['id']} {strain}: {proc.stderr.strip()}")
    results = json.loads(proc.stdout)['results']
    tricks = {}
    for leader, raw in zip(LEADERS, results):
        declarer = DECLARER_OF[leader]
        ns = raw['ns_tricks']
        tricks[declarer] = ns if SIDE_OF[declarer] == 'N/S' else 13 - ns
    return {'id': deal['id'], 'strain': strain, 'tricks': tricks,
            'seconds': round(time.perf_counter() - started, 1)}


def check(deal: dict, record: dict) -> None:
    """The declarer the library was solved with must give its stored count
    (a library keyed by side, before this script's results were exported;
    afterwards, every declarer's)."""
    hands = hands_for(deal['id'])
    for side in ('N/S', 'E/W'):
        declarer = declarer_for(hands, side, record['strain'])
        assert leader_for(declarer) in LEADERS
        stored = deal['tricks'].get(f"{record['strain']}:{side}",
                                    deal['tricks'].get(f"{record['strain']}:{declarer}"))
        got = record['tricks'][declarer]
        if stored != got:
            raise AssertionError(f"deal {deal['id']} {record['strain']}:{side} by {declarer}: "
                                 f"library {stored}, solved {got}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    if not RUST_EXE.exists():
        print(f"Rust engine not built at {RUST_EXE}: run `cargo build --release` in research/solver-rs/")
        return 1

    deals = {d['id']: d for d in json.loads(LIBRARY.read_text())['deals']}
    done = set()
    if TARGET.exists():
        for line in TARGET.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue                    # a line cut off by a hard kill
            done.add((r['id'], r['strain']))
    todo = [(i, s) for i in sorted(deals) for s in STRAINS if (i, s) not in done]
    print(f"{len(done)} solved, {len(todo)} to go, {args.workers} workers", flush=True)

    started = time.perf_counter()
    with TARGET.open('a') as out, ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(solve, deals[i], s): (i, s) for i, s in todo}
        for n, future in enumerate(as_completed(futures), 1):
            record = future.result()
            check(deals[record['id']], record)
            out.write(json.dumps(record) + '\n')
            out.flush()
            os.fsync(out.fileno())
            if n % 20 == 0 or n == len(todo):
                print(f"{n}/{len(todo)} in {time.perf_counter() - started:.0f}s", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
