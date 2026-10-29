from __future__ import annotations
import random
import sys
from pathlib import Path

# Ensure root directory is on python path when running tests from tests/ directory
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from card import Card, SUITS, STRAINS, deal, bid_index, parse_bid
from game import AuctionState, legal_plays, resolve_trick, score_contract, clockwise_from, PARTNERSHIP
from ai import eval_hand_sh, ai_bid, ai_play


def _raises_value_error(fn) -> bool:
    try:
        fn()
    except ValueError:
        return True
    return False


def test_bidding_ladder_and_parsing():
    # 1. Spot checks on bidding ladder indices
    assert bid_index(1, 'C') == 0
    assert bid_index(1, 'D') == 1
    assert bid_index(1, 'H') == 2
    assert bid_index(1, 'S') == 3
    assert bid_index(1, 'NT') == 4
    assert bid_index(2, 'C') == 5
    assert bid_index(7, 'NT') == 34
    assert bid_index(1, 'S') > bid_index(1, 'H')
    assert bid_index(2, 'C') > bid_index(1, 'NT')

    # 2. Exhaustive test: verify all 35 bids from 1C to 7NT strictly increment from 0 to 34
    expected_index = 0
    prev_idx = -1
    for level in range(1, 8):
        for strain in STRAINS:
            idx = bid_index(level, strain)
            assert idx == expected_index, f"Expected {level}{strain} to have index {expected_index}, got {idx}"
            assert idx > prev_idx, f"Bid {level}{strain} ({idx}) not strictly greater than previous ({prev_idx})"
            prev_idx = idx
            expected_index += 1

            # Round-trip parse test for every legal contract bid
            bid_str = f"{level}{strain}"
            parsed = parse_bid(bid_str)
            assert parsed == (level, strain), f"Failed to parse legal bid '{bid_str}'"
    assert expected_index == 35, "Total number of bridge bids should be exactly 35"

    # 3. Non-contract calls return None
    assert parse_bid('Pass') is None
    assert parse_bid('X') is None
    assert parse_bid('XX') is None

    # 4. Invalid strings and edge cases return None
    assert parse_bid('') is None
    assert parse_bid('0C') is None   # Invalid level (< 1)
    assert parse_bid('8C') is None   # Invalid level (> 7)
    assert parse_bid('1Z') is None   # Invalid strain
    assert parse_bid('1') is None    # Incomplete (no strain)
    assert parse_bid('NT') is None   # Incomplete (no level)
    assert parse_bid('foo') is None  # Random string


def test_auction_passed_out():
    auction = AuctionState(dealer='North', vulnerability='None')
    assert auction.current_player() == 'North'
    auction.apply_call('North', 'Pass')
    assert auction.current_player() == 'East'
    auction.apply_call('East', 'Pass')
    assert auction.current_player() == 'South'
    auction.apply_call('South', 'Pass')
    assert auction.current_player() == 'West'
    assert not auction.is_complete
    auction.apply_call('West', 'Pass')
    assert auction.is_complete
    assert auction.passed_out
    assert auction.get_contract() is None


def test_auction_contract_and_declarer():
    # North opens 1H, East passes, South raises 2H, West passes, North bids 4H, East passes, South passes, West passes
    auction = AuctionState(dealer='North', vulnerability='None')
    auction.apply_call('North', '1H')
    auction.apply_call('East', 'Pass')
    auction.apply_call('South', '2H')
    auction.apply_call('West', 'Pass')
    auction.apply_call('North', '4H')
    auction.apply_call('East', 'Pass')
    auction.apply_call('South', 'Pass')
    assert not auction.is_complete  # 2 passes
    auction.apply_call('West', 'Pass')
    assert auction.is_complete

    contract = auction.get_contract()
    assert contract is not None
    assert contract['level'] == 4
    assert contract['strain'] == 'H'
    assert contract['declarer'] == 'North'  # North first bid Hearts
    assert contract['dummy'] == 'South'
    assert contract['leader'] == 'East'     # Left of North
    assert contract['tricks_needed'] == 10
    assert contract['trump'] == 'H'
    assert contract['side'] == 'N/S'


def test_declarer_transfer_of_strain():
    # South bid 1NT, North raised to 3NT -> South is declarer
    auction = AuctionState(dealer='West', vulnerability='Both')
    auction.apply_call('West', 'Pass')
    auction.apply_call('North', 'Pass')
    auction.apply_call('East', 'Pass')
    auction.apply_call('South', '1NT')
    auction.apply_call('West', 'Pass')
    auction.apply_call('North', '3NT')
    auction.apply_call('East', 'Pass')
    auction.apply_call('South', 'Pass')
    auction.apply_call('West', 'Pass')
    assert auction.is_complete

    contract = auction.get_contract()
    assert contract is not None
    assert contract['level'] == 3
    assert contract['strain'] == 'NT'
    assert contract['declarer'] == 'South'  # South first bid NT
    assert contract['dummy'] == 'North'
    assert contract['leader'] == 'West'     # Left of South
    assert contract['tricks_needed'] == 9


