"""Fits hand evaluation and bidding policy to the double dummy dataset.

This is the analysis that replaces `ai.py`'s hand evaluation with something
measured. It reads `research/data/dd_pilot.jsonl` and answers, in order:

  1. Do the *existing* evaluators predict anything? (`eval_hand_sh`, standard HCP)
  2. What is each rank actually worth, in tricks?
  3. A fitted point count, cross-validated out-of-sample.
  4. Is notrump ever the right strain?
  5. Which bidding policy maximises *score*, not tricks?
  6. What does the current `ai_bid` actually score over the same deals?

Nothing here assumes an answer; every number is fit from solved results. The
conclusions are recorded in docs/BIDDING.md under "Hand evaluation and bidding research" so
they survive without re-running this, but re-running is cheap (a few seconds)
and is the right move whenever the dataset grows.

CAVEATS, which matter when reading any number below:
  - 600 declarer-solves come from only 100 deals (6 correlated rows per deal),
    so reported standard errors are optimistic. Effective n is nearer 100.
    The grouped cross-validation in section 3 is the honest generalisation check.
  - The dataset solves only three strains per deal (each side's best fit, plus
    notrump). Arbitrary contracts cannot be scored, so competitive auctions
    cannot be simulated here.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / 'research' / 'data' / 'dd_pilot.jsonl'

RANKS = ['A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2']
POS = {r: i for i, r in enumerate(RANKS)}
HCP_VALUES = {'A': 4, 'K': 3, 'Q': 2, 'J': 1}
SEATS_OF = {'N/S': ('North', 'South'), 'E/W': ('East', 'West')}

#: The card groups the reduced point count uses. Chosen from the full 13-rank
#: fit in section 2: K/Q separate from A/10/9 because the ace behaves like a
#: ten here, not like an honour.
GROUPS = {
    'KQ': {'K', 'Q'},
    'A109': {'A', '10', '9'},
    'mid': {'J', '8', '7', '6', '5'},
    'low': {'4', '3', '2'},
}


# ── Loading ──────────────────────────────────────────────────────────────────

def load_records():
    if not DATA.exists():
        raise SystemExit(f"no dataset at {DATA}\n"
                         f"generate one with: python research/dd_dataset.py --deals 100 --engine rust")
    return [json.loads(line) for line in DATA.read_text(encoding='utf-8').splitlines()
            if line.strip()]


def side_features(hands, seats, strain):
    """Card-count features for a set of seats. Additive: each seat's own counts
    sum to the partnership's, which is what makes this usable as a point count."""
    rank_counts = np.zeros(13)
    groups = dict.fromkeys(GROUPS, 0)
    lengths = defaultdict(int)
    for seat in seats:
        for token in hands[seat].split():
            rank, suit = token[:-1], token[-1]
            rank_counts[POS[rank]] += 1
            lengths[suit] += 1
            for name, members in GROUPS.items():
                if rank in members:
                    groups[name] += 1
    trump_len = 0 if strain == 'NT' else lengths.get(strain, 0)
    return rank_counts, groups, lengths, trump_len


def load_rows(records):
    """One row per declarer-solve (two per record: each side declaring)."""
    rows = []
    for rec in records:
        for res in rec['results']:
            side = res['declaring_side']
            rc, groups, lengths, trump_len = side_features(
                rec['hands'], SEATS_OF[side], rec['strain'])
            own_rc, own_groups, _, own_trump = side_features(
                rec['hands'], (res['declarer'],), rec['strain'])
            rows.append({
                'deal': rec['deal_id'], 'strain': rec['strain'], 'side': side,
                'tricks': res['declarer_tricks'],
                'rank_counts': rc, 'groups': groups, 'lengths': dict(lengths),
                'trump_len': trump_len, 'best_fit': max(lengths.values()),
                'own_groups': own_groups, 'own_trump': own_trump,
            })
    return rows


