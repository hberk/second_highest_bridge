"""Solve the Bidding training deals: fresh random deals, never the challenge's.

Bidding training scores the contract you reach against par by lookup, so every
deal it deals must be solved in all five strains for all four declarers, as
the challenge library is. It must not reuse the challenge's deals, though (the
user's call, 2026-10-27): a hand seen in training would be a hand already seen
when it comes up in Challenge. So these are their own deals, from their own
seed range, solved the way `solve_declarers.py` solves the library: each strain
from all four opening leaders in one Rust call.

Appends one line per (deal, strain) to `research/data/training_tricks.jsonl`,
and writes the fully solved deals to `data/training_deals.json`, in the
challenge library's shape. Resumable: rerun to continue, `--deals` to extend.

    cargo build --release   # in research/solver-rs, once
    python research/solve_training_deals.py --deals 400 --workers 4

Slow deals are never skipped or timed out (the dataset rule), and there is no
Python fallback: the Rust binary must be built.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import random  # noqa: E402

from card import deal  # noqa: E402
from research.dd_dataset import RUST_EXE, hands_to_text  # noqa: E402
from research.solve_declarers import STRAINS, solve  # noqa: E402

#: Far from the dataset's (900,000), the slam deals' (2,000,000) and the
#: fresh head-to-head's (7,000,000).
SEED_BASE = 11_000_000
SOURCE = ROOT / 'research' / 'data' / 'training_tricks.jsonl'
TARGET = ROOT / 'data' / 'training_deals.json'
SEATS = ('North', 'East', 'South', 'West')


def deal_for(deal_id: int) -> dict:
    """The deal for an id, as card text. The global RNG is put back."""
    state = random.getstate()
    try:
        random.seed(SEED_BASE + deal_id)
        return {'id': deal_id, 'hands': hands_to_text(deal())}
    finally:
        random.setstate(state)


def export(deals: dict[int, dict]) -> int:
    tricks: dict[int, dict] = {}
    if SOURCE.exists():
        for line in SOURCE.read_text().splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue                    # a line cut off by a hard kill
            for seat, n in rec['tricks'].items():
                tricks.setdefault(rec['id'], {})[f"{rec['strain']}:{seat}"] = n
    wanted = [f"{s}:{seat}" for s in STRAINS for seat in SEATS]
    out = [{'id': i, 'hands': deals[i]['hands'], 'tricks': {k: tricks[i][k] for k in wanted}}
           for i in sorted(tricks) if i in deals and all(k in tricks[i] for k in wanted)]
    TARGET.write_text(json.dumps({'version': 2, 'deals': out}, separators=(',', ':')))
    print(f"{len(out)} fully solved deals -> {TARGET.relative_to(ROOT)} "
          f"({TARGET.stat().st_size / 1024:.0f} KB)")
    return len(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--deals', type=int, default=400)
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    if not RUST_EXE.exists():
        print(f"Rust engine not built at {RUST_EXE}: run `cargo build --release` in research/solver-rs/")
        return 1

    deals = {i: deal_for(i) for i in range(args.deals)}
    done = set()
    if SOURCE.exists():
        for line in SOURCE.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add((r['id'], r['strain']))
    todo = [(i, s) for i in sorted(deals) for s in STRAINS if (i, s) not in done]
    print(f"{len(done)} solved, {len(todo)} to go, {args.workers} workers", flush=True)

    started = time.perf_counter()
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    with SOURCE.open('a') as out, ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(solve, deals[i], s) for i, s in todo]
        for n, future in enumerate(as_completed(futures), 1):
            out.write(json.dumps(future.result()) + '\n')
            out.flush()
            os.fsync(out.fileno())
            if n % 20 == 0 or n == len(todo):
                print(f"{n}/{len(todo)} in {time.perf_counter() - started:.0f}s", flush=True)
    export(deals)
    return 0


if __name__ == '__main__':
    sys.exit(main())