def test_double_and_redouble():
    auction = AuctionState(dealer='South', vulnerability='N/S')
    auction.apply_call('South', '1S')
    assert 'X' in auction.legal_calls()
    auction.apply_call('West', 'X')  # Opponent doubles
    assert auction.doubled == 'X'
    assert 'XX' in auction.legal_calls()
    auction.apply_call('North', 'XX') # Partner redoubles
    assert auction.doubled == 'XX'
    auction.apply_call('East', 'Pass')
    auction.apply_call('South', 'Pass')
    auction.apply_call('West', 'Pass')
    assert auction.is_complete

    contract = auction.get_contract()
    assert contract['doubled'] == 'XX'


def test_auction_rejects_out_of_turn_calls():
    auction = AuctionState(dealer='North')
    assert _raises_value_error(lambda: auction.apply_call('East', 'Pass'))
    assert auction.calls == []


def test_auction_rejects_insufficient_bids():
    auction = AuctionState(dealer='North')
    auction.apply_call('North', '1H')
    legal = auction.legal_calls()
    assert '1C' not in legal and '1H' not in legal
    assert '1S' in legal
    assert _raises_value_error(lambda: auction.apply_call('East', '1D'))


def test_double_and_redouble_restrictions():
    auction = AuctionState(dealer='North')
    auction.apply_call('North', '1H')
    auction.apply_call('East', 'Pass')
    assert 'X' not in auction.legal_calls()     # South can't double partner's bid
    assert 'XX' not in auction.legal_calls()    # nothing to redouble yet
    assert _raises_value_error(lambda: auction.apply_call('South', 'X'))
    auction.apply_call('South', 'Pass')
    auction.apply_call('West', 'X')
    assert 'XX' in auction.legal_calls()        # North (the doubled side) may redouble
    auction.apply_call('North', 'Pass')
    assert 'XX' not in auction.legal_calls()    # East (the doubling side) may not
    auction.apply_call('East', '2C')
    assert auction.doubled == 'None'            # a new bid wipes out the double


def test_auction_closed_after_completion():
    auction = AuctionState(dealer='North')
    for p in ('North', 'East', 'South', 'West'):
        auction.apply_call(p, 'Pass')
    assert auction.legal_calls() == []
    assert _raises_value_error(lambda: auction.apply_call('North', '1C'))


def test_duplicate_scoring():
    # 1. 2S made 8 tricks (non-vul): 60 contract + 50 part-score = 110
    c1 = {'level': 2, 'strain': 'S', 'declarer': 'South', 'dummy': 'North', 'leader': 'West', 'tricks_needed': 8, 'trump': 'S', 'doubled': 'None', 'vulnerability': 'None', 'side': 'N/S'}
    s1 = score_contract(c1, {'N/S': 8, 'E/W': 5})
    assert s1['made'] is True
    assert s1['points'] == 110

    # 2. 4S made 10 tricks (non-vul): 120 contract + 300 game = 420
    c2 = {'level': 4, 'strain': 'S', 'declarer': 'South', 'dummy': 'North', 'leader': 'West', 'tricks_needed': 10, 'trump': 'S', 'doubled': 'None', 'vulnerability': 'None', 'side': 'N/S'}
    s2 = score_contract(c2, {'N/S': 10, 'E/W': 3})
    assert s2['made'] is True
    assert s2['points'] == 420

    # 3. 4S made 10 tricks (vul): 120 contract + 500 game = 620
    c3 = {'level': 4, 'strain': 'S', 'declarer': 'South', 'dummy': 'North', 'leader': 'West', 'tricks_needed': 10, 'trump': 'S', 'doubled': 'None', 'vulnerability': 'N/S', 'side': 'N/S'}
    s3 = score_contract(c3, {'N/S': 10, 'E/W': 3})
    assert s3['points'] == 620

    # 4. 3NT made 10 tricks (+1 overtrick, vul): (40+30+30=100) + 500 game + 30 overtrick = 630
    c4 = {'level': 3, 'strain': 'NT', 'declarer': 'North', 'dummy': 'South', 'leader': 'East', 'tricks_needed': 9, 'trump': 'NT', 'doubled': 'None', 'vulnerability': 'Both', 'side': 'N/S'}
    s4 = score_contract(c4, {'N/S': 10, 'E/W': 3})
    assert s4['points'] == 630

    # 5. 4S down 2 (non-vul, undoubled): 2 * 50 = 100 to E/W
    s5 = score_contract(c2, {'N/S': 8, 'E/W': 5})
    assert s5['made'] is False
    assert s5['winner'] == 'E/W'
    assert s5['points'] == 100

    # 6. 4S down 2 (vul, doubled): 1st down = 200, 2nd down = 300 -> 500 to E/W
    c6 = {'level': 4, 'strain': 'S', 'declarer': 'South', 'dummy': 'North', 'leader': 'West', 'tricks_needed': 10, 'trump': 'S', 'doubled': 'X', 'vulnerability': 'Both', 'side': 'N/S'}
    s6 = score_contract(c6, {'N/S': 8, 'E/W': 5})
    assert s6['points'] == 500


