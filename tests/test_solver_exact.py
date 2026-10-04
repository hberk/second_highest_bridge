"""Ground truth for the double dummy solver.

tests/fixtures/endings.json is frozen output from exhaustive enumeration. This
suite re-derives it and checks the solver's own structural invariants. Every
later stage validates against the same fixture, so a disagreement here means a
rules change or a bug — never a speedup.

Re-solving 5-card positions costs ~20s each, so by default only positions up to
4 cards are re-derived. To verify the whole fixture:

    SOLVER_EXACT_MAX_CARDS=5 python tests/test_solver_exact.py
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from game import PLAYERS
from bridge.solver.bitstate import (
    Position, SEAT_COUNT, cards_in, count, tricks_available,
)
from bridge.solver.brute import NS_SEATS, best_cards, root_values, solve
from bridge.solver.convert import text_to_index, text_to_mask, trump_to_index

FIXTURE_PATH = Path(__file__).resolve().parent / 'fixtures' / 'endings.json'

#: Re-deriving a 5-card position takes ~20s, so keep the default suite quick.
MAX_CARDS = int(os.environ.get('SOLVER_EXACT_MAX_CARDS', '4'))

#: Rotation checks triple the work; keep them on the cheap positions.
ROTATION_MAX_CARDS = int(os.environ.get('SOLVER_ROTATION_MAX_CARDS', '3'))


def load_fixture() -> dict:
    with FIXTURE_PATH.open(encoding='utf-8') as handle:
        return json.load(handle)


def position_of(entry: dict) -> Position:
    masks = tuple(text_to_mask(entry['hands'][seat]) for seat in PLAYERS)
    trick = tuple(text_to_index(token) for token in entry['trick'].split())
    return Position(masks, PLAYERS.index(entry['leader']), trick,
                    trump_to_index(entry['strain']))


def rotate(pos: Position, seats: int) -> Position:
    """Move every hand `seats` places clockwise, leader and trick with it."""
    hands = [0] * SEAT_COUNT
    for seat, mask in enumerate(pos.hands):
        hands[(seat + seats) % SEAT_COUNT] = mask
    return Position(tuple(hands), (pos.leader + seats) % SEAT_COUNT,
                    pos.trick, pos.trump)


# ── Positions reasoned out by hand ───────────────────────────────────────────
# These do not depend on the fixture, so a corrupted fixture cannot make them
# pass. Each one is small enough to verify by reading it.

def _one_card_position(hand_texts, strain='NT', leader='North') -> Position:
    masks = tuple(text_to_mask(text) for text in hand_texts)
    return Position(masks, PLAYERS.index(leader), (), trump_to_index(strain))


def test_single_trick_second_highest_decides():
    # A K Q J of spades, all following: the K is second-highest, so East wins
    assert solve(_one_card_position(['AS', 'KS', 'QS', 'JS'])) == 0
    # K A 3 2: the K is again second-highest, and North holds it
    assert solve(_one_card_position(['KS', 'AS', '3S', '2S'])) == 1
    # A 4 3 2: the 4 is second-highest, so West takes it
    assert solve(_one_card_position(['AS', '2S', '3S', '4S'])) == 0
    # 2 A 3 4: highest is the ace, second is the 4 — West again
    assert solve(_one_card_position(['2S', 'AS', '3S', '4S'])) == 0


def test_lone_card_of_winning_suit_takes_every_trick():
    # Each seat holds one suit outright, so any lead is the only card of its
    # suit and wins unopposed. North leads, wins, and is on lead again.
    mutual_voids = ['AS KS QS JS', 'AH KH QH JH', 'AD KD QD JD', 'AC KC QC JC']
    pos = _one_card_position(mutual_voids, strain='NT', leader='North')
    assert solve(pos) == 4

    # With diamonds trump, South ruffs every trick alone and takes all four —
    # E/W are void in trump and cannot over-ruff, so N/S still sweep.
    pos = _one_card_position(mutual_voids, strain='D', leader='North')
    assert solve(pos) == 4

    # Same shape, but now a defender holds the trump suit and sweeps instead.
    defender_trumps = ['AS KS QS JS', 'AD KD QD JD', 'AH KH QH JH', 'AC KC QC JC']
    pos = _one_card_position(defender_trumps, strain='D', leader='North')
    assert solve(pos) == 0


# ── The fixture ──────────────────────────────────────────────────────────────

def test_fixture_is_wellformed():
    data = load_fixture()
    positions = data['positions']
    assert positions, "fixture is empty"

    ids = [entry['id'] for entry in positions]
    assert len(ids) == len(set(ids)), "duplicate fixture ids"

    for entry in positions:
        pos = position_of(entry)
        trick = pos.trick

        # No card may appear twice across hands and the trick in progress
        seen = 0
        for mask in pos.hands:
            assert seen & mask == 0, entry['id']
            seen |= mask
        for card in trick:
            assert seen >> card & 1 == 0, entry['id']
            seen |= 1 << card

        # Seats that have already played to this trick hold one card fewer
        cards_each = entry['cards_each']
        played_by = {(pos.leader + i) % SEAT_COUNT for i in range(len(trick))}
        for seat in range(SEAT_COUNT):
            expected = cards_each - (1 if seat in played_by else 0)
            assert count(pos.hands[seat]) == expected, (entry['id'], seat)

        assert 0 <= entry['ns_tricks'] <= tricks_available(pos), entry['id']
        assert entry['nodes'] > 0, entry['id']


def test_fixture_covers_the_awkward_shapes():
    ids = {entry['id'] for entry in load_fixture()['positions']}
    for required in ('crafted-single-suit-nt', 'crafted-single-suit-trump',
                     'crafted-mutual-voids', 'crafted-stranded-ace',
                     'crafted-two-suit', 'crafted-ruff-race'):
        assert required in ids, f"fixture lost coverage of {required}"
    assert any(i.endswith('-mid') for i in ids), "no mid-trick positions"


def test_brute_force_reproduces_the_fixture():
    data = load_fixture()
    checked = 0
    for entry in data['positions']:
        if entry['cards_each'] > MAX_CARDS:
            continue
        actual = solve(position_of(entry))
        assert actual == entry['ns_tricks'], (
            f"{entry['id']}: fixture says {entry['ns_tricks']}, solver says {actual}"
        )
        checked += 1
    assert checked >= 100, f"only re-derived {checked} positions"


# ── Structural invariants of the search itself ───────────────────────────────

def test_seat_rotation_complements_the_value():
    """Rotating seats by one hands N/S's cards to E/W, so the value must flip.

    This is the sharpest available check on seat indexing: it exercises the
    (leader + offset) % 4 arithmetic in resolve() against the minimax layer
    without either being able to cancel the other's error.
    """
    for entry in load_fixture()['positions']:
        if entry['cards_each'] > ROTATION_MAX_CARDS:
            continue
        pos = position_of(entry)
        total = tricks_available(pos)
        base = entry['ns_tricks']

        assert solve(rotate(pos, 2)) == base, entry['id']
        assert solve(rotate(pos, 1)) == total - base, entry['id']
        assert solve(rotate(pos, 3)) == total - base, entry['id']


def test_root_values_agree_with_the_position_value():
    for entry in load_fixture()['positions']:
        if entry['cards_each'] > ROTATION_MAX_CARDS:
            continue
        pos = position_of(entry)
        values = root_values(pos)
        assert set(values) == set(cards_in(pos.moves())), entry['id']

        expected = max(values.values()) if pos.to_act in NS_SEATS else min(values.values())
        assert expected == entry['ns_tricks'], entry['id']


def test_best_cards_achieve_the_value():
    for entry in load_fixture()['positions']:
        if entry['cards_each'] > ROTATION_MAX_CARDS:
            continue
        pos = position_of(entry)
        cards = best_cards(pos)
        assert cards, entry['id']
        for card in cards:
            after, winner = pos.play(card)
            gained = 1 if winner in NS_SEATS else 0
            assert gained + solve(after) == entry['ns_tricks'], (entry['id'], card)


def test_every_line_of_play_ends_with_all_tricks_accounted_for():
    for entry in load_fixture()['positions']:
        if entry['cards_each'] > ROTATION_MAX_CARDS:
            continue
        pos = position_of(entry)
        assert 0 <= entry['ns_tricks'] <= tricks_available(pos), entry['id']


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print(f"\nFixture verified up to {MAX_CARDS} cards per hand.")
