"""Head to head: a new GIB branch against the robots without it.

Names one or more functions in gib.py. The variant side plays with them; the
incumbent side has them return None, i.e. the robots as they were before the
branch existed. Variant at N/S and incumbent at E/W, then swapped, over the
400 solved library deals x 4 dealers. Each contract is scored at its double
dummy trick count, from the variant's own side, so the result is a margin
with 0 as the baseline and measures the AUCTION only (see "TWO METRICS" in
docs/BIDDING.md for why it must be this metric).

    python research/gib_h2h.py _reopening _answer_reopening
    python research/gib_h2h.py SELF_SPLINTER       # a switch: True against False

First used 2026-10-14 for the reopening double: +1.64 per board, t = +2.06,
28 of 1,600 auctions changed.
"""
from __future__ import annotations
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ai         # noqa: E402
import challenge  # noqa: E402
import gib        # noqa: E402
from game import AuctionState  # noqa: E402

SIDE = {'North': 'N/S', 'South': 'N/S', 'East': 'E/W', 'West': 'E/W'}
DEALERS = ['North', 'East', 'South', 'West']
VULS = ['None', 'N/S', 'E/W', 'Both']


def main(names: list[str]) -> None:
    on = {n: getattr(gib, n) for n in names}
    # A function is switched off by returning None; a True/False switch by False.
    off = {n: False if isinstance(on[n], bool) else (lambda ctx, *a, **k: None) for n in names}
    for n in names:
        if isinstance(on[n], bool):
            on[n] = True

    def auction(deal_id, dealer, vul, variant_side):
        hands = challenge.hands_for(deal_id)
        a = AuctionState(dealer=dealer, vulnerability=vul)
        while not a.is_complete:
            p = a.current_player()
            for n, f in (on if SIDE[p] == variant_side else off).items():
                setattr(gib, n, f)
            call, _ = ai.ai_bid_explained(p, hands[p], a)
            a.apply_call(p, call)
        return a.get_contract(), [c for _, c in a.calls]

    def score(deal_id, contract, side):
        if contract is None:
            return 0
        t = challenge.dd_tricks(deal_id, contract['strain'], contract['side'])
        return challenge.score_for(side, contract, t)

    diffs, examples = [], []
    try:
        for deal_id in challenge.deal_ids():
            for k, dealer in enumerate(DEALERS):
                vul = VULS[(deal_id + k) % 4]
                m = 0
                for vs in ('N/S', 'E/W'):
                    c_var, calls_var = auction(deal_id, dealer, vul, vs)
                    c_inc, calls_inc = auction(deal_id, dealer, vul, None)
                    d = score(deal_id, c_var, vs) - score(deal_id, c_inc, vs)
                    m += d
                    if calls_var != calls_inc:
                        examples.append((d, deal_id, dealer, vs,
                                         ' '.join(calls_inc), ' '.join(calls_var)))
                diffs.append(m / 2)
    finally:
        for n, f in on.items():
            setattr(gib, n, f)
    n = len(diffs)
    mean = sum(diffs) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in diffs) / (n - 1))
    print(f"boards {n}, auctions changed {len(examples)}")
    t = f"{mean / (sd / math.sqrt(n)):+.2f}" if sd else "undefined (no board scored differently)"
    print(f"head to head: {mean:+.2f} per board, t = {t}")
    examples.sort()
    for d, i, dl, vs, a0, a1 in examples[:5] + examples[-5:]:
        print(f"{d:+6} deal {i:3} dealer {dl:5} variant {vs}\n      was: {a0}\n      now: {a1}")


if __name__ == '__main__':
    main(sys.argv[1:])