def test_full_ai_game_simulation():
    """AI bids and plays 40 seeded deals: every card legal, 13 tricks, a valid score."""
    played_out = 0
    for seed in range(40):
        random.seed(seed)
        hands = deal()
        auction = AuctionState(dealer=['North', 'East', 'South', 'West'][seed % 4], vulnerability='None')
        while not auction.is_complete:
            curr_p = auction.current_player()
            auction.apply_call(curr_p, ai_bid(curr_p, hands[curr_p], auction))
        if auction.passed_out:
            continue

        contract = auction.get_contract()
        trump, leader, dummy = contract['trump'], contract['leader'], contract['dummy']
        played: list[Card] = []
        tricks_taken = {'N/S': 0, 'E/W': 0}
        for _ in range(13):
            trick: list[tuple[str, Card]] = []
            for player in clockwise_from(leader):
                led = trick[0][1].suit if trick else None
                c = ai_play(player, hands[player], trick, trump, played, visible={dummy: hands[dummy]})
                assert c in legal_plays(hands[player], led), f"seed {seed}: {player} played illegal {c}"
                hands[player].remove(c)
                trick.append((player, c))
            leader = resolve_trick(trick, trump)
            tricks_taken[PARTNERSHIP[leader]] += 1
            played.extend(c for _, c in trick)

        assert tricks_taken['N/S'] + tricks_taken['E/W'] == 13
        res = score_contract(contract, tricks_taken)
        assert res['winner'] in ('N/S', 'E/W') and res['points'] > 0
        played_out += 1

    assert played_out >= 10, f"only {played_out}/40 seeded deals reached play"


def test_second_seat_covers_with_queen():
    """Dummy leads K♠ holding A♠J♠; East with Q♠3♠ must play the Q, not the 3."""
    trick = [('North', Card('S', 'K'))]
    east = [Card('S', 'Q'), Card('S', '3'), Card('H', '5'), Card('D', '7')]
    dummy_rest = [Card('S', 'A'), Card('S', 'J'), Card('H', '9')]

    with_dummy = ai_play('East', east, trick, 'S', [], visible={'North': dummy_rest})
    assert with_dummy == Card('S', 'Q'), f"expected Q♠ with dummy visible, got {with_dummy}"

    without_dummy = ai_play('East', east, trick, 'S', [])
    assert without_dummy == Card('S', 'Q'), f"expected Q♠ with dummy unknown, got {without_dummy}"

    # With A♠3♠, the A would sit on top and hand the trick to the K — duck the 3.
    east_ace = [Card('S', 'A'), Card('S', '3'), Card('H', '5')]
    ducked = ai_play('East', east_ace, trick, 'S', [])
    assert ducked == Card('S', '3'), f"expected 3♠ duck, got {ducked}"


def test_third_seat_covers_to_promote_partners_card():
    """The play this variant turns on. Partner's K is the highest card out and so
    loses; South's A pushes it down into second place, where it wins. The old
    scoring only ever accepted cards that landed second-highest *themselves*, so
    it never found this and threw the 3 away instead."""
    trick = [('North', Card('H', 'K')), ('East', Card('H', '4'))]
    south = [Card('H', 'A'), Card('H', '3'), Card('S', '9')]

    played = ai_play('South', south, trick, 'S', [])
    assert played == Card('H', 'A'), f"expected AH to promote partner's K, got {played}"
    assert resolve_trick(trick + [('South', played)], 'S') == 'North'


def test_third_seat_does_not_hide_behind_a_fragile_partner():
    """Partner's 9 is second-highest of two cards, so the old code read "partner is
    winning" and played low — but any unseen 10 or J displaces the 9. The Q holds
    the trick outright and nothing outstanding can take it."""
    trick = [('North', Card('H', '9')), ('East', Card('H', 'K'))]
    south = [Card('H', 'A'), Card('H', 'Q'), Card('H', '2'), Card('S', '7')]

    played = ai_play('South', south, trick, 'S', [])
    assert played == Card('H', 'Q'), f"expected QH, got {played}"
    assert resolve_trick(trick + [('South', played)], 'S') == 'South'


