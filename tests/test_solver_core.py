"""Holds the packed-integer solver core to bridge/trick.py, the rules oracle.

With rules this variant invents there is no external solver to check against,
so the reference engine is the only safety net the solver gets. Everything the
bit core claims is checked against it here.

Sample counts scale with SOLVER_TEST_SAMPLES for a heavier sweep:
    SOLVER_TEST_SAMPLES=1000000 python tests/test_solver_core.py
"""
from __future__ import annotations
import os
import random
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from card import Card, RANKS, SUITS, deal
from game import PLAYERS, clockwise_from, legal_plays, resolve_trick
from bridge.solver.bitstate import (
    DECK_SIZE, FULL_DECK, SUIT_MASKS, Position, cards_in, count, legal_moves,
    resolve,
)
from bridge.solver.convert import (
    card_to_index, cards_to_mask, hands_to_masks, index_to_card, index_to_seat,
    mask_to_cards, seat_to_index, trump_to_index,
)

SAMPLES = int(os.environ.get('SOLVER_TEST_SAMPLES', '20000'))
DEALS = int(os.environ.get('SOLVER_TEST_DEALS', '60'))

# None and 'NT' are both No-Trump to resolve_trick; exercise both spellings.
STRAINS_UNDER_TEST = SUITS + ['NT', None]


def C(text: str) -> Card:
    """'10H' -> Card('H', '10'), 'AS' -> Card('S', 'A')."""
    return Card(text[-1], text[:-1])


def oracle_winner(indices, leader: int, strain) -> str:
    """Winning seat name according to the reference engine."""
    seats = clockwise_from(index_to_seat(leader))
    trick = [(seats[i], index_to_card(idx)) for i, idx in enumerate(indices)]
    return resolve_trick(trick, strain)


def bit_winner(indices, leader: int, strain) -> str:
    """Winning seat name according to the bit core."""
    return index_to_seat(resolve(tuple(indices), leader, trump_to_index(strain)))


# ── Encoding ─────────────────────────────────────────────────────────────────

def test_card_index_is_a_bijection():
    seen = {}
    for suit in SUITS:
        for rank in RANKS:
            card = Card(suit, rank)
            idx = card_to_index(card)
            assert 0 <= idx < DECK_SIZE
            assert idx not in seen, f"{card} collides with {seen.get(idx)}"
            assert index_to_card(idx) == card
            seen[idx] = card
    assert len(seen) == DECK_SIZE


def test_suit_masks_partition_the_deck():
    total = 0
    for mask in SUIT_MASKS:
        assert count(mask) == 13
        assert total & mask == 0
        total |= mask
    assert total == FULL_DECK


def test_mask_round_trips_a_dealt_hand():
    random.seed(7)
    hands = deal()
    for seat, cards in hands.items():
        mask = cards_to_mask(cards)
        assert count(mask) == 13
        assert set(mask_to_cards(mask)) == set(cards)


def test_cards_in_yields_every_bit_once():
    random.seed(8)
    for _ in range(200):
        indices = random.sample(range(DECK_SIZE), random.randrange(1, 14))
        mask = 0
        for i in indices:
            mask |= 1 << i
        assert sorted(cards_in(mask)) == sorted(indices)


# ── The Second-Highest rule, stated directly against the bit core ────────────
# These mirror tests/test_rules.py so the core carries its own spec coverage
# rather than only ever being compared to another implementation.

def _wins(leader: str, cards, strain: str) -> str:
    indices = [card_to_index(C(c)) for c in cards]
    return bit_winner(indices, seat_to_index(leader), strain)


def test_second_highest_wins_when_all_follow():
    # A K 5 2 of hearts: the K takes it, not the A
    assert _wins('North', ['AH', '5H', 'KH', '2H'], 'NT') == 'South'


def test_lone_card_of_winning_suit_wins():
    assert _wins('North', ['5C', 'AH', 'KD', 'QS'], 'NT') == 'North'


def test_two_cards_of_winning_suit_lower_one_wins():
    assert _wins('North', ['5C', 'AH', '9C', 'KD'], 'NT') == 'North'


def test_discards_do_not_count_even_if_high():
    assert _wins('North', ['5D', 'AH', '9D', '2D'], 'S') == 'North'


def test_single_trump_beats_led_suit():
    assert _wins('North', ['AH', '2S', 'KH', 'QH'], 'S') == 'East'


def test_two_trumps_the_lower_is_second_highest():
    assert _wins('North', ['AH', '2S', 'KH', '9S'], 'S') == 'East'


def test_no_trump_contract_has_no_trumps():
    assert _wins('North', ['AH', '2S', 'KH', '3H'], 'NT') == 'South'


def test_ace_never_wins_a_contested_trick():
    # The structural fact the whole solver design turns on: for the ace to be
    # second-highest something must outrank it, so it only wins alone.
    for suit in SUITS:
        for strain in STRAINS_UNDER_TEST:
            others = [f"{r}{suit}" for r in ('K', '7', '3')]
            winner = _wins('North', [f"A{suit}"] + others, strain)
            assert winner != 'North', (suit, strain)


# ── Legality matches the oracle ──────────────────────────────────────────────