def best_fit_cases(records):
    """One case per (deal, side) where that side's own longest fit was solved,
    carrying both its suit result and its notrump result. This is the unit the
    strain and level questions are asked in."""
    by_deal = defaultdict(dict)
    hands_of = {}
    for rec in records:
        by_deal[rec['deal_id']][rec['strain']] = rec
        hands_of[rec['deal_id']] = rec['hands']

    cases = []
    for deal_id, strains in by_deal.items():
        if 'NT' not in strains:
            continue
        for side in ('N/S', 'E/W'):
            _, groups, lengths, _ = side_features(hands_of[deal_id], SEATS_OF[side], 'NT')
            best = max(sorted(lengths), key=lambda s: (lengths[s], 'CDHS'.index(s)))
            if best not in strains:
                continue
            suit_t = [x for x in strains[best]['results']
                      if x['declaring_side'] == side][0]['declarer_tricks']
            nt_t = [x for x in strains['NT']['results']
                    if x['declaring_side'] == side][0]['declarer_tricks']
            cases.append({
                'deal': deal_id, 'side': side, 'suit': best, 'fit': lengths[best],
                'suit_tricks': suit_t, 'nt_tricks': nt_t, 'groups': groups,
                'is_major': best in 'HS',
            })
    return cases


# ── Fitting ──────────────────────────────────────────────────────────────────

