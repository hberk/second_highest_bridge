"""Measure a robot card-play switch head to head on the challenge library.

Runs the all-robot table on every deal at all 16 board positions twice, with
an `ai` switch off and on, and pairs the boards. A card-play switch leaves the
auction alone, so each pair is the same contract and the difference is purely
the play. Reports the change in the declaring side's tricks and score.

The 16 board positions of one deal often give the same robot line, so they are
not independent: each deal's boards are averaged first, and the t is taken
across deals.

    python research/card_play_h2h.py DRAW_TRUMPS
    python research/card_play_h2h.py DRAW_TRUMPS --deals 100
    python research/card_play_h2h.py NT_LONG_LEAD --set NT_LONG_LEAD_OPENING_ONLY=True
    python research/card_play_h2h.py RUN_LONG_SUIT NT_LONG_LEAD    # both together

A defence switch shows up as FEWER declarer tricks.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai
import challenge
from game import DEALER_ROTATION, VUL_ROTATION


def paired(per_deal: list) -> str:
    diffs = [sum(d) / len(d) for d in per_deal if d]
    n = len(diffs)
    if n < 2:
        return f"n={n}"
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    t = mean / se if se else float('inf') if mean else 0.0
    boards = sum(len(d) for d in per_deal)
    changed = sum(1 for d in per_deal for x in d if x)
    return f"{mean:+.3f} per board (t = {t:+.2f} over {n} deals; {changed} of {boards} boards changed)"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('flags', nargs='+', metavar='flag',
                        help="ai switches to turn off and on together, e.g. DRAW_TRUMPS")
    parser.add_argument('--deals', type=int, default=None)
    parser.add_argument('--set', action='append', default=[], metavar='NAME=VALUE',
                        help="hold another ai switch at True or False for both runs")
    args = parser.parse_args(argv)
    for flag in args.flags:
        if not hasattr(ai, flag):
            print(f"ai has no switch {flag}")
            return 1
    for setting in args.set:
        name, _, raw = setting.partition('=')
        if not hasattr(ai, name) or raw not in ('True', 'False'):
            print(f"bad --set {setting!r}: expected an ai switch and True or False")
            return 1
        setattr(ai, name, raw == 'True')

    deal_ids = challenge.deal_ids()[:args.deals] if args.deals else challenge.deal_ids()
    tricks, points = [], []
    started = time.perf_counter()
    for deal_id in deal_ids:
        tricks.append([])
        points.append([])
        for board in range(1, 17):
            dealer = DEALER_ROTATION[(board - 1) % 4]
            vul = VUL_ROTATION[(board - 1) % 16]
            results = []
            for value in (False, True):
                for flag in args.flags:
                    setattr(ai, flag, value)
                results.append(challenge.robot_table(deal_id, dealer, vul))
            off, on = results
            if off['contract'] is None:
                continue
            if on['contract'] != off['contract']:
                raise AssertionError(f"deal {deal_id} board {board}: the switch changed the auction")
            side = off['contract']['side']
            tricks[-1].append(on['declarer_tricks'] - off['declarer_tricks'])
            def declarer_points(table: dict) -> int:
                result = table['result']
                return result['points'] if result['winner'] == side else -result['points']
            points[-1].append(declarer_points(on) - declarer_points(off))
        if deal_id % 50 == 49:
            print(f"  ...{deal_id + 1} deals, {time.perf_counter() - started:.0f}s", flush=True)

    label = ' + '.join(args.flags) + ''.join(f" ({setting})" for setting in args.set)
    print(f"\n{label}: {len(deal_ids)} deals x 16 boards, {sum(len(d) for d in tricks)} played boards, "
          f"{time.perf_counter() - started:.0f}s")
    print(f"  declarer tricks: {paired(tricks)}")
    print(f"  declarer score (from the declaring side): {paired(points)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
