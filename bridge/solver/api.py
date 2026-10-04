"""Double dummy analysis in domain terms: seat names, ``Card``, strain strings.

This is the layer the app and the replayer talk to. Everything below it is
ints; nothing below it may import ``card`` or ``bridge.auction``. Inputs are
validated here, because a silently malformed position produces a confident
wrong number rather than an error.

Costs are not uniform, and callers should pick a starting point accordingly
(measured on this machine, per position):

    8 cards each   0.45s      13 cards each   ~600s

So post-mortem analysis of a hand's second half is cheap, and opening-lead
analysis is not. ``single_dummy`` therefore takes a deadline and reports how
many samples it actually managed.
"""
from __future__ import annotations
import random
import time
from typing import Dict, Iterable, List, Optional, Sequence

from card import Card, RANKS, SUITS
from game import PLAYERS
from bridge.solver.bitstate import NS_SEATS, Position, cards_in
from bridge.solver.convert import (
    card_to_index, cards_to_mask, index_to_card, trump_to_index,
)
from bridge.solver.bitstate import tricks_available
from bridge.solver.search import Search

FULL_DECK = [Card(suit, rank) for suit in SUITS for rank in RANKS]


# ── Building and checking a position ─────────────────────────────────────────

def _position(hands: Dict[str, Sequence[Card]], strain: str, leader: str,
              trick: Optional[Sequence[Card]] = None) -> Position:
    """Validate a deal and pack it. Raises ValueError on anything malformed."""
    if set(hands) != set(PLAYERS):
        missing = set(PLAYERS) - set(hands)
        raise ValueError(f"hands must name all four seats; missing {sorted(missing)}")
    if leader not in PLAYERS:
        raise ValueError(f"{leader!r} is not a seat")
    if strain not in SUITS and strain != 'NT':
        raise ValueError(f"{strain!r} is not a strain; use one of {SUITS + ['NT']}")

    trick = list(trick or ())
    if len(trick) >= 4:
        raise ValueError("a trick in progress holds at most three cards")

    seen = set()
    for seat in PLAYERS:
        for card in hands[seat]:
            if card in seen:
                raise ValueError(f"{card} appears twice")
            seen.add(card)
    for card in trick:
        if card in seen:
            raise ValueError(f"{card} is both on the trick and in a hand")
        seen.add(card)

    # Seats that have already played to this trick hold one card fewer
    played_by = {PLAYERS[(PLAYERS.index(leader) + i) % 4] for i in range(len(trick))}
    sizes = {seat: len(hands[seat]) + (1 if seat in played_by else 0)
             for seat in PLAYERS}
    if len(set(sizes.values())) != 1:
        raise ValueError(f"hands are uneven once the trick is accounted for: {sizes}")

    return Position(
        tuple(cards_to_mask(hands[seat]) for seat in PLAYERS),
        PLAYERS.index(leader),
        tuple(card_to_index(card) for card in trick),
        trump_to_index(strain),
    )


# ── Double dummy: every hand known ───────────────────────────────────────────

def solve_deal(hands: Dict[str, Sequence[Card]], strain: str, leader: str,
               trick: Optional[Sequence[Card]] = None) -> Dict[str, int]:
    """Tricks each partnership takes from here with optimal play by both sides."""
    position = _position(hands, strain, leader, trick)
    north_south = Search(position.trump).value(position)
    return {'N/S': north_south, 'E/W': tricks_available(position) - north_south}


def card_values(hands: Dict[str, Sequence[Card]], strain: str, leader: str,
                trick: Optional[Sequence[Card]] = None) -> Dict[Card, int]:
    """Every legal card for the seat to act, mapped to resulting N/S tricks.

    This is the replayer's "what was available" analysis. One search is shared
    across all the cards, because sibling lines transpose heavily and a shared
    transposition table is most of the reason this is affordable at all.
    """
    position = _position(hands, strain, leader, trick)
    engine = Search(position.trump)

    values: Dict[Card, int] = {}
    for card in cards_in(position.moves()):
        after, winner = position.play(card)
        gained = 1 if winner in NS_SEATS else 0
        values[index_to_card(card)] = gained + engine.value(after)
    return values


def best_cards(hands: Dict[str, Sequence[Card]], strain: str, leader: str,
               trick: Optional[Sequence[Card]] = None) -> List[Card]:
    """The cards that play as well as anything else, for the seat to act."""
    position = _position(hands, strain, leader, trick)
    values = card_values(hands, strain, leader, trick)
    if not values:
        return []
    target = (max(values.values()) if position.to_act in NS_SEATS
              else min(values.values()))
    return sorted((card for card, value in values.items() if value == target),
                  key=card_to_index)


# ── Single dummy: some hands unknown ─────────────────────────────────────────

def unseen_cards(known: Iterable[Card], played: Iterable[Card] = ()) -> List[Card]:
    """The deck minus everything the caller can already see."""
    seen = set(known) | set(played)
    return [card for card in FULL_DECK if card not in seen]


def single_dummy(visible: Dict[str, Sequence[Card]], hidden: Dict[str, int],
                 pool: Sequence[Card], strain: str, leader: str,
                 trick: Optional[Sequence[Card]] = None, samples: int = 50,
                 deadline: Optional[float] = None,
                 seed: Optional[int] = None) -> Dict[str, object]:
    """Deal the unseen cards many ways, solve each, and report the spread.

    ``visible`` holds the seats whose cards are known, ``hidden`` maps each
    remaining seat to how many cards it holds, and ``pool`` is the unseen cards
    to distribute. Sampling stops at ``samples`` or ``deadline`` seconds,
    whichever comes first — a truncated answer is reported as such rather than
    silently presented as the full one.
    """
    if set(visible) | set(hidden) != set(PLAYERS):
        raise ValueError("visible and hidden together must name all four seats")
    if set(visible) & set(hidden):
        raise ValueError(f"seats cannot be both visible and hidden: "
                         f"{sorted(set(visible) & set(hidden))}")
    if sum(hidden.values()) != len(pool):
        raise ValueError(f"pool holds {len(pool)} cards but the hidden seats "
                         f"need {sum(hidden.values())}")

    rng = random.Random(seed)
    deck = list(pool)
    started = time.perf_counter()
    counts: Dict[int, int] = {}
    taken = 0

    for _ in range(samples):
        if deadline is not None and time.perf_counter() - started >= deadline:
            break

        rng.shuffle(deck)
        hands = {seat: list(cards) for seat, cards in visible.items()}
        at = 0
        for seat, size in hidden.items():
            hands[seat] = deck[at:at + size]
            at += size

        north_south = solve_deal(hands, strain, leader, trick)['N/S']
        counts[north_south] = counts.get(north_south, 0) + 1
        taken += 1

    elapsed = time.perf_counter() - started
    mean = (sum(value * n for value, n in counts.items()) / taken) if taken else None
    return {
        'samples': taken,
        'requested': samples,
        'complete': taken == samples,
        'mean': mean,
        'distribution': dict(sorted(counts.items())),
        'elapsed': elapsed,
    }
