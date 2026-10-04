from __future__ import annotations
from card import Card, SUITS


def legal_plays(hand: list[Card], led_suit: str | None) -> list[Card]:
    """Cards that may legally be played given what was led."""
    if led_suit is None:
        return list(hand)
    in_suit = [c for c in hand if c.suit == led_suit]
    return in_suit if in_suit else list(hand)


def resolve_trick(trick: list[tuple[str, Card]], trump: str | None) -> str:
    """
    Return the winning player name under Second-Highest Bridge rules.
    - If trump is in SUITS and any trump was played, trump is the winning suit.
    - Otherwise (No-Trump or no trump played), the led suit is the winning suit.
    - Second-highest card in the winning suit wins (or the only card if single).
    """
    led_suit = trick[0][1].suit
    is_trump_contract = (trump in SUITS)
    has_trump = is_trump_contract and any(c.suit == trump for _, c in trick)
    winning_suit = trump if has_trump else led_suit

    suit_plays = sorted(
        [(p, c) for p, c in trick if c.suit == winning_suit],
        key=lambda x: x[1].value(),
        reverse=True,
    )
    # Index 1 = second-highest; clamp to 0 when only one card
    winner_idx = min(1, len(suit_plays) - 1)
    return suit_plays[winner_idx][0]

