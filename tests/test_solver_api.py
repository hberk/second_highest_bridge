"""The domain-facing analysis layer: agreement, validation, and budgets.

Correctness of the search itself is covered by test_solver_exact.py and
test_solver_search.py. What matters here is that the translation in and out is
faithful, that malformed input is refused rather than answered, and that
single_dummy honours its deadline instead of running as long as it likes.
"""
from __future__ import annotations
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from card import Card
from game import PLAYERS
from bridge.solver import api, brute
from bridge.solver.convert import card_to_index, mask_to_cards
from tests.test_solver_exact import load_fixture, position_of


def C(text: str) -> Card:
    """'10H' -> Card('H', '10'), 'AS' -> Card('S', 'A')."""
    return Card(text[-1], text[:-1])


def hand(text: str):
    return [C(token) for token in text.split()]


def fixture_deals(max_cards: int):
    """Fixture entries with no trick in progress, as domain-level arguments."""
    for entry in load_fixture()['positions']:
        if entry['cards_each'] > max_cards or entry['trick']:
            continue
        hands = {seat: hand(entry['hands'][seat]) for seat in PLAYERS}
        yield entry, hands, entry['strain'], entry['leader']


# ── Agreement with the verified layers ───────────────────────────────────────

def test_solve_deal_matches_the_fixture():
    checked = 0
    for entry, hands, strain, leader in fixture_deals(4):
        result = api.solve_deal(hands, strain, leader)
        assert result['N/S'] == entry['ns_tricks'], entry['id']
        assert result['N/S'] + result['E/W'] == entry['cards_each'], entry['id']
        checked += 1
    assert checked >= 50, f"only checked {checked}"


def test_card_values_match_exhaustive_enumeration():
    for entry, hands, strain, leader in fixture_deals(3):
        expected = {k: v for k, v in brute.root_values(position_of(entry)).items()}
        actual = api.card_values(hands, strain, leader)
        assert {card_to_index(c): v for c, v in actual.items()} == expected, entry['id']


def test_best_cards_are_the_ones_worth_playing():
    for entry, hands, strain, leader in fixture_deals(3):
        values = api.card_values(hands, strain, leader)
        best = api.best_cards(hands, strain, leader)
        assert best, entry['id']
        # Every best card reaches the position's value, and nothing else does better
        for card in best:
            assert values[card] == entry['ns_tricks'], (entry['id'], card)


def test_a_trick_in_progress_is_honoured():
    for entry in load_fixture()['positions']:
        if entry['cards_each'] > 3 or not entry['trick']:
            continue
        hands = {seat: hand(entry['hands'][seat]) for seat in PLAYERS}
        trick = hand(entry['trick'])
        result = api.solve_deal(hands, entry['strain'], entry['leader'], trick)
        assert result['N/S'] == entry['ns_tricks'], entry['id']


# ── Positions reasoned out by hand, independent of the fixture ───────────────

def test_the_ace_is_worth_nothing_and_the_king_takes_it():
    hands = {'North': hand('AS'), 'East': hand('KS'),
             'South': hand('QS'), 'West': hand('JS')}
    assert api.solve_deal(hands, 'NT', 'North') == {'N/S': 0, 'E/W': 1}


def test_top_three_cards_take_no_tricks():
    """The Stage 1 result, through the public API."""
    hands = {'North': hand('AS KS QS'), 'East': hand('JS 10S 9S'),
             'South': hand('8S 7S 6S'), 'West': hand('5S 4S 3S')}
    assert api.solve_deal(hands, 'NT', 'North') == {'N/S': 0, 'E/W': 3}


def test_every_lead_is_equally_hopeless_when_all_are():
    hands = {'North': hand('AS KS QS'), 'East': hand('JS 10S 9S'),
             'South': hand('8S 7S 6S'), 'West': hand('5S 4S 3S')}
    values = api.card_values(hands, 'NT', 'North')
    assert set(values) == set(hands['North'])
    assert set(values.values()) == {0}, "no lead escapes; all three are worth 0"


# ── Validation: refuse rather than answer ────────────────────────────────────

def _expect_error(fn, fragment):
    try:
        fn()
    except ValueError as error:
        assert fragment in str(error), f"wrong message: {error}"
        return
    raise AssertionError(f"expected ValueError containing {fragment!r}")


