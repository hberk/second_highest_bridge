"""The robots at the experts' tables: for every contested decision in the
1996-2002 championship auctions (championship-study/experts.jsonl, from
github.com/ContractBridge/pbn-files), give the robot the expert's hand and
the experts' calls so far, and record both calls and the robot's pass site.
The experts' earlier calls carry no robot alerts (read like a human's).

    python3.12 experts.py out.jsonl experts.jsonl

experts.jsonl: the championship auctions parsed from github.com/ContractBridge/pbn-files
(the championship study's parse_pbn.py).
"""
from __future__ import annotations
import json, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import pass_trace as T  # noqa: E402
from card import Card  # noqa: E402
from game import AuctionState  # noqa: E402
from survey import features  # noqa: E402
from multiprocessing import Pool

SEAT = {'N': 'North', 'E': 'East', 'S': 'South', 'W': 'West'}
VUL = {'None': 'None', 'NS': 'N/S', 'N/S': 'N/S', 'EW': 'E/W', 'E/W': 'E/W', 'All': 'Both', 'Both': 'Both'}


def cards(h):
    return [Card(s, '10' if r.upper() == 'T' else r.upper()) for s in 'SHDC' for r in h[s]]


def board(line):
    b = json.loads(line)
    vul = VUL.get(b['vul'])
    if vul is None or not b['calls']:
        return []
    h = {SEAT[k]: cards(v) for k, v in b['hands'].items()}
    a = AuctionState(dealer=SEAT[b['dealer']], vulnerability=vul)
    out = []
    for expert in b['calls']:
        if a.is_complete:
            break
        p = a.current_player()
        calls = list(a.calls)
        if expert not in a.legal_calls():
            break
        if T.contested(p, calls):
            try:
                c, why, src, site = T.decide(p, h[p], a, {})
            except Exception as e:
                c, why, src, site = None, repr(e), 'crash', None
            pat = T.pattern(p, calls)
            out.append(dict(event=b['event'], pattern=pat, family=T.family(pat), expert=expert,
                            robot=c, src=src, site=site, why=why, vul=vul, **features(h[p])))
        a.apply_call(p, expert)
    return out


if __name__ == '__main__':
    lines = open(sys.argv[2]).readlines()
    with Pool(4) as pool, open(sys.argv[1], 'w') as f:
        for i, rows in enumerate(pool.imap(board, lines, chunksize=50)):
            for r in rows:
                f.write(json.dumps(r) + '\n')
            if i % 5000 == 0:
                print(i, flush=True)
