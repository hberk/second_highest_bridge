"""Searches for a better hand evaluator than the five-term point count.

Why this exists: at 300 deals the bidding *policy* is exhausted -- the AI already
bids the level a perfect partner model would justify (mean 1.90 against 1.87) --
and the constants are interchangeable (a full refit scores t = -0.25 against the
shipped set). What is left is the evaluation's MAE of ~1.14 tricks. Simulating an
evaluator with error sigma and bidding level = round(estimate) - 6 gives +158 per
board at sigma 0 against ~+68 at today's accuracy, so accuracy is worth an order
of magnitude more than any rule change. That makes MODEL FORM the binding
constraint, and 2978 solved declarer-positions are already enough to search it.

THE HARD CONSTRAINT: every feature must be **additive per hand**. A bidder sees
thirteen cards and has to be able to compute their own contribution, with partner
adding theirs, or the number cannot be used in an auction at all. So combined-hand
features like "the partnership's longest suit" are inadmissible however well they
fit; only per-hand counts that sum are allowed.

Run: python research/evaluator_search.py
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
SEATS_OF = {'N/S': ('North', 'South'), 'E/W': ('East', 'West')}

KQ = {'K', 'Q'}
A109 = {'A', '10', '9'}
MID = {'J', '8', '7', '6', '5'}
LOW = {'4', '3', '2'}


def hand_features(text: str, trump: str) -> dict:
    """Per-hand, additive. Everything here is a count this player can make from
    their own thirteen cards once a trump suit is named."""
    by_suit = defaultdict(list)
    for token in text.split():
        by_suit[token[-1]].append(token[:-1])

    f = defaultdict(float)
    f['trump_len'] = len(by_suit.get(trump, ()))

    for suit, ranks in by_suit.items():
        in_trump = (suit == trump)
        for r in ranks:
            if r in KQ:
                f['kq_trump' if in_trump else 'kq_side'] += 1
            elif r in A109:
                f['a109_trump' if in_trump else 'a109_side'] += 1
            elif r in MID:
                f['mid'] += 1
            else:
                f['low'] += 1

    # Ruffing potential lives in the SIDE suits: a void or singleton outside
    # trumps is what lets a trump be used separately from drawing them.
    for suit in 'SHDC':
        if suit == trump:
            continue
        n = len(by_suit.get(suit, ()))
        if n == 0:
            f['void_side'] += 1
        elif n == 1:
            f['singleton_side'] += 1
        elif n == 2:
            f['doubleton_side'] += 1

    # Length outside trumps that might set up, as a per-hand count.
    side_lengths = [len(by_suit.get(s, ())) for s in 'SHDC' if s != trump]
    f['long_side'] = max(side_lengths) if side_lengths else 0
    # Trump honours that are specifically the SECOND rank of the suit are the
    # ones that win a contested trump trick under this variant's rule.
    return f


def load_rows():
    rows = []
    for line in DATA.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec['strain'] == 'NT':
            continue
        why = rec['why'] if isinstance(rec['why'], list) else [rec['why']]
        for res in rec['results']:
            side = res['declaring_side']
            total = defaultdict(float)
            for seat in SEATS_OF[side]:
                for k, v in hand_features(rec['hands'][seat], rec['strain']).items():
                    total[k] += v
            rows.append({
                'f': total, 'y': res['declarer_tricks'], 'deal': rec['deal_id'],
                'is_best': f"{side} best fit" in why,
            })
    return rows


MODELS = {
    'current (shipped)': ['trump_len', 'kq', 'a109', 'mid', 'low'],
    '+ split honours by trump': ['trump_len', 'kq_trump', 'kq_side',
                                 'a109_trump', 'a109_side', 'mid', 'low'],
    '+ shortness': ['trump_len', 'kq', 'a109', 'mid', 'low',
                    'void_side', 'singleton_side'],
    '+ shortness + doubleton': ['trump_len', 'kq', 'a109', 'mid', 'low',
                                'void_side', 'singleton_side', 'doubleton_side'],
    '+ long side suit': ['trump_len', 'kq', 'a109', 'mid', 'low', 'long_side'],
    'everything': ['trump_len', 'kq_trump', 'kq_side', 'a109_trump', 'a109_side',
                   'mid', 'low', 'void_side', 'singleton_side', 'doubleton_side',
                   'long_side'],
}


def design(rows, names):
    cols = []
    for r in rows:
        f = r['f']
        row = []
        for n in names:
            if n == 'kq':
                row.append(f['kq_trump'] + f['kq_side'])
            elif n == 'a109':
                row.append(f['a109_trump'] + f['a109_side'])
            else:
                row.append(f[n])
        cols.append(row)
    return np.array(cols, float)


def grouped_cv(X, y, deals, folds=5):
    uniq = np.unique(deals)
    rng = np.random.default_rng(0)
    rng.shuffle(uniq)
    oos = np.zeros_like(y)
    for fold in np.array_split(uniq, folds):
        test = np.isin(deals, fold)
        beta, *_ = np.linalg.lstsq(X[~test], y[~test], rcond=None)
        oos[test] = X[test] @ beta
    r2 = 1 - ((y - oos) @ (y - oos)) / ((y - y.mean()) ** 2).sum()
    return r2, np.abs(y - oos).mean()


def main():
    rows = load_rows()
    y = np.array([r['y'] for r in rows], float)
    deals = np.array([r['deal'] for r in rows])
    best_mask = np.array([r['is_best'] for r in rows])
    print(f"{len(rows)} suit-contract declarer-solves from "
          f"{len(set(deals))} deals ({best_mask.sum()} are the side's own best fit)\n")

    print("=" * 78)
    print("MODEL SEARCH  (5-fold cross-validation, grouped by deal)")
    print("=" * 78)
    print(f"  {'model':<28}{'k':>3}{'OOS R2':>9}{'OOS MAE':>10}{'MAE on best fits':>19}")
    results = {}
    for label, names in MODELS.items():
        X = design(rows, names)
        r2, mae = grouped_cv(X, y, deals)
        # accuracy specifically on the contracts the AI actually bids
        uniq = np.unique(deals)
        rng = np.random.default_rng(0)
        rng.shuffle(uniq)
        oos = np.zeros_like(y)
        for fold in np.array_split(uniq, 5):
            test = np.isin(deals, fold)
            beta, *_ = np.linalg.lstsq(X[~test], y[~test], rcond=None)
            oos[test] = X[test] @ beta
        mae_best = np.abs(y[best_mask] - oos[best_mask]).mean()
        results[label] = (r2, mae, mae_best, names)
        print(f"  {label:<28}{len(names):>3}{r2:>9.3f}{mae:>10.3f}{mae_best:>19.3f}")

    base = results['current (shipped)']
    print(f"\n  baseline MAE {base[1]:.3f} overall, {base[2]:.3f} on best fits")
    winner = min(results.items(), key=lambda kv: kv[1][1])
    print(f"  best by OOS MAE: '{winner[0]}' at {winner[1][1]:.3f} "
          f"({base[1] - winner[1][1]:+.3f} against baseline)")

    print("\n" + "=" * 78)
    print(f"COEFFICIENTS of '{winner[0]}' (full-sample fit)")
    print("=" * 78)
    X = design(rows, winner[1][3])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = len(y) - X.shape[1]
    se = np.sqrt(np.diag(np.linalg.pinv(X.T @ X)) * (resid @ resid / dof))
    for n, b, s in zip(winner[1][3], beta, se):
        t = b / s if s else 0.0
        print(f"    {n:<18}{b:+8.3f}  (se {s:.3f}, t {t:+6.2f})"
              f"{'  *' if abs(t) > 2 else ''}")

    print("\n  Reference: an evaluator's MAE maps to score roughly as")
    print("    MAE 1.14 -> ~+68/board,  0.91 -> +80,  0.60 -> +101,  0.00 -> +158")
    print("  so a tenth of a trick of accuracy is worth real points, and far more")
    print("  than any bidding-rule change measured so far (all within +/-5, none significant).")


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
