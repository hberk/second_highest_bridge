"""The table count: one seat's knowledge of the table, derived in one place.

`ai.TableCount` is built once per card by `ai_play` and read by every play
rule. These tests keep it the one place: no play rule rebuilds "what I have
seen" from the deck, the show-outs or the cards played, and what the count
says is true of the real deal at every card of real robot games.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ai
import challenge
from card import Card
from game import DEALER_ROTATION, PLAYERS

#: Names only the count derives from. `_dead` is the count's own helper;
#: `_shown_out` and `_played_in` are the definitions it calls.
_DERIVED = {'_FULL_DECK', '_shown_out', '_played_in'}
_ALLOWED = {'TableCount', '_dead', '_shown_out', '_played_in'}
#: The fallback lead still reads the cards played on its own: it is the rule
#: the next phase rebuilds on the count (docs/CHALLENGE.md, "The table count").
_BLIND = {'_lead', '_gap', '_unplayed_values', '_nt_long_lead'}


def _play_section():
    tree = ast.parse((ROOT / 'ai.py').read_text(encoding='utf-8'))
    start = next(n.lineno for n in tree.body
                 if isinstance(n, ast.ClassDef) and n.name == 'TableCount')
    return [n for n in tree.body if n.lineno >= start
            and isinstance(n, (ast.FunctionDef, ast.ClassDef))]


def test_only_the_count_derives_what_a_seat_has_seen():
    """No play rule reads the deck, the show-outs or a seat's played cards
    itself, and none builds a `seen` set from `played`."""
    offenders = []
    for node in _play_section():
        if node.name in _ALLOWED | _BLIND:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id in _DERIVED:
                offenders.append(f'{node.name} reads {sub.id}')
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == 'set' and sub.args
                    and isinstance(sub.args[0], ast.Name) and sub.args[0].id == 'played'):
                offenders.append(f'{node.name} builds set(played)')
    assert not offenders, offenders


def test_every_card_play_rule_takes_the_count():
    """Each rule `ai_play` calls accepts the count `ai_play` built."""
    tree = ast.parse((ROOT / 'ai.py').read_text(encoding='utf-8'))
    play = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'ai_play')
    called = {sub.func.id for sub in ast.walk(play)
              if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
              and sub.func.id.startswith('_')}
    takes = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)
             and any(a.arg == 'count' for a in n.args.args + n.args.kwonlyargs)}
    rules = called - _BLIND - {'_shed', '_middle_play', '_third_sees_last',
                               '_partner_suit_lead', '_singleton_lead'}
    assert rules <= takes, sorted(rules - takes)


def _games(deals):
    """Every robot decision of these deals, with the real hands at that moment."""
    for deal_id in deals:
        table = challenge.robot_table(deal_id, DEALER_ROTATION[deal_id % 4])
        if table['contract'] is None:
            continue
        contract = table['contract']
        remaining = {s: list(c) for s, c in table['initial_hands'].items()}
        shown = ai.shown_lengths(table['calls'], table['alerts'])
        played, history = [], []
        for entry in table['tricks_log']:
            trick = []
            for seat, card in entry['plays']:
                visible = ai.visible_hands(seat, contract, remaining)
                if ai.NO_PEEK_OPENING_LEAD and not trick and not played:
                    visible = {}
                yield (ai.TableCount(seat, remaining[seat], trick, contract['trump'], played,
                                     visible, history, shown), remaining)
                remaining[seat].remove(card)
                trick = trick + [(seat, card)]
            history.append(entry['plays'])
            played = played + [c for _, c in entry['plays']]


def test_the_count_is_true_of_the_real_deal():
    """At every card of 12 robot games: seen and unseen split the deck; every
    card a hidden hand really holds is unseen; a seat shown out of a suit holds
    none; each hand's size and the auction's floors are true of it."""
    decisions = 0
    for count, remaining in _games(range(12)):
        decisions += 1
        deck = set(ai._FULL_DECK)
        assert count.seen | set(count.unseen) == deck
        assert not count.seen & set(count.unseen)
        for seat in PLAYERS:
            if seat == count.player or seat in count.visible:
                continue
            assert set(remaining[seat]) <= set(count.unseen), seat
            for suit in count.out[seat]:
                assert not any(c.suit == suit for c in remaining[seat]), (seat, suit)
            for suit in 'SHDC':
                held = sum(c.suit == suit for c in remaining[seat])
                assert count.floor(seat, suit) <= held, (seat, suit)
            assert count.size(seat) == len(remaining[seat]), seat
        for suit in 'SHDC':
            assert count.unseen_in(suit) == sorted(count.outstanding(suit))
    assert decisions > 400


def test_dead_and_master_follow_the_cards_gone():
    """A card is dead once every higher card of its suit is gone or mine; the
    master is the suit's highest card still in play."""
    C = lambda t: Card(t[-1], t[:-1])
    count = ai.TableCount('South', [C('KS'), C('5S')], [('West', C('QS'))], None,
                          [C('AS'), C('2S'), C('3S'), C('4S')])
    assert count.dead(C('KS'))
    assert not count.dead(C('5S'))
    assert count.master('S') == C('KS')
    assert count.master('H') == C('AH')


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('PASS', name)
    print("All assertions passed.")
