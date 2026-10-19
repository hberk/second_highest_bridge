"""Turn a finished board into double dummy analysis, one decision at a time.

A completed hand has every card visible, so this is double dummy: no sampling,
no uncertainty, just "what was the best available play and what did that cost".

Ordering matters more than it looks. Analysis points are returned **latest
trick first**, because cost collapses towards the end of a hand — the last few
tricks are microseconds and the opening lead is hours. Working backwards means
a caller on a time budget gets the endgame immediately and gives up only on the
early tricks, which is the right way round: it is also where a post-mortem is
most likely to find something actionable.

No Streamlit here. The progressive-fill UI lives in web/analysis_view.py.
"""
from __future__ import annotations
from typing import Dict, List, NamedTuple, Optional, Sequence

from card import Card
from game import PARTNERSHIP, PLAYERS, clockwise_from
from bridge.trick import legal_plays
from bridge.solver import api


class Decision(NamedTuple):
    """One moment in the play where a seat had a choice."""

    trick_num: int
    seat: str
    played: Card                      # what they actually played
    hands: Dict[str, List[Card]]      # every hand as it stood, before the play
    trick_so_far: List[Card]          # cards already face-up on this trick
    leader: str                       # who led this trick
    strain: str
    cards_each: int                   # hand size before the trick started

    @property
    def side(self) -> str:
        return PARTNERSHIP[self.seat]

    @property
    def choices(self) -> int:
        """Cards legally available. A forced play is not worth analysing."""
        led = self.trick_so_far[0].suit if self.trick_so_far else None
        return len(legal_plays(self.hands[self.seat], led))


def decisions(record: dict, seats: Optional[Sequence[str]] = None,
              max_cards: Optional[int] = None,
              skip_forced: bool = True) -> List[Decision]:
    """Every decision in a finished board, latest trick first.

    ``seats`` limits the result to the seats worth reviewing — usually the ones
    the human played. ``max_cards`` drops decisions from early tricks that are
    too deep to afford. ``skip_forced`` drops plays with only one legal card,
    which cost a full search to confirm that nothing could have been different.
    """
    if record.get('passed_out'):
        return []

    wanted = set(seats) if seats is not None else set(PLAYERS)
    strain = record['contract']['strain']
    hands = {seat: list(cards) for seat, cards in record['initial_hands'].items()}

    found: List[Decision] = []
    for entry in record['tricks_log']:
        leader = entry['leader']
        cards_each = len(hands[leader])
        table: List[Card] = []

        for seat, card in entry['plays']:
            if seat in wanted:
                found.append(Decision(
                    trick_num=entry['trick_num'],
                    seat=seat,
                    played=card,
                    hands={s: list(cs) for s, cs in hands.items()},
                    trick_so_far=list(table),
                    leader=leader,
                    strain=strain,
                    cards_each=cards_each,
                ))
            hands[seat].remove(card)
            table.append(card)

    if max_cards is not None:
        found = [d for d in found if d.cards_each <= max_cards]
    if skip_forced:
        found = [d for d in found if d.choices > 1]

    # Latest first: cheapest first, and the endgame is the useful part
    found.reverse()
    return found


def analyse(decision: Decision) -> dict:
    """Score one decision. Cost rises steeply with ``decision.cards_each``."""
    values = api.card_values(decision.hands, decision.strain, decision.leader,
                             decision.trick_so_far)
    if decision.played not in values:
        raise ValueError(f"{decision.played} was not legal for {decision.seat} "
                         f"on trick {decision.trick_num}")

    # Every value counts N/S tricks; flip the sense for a defender of that side
    for_north_south = decision.side == 'N/S'
    best = max(values.values()) if for_north_south else min(values.values())
    actual = values[decision.played]
    loss = (best - actual) if for_north_south else (actual - best)

    return {
        'trick_num': decision.trick_num,
        'seat': decision.seat,
        'side': decision.side,
        'played': decision.played,
        'played_value': actual,
        'best_value': best,
        'loss': loss,
        'was_best': loss == 0,
        'best_cards': sorted(
            (card for card, value in values.items() if value == best),
            key=lambda c: (c.suit, -c.value()),
        ),
        'values': values,
        'cards_each': decision.cards_each,
    }


def key_of(record: dict, decision: Decision) -> tuple:
    """Stable cache key for one decision of one board.

    The cache is shared by every session, so the board NUMBER alone collided:
    two players' board 1 (or a reloaded page's), and in challenge mode your
    board and the robots' board on the same deal. The deal and the play
    themselves are the identity.
    """
    deal = tuple(sorted((seat, tuple(str(c) for c in cards))
                        for seat, cards in record['initial_hands'].items()))
    play = tuple((seat, str(card)) for entry in record['tricks_log']
                 for seat, card in entry['plays'])
    return (hash((deal, play)), decision.trick_num, decision.seat)
