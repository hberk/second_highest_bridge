"""Packed-integer core for the Second-Highest double dummy solver.

This module is deliberately free of ``Card`` objects, seat names and everything
else from the domain and presentation layers: it is plain ints throughout, so
the search in later stages stays cheap in its hot loops and the core stays
small enough to port if Python becomes the bottleneck. All translation to and
from the domain layer lives in ``bridge/solver/convert.py``.

``bridge/trick.py`` remains the executable specification of the rules. Nothing
here is authoritative; every function below is property-tested against that
oracle in ``tests/test_solver_core.py``.

Encoding
--------
card    ``suit * 13 + rank`` — clubs occupy bits 0-12, diamonds 13-25,
        hearts 26-38, spades 39-51.
rank    ``0`` is the deuce and ``12`` the ace, matching ``card.RANK_VALUE``.
suit    ``0-3`` for C/D/H/S, matching ``card.SUITS``.
seat    ``0-3`` for North/East/South/West, matching ``bridge.auction.PLAYERS``.
hand    a 52-bit int with one bit set per card held.
trump   ``0-3`` for a suit contract, ``None`` for No-Trump.
"""
from __future__ import annotations
from typing import Iterator, NamedTuple, Optional, Tuple

RANKS_PER_SUIT = 13
SUIT_COUNT = 4
SEAT_COUNT = 4

#: North and South, matching ``bridge.auction.PLAYERS`` ordering.
NS_SEATS = (0, 2)
DECK_SIZE = RANKS_PER_SUIT * SUIT_COUNT

SUIT_MASK = (1 << RANKS_PER_SUIT) - 1
FULL_DECK = (1 << DECK_SIZE) - 1

#: One 52-bit mask per suit, indexed by suit.
SUIT_MASKS = tuple(SUIT_MASK << (s * RANKS_PER_SUIT) for s in range(SUIT_COUNT))

#: Lookup tables, not division — these sit on the hottest path in the search.
SUIT_OF = tuple(i // RANKS_PER_SUIT for i in range(DECK_SIZE))
RANK_OF = tuple(i % RANKS_PER_SUIT for i in range(DECK_SIZE))


def _second_highest_table() -> tuple:
    """Rank of the second-highest set bit of every 13-bit mask.

    This is *the* primitive of the variant, so it is a table rather than a
    computation. A mask with one bit set answers with that bit, which is the
    lone-card-wins rule falling out for free. Index 0 is never a legal query
    and answers 0.
    """
    table = [0] * (1 << RANKS_PER_SUIT)
    for mask in range(1, 1 << RANKS_PER_SUIT):
        top = mask.bit_length() - 1
        rest = mask ^ (1 << top)
        table[mask] = (rest.bit_length() - 1) if rest else top
    return tuple(table)


SECOND_HIGHEST = _second_highest_table()

def card_index(suit: int, rank: int) -> int:
    """Card index for a suit (0-3) and rank (0 = deuce, 12 = ace)."""
    return suit * RANKS_PER_SUIT + rank


def cards_in(mask: int) -> Iterator[int]:
    """Yield the card index of every set bit, lowest first."""
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def count(mask: int) -> int:
    """Number of cards in a mask. (``int.bit_count`` is 3.10+; this is 3.9.)"""
    return bin(mask).count('1')


def legal_moves(hand: int, led_suit: Optional[int]) -> int:
    """Mask of cards that may legally be played. Mirrors ``legal_plays``."""
    if led_suit is None:
        return hand
    follow = hand & SUIT_MASKS[led_suit]
    return follow if follow else hand


def resolve(plays: Tuple[int, ...], leader: int, trump: Optional[int]) -> int:
    """Seat that wins the trick under the Second-Highest rule.

    ``plays`` holds card indices in play order, ``plays[0]`` played by
    ``leader``. Mirrors ``bridge.trick.resolve_trick``: the winning suit is
    trump when any trump was played, otherwise the led suit; the second-highest
    card of that suit takes the trick, or the only card when just one was
    played in it.
    """
    winning_suit = SUIT_OF[plays[0]]
    if trump is not None:
        for idx in plays:
            if SUIT_OF[idx] == trump:
                winning_suit = trump
                break

    base = winning_suit * RANKS_PER_SUIT
    ceiling = base + RANKS_PER_SUIT
    ranks = 0
    for idx in plays:
        if base <= idx < ceiling:
            ranks |= 1 << (idx - base)

    # SECOND_HIGHEST folds in the lone-card-wins case
    winner = base + SECOND_HIGHEST[ranks]
    return (leader + plays.index(winner)) % SEAT_COUNT


class Position(NamedTuple):
    """A point in the play, mid-trick or between tricks.

    Convenient rather than fast: the Stage 2 search is expected to carry the
    same four fields in mutable locals with an undo step. The free functions
    above are the parts meant to be called from a hot loop.
    """

    hands: Tuple[int, ...]          # one mask per seat
    leader: int                     # seat that led the current trick
    trick: Tuple[int, ...]          # cards played to it so far, in play order
    trump: Optional[int]

    @property
    def to_act(self) -> int:
        return (self.leader + len(self.trick)) % SEAT_COUNT

    @property
    def led_suit(self) -> Optional[int]:
        return SUIT_OF[self.trick[0]] if self.trick else None

    @property
    def cards_left(self) -> int:
        return sum(count(h) for h in self.hands)

    def moves(self) -> int:
        """Mask of legal cards for the seat to act."""
        return legal_moves(self.hands[self.to_act], self.led_suit)

    def play(self, card: int) -> Tuple['Position', Optional[int]]:
        """Play ``card`` for the seat to act.

        Returns the new position and, when the card completed a trick, the seat
        that won it — which is also the new position's leader.
        """
        hands = list(self.hands)
        hands[self.to_act] &= ~(1 << card)
        trick = self.trick + (card,)
        if len(trick) < SEAT_COUNT:
            return self._replace(hands=tuple(hands), trick=trick), None
        winner = resolve(trick, self.leader, self.trump)
        return Position(tuple(hands), winner, (), self.trump), winner


def tricks_available(position: Position) -> int:
    """Tricks still to be played from a position, counting the one in progress."""
    return (position.cards_left + len(position.trick)) // SEAT_COUNT
