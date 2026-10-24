"""Head to head on fresh random deals, for bidding changes too rare or too
small for the 400 library deals.

Every board is bid both ways (the variant side at N/S, then at E/W, against
the robots as they are), which takes about two minutes for 3,000 deals. Only
the contracts an auction actually changes are solved, with the Rust engine,
and every other board scores 0 by construction. A solve takes 10-40 s, so
the solving is the cost: about 1,500 contracts for 3,000 deals and a large
change. Solves are cached by (deal, strain, declarer) and shared across runs.

    python research/gib_fresh_h2h.py bid 3000 variants.json research/data/fresh_bid.json
    python research/gib_fresh_h2h.py solve research/data/fresh_bid.json research/data/fresh_solved.jsonl
    python research/gib_fresh_h2h.py score research/data/fresh_bid.json research/data/fresh_solved.jsonl

variants.json names each variant's gib/ai constants, e.g.
{"game28": {"GAME": 28}, "both": {"GAME": 28, "MAJOR_OVER_3NT": true}}.
The incumbent keeps the module's values unless `--base base.json` sets them,
which is how a change already in the code is measured against the old one.

Deals come from random.seed(SEED + id) and `card.deal`: research only, since
reseeding the global RNG is what the app must never do (`challenge.hands_for`).
First used 2026-10-23 (BIDDING.md, "Game by points"): the library alone
measured lighter overcalls at +1.5 a board, t = +2.3, and 3,000 fresh deals
at -0.8, t = -3.2.
"""
from __future__ import annotations

import json
import math
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai          # noqa: E402
import challenge   # noqa: E402
import gib         # noqa: E402
from bridge.auction import clockwise_from  # noqa: E402
from card import deal  # noqa: E402
from game import AuctionState  # noqa: E402
from research.dd_dataset import RUST_EXE  # noqa: E402

SIDE = {'North': 'N/S', 'South': 'N/S', 'East': 'E/W', 'West': 'E/W'}
DEALERS = ['North', 'East', 'South', 'West']
VULS = ['None', 'N/S', 'E/W', 'Both']
SEED = 7_000_000
VARIANTS: dict = {}
BASE: dict = {}


def _module(name: str):
    return gib if hasattr(gib, name) else ai


def _values(spec: dict) -> dict:
    return {k: tuple(v) if isinstance(v, list) else v for k, v in spec.items()}


def setup(variants: dict, base: dict) -> None:
    VARIANTS.update({k: _values(v) for k, v in variants.items()})
    BASE.update(_values(base))
    for v in VARIANTS.values():
        for name in v:
            BASE.setdefault(name, getattr(_module(name), name))


def hands(deal_id: int) -> dict:
    random.seed(SEED + deal_id)
    return {seat: list(cards) for seat, cards in deal().items()}


def auction(h: dict, dealer: str, vul: str, variant: dict, variant_side: str | None):
    a = AuctionState(dealer=dealer, vulnerability=vul)
    while not a.is_complete:
        p = a.current_player()
        for name, value in (variant if SIDE[p] == variant_side else BASE).items():
            setattr(_module(name), name, value)
        call, _ = ai.ai_bid_explained(p, h[p], a)
        a.apply_call(p, call)
    for name, value in BASE.items():
        setattr(_module(name), name, value)
    c = a.get_contract()
    keep = ('level', 'strain', 'declarer', 'side', 'doubled', 'vulnerability', 'tricks_needed', 'trump')
    return (None if c is None else {k: c[k] for k in keep}), ' '.join(call for _, call in a.calls)


def bid_deal(deal_id: int) -> list[dict]:
    h = hands(deal_id)
    rows = []
    for k, dealer in enumerate(DEALERS):
        vul = VULS[(deal_id + k) % 4]
        inc, calls_inc = auction(h, dealer, vul, {}, None)
        for name, variant in VARIANTS.items():
            for vs in ('N/S', 'E/W'):
                new, calls_new = auction(h, dealer, vul, variant, vs)
                if calls_new != calls_inc:
                    rows.append(dict(deal=deal_id, dealer=dealer, vul=vul, var=name, vs=vs,
                                     inc=inc, new=new, calls_inc=calls_inc, calls_new=calls_new))
    return rows


def _init(variants: dict, base: dict) -> None:
    setup(variants, base)


