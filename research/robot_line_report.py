"""Where the robots give tricks away: a report on presolved robot lines.

Reads research/data/robot_lines.jsonl (written by presolve_robot_lines.py) and
classifies every card that cost a trick against double dummy: which side,
which seat in the trick, following, ruffing or discarding, and how far into
the hand. A line counts by the share of the 16 board positions that produce
it, so every deal weighs the same however many lines its boards give.

Double dummy sees all four hands and the robots don't. A defender's "mistake"
here may have been the right play on what the defender could see, so treat
these as places to look, not a verdict; check a pattern single dummy before
changing the robots for it.

    python research/robot_line_report.py
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IN = ROOT / 'research' / 'data' / 'robot_lines.jsonl'
BOARDS = 16
NS = ('North', 'South')


def best(decision: dict) -> int:
    values = [v for _, v in decision['values']]
    return max(values) if decision['seat'] in NS else min(values)


def mistakes(record: dict) -> List[dict]:
    """Every card in this line that played worse than the best available."""
    contract = record['contract']
    trump = None if contract['strain'] == 'NT' else contract['strain']
    declaring = NS if contract['side'] == 'N/S' else ('East', 'West')
    out = []
    led = None
    for k, decision in enumerate(record['decisions']):
        card = decision['played']
        suit = card[-1]
        place = k % 4
        if place == 0:
            led = suit
        values = dict(decision['values'])
        lost = abs(best(decision) - values[card])
        if place == 0:
            action = 'opening lead' if k == 0 else 'lead'
        elif suit == led:
            action = 'follow'
        elif trump is not None and suit == trump:
            action = 'ruff'
        else:
            action = 'discard'
        trick = k // 4 + 1
        out.append({
            'k': k, 'trick': trick, 'seat': decision['seat'], 'card': card, 'lost': lost,
            'side': 'declarer side' if decision['seat'] in declaring else 'defence',
            'position': ['lead', '2nd hand', '3rd hand', '4th hand'][place],
            'action': action,
            'stage': 'tricks 1-4' if trick <= 4 else 'tricks 5-9' if trick <= 9 else 'tricks 10-13',
            'strain': 'NT' if trump is None else 'suit',
            'choices': len(decision['values']),
        })
    return out


def table(title: str, rows: Dict[str, List[float]], decisions: Dict[str, float], deals: int) -> None:
    print(f"\n{title}")
    print(f"  {'':<26}{'cards played':>13}{'costly':>9}{'rate':>8}{'tricks lost':>13}{'per deal':>10}")
    for name in sorted(set(rows) | set(decisions), key=lambda n: -rows[n][1] if n in rows else 0):
        count, tricks = rows[name] if name in rows else (0.0, 0.0)
        seen = decisions.get(name, 0)
        rate = count / seen if seen else 0
        print(f"  {name:<26}{seen:>13.0f}{count:>9.1f}{rate:>8.1%}{tricks:>13.1f}{tricks / deals:>10.3f}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--in', dest='path', type=Path, default=DEFAULT_IN)
    parser.add_argument('--worst', type=int, default=10, help="deals to list, most tricks given away first")
    args = parser.parse_args(argv)

    records = [json.loads(line) for line in args.path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not records:
        print("no records yet")
        return 1
    versions = {r['robot_version'] for r in records}
    deals = len({r['deal_id'] for r in records})
    print(f"{len(records)} robot lines on {deals} deals; robot version {', '.join(sorted(versions))}")
    if len(versions) > 1:
        print("WARNING: more than one robot version; rerun the presolve so all lines match the current robots")

    by: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    seen: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    per_deal: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    totals = defaultdict(float)
    for record in records:
        weight = len(record['boards']) / BOARDS
        contract = record['contract']
        opening = best(record['decisions'][0])
        declaring_ns = contract['side'] == 'N/S'
        dd = opening if declaring_ns else 13 - opening
        actual = record['ns_tricks'] if declaring_ns else 13 - record['ns_tricks']
        totals['declarer tricks, double dummy'] += dd * weight
        totals['declarer tricks, robots'] += actual * weight
        for m in mistakes(record):
            keys = {
                'side': m['side'],
                'side and action': f"{m['side']}: {m['action']}",
                'side and seat in trick': f"{m['side']}: {m['position']}",
                'side and stage': f"{m['side']}: {m['stage']}",
                'side and strain': f"{m['side']}: {m['strain']}",
            }
            for group, key in keys.items():
                if m['choices'] > 1:
                    seen[group][key] += weight
                if m['lost']:
                    by[group][key][0] += weight
                    by[group][key][1] += m['lost'] * weight
            if m['lost']:
                per_deal[record['deal_id']][m['side']] += m['lost'] * weight

    print(f"\nDeclarer's tricks per deal: double dummy {totals['declarer tricks, double dummy'] / deals:.2f}, "
          f"robots {totals['declarer tricks, robots'] / deals:.2f}")
    print("Costly cards can offset: a trick the declarer side gives away can come back from the defence.")
    print("'cards played' counts only decisions with more than one legal card.")
    for group in ('side', 'side and action', 'side and seat in trick', 'side and stage', 'side and strain'):
        table(f"By {group}", by[group], seen[group], deals)

    print(f"\nDeals where the robots gave away the most tricks (both sides, board-weighted):")
    worst = sorted(per_deal.items(), key=lambda kv: -sum(kv[1].values()))[:args.worst]
    for deal_id, sides in worst:
        print(f"  deal {deal_id:>3}: defence {sides.get('defence', 0):4.1f}, declarer side {sides.get('declarer side', 0):4.1f}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
