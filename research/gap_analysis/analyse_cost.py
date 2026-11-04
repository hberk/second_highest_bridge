"""Rank the costed passes: for each (site, family) group and each natural
alternative, the mean gain over the pass in points and IMPs, with a t value over deals (each deal counts once; at least MIN_DEALS deals).

    python3.12 analyse_cost.py cost.jsonl [min_n]
"""
from __future__ import annotations
import collections, json, math, sys

MIN_DEALS = 8
IMP = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750, 900, 1100,
       1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000]


def imps(d):
    s = 1 if d >= 0 else -1
    return s * sum(1 for t in IMP if abs(d) >= t)


def stats(xs):
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0
    return m, (m / (sd / math.sqrt(n)) if sd else 0.0)


def load(path):
    rows, boards = [], 0
    for line in open(path):
        r = json.loads(line)
        if 'job' in r:
            boards += 1
        else:
            rows.append(r)
    return rows, boards


def groups(rows, key):
    g = collections.defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    return g


def table(rows, boards, key, min_n, label):
    out = []
    for k, xs in groups(rows, key).items():
        if len(xs) < min_n:
            continue
        for kind in ('X', 'own', 'raise', 'nt'):
            v = [x['alts'][kind] for x in xs if kind in x['alts'] and x['alts'][kind][1] is not None]
            if len(v) < min_n:
                continue
            pts = [a[1] for a in v]
            # A deal is bid 16 times, so one hand repeats: the t values are
            # over deals (each deal's mean), not over boards.
            by_deal = collections.defaultdict(list)
            for x in xs:
                if kind in x['alts'] and x['alts'][kind][1] is not None:
                    by_deal[x['deal']].append(x['alts'][kind][1])
            if len(by_deal) < MIN_DEALS:
                continue
            dp = [sum(a) / len(a) for a in by_deal.values()]
            di = [sum(map(imps, a)) / len(a) for a in by_deal.values()]
            mp, tp = sum(pts) / len(pts), stats(dp)[1]
            mi, ti = sum(map(imps, pts)) / len(pts), stats(di)[1]
            out.append(dict(key=k, kind=kind, n=len(v), deals=len(by_deal), of=len(xs), pts=mp, t=tp, imps=mi, ti=ti,
                            per_board=sum(pts) / boards, better=sum(p > 0 for p in pts),
                            worse=sum(p < 0 for p in pts)))
    out.sort(key=lambda r: -r['per_board'])
    print(f"\n== {label}: groups with n >= {min_n}, best first by points per board "
          f"(all {boards} boards)")
    print(f"{'pts/bd':>7} {'mean':>6} {'t':>5} {'IMPs':>5} {'tI':>5} {'n':>4}/{'of':<4} "
          f"{'b':>3}/{'w':<3} {'deals':>5} alt   group")
    for r in out[:45]:
        print(f"{r['per_board']:+7.2f} {r['pts']:+6.0f} {r['t']:+5.1f} {r['imps']:+5.2f} "
              f"{r['ti']:+5.1f} {r['n']:4}/{r['of']:<4} {r['better']:3}/{r['worse']:<3} {r['deals']:5} "
              f"{r['kind']:5} {r['key']}")
    return out


if __name__ == '__main__':
    rows, boards = load(sys.argv[1])
    min_n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    print(f"{len(rows)} costed passes on {boards} boards")
    table(rows, boards, lambda r: r['site'], min_n, 'by site')
    table(rows, boards, lambda r: (r['site'], r['family']), min_n, 'by site and family')
    table(rows, boards, lambda r: r['family'], min_n, 'by family')
