"""Seated head to head for robot card-play switches.

`card_play_h2h.py` turns a switch on for all four seats, which reports the
change in declarer tricks: fine for a declarer-only or defence-only change,
but a change that both declarer and defenders use pulls both ways and nets
out. Here the switches are on for ONE side only, against robots without
them, then the sides swap; each board is scored from the switched side, so
the result is what the change is worth to whoever uses it. The auction is
untouched (card play only), so each pair is the same contract.

    python research/card_play_seated.py SHOWOUT_MIDDLE
    python research/card_play_seated.py SHOWOUT_MIDDLE AUCTION_IN_PLAY --deals 100
    python research/card_play_seated.py X --shard 0/2 --dump a.json   # split across
    python research/card_play_seated.py X --shard 1/2 --dump b.json   # processes,
    python research/card_play_seated.py --merge a.json b.json         # then merge

Boards of one deal share robot lines, so each deal's boards are averaged
first and the t is taken across deals. The play doesn't depend on the
vulnerability, so a switched side's play is reused across boards with the
same auction and only rescored.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai
import challenge
from game import DEALER_ROTATION, PARTNERSHIP, VUL_ROTATION


def paired(per_deal: list) -> str:
    diffs = [sum(d) / len(d) for d in per_deal if d]
    n = len(diffs)
    if n < 2:
        return f"n={n}"
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    t = mean / se if se else (float('inf') if mean else 0.0)
    boards = sum(len(d) for d in per_deal)
    changed = sum(1 for d in per_deal for x in d if x)
    return f"{mean:+.3f} per board (t = {t:+.2f} over {n} deals; {changed} of {boards} boards changed)"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('flags', nargs='*', help="ai switches the switched side plays with")
    parser.add_argument('--deals', type=int, default=None)
    parser.add_argument('--shard', default=None, metavar='I/N', help="play every Nth deal from I")
    parser.add_argument('--dump', default=None, help="write the per-deal results to this file")
    parser.add_argument('--merge', nargs='+', default=None, help="merge --dump files and report")
    parser.add_argument('--set', action='append', default=[], metavar='NAME=VALUE',
                        help="hold another ai switch at True or False for everyone")
    args = parser.parse_args(argv)
    if args.merge:
        parts = [json.load(open(f)) for f in args.merge]
        print(f"\n{parts[0]['label']}, seated: merged {len(parts)} shards")
        print(f"  switched side's tricks: {paired([d for p in parts for d in p['tricks']])}")
        print(f"  switched side's score:  {paired([d for p in parts for d in p['points']])}")
        return 0
    for flag in args.flags:
        if not isinstance(getattr(ai, flag, None), bool):
            print(f"ai has no switch {flag}")
            return 1
    for setting in args.set:
        name, _, raw = setting.partition('=')
        if not isinstance(getattr(ai, name, None), bool) or raw not in ('True', 'False'):
            print(f"bad --set {setting!r}")
            return 1
        setattr(ai, name, raw == 'True')

    switched = {'side': None}
    replayed: dict = {}                   # (deal, calls, side) -> tricks taken
    real_play = challenge.ai_play

    def play(seat, *a, **k):
        on = PARTNERSHIP[seat] == switched['side']
        for flag in args.flags:
            setattr(ai, flag, on)
        return real_play(seat, *a, **k)

    challenge.ai_play = play
    deal_ids = challenge.deal_ids()[:args.deals] if args.deals else challenge.deal_ids()
    if args.shard:
        i, n = (int(x) for x in args.shard.split('/'))
        deal_ids = deal_ids[i::n]
    points, tricks = [], []
    started = time.perf_counter()
    try:
        for deal_id in deal_ids:
            points.append([])
            tricks.append([])
            for board in range(1, 17):
                dealer = DEALER_ROTATION[(board - 1) % 4]
                vul = VUL_ROTATION[(board - 1) % 16]
                switched['side'] = None
                base = challenge.robot_table(deal_id, dealer, vul)
                if base['contract'] is None:
                    continue
                gain_p = gain_t = 0.0
                for side in ('N/S', 'E/W'):
                    switched['side'] = side
                    key = (deal_id, tuple(base['calls']), side)
                    if key not in replayed:
                        var = challenge.robot_table(deal_id, dealer, vul)
                        if var['contract'] != base['contract']:
                            raise AssertionError(f"deal {deal_id}: the switch changed the auction")
                        replayed[key] = dict(var['tricks_taken'])
                    taken = replayed[key]
                    result = challenge.score_contract(base['contract'], taken)
                    def score(r):
                        return r['points'] if r['winner'] == side else -r['points']
                    gain_p += score(result) - score(base['result'])
                    gain_t += taken[side] - base['tricks_taken'][side]
                points[-1].append(gain_p / 2)
                tricks[-1].append(gain_t / 2)
            if deal_id % 100 == 99:
                print(f"  ...{deal_id + 1} deals, {time.perf_counter() - started:.0f}s", flush=True)
    finally:
        challenge.ai_play = real_play

    label = ' + '.join(args.flags) + ''.join(f" ({s})" for s in args.set)
    if args.dump:
        with open(args.dump, 'w') as f:
            json.dump({'label': label, 'tricks': tricks, 'points': points}, f)
    print(f"\n{label}, seated: {len(deal_ids)} deals x 16 boards, "
          f"{time.perf_counter() - started:.0f}s")
    print(f"  switched side's tricks: {paired(tricks)}")
    print(f"  switched side's score:  {paired(points)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
