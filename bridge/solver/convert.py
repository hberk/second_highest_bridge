"""The single boundary between domain objects and solver ints.

Keeping every ``Card``, seat name and strain string in this one module is what
lets ``bitstate.py`` stay pure ints. Nothing else under ``bridge/solver/``
should import from ``card`` or ``bridge.auction``.
"""
from __future__ import annotations
from typing import Dict, Iterable, List, Optional, Tuple

from card import Card, RANKS, RANK_VALUE, SUITS
from bridge.auction import PLAYERS
from bridge.solver.bitstate import RANKS_PER_SUIT, cards_in

#: Index order matches ``suit * 13 + rank`` by construction.
_INDEX_TO_CARD = tuple(Card(s, r) for s in SUITS for r in RANKS)


def card_to_index(card: Card) -> int:
    return SUITS.index(card.suit) * RANKS_PER_SUIT + RANK_VALUE[card.rank]


def index_to_card(index: int) -> Card:
    return _INDEX_TO_CARD[index]


def cards_to_mask(cards: Iterable[Card]) -> int:
    mask = 0
    for card in cards:
        mask |= 1 << card_to_index(card)
    return mask


def mask_to_cards(mask: int) -> List[Card]:
    """Cards in a mask, low to high — *not* the display order ``deal()`` uses."""
    return [_INDEX_TO_CARD[i] for i in cards_in(mask)]


def hands_to_masks(hands: Dict[str, List[Card]]) -> Tuple[int, ...]:
    """A ``deal()`` dict keyed by seat name to one mask per seat, N/E/S/W."""
    return tuple(cards_to_mask(hands[seat]) for seat in PLAYERS)


# ── ASCII card text, for fixtures and debugging ──────────────────────────────
# 'AS', '10H', '2C' — deliberately not str(Card), whose suit symbols do not
# survive a round trip through JSON on a Windows console.

def index_to_text(index: int) -> str:
    card = _INDEX_TO_CARD[index]
    return f"{card.rank}{card.suit}"


def text_to_index(text: str) -> int:
    return card_to_index(Card(text[-1], text[:-1]))


def mask_to_text(mask: int) -> str:
    """Bridge reading order: spades first, ranks high to low, space separated."""
    out = []
    for suit in reversed(SUITS):
        base = SUITS.index(suit) * RANKS_PER_SUIT
        for rank in range(RANKS_PER_SUIT - 1, -1, -1):
            if mask >> (base + rank) & 1:
                out.append(index_to_text(base + rank))
    return ' '.join(out)


def text_to_mask(text: str) -> int:
    mask = 0
    for token in text.split():
        mask |= 1 << text_to_index(token)
    return mask


def suit_to_index(suit: str) -> int:
    return SUITS.index(suit)


def index_to_suit(index: int) -> str:
    return SUITS[index]


def trump_to_index(strain: Optional[str]) -> Optional[int]:
    """Strain to trump index. ``'NT'`` and ``None`` both mean no trump suit."""
    return SUITS.index(strain) if strain in SUITS else None


def seat_to_index(seat: str) -> int:
    return PLAYERS.index(seat)


def index_to_seat(index: int) -> str:
    return PLAYERS[index]