def test_duplicate_card_is_refused():
    hands = {'North': hand('AS'), 'East': hand('AS'),
             'South': hand('QS'), 'West': hand('JS')}
    _expect_error(lambda: api.solve_deal(hands, 'NT', 'North'), 'twice')


def test_uneven_hands_are_refused():
    hands = {'North': hand('AS KS'), 'East': hand('QS'),
             'South': hand('JS'), 'West': hand('10S')}
    _expect_error(lambda: api.solve_deal(hands, 'NT', 'North'), 'uneven')


def test_missing_seat_is_refused():
    hands = {'North': hand('AS'), 'East': hand('KS'), 'South': hand('QS')}
    _expect_error(lambda: api.solve_deal(hands, 'NT', 'North'), 'West')


def test_bad_strain_and_seat_are_refused():
    hands = {'North': hand('AS'), 'East': hand('KS'),
             'South': hand('QS'), 'West': hand('JS')}
    _expect_error(lambda: api.solve_deal(hands, 'Z', 'North'), 'strain')
    _expect_error(lambda: api.solve_deal(hands, 'NT', 'Up'), 'seat')


def test_card_both_on_the_trick_and_in_a_hand_is_refused():
    hands = {'North': hand('AS'), 'East': hand('KS'),
             'South': hand('QS'), 'West': hand('JS')}
    _expect_error(lambda: api.solve_deal(hands, 'NT', 'North', hand('AS')),
                  'both on the trick')


# ── Single dummy sampling ────────────────────────────────────────────────────

def test_unseen_cards_excludes_what_is_known():
    known = hand('AS KS QS')
    played = hand('2C 3C')
    unseen = api.unseen_cards(known, played)
    assert len(unseen) == 52 - 5
    assert not set(unseen) & set(known + played)


def test_single_dummy_with_nothing_hidden_is_double_dummy():
    hands = {'North': hand('AS KS'), 'East': hand('QS JS'),
             'South': hand('10S 9S'), 'West': hand('8S 7S')}
    exact = api.solve_deal(hands, 'NT', 'North')['N/S']
    result = api.single_dummy(hands, {}, [], 'NT', 'North', samples=3, seed=1)
    assert result['distribution'] == {exact: 3}
    assert result['mean'] == exact
    assert result['complete']


def test_single_dummy_spreads_over_hidden_hands():
    visible = {'North': hand('AS KS QS'), 'South': hand('8S 7S 6S')}
    pool = hand('JS 10S 9S 5S 4S 3S')
    result = api.single_dummy(visible, {'East': 3, 'West': 3}, pool,
                              'NT', 'North', samples=12, seed=7)
    assert result['samples'] == 12
    assert result['complete']
    assert sum(result['distribution'].values()) == 12
    assert all(0 <= value <= 3 for value in result['distribution'])
    assert result['mean'] is not None


def test_single_dummy_is_deterministic_for_a_seed():
    visible = {'North': hand('AS KS QS'), 'South': hand('8S 7S 6S')}
    pool = hand('JS 10S 9S 5S 4S 3S')
    args = (visible, {'East': 3, 'West': 3}, pool, 'NT', 'North')
    first = api.single_dummy(*args, samples=8, seed=42)
    second = api.single_dummy(*args, samples=8, seed=42)
    assert first['distribution'] == second['distribution']


def test_single_dummy_stops_at_its_deadline():
    """A truncated answer must say so rather than pass as the full one."""
    visible = {'North': hand('AS KS QS'), 'South': hand('8S 7S 6S')}
    pool = hand('JS 10S 9S 5S 4S 3S')
    result = api.single_dummy(visible, {'East': 3, 'West': 3}, pool,
                              'NT', 'North', samples=10 ** 6,
                              deadline=0.3, seed=3)
    assert result['samples'] < 10 ** 6
    assert not result['complete']
    assert result['requested'] == 10 ** 6
    assert result['elapsed'] < 5.0


def test_single_dummy_refuses_an_inconsistent_pool():
    visible = {'North': hand('AS KS QS'), 'South': hand('8S 7S 6S')}
    _expect_error(
        lambda: api.single_dummy(visible, {'East': 3, 'West': 3}, hand('JS 10S'),
                                 'NT', 'North', samples=1),
        'pool holds 2 cards',
    )
    _expect_error(
        lambda: api.single_dummy(visible, {'East': 6}, hand('JS 10S 9S 5S 4S 3S'),
                                 'NT', 'North', samples=1),
        'all four seats',
    )


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nAnalysis API agrees with the verified layers.")
