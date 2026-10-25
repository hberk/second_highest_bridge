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


def test_the_fast_search_gives_the_plain_searchs_answer():
    """`_fast_search` (alpha-beta, rank equivalence) must agree with `_search`
    exactly: the deeper endgame relies on it."""
    import random
    rnd = random.Random(20261020)
    for n in (2, 3, 4):
        for _ in range(25):
            deck = list(ai._FULL_DECK)
            rnd.shuffle(deck)
            hands = {p: deck[i * n:(i + 1) * n] for i, p in enumerate(PLAYERS)}
            trump = rnd.choice(['S', 'H', 'D', 'C', None])
            leader = rnd.choice(PLAYERS)
            slow = ai._search({p: list(h) for p, h in hands.items()}, [], leader, trump, 'N/S', {})
            fast = ai._fast_search({p: list(h) for p, h in hands.items()}, [], leader, trump, 'N/S', {})
            assert slow == fast, (hands, trump, leader, slow, fast)


def test_a_human_call_reads_the_way_gib_means_it():
    """The robots read a human's call by GIB's alert for it, not by the
    human's self-alert: an opening 1S is 5+ spades."""
    from meanings import gib_alert
    auction = AuctionState(dealer='North', vulnerability='None')
    assert gib_alert(auction, '1S') == "5+ \u2660, 11-21 HCP."
    assert gib_alert(auction, 'Pass') is None
    auction.apply_call('North', '1H')
    why = gib_alert(auction, '2NT')       # East: Unusual, the two lowest unbid
    assert why and '5+ \u2663' in why and '5+ \u2666' in why, why


def test_the_searches_stay_exact_when_their_memory_is_shared():
    """The endgame searches each candidate card with one memory per layout.
    A position already known exactly used to be searched again with an empty
    window and its entry overwritten with a wrong bound (deal 4: West's 3D
    scored 43 where it is worth 46). Both searches must give `_search`'s
    answer for every card in turn."""
    import random
    from game import legal_plays
    # The position it was found in (deal 4, clubs trumps): South led the
    # 9D, West to play from AH KD 6D 3D. Each of West's diamonds in turn, one
    # memory: the 3D is worth 3 tricks to E/W, as searched fresh.
    hands = {'West': ['AH', 'KD', '6D', '3D'], 'East': ['9S', '8H', '5D', '9C'],
             'North': ['10D', 'JD', 'QD', 'KH'], 'South': ['7D', 'AD', 'AS']}
    masks = [sum(1 << ai._bit(C(c)) for c in hands[p]) for p in PLAYERS]
    west, south = PLAYERS.index('West'), PLAYERS.index('South')
    for search in ('fast', 'bit'):
        memo: dict = {}
        got = []
        for card in ('KD', '6D', '3D'):
            if search == 'bit':
                masks[west] ^= 1 << ai._bit(C(card))
                got.append(ai._bit_search(masks, ((south, ai._bit(C('9D'))), (west, ai._bit(C(card)))),
                                          south, ai.SUITS.index('C'), False, memo))
                masks[west] ^= 1 << ai._bit(C(card))
            else:
                h = {p: [C(c) for c in v if not (p == 'West' and c == card)] for p, v in hands.items()}
                got.append(ai._fast_search(h, [('South', C('9D')), ('West', C(card))],
                                           'South', 'C', 'E/W', memo))
        assert got == [2, 3, 3], (search, got)
    rnd = random.Random(11)
    for n in (2, 3, 4):
        for _ in range(60):
            deck = list(ai._FULL_DECK)
            rnd.shuffle(deck)
            hands = {p: deck[i * n:(i + 1) * n] for i, p in enumerate(PLAYERS)}
            trump = rnd.choice(['S', 'H', 'D', 'C', None])
            leader = rnd.choice(PLAYERS)
            side = rnd.choice(['N/S', 'E/W'])
            fast, bits = {}, {}
            for card in legal_plays(hands[leader], None):
                h = {p: list(v) for p, v in hands.items()}
                h[leader].remove(card)
                exact = ai._search({p: list(v) for p, v in h.items()}, [(leader, card)],
                                   leader, trump, side, {})
                assert ai._fast_search({p: list(v) for p, v in h.items()}, [(leader, card)],
                                       leader, trump, side, fast) == exact
                masks = [sum(1 << ai._bit(c) for c in h[p]) for p in PLAYERS]
                assert ai._bit_search(masks, ((PLAYERS.index(leader), ai._bit(card)),),
                                      PLAYERS.index(leader),
                                      ai.SUITS.index(trump) if trump else None,
                                      side == 'N/S', bits) == exact


def test_the_bit_trick_winner_follows_the_rules():
    import random
    from game import resolve_trick
    rnd = random.Random(2)
    for _ in range(3000):
        cards = rnd.sample(ai._FULL_DECK, 4)
        lead = rnd.randrange(4)
        trump = rnd.choice(['C', 'D', 'H', 'S', None])
        trick = [(PLAYERS[(lead + k) % 4], c) for k, c in enumerate(cards)]
        bits = tuple((PLAYERS.index(p), ai._bit(c)) for p, c in trick)
        winner = ai._bit_winner(bits, ai.SUITS.index(trump) if trump else None)
        assert PLAYERS[winner] == resolve_trick(trick, trump)