def ols(X, y):
    """Least squares with standard errors and t-stats. No scipy dependency."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    sigma2 = resid @ resid / max(n - k, 1)
    se = np.sqrt(np.diag(np.linalg.pinv(X.T @ X)) * sigma2)
    with np.errstate(divide='ignore', invalid='ignore'):
        t = beta / np.where(se == 0, np.nan, se)
    r2 = 1 - (resid @ resid) / ((y - y.mean()) ** 2).sum()
    return beta, se, t, r2, np.abs(resid).mean()


def point_count_matrix(rows):
    X = np.array([[r['trump_len']] + [r['groups'][g] for g in GROUPS] for r in rows], float)
    y = np.array([r['tricks'] for r in rows], float)
    return X, y, ['trump_len'] + list(GROUPS)


def predict_tricks(fit, groups, trump_len):
    """Expected tricks from the fitted point count."""
    return (fit['trump_len'] * trump_len
            + sum(fit[g] * groups[g] for g in GROUPS))


# ── Report sections ──────────────────────────────────────────────────────────

def section_incumbent(rows, records):
    print("=" * 70)
    print("1. DO THE EXISTING EVALUATORS PREDICT ANYTHING?")
    print("=" * 70)
    y = np.array([r['tricks'] for r in rows], float)
    hcp = np.array([sum(HCP_VALUES.get(RANKS[i], 0) * c
                        for i, c in enumerate(r['rank_counts'])) for r in rows], float)
    print(f"  standard HCP     r = {np.corrcoef(hcp, y)[0, 1]:+.3f}   "
          f"R2 = {np.corrcoef(hcp, y)[0, 1] ** 2:.3f}")
    try:
        from ai import eval_hand_sh
        from research import dd_dataset as ds
        cache, ev = {}, []
        for rec in records:
            if rec['deal_id'] not in cache:
                cache[rec['deal_id']] = ds.deal_for(rec['deal_id'])
            hands = cache[rec['deal_id']]
            for res in rec['results']:
                ev.append(sum(eval_hand_sh(hands[s])['total_pts']
                              for s in SEATS_OF[res['declaring_side']]))
        ev = np.array(ev, float)
        r = np.corrcoef(ev, y)[0, 1]
        print(f"  ai.eval_hand_sh  r = {r:+.3f}   R2 = {r ** 2:.3f}   <-- no signal")
        nt_only = np.array([row['strain'] == 'NT' for row in rows])
        r_nt = np.corrcoef(ev[nt_only], y[nt_only])[0, 1]
        print(f"                   r = {r_nt:+.3f} in notrump alone (actively negative)")
    except Exception as exc:                                  # pragma: no cover
        print(f"  (eval_hand_sh check skipped: {exc})")
    fit_len = np.array([r['trump_len'] if r['strain'] != 'NT' else r['best_fit']
                        for r in rows], float)
    suit = np.array([r['strain'] != 'NT' for r in rows])
    r = np.corrcoef(fit_len[suit], y[suit])[0, 1]
    print(f"  fit length (suit contracts only)  r = {r:+.3f}   R2 = {r ** 2:.3f}")


def section_rank_values(rows):
    print("\n" + "=" * 70)
    print("2. WHAT IS EACH RANK WORTH? (suit contracts, tricks per card)")
    print("=" * 70)
    suit = [r for r in rows if r['strain'] != 'NT']
    y = np.array([r['tricks'] for r in suit], float)
    RC = np.array([r['rank_counts'] for r in suit])
    X = np.hstack([np.ones((len(suit), 1)), RC[:, :12],
                   np.array([[r['trump_len']] for r in suit], float)])
    names = ['intercept'] + RANKS[:12] + ['trump_len']
    beta, se, t, r2, mae = ols(X, y)
    print(f"  R2 = {r2:.3f}   MAE = {mae:.2f} tricks   n = {len(y)}")
    print("  (coefficient = tricks gained by upgrading one '2' into that rank)")
    for nm, b, s, tt in zip(names, beta, se, t):
        flag = '  *' if abs(tt) > 2 else ''
        print(f"    {nm:<12}{b:+7.3f}  (se {s:.3f}, t {tt:+6.2f}){flag}")
    ace, ten = beta[names.index('A')], beta[names.index('10')]
    print(f"  NOTE: the ace is worth {ace:+.3f} against the ten's {ten:+.3f}. It cannot win a")
    print("        contested trick, so it sits with the tens rather than the honours -- but")
    print("        do NOT hard-code a significance claim here. The ace's estimate has")
    print("        wandered with sample size: +0.186 (t=1.69) at 100 deals, +0.221 (t=3.51)")
    print("        at 153, +0.097 (t=2.47) at 300. Read the t column above, not this text.")


def section_point_count(rows):
    print("\n" + "=" * 70)
    print("3. THE POINT COUNT, CROSS-VALIDATED")
    print("=" * 70)
    suit = [r for r in rows if r['strain'] != 'NT']
    X, y, names = point_count_matrix(suit)
    deals = np.array([r['deal'] for r in suit])

    beta, _, _, r2, mae = ols(X, y)
    uniq = np.unique(deals)
    rng = np.random.default_rng(0)
    rng.shuffle(uniq)
    oos = np.zeros_like(y)
    for fold in np.array_split(uniq, 5):
        test = np.isin(deals, fold)
        b, *_ = np.linalg.lstsq(X[~test], y[~test], rcond=None)
        oos[test] = X[test] @ b
    r2_oos = 1 - ((y - oos) @ (y - oos)) / ((y - y.mean()) ** 2).sum()

    print(f"  in-sample      R2 = {r2:.3f}   MAE = {mae:.2f} tricks")
    print(f"  out-of-sample  R2 = {r2_oos:.3f}   MAE = {np.abs(y - oos).mean():.2f} tricks"
          f"   (5-fold, grouped by deal)")
    print("\n  Second-Highest Points (per card; additive, so each player counts their own):")
    for nm, b in zip(names, beta):
        print(f"    {nm:<12}{b:+7.3f} tricks   ({b * 10:+5.1f} on a x10 scale)")

    XO = np.array([[r['own_trump']] + [r['own_groups'][g] for g in GROUPS]
                   for r in suit], float)
    _, _, _, r2_own, mae_own = ols(XO, y)
    print(f"\n  one hand alone explains R2 = {r2_own:.3f} of the pair's tricks "
          f"(MAE {mae_own:.2f});")
    print(f"  the full 26 cards explain {r2:.3f}. Closing that gap is the auction's job.")
    return dict(zip(names, beta))


def section_notrump(cases, rows):
    print("\n" + "=" * 70)
    print("4. IS NOTRUMP EVER RIGHT?")
    print("=" * 70)
    suit = np.array([c['suit_tricks'] for c in cases], float)
    nt = np.array([c['nt_tricks'] for c in cases], float)
    print(f"  n = {len(cases)} (deal, side) pairs, each compared against ITS OWN best fit")
    print(f"    mean tricks in the suit fit : {suit.mean():.2f}")
    print(f"    mean tricks in notrump      : {nt.mean():.2f}")
    print(f"    mean difference             : {(suit - nt).mean():+.2f} in favour of the suit")
    print(f"    suit better {(suit > nt).sum():>4} ({(suit > nt).mean() * 100:.0f}%)"
          f"   tied {(suit == nt).sum():>3} ({(suit == nt).mean() * 100:.0f}%)"
          f"   notrump better {(nt > suit).sum():>3} ({(nt > suit).mean() * 100:.0f}%)")
    print("  The gap WIDENS with a longer fit:")
    for lo, hi in ((7, 7), (8, 8), (9, 13)):
        m = np.array([lo <= c['fit'] <= hi for c in cases])
        if m.sum() >= 5:
            print(f"    fit {lo}-{hi}: n={m.sum():>3}  suit {suit[m].mean():5.2f}   "
                  f"NT {nt[m].mean():5.2f}   diff {(suit - nt)[m].mean():+5.2f}")
    nt_rows = [r for r in rows if r['strain'] == 'NT']
    yn = np.array([r['tricks'] for r in nt_rows], float)
    RC = np.array([r['rank_counts'] for r in nt_rows])
    X = np.hstack([np.ones((len(nt_rows), 1)), RC[:, :12],
                   np.array([[r['best_fit']] for r in nt_rows], float)])
    *_, r2_nt, _ = ols(X, yn)
    q = np.corrcoef(RC[:, POS['Q']], yn)[0, 1]
    print(f"  Notrump is not merely bad, it is near-unpredictable: R2 = {r2_nt:.3f}")
    print(f"  from all 13 rank counts + fit length. Best single correlate is the")
    print(f"  queen count at r = {q:+.3f}. Don't try to evaluate NT better - stop bidding it.")


def section_policies(cases, fit):
    print("\n" + "=" * 70)
    print("5. WHICH BIDDING POLICY MAXIMISES SCORE?")
    print("=" * 70)
    try:
        from bridge.scoring import score_contract
    except Exception as exc:                                  # pragma: no cover
        print(f"  (skipped: {exc})")
        return

    def value(side, strain, level, tricks, vul='None'):
        contract = {'side': side, 'vulnerability': vul, 'tricks_needed': level + 6,
                    'level': level, 'strain': strain, 'doubled': 'None'}
        other = 'E/W' if side == 'N/S' else 'N/S'
        res = score_contract(contract, {side: tricks, other: 13 - tricks})
        return res['points'] if res['winner'] == side else -res['points']

    def run(choose, label):
        scores, made = [], []
        for c in cases:
            strain, level = choose(c)
            tricks = c['nt_tricks'] if strain == 'NT' else c['suit_tricks']
            scores.append(value(c['side'], strain, level, tricks))
            made.append(tricks >= level + 6)
        print(f"    {label:<44} {np.mean(scores):+7.1f}   made {np.mean(made) * 100:3.0f}%")

    print("  mean score per board, not vulnerable:")
    run(lambda c: ('NT', 3), "always 3NT")
    run(lambda c: (c['suit'], 2), "always 2 of our best fit")
    run(lambda c: (c['suit'], 3), "always 3 of our best fit")
    run(lambda c: (c['suit'], int(np.clip(c['fit'] - 6, 1, 3))), "level = fit - 6 (cap 3)")
    run(lambda c: (c['suit'], 4 if (c['is_major'] and
                                    predict_tricks(fit, c['groups'], c['fit']) >= 9.5)
                   else 2), "2 of our fit, 4M when count >= 9.5")
    run(lambda c: (c['suit'], max(c['suit_tricks'] - 6, 1)), "ORACLE: bid exactly what makes")
    print("\n  Undoubled overtricks score the same as contracted tricks, so")
    print("  underbidding is nearly free and the only prize for bidding higher")
    print("  is the game bonus. Game is rare:")
    maj = [c for c in cases if c['is_major']]
    mnr = [c for c in cases if not c['is_major']]
    print(f"    4-major makeable {np.mean([c['suit_tricks'] >= 10 for c in maj]) * 100:4.0f}%"
          f"   5-minor {np.mean([c['suit_tricks'] >= 11 for c in mnr]) * 100:4.0f}%"
          f"   3NT {np.mean([c['nt_tricks'] >= 9 for c in cases]) * 100:4.0f}%")
    print("\n  Flat level policies, showing why underbidding wins:")
    for lvl in range(1, 5):
        s = np.mean([value(c['side'], c['suit'], lvl, c['suit_tricks']) for c in cases])
        note = "  (not actually available - see section 7)" if lvl == 1 else ""
        print(f"    always {lvl}-level: {s:+7.1f}{note}")
    print("\n  Game trigger, majors only (4M needs 10 tricks):")
    for thresh in (9.0, 9.5, 10.0):
        sub_cases = [c for c in cases if c['is_major']
                     and predict_tricks(fit, c['groups'], c['fit']) >= thresh]
        if len(sub_cases) < 3:
            continue
        g = np.mean([value(c['side'], c['suit'], 4, c['suit_tricks']) for c in sub_cases])
        two = np.mean([value(c['side'], c['suit'], 2, c['suit_tricks']) for c in sub_cases])
        print(f"    count >= {thresh}: n={len(sub_cases):>3}   bid 4M {g:+7.1f}   "
              f"bid 2M {two:+7.1f}   {'GAME WINS' if g > two else 'partscore wins'}")


def section_current_ai(records):
    print("\n" + "=" * 70)
    print("6. WHAT DOES THE CURRENT ai_bid ACTUALLY SCORE?")
    print("=" * 70)
    try:
        from collections import Counter
        from game import AuctionState
        from ai import ai_bid
        from bridge.scoring import score_contract
        from research import dd_dataset as ds
    except Exception as exc:                                  # pragma: no cover
        print(f"  (skipped: {exc})")
        return

    players = ['North', 'East', 'South', 'West']
    solved = defaultdict(dict)
    for rec in records:
        solved[rec['deal_id']][rec['strain']] = rec

    contracts, passed = [], 0
    for deal_id in sorted(solved):
        hands = ds.deal_for(deal_id)
        auction = AuctionState(dealer=players[deal_id % 4], vulnerability='None')
        guard = 0
        while not auction.is_complete and guard < 40:
            who = auction.current_player()
            auction.apply_call(who, ai_bid(who, hands[who], auction))
            guard += 1
        contract = auction.get_contract()
        if contract is None:
            passed += 1
        else:
            contracts.append((deal_id, contract))

    strains = Counter(c['strain'] for _, c in contracts)
    high = sum(1 for _, c in contracts if c['level'] >= 3)
    print(f"  {len(contracts)} contracts reached, {passed} passed out")
    print("  strain: " + "  ".join(f"{k}:{v / len(contracts) * 100:.0f}%"
                                   for k, v in strains.most_common()))
    print(f"  at the 3-level or higher: {high / len(contracts) * 100:.0f}%")

    in_fit = 0
    for deal_id, contract in contracts:
        if contract['strain'] == 'NT':
            continue
        any_record = next(iter(solved[deal_id].values()))
        _, _, lengths, _ = side_features(
            any_record['hands'], SEATS_OF[contract['side']], 'NT')
        if lengths.get(contract['strain'], 0) == max(lengths.values()):
            in_fit += 1
    print(f"  played in the side's own longest fit: {in_fit}/{len(contracts)}"
          f" = {in_fit / len(contracts) * 100:.0f}%")

    scores = []
    for deal_id, contract in contracts:
        strain, side = contract['strain'], contract['side']
        if strain not in solved[deal_id]:
            continue
        match = [x for x in solved[deal_id][strain]['results']
                 if x['declaring_side'] == side]
        if not match:
            continue
        tricks = match[0]['declarer_tricks']
        other = 'E/W' if side == 'N/S' else 'N/S'
        res = score_contract(contract, {side: tricks, other: 13 - tricks})
        scores.append(res['points'] if res['winner'] == side else -res['points'])
    if scores:
        print(f"  scorable: {len(scores)}   mean score {np.mean(scores):+.1f} per board"
              f"   made {np.mean(np.array(scores) > 0) * 100:.0f}%")


def section_fit_finding(records):
    print("\n" + "=" * 70)
    print("7. FIT-FINDING AND COMPETITION")
    print("=" * 70)
    by_deal = defaultdict(dict)
    hands_of = {}
    for rec in records:
        by_deal[rec['deal_id']][rec['strain']] = rec
        hands_of[rec['deal_id']] = rec['hands']

    found_longest = found_four = total = 0
    for hands in hands_of.values():
        for side in ('N/S', 'E/W'):
            seat1, seat2 = SEATS_OF[side]
            _, _, l1, _ = side_features(hands, (seat1,), 'NT')
            _, _, l2, _ = side_features(hands, (seat2,), 'NT')
            comb = {s: l1.get(s, 0) + l2.get(s, 0) for s in 'SHDC'}
            true_best = max(comb.values())
            long1 = max(sorted(l1), key=lambda s: (l1[s], 'CDHS'.index(s)))
            long2 = max(sorted(l2), key=lambda s: (l2[s], 'CDHS'.index(s)))
            total += 1
            if comb[max({long1, long2}, key=lambda s: comb[s])] == true_best:
                found_longest += 1
            four = {s for s in 'SHDC' if l1.get(s, 0) >= 4 or l2.get(s, 0) >= 4}
            if four and comb[max(four, key=lambda s: comb[s])] == true_best:
                found_four += 1
    print(f"  partner shows only their longest suit -> true best fit found "
          f"{found_longest}/{total} = {found_longest / total * 100:.0f}%")
    print(f"  partner shows every 4+ suit           -> "
          f"{found_four}/{total} = {found_four / total * 100:.0f}%")
    print("  Fit-finding is NOT the hard part; not overriding it with notrump is.")

    sums, both_seven, n = [], 0, 0
    for deal_id, strains in by_deal.items():
        tricks = {}
        for side in ('N/S', 'E/W'):
            _, _, lengths, _ = side_features(hands_of[deal_id], SEATS_OF[side], 'NT')
            best = max(sorted(lengths), key=lambda s: (lengths[s], 'CDHS'.index(s)))
            if best not in strains:
                tricks = None
                break
            tricks[side] = [x for x in strains[best]['results']
                            if x['declaring_side'] == side][0]['declarer_tricks']
        if not tricks:
            continue
        n += 1
        sums.append(tricks['N/S'] + tricks['E/W'])
        if tricks['N/S'] >= 7 and tricks['E/W'] >= 7:
            both_seven += 1
    if n:
        print(f"\n  both sides' tricks in their OWN best fits sum to {np.mean(sums):.2f} "
              f"on average (n={n});")
        print(f"  13 would mean perfectly divided. Both sides can take 7+ in "
              f"{both_seven / n * 100:.0f}% of deals,")
        print("  so the 1-level is not actually available - the realistic floor is 2.")


def main():
    records = load_records()
    rows = load_rows(records)
    cases = best_fit_cases(records)
    print(f"{len(records)} records, {len({r['deal_id'] for r in records})} deals, "
          f"{len(rows)} declarer-solves, {len(cases)} best-fit cases\n")
    section_incumbent(rows, records)
    section_rank_values(rows)
    fit = section_point_count(rows)
    section_notrump(cases, rows)
    section_policies(cases, fit)
    section_current_ai(records)
    section_fit_finding(records)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
