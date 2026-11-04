"""For each candidate gap (site, family): how often it comes up on fresh
deals (survey), what the alternatives gained on the solved deals (cost), and
what the experts did with the same hands where the robot passes from that
site (experts). Writes candidates.json and prints a table.

    python3.12 compare.py survey.jsonl cost.jsonl experts.jsonl
"""
from __future__ import annotations
import collections, json, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from analyse_cost import load, imps, stats, MIN_DEALS  # noqa: E402

VALUES = lambda r: r['hcp'] >= 10 or max(r['len'].values()) >= 6  # noqa: E731


def kind(call):
    if call == 'Pass':
        return 'Pass'
    if call in ('X', 'XX'):
        return call
    return 'NT' if call.endswith('NT') else 'suit'


def main(sp, cp, ep):
    boards = 0
    surv = collections.Counter()
    for line in open(sp):
        r = json.loads(line)
        boards += 4
        for x in r['passes']:
            if x['contested'] and VALUES(x):
                surv[(x['site'], x['family'])] += 1
    rows, cboards = load(cp)
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r['site'], r['family'])].append(r)
    exp = collections.defaultdict(list)
    for line in open(ep):
        r = json.loads(line)
        if r['robot'] == 'Pass' and VALUES(r):
            exp[(r['site'], r['family'])].append(r)
    out = []
    for key, xs in groups.items():
        for k in ('X', 'own', 'raise', 'nt'):
            by = collections.defaultdict(list)
            for x in xs:
                a = x['alts'].get(k)
                if a and a[1] is not None:
                    by[x['deal']].append(a[1])
            if len(by) < MIN_DEALS:
                continue
            pts = [v for a in by.values() for v in a]
            dm = [sum(a) / len(a) for a in by.values()]
            mean, t = sum(pts) / len(pts), stats(dm)[1]
            e = exp.get(key, [])
            ek = collections.Counter(kind(r['expert']) for r in e)
            freq = surv[key] / boards * 100
            out.append(dict(site=key[0], family=key[1], alt=k, deals=len(by), mean=mean, t=t,
                            imps=sum(map(imps, pts)) / len(pts),
                            per100=freq, per_board=mean * freq / 100,
                            experts=len(e), expert_act=(1 - ek['Pass'] / len(e)) if e else None,
                            expert_kinds=dict(ek)))
    out.sort(key=lambda r: -(r['per_board'] if r['t'] >= 2 else -1e9 + r['per_board']))
    json.dump(out, open('candidates.json', 'w'), indent=1)
    print(f"survey {boards} boards; cost {cboards} boards; t over deals")
    print(f"{'pts/bd':>7} {'/100bd':>6} {'mean':>5} {'t':>5} {'IMPs':>5} {'deals':>5} "
          f"{'exp n':>5} {'act':>4} alt   site | family")
    for r in out[:40]:
        act = f"{r['expert_act']:.2f}" if r['expert_act'] is not None else '  - '
        print(f"{r['per_board']:+7.2f} {r['per100']:6.2f} {r['mean']:+5.0f} {r['t']:+5.1f} "
              f"{r['imps']:+5.2f} {r['deals']:5} {r['experts']:5} {act} {r['alt']:5} "
              f"{r['site']} | {r['family']}  {r['expert_kinds']}")


if __name__ == '__main__':
    main(*sys.argv[1:4])
