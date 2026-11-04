"""Check the top candidate gaps on fresh deals, solved double dummy.

    python3.12 fresh.py bid survey.jsonl fresh_bid.json [per_group]
    python3.12 fresh.py solve fresh_bid.json fresh_solved.jsonl
    python3.12 fresh.py score fresh_bid.json fresh_solved.jsonl

`bid` replays each survey pass in GROUPS (hands with values), tries the
natural alternatives (cost.menu), lets the robots finish, and stores every
contract. `solve` runs the Rust engine on each distinct (deal, strain,
declarer); `score` gives each alternative's mean gain over the pass. Each
instance is a different deal (one per deal and group), so t is honest.
"""
from __future__ import annotations
import collections, json, math, random, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import pass_trace as T  # noqa: E402
from cost import menu, finish, short  # noqa: E402
from analyse_cost import imps  # noqa: E402
from card import deal  # noqa: E402
from challenge import score_for  # noqa: E402
from game import AuctionState  # noqa: E402
from bridge.auction import clockwise_from  # noqa: E402
from research.dd_dataset import RUST_EXE  # noqa: E402

SEED = 30_000_000
GROUPS = [
    ('gib:_defend:4540', '(1NT) P (2x) P (2y) P (P) ?'),
    ('gib:_defend:4540', '(3x) ?'),
    ('gib:_defend:4540', '(1x) P (1y) P (2x) ?'),
    ('gib:_defend:4540', '(1x) P (4x) ?'),
    ('gib:_defend:4540', '(2x) P (4x) ?'),
    ('gib:_defend:4540', '(1x) P (1y) ?'),
    ('gib:_defend:4540', '(1x) P (2y) ?'),
    ('gib:_defend:4540', '(1x) P (2x) ?'),
    ('gib:_respond_over_interference:3404', '1x (2y) ?'),
    ('ai:_previous_system:1426', '(1x) X (2x) X (P) ?'),
]


def hands(deal_id):
    random.seed(SEED + deal_id)
    return {s: list(c) for s, c in deal().items()}


def contract(c):
    if c is None:
        return None
    return {k: c[k] for k in ('level', 'strain', 'declarer', 'side', 'doubled',
                              'vulnerability', 'tricks_needed', 'trump')}


def replay(job):
    deal_id, dealer, vul, seat, pattern, group = job
    h = hands(deal_id)
    a = AuctionState(dealer=dealer, vulnerability=vul)
    al = {}
    while not a.is_complete:
        p = a.current_player()
        calls = list(a.calls)
        c, why, src, site = T.decide(p, h[p], a, al)
        if p == seat and c == 'Pass' and T.pattern(p, calls) == pattern:
            legal = a.legal_calls()
            al[len(a.calls)] = why
            a.apply_call(p, c)
            base, _ = finish(h, dealer, vul, list(a.calls), al)
            del al[len(calls)]
            alts = {}
            for kind, x in menu(p, h[p], calls, legal).items():
                try:
                    con, seq = finish(h, dealer, vul, calls + [(p, x)], al)
                except Exception as e:
                    continue
                alts[kind] = [x, contract(con), ' '.join(seq)]
            return dict(deal=deal_id, dealer=dealer, vul=vul, seat=seat, pattern=pattern,
                        group=list(group), site=site, actual=contract(base),
                        hand=' '.join(f"{c.rank}{c.suit}" for c in h[p]), alts=alts)
        al[len(a.calls)] = why
        a.apply_call(p, c)
    return None


def bid(survey, out, per):
    want = {g: [] for g in GROUPS}
    seen = set()
    for line in open(survey):
        for r in json.loads(line)['passes']:
            g = (r['site'], r['family'])
            if g in want and len(want[g]) < per and (r['hcp'] >= 10 or max(r['len'].values()) >= 6) \
                    and (r['deal'], g) not in seen:
                seen.add((r['deal'], g))
                want[g].append((r['deal'], r['dealer'], r['vul'], r['seat'], r['pattern'], g))
    jobs = [j for v in want.values() for j in v]
    print({g[1]: len(v) for g, v in want.items()}, flush=True)
    with Pool(4) as pool:
        rows = [r for r in pool.imap(replay, jobs, chunksize=4) if r]
    json.dump(rows, open(out, 'w'))
    print(len(rows), 'replayed')


def solved(path):
    t = {}
    try:
        for line in open(path):
            r = json.loads(line)
            for d, v in r['ns'].items():
                t[(r['deal'], r['strain'], d)] = v
    except FileNotFoundError:
        pass
    return t


def solve(bid_file, out):
    rows = json.load(open(bid_file))
    done = solved(out)
    need = collections.defaultdict(set)
    for r in rows:
        for c in [r['actual']] + [a[1] for a in r['alts'].values()]:
            if c and (r['deal'], c['strain'], c['declarer']) not in done:
                need[(r['deal'], c['strain'])].add(c['declarer'])
    print(sum(map(len, need.values())), 'contracts to solve', flush=True)

    def job(item):
        (deal_id, strain), ds = item
        ds = sorted(ds)
        h = hands(deal_id)
        payload = {'hands': {s: ' '.join(f"{c.rank}{c.suit}" for c in h[s]) for s in h},
                   'strain': strain,
                   'queries': [{'leader': clockwise_from(d)[1], 'trick': []} for d in ds]}
        p = subprocess.run([str(RUST_EXE)], input=json.dumps(payload), capture_output=True,
                           text=True, check=True)
        res = json.loads(p.stdout)['results']
        return dict(deal=deal_id, strain=strain, ns={d: x['ns_tricks'] for d, x in zip(ds, res)})

    with ThreadPoolExecutor(4) as pool, open(out, 'a') as f:
        for k, r in enumerate(pool.map(job, sorted(need.items()))):
            f.write(json.dumps(r) + '\n')
            f.flush()
            if k % 50 == 0:
                print(k, flush=True)


def score(bid_file, solved_file):
    rows = json.load(open(bid_file))
    t = solved(solved_file)

    def pts(r, c):
        if c is None:
            return 0
        ns = t.get((r['deal'], c['strain'], c['declarer']))
        if ns is None:
            return None
        side = T.SIDE[r['seat']]
        return score_for(side, c, ns if c['side'] == 'N/S' else 13 - ns)

    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        base = pts(r, r['actual'])
        if base is None:
            continue
        for k, a in r['alts'].items():
            v = pts(r, a[1])
            if v is not None:
                by[tuple(r['group'])][k].append((v - base, r))
    for g, ks in by.items():
        n = sum(1 for r in rows if tuple(r['group']) == g)
        print(f"\n{g[1]}   [{g[0]}]  {n} deals")
        for k, vs in sorted(ks.items()):
            d = [v for v, _ in vs]
            m = sum(d) / len(d)
            sd = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1)) if len(d) > 1 else 0
            im = [imps(x) for x in d]
            mi = sum(im) / len(im)
            sdi = math.sqrt(sum((x - mi) ** 2 for x in im) / (len(im) - 1)) if len(im) > 1 else 0
            print(f"   {k:5} n={len(d):3}  {m:+6.0f} pts (t {m / (sd / math.sqrt(len(d))) if sd else 0:+.1f})"
                  f"  {mi:+5.2f} IMPs (t {mi / (sdi / math.sqrt(len(im))) if sdi else 0:+.1f})"
                  f"  better {sum(x > 0 for x in d)} worse {sum(x < 0 for x in d)}")


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'bid':
        bid(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 60)
    elif cmd == 'solve':
        solve(sys.argv[2], sys.argv[3])
    elif cmd == 'score':
        score(sys.argv[2], sys.argv[3])
