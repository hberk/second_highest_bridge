"""What the robots' contested passes cost, on the 800 fully solved deals
(data/solved_deals.json + data/training_deals.json, 16 boards each).

For every robot Pass in a contested auction, try a fixed menu of
natural alternatives (`menu`), for passes on hands with values (`worth`), let the robots finish each auction, and
score it at the double dummy result from the passer's side. Records the code
site of the pass (trace.origin), so passes can be grouped by where they came
from. Research only.

    python3.12 cost.py out.jsonl
"""
from __future__ import annotations
import json, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import pass_trace as T  # noqa: E402
import ai  # noqa: E402
from card import Card  # noqa: E402
from challenge import score_for  # noqa: E402
from game import AuctionState, DEALER_ROTATION, VUL_ROTATION  # noqa: E402
from survey import features, hand_text  # noqa: E402
from multiprocessing import Pool

ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'data') + '/'
DEALS = {}
for tag, f in (('L', 'solved_deals.json'), ('T', 'training_deals.json')):
    for d in json.load(open(ROOT + f))['deals']:
        DEALS[f"{tag}{d['id']}"] = d


def hands(key):
    raw = DEALS[key]['hands']
    return {s: [Card(t[-1], t[:-1]) for t in raw[s].split()] for s in raw}


def value(key, c, side):
    if c is None:
        return 0
    return score_for(side, c, DEALS[key]['tricks'][f"{c['strain']}:{c['declarer']}"])


def finish(h, dealer, vul, calls, alerts):
    a = AuctionState(dealer=dealer, vulnerability=vul)
    for w, c in calls:
        a.apply_call(w, c)
    al = dict(alerts)
    while not a.is_complete and len(a.calls) < 80:
        p = a.current_player()
        c, why = ai.ai_bid_explained(p, h[p], a, al)
        al[len(a.calls)] = why
        a.apply_call(p, c)
    return a.get_contract(), [c for _, c in a.calls]


#: Sites whose pass is itself the meaning (a penalty pass, a pre-emptor's
#: discipline, partner's game or penalty double standing): never costed.
MEANT = ('_preemptor_passes', '_lead_doubler_passes', '_doubled_or_base', '_penalty_or_base',
         '_after_jam', '_own_suit_raised', '_two_suiter_choice', 'they_opened:4210')


def worth(site, hcp, ln):
    """A pass worth costing: values (10+ HCP) or a six-card suit, from a
    site that is not a deliberate pass."""
    return (hcp >= 10 or max(ln.values()) >= 6) and not any(m in site for m in MEANT)


def menu(p, cards, calls, legal):
    """The natural alternatives to a pass: X; my longest suit outside
    theirs (5+); partner's last suit with 3+; notrump with no singleton.
    Each at its cheapest legal level, up to the five level (3NT for NT)."""
    ln = {s: sum(c.suit == s for c in cards) for s in 'SHDC'}
    theirs = {c[1:] for w, c in calls if w not in (p, T.PARTNER[p]) and c[0].isdigit()}
    pd = [c[1:] for w, c in calls if w == T.PARTNER[p] and c[0].isdigit()]

    def cheapest(s, top=5):
        for lvl in range(1, top + 1):
            if f"{lvl}{s}" in legal:
                return f"{lvl}{s}"
        return None
    out = {}
    if 'X' in legal:
        out['X'] = 'X'
    own = [s for s in 'SHDC' if s not in theirs and ln[s] >= 5]
    if own:
        s = max(own, key=lambda x: (ln[x], 'CDHS'.index(x)))
        c = cheapest(s)
        if c:
            out['own'] = c
    if pd and pd[-1] in 'SHDC' and ln[pd[-1]] >= 3:
        c = cheapest(pd[-1])
        if c and c not in out.values():
            out['raise'] = c
    if min(ln.values()) >= 2:
        c = cheapest('NT', 3)
        if c:
            out['nt'] = c
    return out


def short(c):
    if c is None:
        return 'AP'
    d = {'None': '', 'X': 'X', 'XX': 'XX'}.get(c['doubled'], '')
    return f"{c['level']}{c['strain']}{d} {c['declarer'][0]}"


def board(job):
    key, b = job
    dealer = DEALER_ROTATION[(b - 1) % 4]
    vul = VUL_ROTATION[(b - 1) % 16]
    h = hands(key)
    a = AuctionState(dealer=dealer, vulnerability=vul)
    al, dec = {}, []
    while not a.is_complete and len(a.calls) < 80:
        p = a.current_player()
        calls = list(a.calls)
        c, why, src, site = T.decide(p, h[p], a, al)
        if c == 'Pass' and T.contested(p, calls):
            pl = T.partner_last(p, calls)
            f = features(h[p])
            if worth(site, f['hcp'], f['len']):
                dec.append((p, calls, dict(al), why, src, site, a.legal_calls(),
                            al.get(pl, '') if pl is not None else ''))
        al[len(a.calls)] = why
        a.apply_call(p, c)
    final = a.get_contract()
    out = []
    for p, calls, als, why, src, site, legal, palert in dec:
        side = T.SIDE[p]
        actual = value(key, final, side)
        alts = {}
        for kind, x in menu(p, h[p], calls, legal).items():
            try:
                con, seq = finish(h, dealer, vul, calls + [(p, x)], als)
            except Exception as e:
                alts[kind] = [x, None, repr(e)]
                continue
            alts[kind] = [x, value(key, con, side) - actual, short(con)]
        pat = T.pattern(p, calls)
        out.append(dict(deal=key, board=b, seat=p, vul=vul, pattern=pat, family=T.family(pat),
                        src=src, site=site, why=why, partner_alert=palert,
                        final=short(final), actual=actual, alts=alts,
                        hand=hand_text(h[p]), **features(h[p])))
    out.append({'job': [key, b]})
    return out


if __name__ == '__main__':
    out = sys.argv[1]
    done = set()
    try:
        done = {tuple(json.loads(l)['job']) for l in open(out) if '"job"' in l}
    except FileNotFoundError:
        pass
    which = sys.argv[2] if len(sys.argv) > 2 else 'LT'
    jobs = [(k, b) for k in DEALS if k[0] in which for b in range(1, 17) if (k, b) not in done]
    with Pool(4) as pool, open(out, 'a') as f:
        for i, rows in enumerate(pool.imap_unordered(board, jobs, chunksize=4)):
            for r in rows:
                f.write(json.dumps(r) + '\n')
            f.flush()
            if i % 200 == 0:
                print(i, len(jobs), flush=True)
