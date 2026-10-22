from __future__ import annotations
import random

SUITS = ['C', 'D', 'H', 'S']          # low → high for tiebreak (S outranks C)
SUIT_SYMBOLS = {'C': '♣', 'D': '♦', 'H': '♥', 'S': '♠'}
SUIT_NAMES   = {'C': 'Clubs', 'D': 'Diamonds', 'H': 'Hearts', 'S': 'Spades'}
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}   # 2 → 0, A → 12

# Bidding constants
STRAINS = ['C', 'D', 'H', 'S', 'NT']
STRAIN_SYMBOLS = {'C': '♣', 'D': '♦', 'H': '♥', 'S': '♠', 'NT': 'NT'}
STRAIN_NAMES   = {'C': 'Clubs', 'D': 'Diamonds', 'H': 'Hearts', 'S': 'Spades', 'NT': 'No-Trump'}
LEVELS = list(range(1, 8))
VULNERABILITIES = ['None', 'N/S', 'E/W', 'Both']

def bid_index(level: int, strain: str) -> int:
    """Returns integer 0..34 for comparing bids on the bidding ladder."""
    return (level - 1) * 5 + STRAINS.index(strain)

def parse_bid(call_str: str) -> tuple[int, str] | None:
    """Parse '1C', '3NT', '4S' into (level, strain). Returns None for Pass/X/XX or invalid strings."""
    if not call_str or call_str in ('Pass', 'X', 'XX'):
        return None
    if len(call_str) < 2 or not call_str[0].isdigit():
        return None
    level = int(call_str[0])
    strain = call_str[1:]
    if level not in LEVELS or strain not in STRAINS:
        return None
    return (level, strain)


class Card:
    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank

    def value(self) -> int:
        return RANK_VALUE[self.rank]

    def __str__(self) -> str:
        return f"{self.rank}{SUIT_SYMBOLS[self.suit]}"

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: object) -> bool:
        # Compared by class NAME, not identity, so a Card made before a module
        # reload still equals one made after. The Streamlit app (retired
        # 2026-10-21) re-imported every module on a source change, and an
        # isinstance test made its double dummy panel reject every recorded
        # play as "not legal". Kept: harmless, and test_solver_replay checks it.
        if type(other).__name__ != 'Card':
            return NotImplemented
        return self.suit == other.suit and self.rank == other.rank

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))


def deal() -> dict[str, list[Card]]:
    """Shuffle and deal 13 cards to each player, sorted by suit then rank."""
    deck = [Card(s, r) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    players = ['North', 'East', 'South', 'West']
    return {
        p: sorted(deck[i * 13:(i + 1) * 13],
                  key=lambda c: (SUITS.index(c.suit), c.value()), reverse=True)
        for i, p in enumerate(players)
    }


def auto_contract(north: list[Card], south: list[Card]) -> str:
    """Return the trump suit: longest combined N/S fit; tiebreak favors higher suit."""
    combined = north + south
    counts = {s: sum(1 for c in combined if c.suit == s) for s in SUITS}
    return max(SUITS, key=lambda s: (counts[s], SUITS.index(s)))
