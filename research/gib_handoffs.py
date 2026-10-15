"""Where does GIB hand the call to ai.py's fallback?

`ai.ai_bid_explained` asks `gib.gib_bid` first and falls back to the previous
system when it returns None. This deals random boards, lets four robots bid
them, and records every handoff as the auction seen from the bidder's seat,
opponents' calls in brackets: `1D (2C) Pass (Pass) ?`.

    python research/gib_handoffs.py survey 4000 research/data/handoffs.json
    python research/gib_handoffs.py roles research/data/handoffs.json
    python research/gib_handoffs.py families research/data/handoffs.json 40
    python research/gib_handoffs.py hands research/data/handoffs.json "1x (1y) X (2y) ?"

`roles` groups by seat and round, `families` by auction shape with suits
replaced by letters in order of appearance (`1x (P) 1y (1z) ?`), and `hands`
prints real hands for one family so a bridge player can judge the calls.
Read-only analysis; the app never imports this. First run (2026-10-14, 4,000
boards): 14.9% of calls handed off, on 48% of boards; see docs/BIDDING.md.
"""
from __future__ import annotations
import collections
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ai   # noqa: E402
import gib  # noqa: E402
from card import deal  # noqa: E402
from game import AuctionState  # noqa: E402

DEALERS = ['North', 'East', 'South', 'West']
VULS = ['None', 'N/S', 'E/W', 'Both']
PARTNER = {'North': 'South', 'South': 'North', 'East': 'West', 'West': 'East'}
SYM = {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}


def pattern(player: str, calls: list) -> str:
    """Calls from the first bid on, opponents bracketed, from player's seat."""
    out, started = [], False
    for w, c in calls:
        if not started and c == 'Pass':
            continue
        started = True
        out.append(c if w in (player, PARTNER[player]) else f'({c})')
    return ' '.join(out + ['?']) if out else '?'


def family(pat: str) -> str:
    """Suits replaced by x, y, z, w in order of appearance; Pass as P."""
    names: dict[str, str] = {}

    def sub(m):
        lvl, s = m.group(1), m.group(2)
        if s == 'NT':
            return lvl + 'NT'
        if s not in names:
            names[s] = 'xyzw'[len(names)]
        return lvl + names[s]
    return re.sub(r'(\d)(NT|[CDHS])', sub, pat).replace('Pass', 'P')


def role(pat: str) -> tuple[str, str, bool]:
    """(seat, which of its calls, have the opponents bid beyond opening)."""
    t = pat.split()
    k = len(t) - 1
    we = not t[0].startswith('(')
    seat = ({0: 'opener', 2: 'responder'} if we else {1: 'overcaller', 3: 'advancer'}).get(k % 4, '?')
    rnd = ['1st', '2nd', '3rd+'][min(k // 4, 2)]
    theirs = [x for x in t[:-1] if x.startswith('(') and x != '(Pass)']
    return seat, rnd, len(theirs) > (0 if we else 1)


def survey(n: int, out: str, seed: int = 20261014) -> None:
    handoff = collections.Counter()
    fallback = collections.defaultdict(collections.Counter)
    examples: dict[str, list] = {}
    total = boards_with = 0
    random.seed(seed)
    for b in range(n):
        hands = deal()
        dealer = DEALERS[b % 4]
        a = AuctionState(dealer=dealer, vulnerability=VULS[(b // 4) % 4])
        hit = False
        while not a.is_complete:
            p = a.current_player()
            total += 1
            g = gib.gib_bid(p, hands[p], a)
            call, why = ai.ai_bid_explained(p, hands[p], a)
            if g is None:
                hit = True
                pat = pattern(p, a.calls)
                handoff[pat] += 1
                fallback[pat][call] += 1
                examples.setdefault(pat, []).append({
                    'board': b, 'dealer': dealer, 'seat': p,
                    'hand': ' '.join(f'{c.rank}{c.suit}' for c in hands[p]),
                    'calls': [c for _, c in a.calls], 'call': call, 'why': why})
            a.apply_call(p, call)
        boards_with += hit
    k = sum(handoff.values())
    print(f"{n} boards, {total} calls; handoffs: {k} calls ({100 * k / total:.1f}%), "
          f"on {boards_with} boards ({100 * boards_with / n:.0f}%); {len(handoff)} auctions")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({'handoff': handoff, 'fallback': fallback, 'examples': examples},
              open(out, 'w', encoding='utf-8'), indent=1)


def roles(d: dict) -> None:
    tab, pas = collections.Counter(), collections.Counter()
    for pat, n in d['handoff'].items():
        r = role(pat)
        tab[r] += n
        pas[r] += d['fallback'][pat].get('Pass', 0)
    tot = sum(tab.values())
    print(f"{'seat':11} {'call':5} {'contested':9} {'handoffs':>8} {'share':>6} {'fallback passes':>16}")
    for (seat, rnd, cont), n in tab.most_common():
        print(f"{seat:11} {rnd:5} {('yes' if cont else 'no'):9} {n:8} {100 * n / tot:5.1f}% "
              f"{100 * pas[(seat, rnd, cont)] / n:15.0f}%")


def families(d: dict, top: int) -> None:
    fam, members = collections.Counter(), collections.defaultdict(collections.Counter)
    kinds = collections.defaultdict(collections.Counter)
    for pat, n in d['handoff'].items():
        f = family(pat)
        fam[f] += n
        members[f][pat] += n
        for c, k in d['fallback'][pat].items():
            kinds[f]['Pass' if c == 'Pass' else 'X' if c in ('X', 'XX') else 'bid'] += k
    total, cum = sum(fam.values()), 0
    print(f"{len(fam)} families, {total} handoffs")
    for f, n in fam.most_common(top):
        cum += n
        k = kinds[f]
        print(f"{n:4} {100 * cum / total:5.1f}%  {f:34} pass {k['Pass']:3} bid {k['bid']:3} "
              f"dbl {k['X']:3}   e.g. {members[f].most_common(1)[0][0]}")


def hands(d: dict, fam: str, limit: int = 25) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tests'))
    shown = 0
    for pat, exs in d['examples'].items():
        if family(pat) != fam:
            continue
        for e in exs:
            by = collections.defaultdict(list)
            for tok in e['hand'].split():
                by[tok[-1]].append(tok[:-1])
            disp = '  '.join(SYM[s] + (''.join(by[s]) or '—') for s in 'SHDC')
            print(f"{pat:30} {disp:40} -> {e['call']:4} \"{e['why']}\"")
            shown += 1
            if shown >= limit:
                return


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'survey':
        survey(int(sys.argv[2]), sys.argv[3])
    else:
        data = json.load(open(sys.argv[2], encoding='utf-8'))
        if cmd == 'roles':
            roles(data)
        elif cmd == 'families':
            families(data, int(sys.argv[3]) if len(sys.argv) > 3 else 40)
        elif cmd == 'hands':
            hands(data, sys.argv[3])
