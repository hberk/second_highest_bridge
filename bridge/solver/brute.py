"""Exhaustive double dummy search: no pruning, no memoisation, no heuristics.

This module defines what a correct answer *is* for the Second-Highest variant.
It is deliberately the slowest possible implementation, and it is meant to stay
that way — every later optimisation is validated by reproducing the numbers
this produces, so it must never learn any of their tricks. It is kept
permanently rather than deleted once superseded.

The value of a position is the number of tricks North/South take from it with
optimal play by both sides. The game is zero-sum between partnerships, so
N/S maximise, E/W minimise, and no coordination protocol is needed.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from bridge.solver.bitstate import (
    NS_SEATS, SEAT_COUNT, SUIT_OF, Position, cards_in, count, legal_moves,
    resolve,
)


def _search(hands: Tuple[int, ...], leader: int, trick: Tuple[int, ...],
            trump: Optional[int], counter: List[int]) -> int:
    """Tricks N/S take from here. Plain minimax over every legal line."""
    counter[0] += 1

    if not any(hands):
        return 0

    seat = (leader + len(trick)) % SEAT_COUNT
    led = SUIT_OF[trick[0]] if trick else None
    maximizing = seat in NS_SEATS
    best = -1 if maximizing else SEAT_COUNT * 14

    for card in cards_in(legal_moves(hands[seat], led)):
        rest = list(hands)
        rest[seat] &= ~(1 << card)
        played = trick + (card,)

        if len(played) == SEAT_COUNT:
            winner = resolve(played, leader, trump)
            gained = 1 if winner in NS_SEATS else 0
            value = gained + _search(tuple(rest), winner, (), trump, counter)
        else:
            value = _search(tuple(rest), leader, played, trump, counter)

        if maximizing:
            if value > best:
                best = value
        elif value < best:
            best = value

    return best


def solve(position: Position) -> int:
    """Tricks N/S take from ``position`` with optimal play by both sides."""
    return _search(position.hands, position.leader, position.trick,
                   position.trump, [0])


def solve_with_nodes(position: Position) -> Tuple[int, int]:
    """``solve``, plus the number of nodes visited — the cost baseline."""
    counter = [0]
    value = _search(position.hands, position.leader, position.trick,
                    position.trump, counter)
    return value, counter[0]


def root_values(position: Position) -> Dict[int, int]:
    """Every legal card at the root mapped to the N/S trick count it leads to.

    Stage 3 mines exactly this: the optimal move is whichever card is best for
    the side to act, and the spread across cards is how much the choice matters.
    """
    seat = position.to_act
    values: Dict[int, int] = {}

    for card in cards_in(position.moves()):
        after, winner = position.play(card)
        gained = 1 if winner in NS_SEATS else 0
        values[card] = gained + _search(after.hands, after.leader, after.trick,
                                        after.trump, [0])
    return values


def best_cards(position: Position) -> List[int]:
    """Cards that achieve the position's value for the side to act."""
    values = root_values(position)
    if position.to_act in NS_SEATS:
        target = max(values.values())
    else:
        target = min(values.values())
    return sorted(card for card, value in values.items() if value == target)
