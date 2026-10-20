"""What the robots know when they play: no peeking at dummy before the opening
lead, show-outs in mid-hand play, and the lengths the auction showed.

Each is a switch in ai.py (NO_PEEK_OPENING_LEAD, SHOWOUT_MIDDLE,
AUCTION_IN_PLAY); the tests run with them as shipped.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai
import challenge
from card import Card
from game import AuctionState, PARTNERS, PLAYERS


def C(text: str) -> Card:
    return Card(text[-1], text[:-1])


def _contract(deal_id: int, dealer: str):
    hands = challenge.hands_for(deal_id)
    auction = AuctionState(dealer=dealer, vulnerability='None')
    while not auction.is_complete:
        who = auction.current_player()
        auction.apply_call(who, ai.ai_bid_explained(who, hands[who], auction)[0])
    return hands, auction.get_contract()


def test_the_opening_leader_never_sees_dummy():
    """Dummy goes down after the opening lead. Before, the robot leader was
    handed dummy's cards: 27 of 1,589 library leads changed (deals 164, 212)."""
    for deal_id in (164, 212) + tuple(range(20)):
        hands, contract = _contract(deal_id, 'North')
        if contract is None:
            continue
        leader = PLAYERS[(PLAYERS.index(contract['declarer']) + 1) % 4]
        trump = contract['trump']
        view = ai.visible_hands(leader, contract, hands)
        seen = ai.ai_play(leader, list(hands[leader]), [], trump, [], visible=view, history=[])
        blind = ai.ai_play(leader, list(hands[leader]), [], trump, [], visible={}, history=[])
        assert seen == blind, (deal_id, seen, blind)


def test_an_opponent_who_showed_out_holds_none_of_the_suit():
    """East second to play, South still to come: once South has shown out of
    spades, South can't hold a spade, so none is a threat to East's card."""
    hand = [C('KS'), C('9S'), C('4H')]
    trick = [('North', C('5S'))]
    pool = ai._later_holdings('East', hand, trick, [], {})
    assert any(c.suit == 'S' for c in pool)
    pool = ai._later_holdings('East', hand, trick, [], {}, {'South': {'S'}})
    assert not any(c.suit == 'S' for c in pool)
    # West is East's partner, not a threat: its show-out removes nothing.
    pool = ai._later_holdings('East', hand, trick, [], {}, {'West': {'S'}})
    assert any(c.suit == 'S' for c in pool)


def test_alerts_give_the_lengths_the_auction_showed():
    calls = [('North', '1S'), ('East', 'X'), ('South', '2NT'), ('West', '3H'),
             ('North', 'Pass'), ('East', '3D'), ('South', '3C')]
    alerts = {0: "5+ ♠, 11-21 HCP.", 1: "Negative: 4+ ♥ ♠, 8+ HCP.",
              2: "Unusual: 5+ ♣ and 5+ ♦, 8+ HCP.",
              3: "Support double: exactly 3 ♥.", 4: "Nothing to add.",
              5: "3+ ♦, usually 4. 11-21 HCP.", 6: "4+ ♥ and 4+ ♠. Artificial."}
    shown = ai.shown_lengths(calls, alerts)
    assert shown['North'] == {'S': 5}
    assert shown['East'] == {'H': 4, 'S': 4, 'D': 3}
    assert shown['South'] == {'C': 5, 'D': 5, 'H': 4, 'S': 4}
    assert shown['West'] == {'H': 3}


def test_the_opening_lead_is_partners_bid_suit():
    """Partner overcalled spades (5+): lead one, the second-highest as
    `_lead` would, even with a better-looking suit of my own."""
    hand = [C('QS'), C('7S'), C('AH'), C('KH'), C('QH'), C('JH'), C('2D'),
            C('3D'), C('4D'), C('5C'), C('6C'), C('7C'), C('8C')]
    shown = {'North': {}, 'East': {'S': 5}, 'South': {}, 'West': {}}
    assert ai._partner_suit_lead('West', hand, 'H', shown) == C('7S')
    # Not when partner's suit is trumps, nor with nothing in it, nor on a
    # four-card showing (a negative double's 4+).
    assert ai._partner_suit_lead('West', hand, 'S', shown) is None
    assert ai._partner_suit_lead('West', [c for c in hand if c.suit != 'S'], 'H', shown) is None
    assert ai._partner_suit_lead('West', hand, 'H', {'East': {'S': 4}}) is None


def test_layouts_fit_the_bidding():
    """A defender who bid 5+ in a suit can't hold fewer: `_splits` drops the
    layouts that would give them less."""
    hand = [C('AH'), C('KH'), C('QH'), C('2C'), C('3C'), C('4C'), C('5C'),
            C('6C'), C('7C'), C('8C'), C('9C'), C('10C'), C('JC')]
    seen = set(hand)
    outstanding = [c.value() for c in ai._FULL_DECK if c.suit == 'H' and c not in seen]
    free = ai._splits('North', hand, 'H', outstanding, seen, [])
    left = PLAYERS[(PLAYERS.index('North') + 1) % 4]
    bid = ai._splits('North', hand, 'H', outstanding, seen, [], {left: {'H': 5}})
    assert any(len(a) < 5 for a, _, _ in free)
    assert bid and all(len(a) >= 5 for a, _, _ in bid)


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print("All assertions passed.")
