"""Frequency survey: every robot Pass in a contested auction on fresh deals,
with the code site that produced it.

    python3.12 survey.py N out.jsonl [start]

Deals: random.seed(30_000_000 + id), card.deal (research only). Each deal is
bid four times (each dealer, vulnerability rotating). One JSON line per deal:
passes (contested, or right after partner's artificial call) in full, plus a
count of all contested decisions by family so pass rates can be computed.
"""
from __future__ import annotations
import collections, json, random, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import pass_trace as T  # noqa: E402
from card import deal  # noqa: E402
from game import AuctionState  # noqa: E402
from multiprocessing import Pool

SEED = 30_000_000
DEALERS = ['North', 'East', 'South', 'West']
VULS = ['None', 'N/S', 'E/W', 'Both']
HCP = {'A': 4, 'K': 3, 'Q': 2, 'J': 1}


def hand_text(cards):
    return ' '.join(f"{c.rank}{c.suit}" for c in cards)


def features(cards):
    ln = collections.Counter(c.suit for c in cards)
    return dict(hcp=sum(HCP.get(c.rank, 0) for c in cards),
                len={s: ln[s] for s in 'SHDC'})


def bid_board(h, dealer, vul):
    a = AuctionState(dealer=dealer, vulnerability=vul)
    al, rows, fams = {}, [], collections.Counter()
    while not a.is_complete:
        p = a.current_player()
        calls = list(a.calls)
        c, why, src, site = T.decide(p, h[p], a, al)
        con = T.contested(p, calls)
        pl = T.partner_last(p, calls)
        partner_art = (pl is not None and pl == len(calls) - 2
                       and bool(T.ARTIFICIAL.search(al.get(pl, ''))))
        if con or partner_art:
            pat = T.pattern(p, calls)
            fam = T.family(pat)
            if con:
                fams[(fam, c == 'Pass')] += 1
            if c == 'Pass':
                rows.append(dict(seat=p, pattern=pat, family=fam, src=src, site=site, why=why,
                                 contested=con, partner_art=partner_art,
                                 partner_alert=al.get(pl, '') if pl is not None else '',
                                 rho=calls[-1][1] if calls else None,
                                 vul=vul, hand=hand_text(h[p]), **features(h[p])))
        al[len(a.calls)] = why
        a.apply_call(p, c)
    return rows, fams


def run(deal_id):
    random.seed(SEED + deal_id)
    h = {s: list(c) for s, c in deal().items()}
    rows, fams = [], collections.Counter()
    for k, dealer in enumerate(DEALERS):
        r, f = bid_board(h, dealer, VULS[(deal_id + k) % 4])
        for x in r:
            x.update(deal=deal_id, dealer=dealer)
        rows += r
        fams.update(f)
    return dict(deal=deal_id, passes=rows,
                fams=[[f, p, n] for (f, p), n in fams.items()])


if __name__ == '__main__':
    n, out = int(sys.argv[1]), sys.argv[2]
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    with Pool(4) as pool, open(out, 'a') as f:
        for i, r in enumerate(pool.imap(run, range(start, start + n), chunksize=20)):
            f.write(json.dumps(r) + '\n')
            if i % 500 == 0:
                print(i, flush=True)