def test_a_natural_suit_bid_with_no_number_is_a_floor_of_one():
    """Board 17: "Longest suit other than theirs, ♥" names no length, but it
    is still partner's suit. Artificial calls and splinters show nothing."""
    calls = [('North', 'Pass'), ('East', '1S'), ('South', 'X'), ('West', 'XX'),
             ('North', '2H'), ('East', '2C'), ('South', '4D')]
    alerts = {1: "5+ ♠, 11-21 HCP.", 2: "Takeout: 12+ HCP.", 3: "10+ HCP.",
              4: "Longest suit other than theirs, ♥. Answering the double.",
              5: "Stayman: asks for a 4-card major. Artificial.",
              6: "Splinter: 4+ ♥, short ♦, 13-15 HCP."}
    shown = ai.shown_lengths(calls, alerts)
    assert shown['North'] == {'H': 1}
    assert shown['East'] == {'S': 5}
    assert shown['South'] == {'H': 4}


def test_board_17_leads_partners_hearts_at_trick_one_and_trick_three():
    """North answered South's double with 2♥; East played 2♠. South, with
    ♥KJ73, leads the J♥ (the second-highest, as any lead), not the Q♣."""
    def hand(text):
        out = []
        for suit, cards in zip('SHDC', text.split()):
            out += [Card(suit, '10' if r == 'T' else r) for r in cards]
        return out
    south = hand('95 KJ73 A97 KQT6')
    shown = {'North': {'H': 1}, 'East': {'S': 5}, 'South': {}, 'West': {}}
    assert ai.ai_play('South', south, [], 'S', [], shown=shown) == C('JH')
    # Later, on lead again with dummy down: still hearts while nobody is out
    # (the card is the defender suit plan's, from deal 356).
    dummy = hand('876 AT8 KQ J7432')
    played = [C('QC'), C('JC'), C('8C'), C('5C'), C('6S'), C('2S'), C('4S'), C('5S')]
    history = [[('South', C('QC')), ('West', C('JC')), ('North', C('8C')), ('East', C('5C'))],
               [('West', C('6S')), ('North', C('2S')), ('East', C('4S')), ('South', C('5S'))]]
    left = [c for c in south if c not in played]
    lead = ai.ai_play('South', left, [], 'S', played, visible={'West': dummy},
                      history=history, shown=shown)
    assert lead.suit == "H", lead
    # Not once declarer has shown out: that gives a ruff.
    history.append([('South', C('JH')), ('West', C('8H')), ('North', C('QH')), ('East', C('4S'))])
    assert ai._fit_lead('South', left, 'S', shown, history, {'West': dummy}) is None


def test_a_defender_leads_back_the_suit_partner_is_out_of():
    """Partner showed out of clubs and may still hold a trump: lead a club
    (my lowest) for the ruff."""
    hand = [C('KC'), C('4C'), C('AD'), C('5D')]
    history = [[('East', C('2H')), ('South', C('3H')), ('West', C('4H')), ('North', C('5H'))],
               [('East', C('3C')), ('South', C('5C')), ('West', C('7S')), ('North', C('6C'))]]
    assert ai._ruff_return('East', hand, 'S', history, {'North': [C('9D')]}) == C('4C')
    # Not once partner is out of trumps too.
    history.append([('North', C('2S')), ('East', C('6D')), ('South', C('3S')), ('West', C('8H'))])
    assert ai._ruff_return('East', hand, 'S', history, {'North': [C('9D')]}) is None


def test_partners_lead_reads_as_a_singleton_when_the_higher_cards_are_in_sight():
    """West led the 10 of diamonds. Every higher diamond is in my hand or
    dummy's, and the robots lead the second-highest from two or more, so the
    ten was a singleton: lead a diamond back before West shows out."""
    east = [C('AD'), C('KD'), C('QD'), C('3D'), C('AH'), C('2H')]
    dummy = [C('JD'), C('9D'), C('KH'), C('QH'), C('JH'), C('5C')]
    history = [[('West', C('10D')), ('North', C('9D')), ('East', C('AD')), ('South', C('2D'))]]
    east.remove(C('AD')); dummy.remove(C('9D'))
    shown = {'North': {}, 'East': {}, 'South': {'S': 5}, 'West': {}}
    assert ai._short_lead('East', east, 'S', history, {'North': dummy}, shown) == 'D'
    assert ai._ruff_return('East', east, 'S', history, {'North': dummy}, shown) == C('3D')
    # Partner's own bid suit is led from length: no reading.
    assert ai._short_lead('East', east, 'S', history, {'North': dummy},
                          {**shown, 'West': {'D': 5}}) is None


def test_an_honour_lead_is_read_by_counting_alone():
    """Deal 356: South led the K♥ from K-7-3-2. Every higher heart was in
    sight, so by the lead convention it was a singleton; an honour's card
    isn't read, and by counting alone it is too often from length."""
    from test_card_play_rules import replay, DEAL_356
    hands, played, history = replay(356, DEAL_356)
    view = ai.visible_hands('North', {'declarer': 'East', 'dummy': 'West'}, hands)
    assert ai._short_lead('North', hands['North'], 'S', history, view, None) is None


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print("All assertions passed.")
