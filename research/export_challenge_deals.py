"""Extract the app-facing slice of the solved datasets.

`research/data/dd_pilot.jsonl` is research tooling: 2,000 records carrying node
counts, timings and which engine solved them, each strain solved for one
declarer per side. `research/data/declarer_tricks.jsonl`
(`research/solve_declarers.py`) solves the same deals for all four declarers.
The app needs none of the bookkeeping, only the cards and the trick count for
every (strain, declarer), so that a contract a player reaches can be scored
double dummy by lookup instead of by a 600-second solve, whichever partner
declares.

So this writes `data/solved_deals.json`: the deals that are solved in ALL FIVE
strains for ALL FOUR declarers, and nothing else. That completeness is what
makes the challenge mode possible: whatever contract the auction lands in, the
exact trick count is already known. Where both files solved a declarer they
must agree, or nothing is written.

Run after extending either dataset:

    python research/export_challenge_deals.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE = ROOT / 'research' / 'data' / 'dd_pilot.jsonl'
DECLARERS = ROOT / 'research' / 'data' / 'declarer_tricks.jsonl'
TARGET = ROOT / 'data' / 'solved_deals.json'

STRAINS = ('C', 'D', 'H', 'S', 'NT')
SEATS = ('North', 'East', 'South', 'West')


def main() -> int:
    for path in (SOURCE, DECLARERS):
        if not path.exists():
            print(f"missing {path}")
            return 1

    hands: dict[int, dict] = {}
    tricks: dict[int, dict] = defaultdict(dict)
    for line in SOURCE.open(encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        did = rec['deal_id']
        hands[did] = rec['hands']
        for res in rec['results']:
            tricks[did][f"{rec['strain']}:{res['declarer']}"] = res['declarer_tricks']

    clashes = 0
    for line in DECLARERS.open(encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        for seat, n in rec['tricks'].items():
            key = f"{rec['strain']}:{seat}"
            if tricks[rec['id']].get(key, n) != n:
                print(f"deal {rec['id']} {key}: dd_pilot {tricks[rec['id']][key]}, declarer_tricks {n}")
                clashes += 1
            tricks[rec['id']][key] = n
    if clashes:
        print(f"{clashes} counts disagree; nothing written")
        return 1

    wanted = [f"{s}:{seat}" for s in STRAINS for seat in SEATS]
    deals = []
    for did in sorted(hands):
        have = tricks[did]
        if any(k not in have for k in wanted):
            continue          # partially solved: cannot score every contract
        deals.append({
            'id': did,
            'hands': hands[did],
            # "<strain>:<declarer>" -> tricks the declaring side takes, double dummy
            'tricks': {k: have[k] for k in wanted},
        })

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open('w', encoding='utf-8') as f:
        json.dump({'version': 2, 'deals': deals}, f, separators=(',', ':'))

    size = TARGET.stat().st_size
    print(f"{len(deals)} fully-solved deals -> {TARGET.relative_to(ROOT)} "
          f"({size / 1024:.0f} KB)")
    print(f"  (skipped {len(hands) - len(deals)} deals that are not solved in "
          f"all {len(wanted)} strain/declarer combinations)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