def test_third_seat_still_ducks_behind_a_safe_partner():
    """No regression where the old branch was right: partner's Q is already
    second-highest and no outstanding card dislodges it, so South plays low."""
    trick = [('North', Card('H', 'Q')), ('East', Card('H', 'A'))]
    south = [Card('H', 'K'), Card('H', '6'), Card('H', '2'), Card('S', '7')]

    played = ai_play('South', south, trick, 'S', [])
    assert played == Card('H', '2'), f"expected the 2H duck, got {played}"
    assert resolve_trick(trick + [('South', played)], 'S') == 'North'


def test_third_seat_spends_nothing_on_a_lost_trick():
    """Partner's 2 cannot survive and no card of South's changes that, so the
    cheapest equivalent card goes — the A is not thrown at it."""
    trick = [('North', Card('H', '2')), ('East', Card('H', '5'))]
    south = [Card('H', 'A'), Card('H', '4'), Card('H', '3'), Card('S', '8')]

    played = ai_play('South', south, trick, 'S', [])
    assert played == Card('H', '3'), f"expected the cheap 3H, got {played}"


def test_middle_play_follows_suit_and_plays_from_hand():
    """The survival scoring must never talk the AI into a revoke."""
    random.seed(404)
    for _ in range(200):
        hands = deal()
        lead = hands['North'][0]
        east_legal = [c for c in hands['East'] if c.suit == lead.suit] or hands['East']
        trick = [('North', lead), ('East', east_legal[0])]
        got = ai_play('South', hands['South'], trick, 'S', [])
        assert got in hands['South']
        if any(c.suit == lead.suit for c in hands['South']):
            assert got.suit == lead.suit, f"revoked: led {lead.suit}, played {got}"


def test_defender_cashes_a_sure_trick_seen_through_dummy():
    """Deal 92, 1NT by North: East wins the J♦ at trick 2 with K765 of clubs,
    dummy's J1032 in view and the 8♣ 9♣ 4♣ gone. The A♣ is the only club East
    can't see, so its holder must play it under the K♣ -- a sure trick. The 7♣
    (what East used to lead) loses to dummy's J♣, and the king never scores."""
    import challenge
    hands = challenge.hands_for(92)
    tricks = [[('East', Card('C', 'Q')), ('South', Card('C', '8')),
               ('West', Card('C', '4')), ('North', Card('C', '9'))],
              [('North', Card('D', 'Q')), ('East', Card('D', 'J')),
               ('South', Card('D', '3')), ('West', Card('D', '5'))]]
    played = []
    for trick in tricks:
        for seat, card in trick:
            hands[seat].remove(card)
            played.append(card)
    got = ai_play('East', hands['East'], [], None, played,
                  visible={'South': hands['South']}, history=tricks)
    assert got == Card('C', 'K'), f"expected the sure K♣, got {got}"


def test_a_trick_declarer_could_ruff_is_not_sure():
    """The same K♣ over a lone unseen A♣ is sure in notrump, but not in spades:
    with the A♣ on declarer's left, declarer may be void and ruff."""
    import ai
    east = [Card('C', 'K'), Card('C', '5')]
    dummy = [Card('C', 'J'), Card('C', '10')]
    played = [Card('C', r) for r in ('2', '3', '4', '6', '7', '8', '9', 'Q')]
    view = {'South': dummy}
    assert ai._sure_lead('East', east, None, played, view, []) == Card('C', 'K')
    assert ai._sure_lead('East', east, 'S', played, view, []) is None



def _cards(text: str) -> list[Card]:
    return [Card(suit, '10' if r == 'T' else r)
            for suit, part in zip('SHDC', text.split()) if part != '-' for r in part]


def test_partners_game_stands_and_a_three_level_lone_rebid_shows_six():
    """The user's training deal (2026-10-28): 1S 3D P P 3S P 4S P, and North
    bid 5S. The previous system read 4S as a raise and, with 4S gone, bid on."""
    import ai
    north = _cards('AJ8432 Q862 - AKQ')
    a = AuctionState('North', 'None')
    for who, call in [('North', '1S'), ('East', '3D'), ('South', 'Pass'), ('West', 'Pass')]:
        a.apply_call(who, call)
    assert ai.ai_bid_explained('North', north, a) == ('3S', '6+ \u2660. Rebidding my own suit.')
    five = _cards('AJ843 Q862 - AKQ2')
    assert ai.ai_bid('North', five, a) == 'Pass'
    for who, call in [('North', '3S'), ('East', 'Pass'), ('South', '4S'), ('West', 'Pass')]:
        a.apply_call(who, call)
    assert ai.ai_bid('North', north, a) == 'Pass'


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
    print("All bidding and scoring tests passed successfully!")
