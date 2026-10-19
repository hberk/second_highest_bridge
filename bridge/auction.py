from __future__ import annotations
import re
from card import SUITS, STRAINS, LEVELS, parse_bid, bid_index

PLAYERS = ['North', 'East', 'South', 'West']
PARTNERS = {'North': 'South', 'South': 'North', 'East': 'West', 'West': 'East'}
PARTNERSHIP = {'North': 'N/S', 'South': 'N/S', 'East': 'E/W', 'West': 'E/W'}

#: The longest alert, the robots' own limit: it has to fit a tooltip.
ALERT_MAX = 70


def clean_alert(text: str | None) -> str:
    """An alert a person wrote (typed, or imported from LIN) as one line of
    plain text, at most ALERT_MAX characters.

    This is NOT the XSS defence -- `call_badge` escapes every alert it renders,
    and that is the only place alert text reaches markup. It only keeps the
    tooltip one tidy line. Port: `cleanAlert` in frontend/src/lib/engine/auction.ts.
    """
    text = re.sub(r'[\x00-\x1f\x7f]+', ' ', text or '')
    return re.sub(r'\s+', ' ', text).strip()[:ALERT_MAX]


def clockwise_from(player: str) -> list[str]:
    """Return all 4 players in clockwise order starting from player."""
    start = PLAYERS.index(player)
    return [PLAYERS[(start + i) % 4] for i in range(4)]


class AuctionState:
    """Manages the full Bridge Auction / Bidding phase."""

    def __init__(self, dealer: str = 'North', vulnerability: str = 'None'):
        self.dealer = dealer
        self.vulnerability = vulnerability
        self.calls: list[tuple[str, str]] = []  # [(player, call_str), ...]
        self.highest_bid: tuple[int, str, str] | None = None  # (level, strain, player)
        self.doubled: str = 'None'  # 'None' | 'X' | 'XX'
        self.is_complete: bool = False
        self.passed_out: bool = False

    def current_player(self) -> str:
        """Returns the player whose turn it is to make a call."""
        start = PLAYERS.index(self.dealer)
        return PLAYERS[(start + len(self.calls)) % 4]

    def legal_calls(self) -> list[str]:
        """Returns a list of all legal call strings for current_player."""
        if self.is_complete:
            return []

        calls = ['Pass']
        curr_p = self.current_player()
        curr_side = PARTNERSHIP[curr_p]

        # Double (X)
        if self.highest_bid is not None and self.doubled == 'None':
            if PARTNERSHIP[self.highest_bid[2]] != curr_side:
                calls.append('X')

        # Redouble (XX)
        if self.highest_bid is not None and self.doubled == 'X':
            if PARTNERSHIP[self.highest_bid[2]] == curr_side:
                calls.append('XX')

        # Bids: 1C..7NT strictly higher than current highest_bid
        min_idx = -1
        if self.highest_bid is not None:
            min_idx = bid_index(self.highest_bid[0], self.highest_bid[1])

        for lvl in LEVELS:
            for strain in STRAINS:
                if bid_index(lvl, strain) > min_idx:
                    calls.append(f"{lvl}{strain}")

        return calls

    def apply_call(self, player: str, call: str) -> None:
        """Apply a call (Pass, X, XX, or bid) made by player."""
        if self.is_complete:
            raise ValueError("Auction is already complete")
        if player != self.current_player():
            raise ValueError(f"Not {player}'s turn to bid (expected {self.current_player()})")
        if call not in self.legal_calls():
            raise ValueError(f"Illegal call '{call}' for {player}")

        self.calls.append((player, call))

        if call == 'Pass':
            # Check for passed out (4 passes right away)
            if len(self.calls) == 4 and all(c == 'Pass' for _, c in self.calls):
                self.is_complete = True
                self.passed_out = True
            elif len(self.calls) >= 4:
                # Check if last 3 calls were Pass following a bid
                if self.calls[-1][1] == 'Pass' and self.calls[-2][1] == 'Pass' and self.calls[-3][1] == 'Pass':
                    self.is_complete = True
        elif call == 'X':
            self.doubled = 'X'
        elif call == 'XX':
            self.doubled = 'XX'
        else:
            parsed = parse_bid(call)
            if parsed is not None:
                self.highest_bid = (parsed[0], parsed[1], player)
                self.doubled = 'None'

    def get_contract(self) -> dict | None:
        """Returns final contract dictionary once auction is complete."""
        if not self.is_complete or self.passed_out or self.highest_bid is None:
            return None

        level, strain, winning_bidder = self.highest_bid
        winning_side = PARTNERSHIP[winning_bidder]

        # Declarer is first player in partnership who bid this strain
        declarer = None
        for p, call in self.calls:
            parsed = parse_bid(call)
            if parsed and parsed[1] == strain and PARTNERSHIP[p] == winning_side:
                declarer = p
                break

        if declarer is None:
            declarer = winning_bidder

        dummy = PARTNERS[declarer]
        leader = clockwise_from(declarer)[1]
        tricks_needed = 6 + level

        return {
            'level': level,
            'strain': strain,
            'declarer': declarer,
            'dummy': dummy,
            'leader': leader,
            'tricks_needed': tricks_needed,
            'trump': strain if strain in SUITS else 'NT',
            'doubled': self.doubled,
            'vulnerability': self.vulnerability,
            'side': winning_side,
        }