def bid(n: int, variants: dict, base: dict, out: str) -> None:
    with Pool(initializer=_init, initargs=(variants, base)) as pool:
        rows = [r for rs in pool.imap(bid_deal, range(1, n + 1), chunksize=50) for r in rs]
    json.dump(dict(n=n, variants=variants, base=base, rows=rows), open(out, 'w'))
    print(f"{len(rows)} auctions changed")


def _solved(path: str) -> dict:
    tricks = {}
    if Path(path).exists():
        for line in open(path):
            r = json.loads(line)
            for declarer, t in r['ns'].items():
                tricks[(r['deal'], r['strain'], declarer)] = t
    return tricks


def solve(bid_file: str, out: str) -> None:
    rows = json.load(open(bid_file))['rows']
    done = _solved(out)
    need: dict = {}
    for r in rows:
        for c in (r['inc'], r['new']):
            if c and (r['deal'], c['strain'], c['declarer']) not in done:
                need.setdefault((r['deal'], c['strain']), set()).add(c['declarer'])
    print(f"{sum(len(v) for v in need.values())} contracts to solve", flush=True)

    def job(item):
        (deal_id, strain), declarers = item
        declarers = sorted(declarers)
        h = hands(deal_id)
        payload = {'hands': {s: ' '.join(f"{c.rank}{c.suit}" for c in h[s]) for s in h},
                   'strain': strain,
                   'queries': [{'leader': clockwise_from(d)[1], 'trick': []} for d in declarers]}
        proc = subprocess.run([str(RUST_EXE)], input=json.dumps(payload), capture_output=True,
                              text=True, check=True)
        results = json.loads(proc.stdout)['results']
        return dict(deal=deal_id, strain=strain,
                    ns={d: r['ns_tricks'] for d, r in zip(declarers, results)})

    with ThreadPoolExecutor(4) as pool, open(out, 'a') as f:
        for k, r in enumerate(pool.map(job, sorted(need.items()))):
            f.write(json.dumps(r) + '\n')
            f.flush()
            if k % 50 == 0:
                print(k, flush=True)


def score(bid_file: str, solved_file: str, verbose: bool) -> None:
    data = json.load(open(bid_file))
    tricks = _solved(solved_file)
    n, rows = data['n'], data['rows']
    missing = sorted({r['deal'] for r in rows for c in (r['inc'], r['new'])
                      if c and (r['deal'], c['strain'], c['declarer']) not in tricks})
    if missing:                          # score the deals solved so far
        n = missing[0] - 1
        rows = [r for r in rows if r['deal'] <= n]
    print(f"deals 1-{n}, {4 * n} boards")

    def points(deal_id, c, side):
        if c is None:
            return 0
        t = tricks[(deal_id, c['strain'], c['declarer'])]
        return challenge.score_for(side, c, t if c['side'] == 'N/S' else 13 - t)

    for name in data['variants']:
        boards, examples = {}, []
        for r in rows:
            if r['var'] != name:
                continue
            d = points(r['deal'], r['new'], r['vs']) - points(r['deal'], r['inc'], r['vs'])
            key = (r['deal'], r['dealer'])
            boards[key] = boards.get(key, 0) + d / 2
            examples.append((d, r['deal'], r['dealer'], r['vs'], r['calls_inc'], r['calls_new']))
        values = list(boards.values()) + [0.0] * (4 * n - len(boards))
        mean = sum(values) / len(values)
        sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
        t = mean / (sd / math.sqrt(len(values))) if sd else 0.0
        better = sum(e[0] > 0 for e in examples)
        worse = sum(e[0] < 0 for e in examples)
        print(f"{name}: {mean:+.2f} per board, t = {t:+.2f}, "
              f"{len(examples)} auctions changed ({better} better, {worse} worse)")
        if verbose:
            examples.sort()
            for e in examples[:5] + examples[-5:]:
                print(f"    {e[0]:+6} deal {e[1]} dealer {e[2]} variant {e[3]}\n"
                      f"          was: {e[4]}\n          now: {e[5]}")


def main(argv: list[str]) -> None:
    base = {}
    if '--base' in argv:
        i = argv.index('--base')
        base = json.load(open(argv[i + 1]))
        del argv[i:i + 2]
    cmd = argv[0]
    if cmd == 'bid':
        variants = json.load(open(argv[2]))
        setup(variants, base)
        bid(int(argv[1]), variants, base, argv[3])
    elif cmd == 'solve':
        solve(argv[1], argv[2])
    elif cmd == 'score':
        score(argv[1], argv[2], '-v' in argv)


if __name__ == '__main__':
    main(sys.argv[1:])
