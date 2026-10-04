"""Direct tests of the Second-Highest trick rule and follow-suit legality."""
from __future__ import annotations
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from card import Card
from game import resolve_trick, legal_plays, clockwise_from


def C(text: str) -> Card:
    """'10H' -> Card('H', '10'), 'AS' -> Card('S', 'A')."""
    return Card(text[-1], text[:-1])


def trick(leader: str, *cards: str) -> list[tuple[str, Card]]:
    """Cards in play order starting from `leader`, e.g. trick('North', 'AH', '5H', 'KH', '2H')."""
    return list(zip(clockwise_from(leader), (C(c) for c in cards)))


# ── Who wins the trick ───────────────────────────────────────────────────────

def test_second_highest_wins_when_all_follow():
    # A K 5 2 of hearts: the K takes it, not the A
    assert resolve_trick(trick('North', 'AH', '5H', 'KH', '2H'), 'NT') == 'South'


def test_winner_depends_on_rank_not_seat():
    for leader in ('North', 'East', 'South', 'West'):
        t = trick(leader, 'AH', '5H', 'KH', '2H')
        assert resolve_trick(t, 'NT') == clockwise_from(leader)[2], leader


def test_lone_card_of_winning_suit_wins():
    # North leads the only club; everyone else discards
    assert resolve_trick(trick('North', '5C', 'AH', 'KD', 'QS'), 'NT') == 'North'


def test_two_cards_of_winning_suit_lower_one_wins():
    # Only the 5 and 9 of clubs are in the led suit: the 5 is second-highest
    assert resolve_trick(trick('North', '5C', 'AH', '9C', 'KD'), 'NT') == 'North'


def test_discards_do_not_count_even_if_high():
    # Diamonds led, no trumps played; East's heart ace is a discard. 9 5 2 -> the 5 wins
    assert resolve_trick(trick('North', '5D', 'AH', '9D', '2D'), 'S') == 'North'


def test_single_trump_beats_led_suit():
    # Spades trump; East ruffs with the 2 and the only trump wins, however low
    assert resolve_trick(trick('North', 'AH', '2S', 'KH', 'QH'), 'S') == 'East'


def test_two_trumps_the_lower_is_second_highest():
    # Two ruffs (9 and 2): the 2 is second-highest in the trump suit
    assert resolve_trick(trick('North', 'AH', '2S', 'KH', '9S'), 'S') == 'East'


def test_no_trump_contract_has_no_trumps():
    # In NT a spade is just a discard on a heart lead: A K 3 of hearts -> K
    assert resolve_trick(trick('North', 'AH', '2S', 'KH', '3H'), 'NT') == 'South'


# ── Follow suit ──────────────────────────────────────────────────────────────

def test_must_follow_suit():
    hand = [C('AS'), C('3H'), C('9H'), C('KD')]
    assert set(legal_plays(hand, 'H')) == {C('3H'), C('9H')}


def test_void_may_play_anything():
    hand = [C('AS'), C('KD')]
    assert set(legal_plays(hand, 'H')) == set(hand)


def test_leader_may_play_anything():
    hand = [C('AS'), C('3H')]
    assert set(legal_plays(hand, None)) == set(hand)


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
    print("All trick-rule tests passed.")