def test_legal_moves_matches_oracle():
    rng = random.Random(11)
    for _ in range(SAMPLES):
        size = rng.randrange(1, 14)
        indices = rng.sample(range(DECK_SIZE), size)
        hand = [index_to_card(i) for i in indices]
        mask = cards_to_mask(hand)

        for led in [None] + SUITS:
            expected = set(legal_plays(hand, led))
            led_idx = None if led is None else SUITS.index(led)
            actual = set(mask_to_cards(legal_moves(mask, led_idx)))
            assert actual == expected, (sorted(map(str, hand)), led)


# ── Resolution matches the oracle ────────────────────────────────────────────

def test_resolve_matches_oracle_on_full_tricks():
    rng = random.Random(12)
    for _ in range(SAMPLES):
        indices = rng.sample(range(DECK_SIZE), 4)
        leader = rng.randrange(4)
        strain = rng.choice(STRAINS_UNDER_TEST)
        expected = oracle_winner(indices, leader, strain)
        actual = bit_winner(indices, leader, strain)
        assert actual == expected, (
            [str(index_to_card(i)) for i in indices], leader, strain,
            f"oracle={expected} bits={actual}",
        )


def test_resolve_matches_oracle_on_partial_tricks():
    rng = random.Random(13)
    for _ in range(SAMPLES):
        size = rng.randrange(1, 4)
        indices = rng.sample(range(DECK_SIZE), size)
        leader = rng.randrange(4)
        strain = rng.choice(STRAINS_UNDER_TEST)
        expected = oracle_winner(indices, leader, strain)
        actual = bit_winner(indices, leader, strain)
        assert actual == expected, (
            [str(index_to_card(i)) for i in indices], leader, strain,
        )


def test_resolve_matches_oracle_on_single_suit_tricks():
    # Random cards are usually four different suits, which never exercises the
    # ranking path hard. Force every card into the winning suit.
    rng = random.Random(14)
    for _ in range(SAMPLES):
        suit = rng.randrange(4)
        ranks = rng.sample(range(13), 4)
        indices = [suit * 13 + r for r in ranks]
        leader = rng.randrange(4)
        strain = rng.choice(STRAINS_UNDER_TEST)
        assert bit_winner(indices, leader, strain) == oracle_winner(indices, leader, strain), (
            [str(index_to_card(i)) for i in indices], strain,
        )


# ── Whole deals, both engines in lockstep ────────────────────────────────────

def test_full_deals_match_the_oracle_trick_for_trick():
    for seed in range(DEALS):
        random.seed(seed)
        hands = deal()
        rng = random.Random(seed + 10_000)
        strain = rng.choice(STRAINS_UNDER_TEST)
        leader = rng.choice(PLAYERS)

        remaining = {seat: list(cards) for seat, cards in hands.items()}
        pos = Position(hands_to_masks(hands), seat_to_index(leader), (), trump_to_index(strain))

        oracle_counts = {seat: 0 for seat in PLAYERS}
        bit_counts = [0, 0, 0, 0]

        for trick_no in range(13):
            trick = []
            for seat in clockwise_from(leader):
                led = trick[0][1].suit if trick else None
                expected_legal = legal_plays(remaining[seat], led)

                assert pos.to_act == seat_to_index(seat), (seed, trick_no, seat)
                assert set(mask_to_cards(pos.moves())) == set(expected_legal), (
                    seed, trick_no, seat,
                )

                # Deterministic pick from a stable ordering
                choices = sorted(expected_legal, key=card_to_index)
                card = choices[rng.randrange(len(choices))]

                remaining[seat].remove(card)
                trick.append((seat, card))
                pos, winner = pos.play(card_to_index(card))

            expected_winner = resolve_trick(trick, strain)
            assert winner is not None
            assert index_to_seat(winner) == expected_winner, (seed, trick_no, strain)
            assert pos.leader == winner, "trick winner must lead the next trick"
            assert pos.trick == ()

            oracle_counts[expected_winner] += 1
            bit_counts[winner] += 1
            leader = expected_winner

        assert all(hand == 0 for hand in pos.hands), "every card must be played"
        assert sum(bit_counts) == 13
        assert [oracle_counts[seat] for seat in PLAYERS] == bit_counts, seed


def test_position_conserves_cards():
    random.seed(99)
    hands = deal()
    rng = random.Random(99)
    pos = Position(hands_to_masks(hands), 0, (), trump_to_index('S'))

    for played in range(DECK_SIZE):
        # Completed tricks leave the position, so hands shrink by one per play
        # and the table holds only the trick in progress.
        assert pos.cards_left == DECK_SIZE - played, played
        assert len(pos.trick) == played % 4, played

        moves = list(cards_in(pos.moves()))
        assert moves, "a seat with cards always has a legal play"
        held = pos.hands[pos.to_act]
        assert all(held >> m & 1 for m in moves), "cannot play a card not held"
        pos, _ = pos.play(moves[rng.randrange(len(moves))])

    assert pos.cards_left == 0
    assert pos.trick == ()


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print(f"\nSolver core matches the oracle (samples={SAMPLES}, deals={DEALS}).")
