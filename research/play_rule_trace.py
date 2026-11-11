"""Which play rule chose each robot card, and what the costly ones cost.

Replays every line of a presolved file (research/presolve_robot_lines.py, made
with the current code) and records, for each card, the rule in ai.py that
picked it: the last rule that returned a card different from the one it was
given. The solver's values then give the tricks each rule gives away a board,
gross, as robot_line_report.py counts them.

    python research/play_rule_trace.py <lines.jsonl> <out.json>

Nov 10 audit on main (199 deals): 5.09 tricks a board, 2.82 of them from rules
that read only their own hand and the cards played (_lead, _shed, _play_last).
"""
from __future__ import annotations

import inspect
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ai
import challenge
from card import Card
from research.robot_line_report import mistakes
from research.presolve_robot_lines import text

RULES = [
    '_partner_suit_lead', '_singleton_lead', '_fit_lead', '_draw_trump', '_entry_to_draw',
    '_ruff_lead', '_run_long_suit', '_ruff_return', '_sure_lead', '_nt_defence_suit',
    '_nt_long_lead', '_defender_suit_plan', '_lead', '_ruff_for_idle_trump',
    '_sure_lead_declarer', '_force_dummy', '_play_last', '_last_suit_plan', '_middle_play',
    '_third_sees_last', '_third_hand_plan', '_cover_for_partner', '_cover_unseen_partner',
    '_ruff_for_draw', '_located_suit_plan', '_endgame_totals',
]

state = {'depth': 0, 'log': None}


def wrap(name, fn):
    sig = inspect.signature(fn)

    def inner(*args, **kwargs):
        top = state['log'] is not None and state['depth'] == 0
        state['depth'] += 1
        try:
            result = fn(*args, **kwargs)
        finally:
            state['depth'] -= 1
        if top:
            bound = sig.bind_partial(*args, **kwargs)
            has_choice = 'choice' in bound.arguments
            state['log'].append((name, result, bound.arguments.get('choice'), has_choice))
        return result
    return inner


for name in RULES:
    setattr(ai, name, wrap(name, getattr(ai, name)))

real_play = ai.ai_play
traces: list = []


def traced_play(*args, **kwargs):
    state['log'] = []
    try:
        card = real_play(*args, **kwargs)
    finally:
        log, state['log'] = state['log'], None
    rule = None
    current = None
    idle = False
    for name, result, choice_in, has_choice in log:
        if name == '_ruff_for_idle_trump':
            idle = result is not None
            continue
        if name == '_endgame_totals':
            if result and current != card:
                rule = 'endgame search (5 cards)'
                current = card
            continue
        if isinstance(result, Card) and (not has_choice or result != choice_in):
            rule, current = name, result
            if name == '_lead' and idle:
                rule = '_ruff_for_idle_trump'
    if current != card:
        rule = (rule or '?') + '+inline'
    traces.append(rule)
    return card


challenge.ai_play = traced_play


def main(path, out):
    by_rule = defaultdict(lambda: {'cards': 0, 'costly': 0, 'lost': 0.0,
                                   'by_side': defaultdict(float)})
    deals = set()
    total = 0.0
    for line in open(path):
        rec = json.loads(line)
        deals.add(rec['deal_id'])
        b = rec['boards'][0]
        traces.clear()
        table = challenge.robot_table(rec['deal_id'], b['dealer'], b['vulnerability'])
        plays = [text(c) for t in table['tricks_log'] for _, c in t['plays']]
        assert plays == rec['plays'], rec['key']
        weight = len(rec['boards']) / 16
        total += weight
        for m in mistakes(rec):
            rule = traces[m['k']]
            if m['k'] == 0:
                rule = 'opening lead: ' + rule
            elif m['action'] in ('discard', 'ruff'):
                rule = rule + ' [' + m['action'] + ']'
            r = by_rule[rule]
            r['cards'] += weight
            if m['lost']:
                r['costly'] += weight
                r['lost'] += weight * m['lost']
                key = 'opening lead' if m['k'] == 0 else m['side']
                r['by_side'][key] += weight * m['lost']
    n = total
    rows = []
    for rule, r in by_rule.items():
        rows.append({'rule': rule, 'cards_per_board': r['cards'] / n,
                     'costly_per_board': r['costly'] / n, 'lost_per_board': r['lost'] / n,
                     'lost_by_side': {k: v / n for k, v in r['by_side'].items()}})
    rows.sort(key=lambda x: -x['lost_per_board'])
    json.dump({'deals': n, 'rows': rows}, open(out, 'w'), indent=1)
    print(f'{len(deals)} deals, {n:.1f} board-weight')
    print(f"{'rule':40s} {'cards/bd':>8s} {'costly':>7s} {'lost':>6s}  by side")
    for x in rows:
        sides = ', '.join(f'{k} {v:.2f}' for k, v in sorted(x['lost_by_side'].items()))
        print(f"{x['rule']:40s} {x['cards_per_board']:8.2f} {x['costly_per_board']:7.2f} "
              f"{x['lost_per_board']:6.2f}  {sides}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
