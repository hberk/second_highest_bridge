"""Extract the app-facing slice of the solved dataset.

`research/data/dd_pilot.jsonl` is research tooling: 1,489 records carrying node
counts, timings and which engine solved them. The app needs none of that — only
the cards and the trick count for every (strain, declaring side), so that a
contract a player reaches can be scored double dummy by lookup instead of by a
600-second solve.

So this writes `data/solved_deals.json`: the deals that are solved in ALL FIVE
strains for BOTH declaring sides, and nothing else. That completeness is what
makes the challenge mode possible — whatever contract the auction lands in, the
exact trick count is already known.

Run after extending the dataset:

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
TARGET = ROOT / 'data' / 'solved_deals.json'

STRAINS = ('C', 'D', 'H', 'S', 'NT')
SIDES = ('N/S', 'E/W')


def main() -> int:
    if not SOURCE.exists():
        print(f"missing {SOURCE}")
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
            tricks[did][f"{rec['strain']}:{res['declaring_side']}"] = \
                res['declarer_tricks']

    wanted = [f"{s}:{side}" for s in STRAINS for side in SIDES]
    deals = []
    for did in sorted(hands):
        have = tricks[did]
        if any(k not in have for k in wanted):
            continue          # partially solved: cannot score every contract
        deals.append({
            'id': did,
            'hands': hands[did],
            # "<strain>:<declaring side>" -> tricks that side takes, double dummy
            'tricks': {k: have[k] for k in wanted},
        })

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open('w', encoding='utf-8') as f:
        json.dump({'version': 1, 'deals': deals}, f, separators=(',', ':'))

    size = TARGET.stat().st_size
    print(f"{len(deals)} fully-solved deals -> {TARGET.relative_to(ROOT)} "
          f"({size / 1024:.0f} KB)")
    print(f"  (skipped {len(hands) - len(deals)} deals that are not solved in "
          f"all {len(wanted)} strain/side combinations)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
