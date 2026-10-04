"""The optimised search must agree with exhaustive enumeration, exactly.

Every reduction in bridge/solver/search.py is meant to be sound, so the only
acceptable outcome is identical answers on the whole frozen fixture. Each
optimisation is also exercised with the others switched off, so a disagreement
can be bisected to the one that caused it rather than just observed.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from bridge.solver import brute, search
from bridge.solver.bitstate import Position, SEAT_COUNT
from tests.fixtures.generate_endings import random_ending
from tests.test_solver_exact import load_fixture, position_of, rotate

#: Cross-checking against enumeration is only affordable on small positions.
CROSS_CHECK_CARDS = int(os.environ.get('SOLVER_CROSS_CHECK_CARDS', '4'))


def fixture_positions(max_cards: int = 99):
    for entry in load_fixture()['positions']:
        if entry['cards_each'] <= max_cards:
            yield entry, position_of(entry)


# ── Agreement with the frozen ground truth ───────────────────────────────────

def test_search_reproduces_the_whole_fixture():
    checked = 0
    for entry, pos in fixture_positions():
        actual = search.solve(pos)
        assert actual == entry['ns_tricks'], (
            f"{entry['id']}: fixture {entry['ns_tricks']}, search {actual}"
        )
        checked += 1
    assert checked >= 180, f"only checked {checked}"


def test_each_optimisation_alone_reproduces_the_fixture():
    """Bisects a disagreement to a single reduction rather than the pair."""
    settings = [
        ('raw-key table, no move reduction',
         dict(use_table=True, normalise_key=False, reduce_moves=False)),
        ('normalised-key table only',
         dict(use_table=True, normalise_key=True, reduce_moves=False)),
        ('move reduction only',
         dict(use_table=False, normalise_key=False, reduce_moves=True)),
        ('zero-window alone',
         dict(use_table=False, normalise_key=False, reduce_moves=False)),
        ('natural move order',
         dict(ordering='natural')),
    ]
    for label, options in settings:
        for entry, pos in fixture_positions(CROSS_CHECK_CARDS):
            actual = search.solve(pos, **options)
            assert actual == entry['ns_tricks'], (
                f"{label} broke {entry['id']}: "
                f"fixture {entry['ns_tricks']}, search {actual}"
            )


def test_move_ordering_cannot_change_an_answer():
    """Ordering is sound by construction; this pins it against regression."""
    for entry, pos in fixture_positions():
        natural = search.solve(pos, ordering='natural')
        trick = search.solve(pos, ordering='trick')
        assert natural == trick == entry['ns_tricks'], entry['id']


def test_zero_window_probes_are_monotone():
    """reaches(k) must be a step function: true up to the value, false after."""
    for entry, pos in fixture_positions(CROSS_CHECK_CARDS):
        total = search.tricks_available(pos)
        engine = search.Search(pos.trump)
        answers = [engine.reaches(pos, need) for need in range(total + 2)]
        expected = [need <= entry['ns_tricks'] for need in range(total + 2)]
        assert answers == expected, entry['id']


# ── Agreement with enumeration on positions outside the fixture ──────────────

def test_search_agrees_with_enumeration_on_fresh_positions():
    """Guards against the fixture and the search sharing a blind spot."""
    for cards_each in (2, 3, 4):
        for seed in range(500, 500 + (24 if cards_each < 4 else 12)):
            pos = random_ending(seed, cards_each, mid_trick=seed % 4)
            expected = brute.solve(pos)
            actual = search.solve(pos)
            assert actual == expected, (cards_each, seed, expected, actual)


def test_seat_rotation_complements_the_value():
    for entry, pos in fixture_positions(CROSS_CHECK_CARDS):
        total = search.tricks_available(pos)
        base = entry['ns_tricks']
        assert search.solve(rotate(pos, 2)) == base, entry['id']
        assert search.solve(rotate(pos, 1)) == total - base, entry['id']
        assert search.solve(rotate(pos, 3)) == total - base, entry['id']


# ── The reductions actually reduce ───────────────────────────────────────────

def test_search_visits_far_fewer_nodes_than_enumeration():
    brute_nodes = 0
    search_nodes = 0
    for entry, pos in fixture_positions():
        if entry['cards_each'] < 4:
            continue
        brute_nodes += entry['nodes']
        search_nodes += search.solve_with_nodes(pos)[1]

    assert search_nodes > 0
    ratio = brute_nodes / search_nodes
    # Measured around 400x; a large margin keeps this from being brittle while
    # still failing loudly if a reduction silently stops reducing.
    assert ratio > 50, f"only {ratio:.1f}x fewer nodes than enumeration"


def test_equivalence_reduction_cuts_the_move_list():
    """K Q J with nothing live between them is one move, not three."""
    from bridge.solver.convert import text_to_mask, trump_to_index

    engine = search.Search(trump_to_index('NT'))
    hands = (
        text_to_mask('KS QS JS'),      # North: a solid run
        text_to_mask('AS 4S 3S'),
        text_to_mask('10S 9S 8S'),
        text_to_mask('7S 6S 5S'),
    )
    moves = engine._distinct_moves(hands, 0, hands[0], 0)
    assert bin(moves).count('1') == 1, "a run of touching cards is one move"

    # With the ace on the table the run is unaffected, but a live card inside
    # the run would split it: give North K J and leave the queen outstanding.
    split = (
        text_to_mask('KS JS 3S'),
        text_to_mask('AS QS 4S'),
        text_to_mask('10S 9S 8S'),
        text_to_mask('7S 6S 5S'),
    )
    moves = engine._distinct_moves(split, 0, split[0], 0)
    assert bin(moves).count('1') == 3, "a live card between them splits the run"


def test_cards_on_the_table_split_equivalence_classes():
    """The gotcha: 'live' must include the current trick, not just hands."""
    from bridge.solver.convert import text_to_index, text_to_mask, trump_to_index

    engine = search.Search(trump_to_index('NT'))
    # South holds Q and 9; the jack and ten are gone from all hands.
    hands = (
        text_to_mask('AS KS'),
        text_to_mask('8S 7S'),
        text_to_mask('QS 9S'),
        text_to_mask('6S 5S'),
    )
    # Nothing live between Q and 9, so they are interchangeable
    assert bin(engine._distinct_moves(hands, 2, hands[2], 0)).count('1') == 1

    # Now put the ten face-up on the trick: it sits between them and they are not
    table = 1 << text_to_index('10S')
    assert bin(engine._distinct_moves(hands, 2, hands[2], table)).count('1') == 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nOptimised search agrees with exhaustive enumeration.")
