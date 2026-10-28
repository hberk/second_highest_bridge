"""Regression tests for level discipline in ai_bid.

Two bugs are pinned here, and they are the same underlying mistake: bidding a
level the hand has no reason to think it can make.

The first is historical — a re-raise cascade that treated partner's raise of a
suit this hand had bid as a fresh suit to raise again, bouncing single raises to
the 4-level on 35% of all-AI boards.

The second was introduced during the double-dummy rewrite and caught by a smoke
test before it shipped: `_cheapest` climbed to whatever was legal, so in a
contested auction "raise to the 2-level" found no legal 2-bid and walked up to
SEVEN. It put 14 of 40 contracts at the 7-level. ai_bid now caps every raise at
`int(combined estimate) - 6` — the highest level the fit is expected to make.

The hands below pin their own evaluation in the test that uses them, so a later
change to eval_hand_sh fails with a clear message instead of silently changing
what the behaviour tests exercise.
"""
from __future__ import annotations
import random
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import ai
import gib
from card import Card, deal, parse_bid
from game import AuctionState, PARTNERS, PLAYERS

ALL_CALLS = [f"{level}{strain}" for level in range(1, 8)
             for strain in ('C', 'D', 'H', 'S', 'NT')]


def hand(text: str) -> list:
    """'AS 10H 2C' -> [Card('S','A'), Card('H','10'), Card('C','2')]."""
    return [Card(token[-1], token[:-1]) for token in text.split()]


def auction_after(*calls: str, dealer: str = 'North') -> AuctionState:
    auction = AuctionState(dealer=dealer, vulnerability='None')
    for call in calls:
        auction.apply_call(auction.current_player(), call)
    return auction


#: Five-card spade support with ordinary honours: enough that opposite an opening
#: the partnership estimate clears GAME_TRICKS.
BIG_SPADE_SUPPORT = hand('QS JS 9S 8S 6S 5S 3S 8H 6H 5H QD 10D QC')

#: Four-card club support with ordinary honours: worth the partscore opposite an
#: opening, but nowhere near game — and a minor fit has no game to reach anyway.
CLUB_SUPPORT = hand('KS 10S 7S QH 10H 7H 3H JD 10D KC QC JC 10C')

#: Three small clubs and nothing at all. Enough to enter the support branch, far
#: too little to justify raising into a contested auction.
MINIMUM_CLUB_SUPPORT = hand('8S 6S 4S 9H 7H 5H 3H 8D 6D 4D QC 9C 5C')


def test_game_call_is_four_of_a_major_and_nothing_else():
    """Five of a minor needs eleven tricks (makeable 11%); 3NT needs nine and
    loses to the suit fit even when it makes. A minor fit has no game to bid."""
    assert ai._game_call('S', ALL_CALLS) == '4S'
    assert ai._game_call('H', ALL_CALLS) == '4H'
    assert ai._game_call('C', ALL_CALLS) is None
    assert ai._game_call('D', ALL_CALLS) is None

    for strain in ('C', 'D', 'H', 'S'):
        call = ai._game_call(strain, ALL_CALLS)
        assert call != '3NT'
        assert call not in ('5C', '5D'), "five of a minor is never worth bidding"
        assert call not in ('4C', '4D'), "four of a minor scores as a partscore"


def test_a_major_fit_worth_game_reaches_four():
    combined = (ai.eval_hand_sh(BIG_SPADE_SUPPORT)['suit_pts']['S']
                + ai.PROMISE_OPENED)
    assert combined >= ai.GAME_TRICKS, \
        f"hand no longer clears the game threshold ({combined:.2f})"

    auction = auction_after('1S', 'Pass')      # North opens, East passes, South to call
    assert auction.current_player() == 'South'
    assert ai.ai_bid('South', BIG_SPADE_SUPPORT, auction) == '4S'


def test_inverted_minors():
    """GIB plays inverted minors: 1m-2m is the STRONG raise (10+, forcing) and
    1m-3m the weak one. A four-card major is shown first."""
    strong = hand('KS 7S 3S QH 10H 7H JD 10D KC QC JC 10C 4C')
    assert gib.Hand(strong).hcp >= gib.INVERTED_MIN
    call, why = ai.ai_bid_explained('South', strong, auction_after('1C', 'Pass'))
    assert call == '2C' and 'Inverted' in why, (call, why)

    weak = hand('8S 6S 4S 9H 7H 3D 2D QC 9C 8C 7C 5C 2C')
    call, why = ai.ai_bid_explained('South', weak, auction_after('1C', 'Pass'))
    assert gib.Hand(weak).hcp < gib.RESPONSE_MIN and call == 'Pass', (call, why)

    shaped = hand('8S 6S 4S 9H 7H 3D AD QC 9C 8C 7C 5C JC')
    call, why = ai.ai_bid_explained('South', shaped, auction_after('1C', 'Pass'))
    assert call == '3C' and 'Weak' in why, (call, why)

    # The four-card heart suit comes first, whatever the club support.
    assert ai.ai_bid('South', CLUB_SUPPORT, auction_after('1C', 'Pass')) == '1H'


def test_a_weak_hand_leaves_partner_at_the_one_level():
    """Underbidding is nearly free, so a hand with nothing does not raise at all."""
    combined = (ai.eval_hand_sh(MINIMUM_CLUB_SUPPORT)['suit_pts']['C']
                + ai.PROMISE_OPENED)
    assert combined < ai.PARTSCORE_LEVEL + 6, (
        f"hand must be too weak for the 2-level ({combined:.2f})")

    auction = auction_after('1C', 'Pass')
    assert ai.ai_bid('South', MINIMUM_CLUB_SUPPORT, auction) == 'Pass'


def test_a_raise_never_climbs_past_what_the_fit_can_make():
    """The 7-level bug. In a contested auction the cheapest legal call in our
    suit can be 7C; bidding it because it is 'the cheapest raise' is absurd."""
    auction = auction_after('1C', '6H')
    assert auction.current_player() == 'South'
    legal = auction.legal_calls()
    assert ai._cheapest('C', ai.PARTSCORE_LEVEL, legal) == '7C', \
        "precondition: the cheapest club raise here really is at the 7-level"

    call = ai.ai_bid('South', MINIMUM_CLUB_SUPPORT, auction)
    assert call == 'Pass', f"bid {call} rather than passing a hopeless 7-level raise"


def test_no_runaway_levels_over_many_boards():
    """The same guard, swept over real deals rather than one built position:
    GIB bids games and slams, but a five-level contract still needs the
    values for one. Except a jam (`gib.JAM_GAME`): ten trumps bid five of a
    minor on purpose, to make or to take their game away. And except five
    bid straight over their four-level game, a sacrifice: seed 11 board 112,
    1C (1S) 2H (2S) 3H P 4H (4S) P P 5H on 21 HCP, one down double dummy
    against their 4S making (NEG_BIDS_FIVE's 2H first reached it)."""
    random.seed(11)
    for index in range(200):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        guard = 0
        jams = set()
        while not auction.is_complete and guard < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)
            if 'to jam the auction' in why:
                jams.add((who, call))
            auction.apply_call(who, call)
            guard += 1
        contract = auction.get_contract()
        jammed = any(who in (contract['declarer'], PARTNERS[contract['declarer']])
                     for who, _ in jams) if contract else False
        bids = [(who, c) for who, c in auction.calls if c not in ('Pass', 'X', 'XX')]
        saved = (contract is not None and contract['level'] == 5 and len(bids) >= 2
                 and bids[-2][1][0] == '4'
                 and bids[-2][0] not in (contract['declarer'], PARTNERS[contract['declarer']]))
        if contract and contract['level'] >= 5 and contract['doubled'] == 'None' \
                and not (jammed and contract['level'] == 5) and not saved:
            seats = [contract['declarer'], PARTNERS[contract['declarer']]]
            combined = sum(gib.Hand(hands[s]).hcp for s in seats)
            assert combined >= 22, (
                f"reached {contract['level']}{contract['strain']} on {combined} HCP: "
                f"{[c for _, c in auction.calls]}")


def test_two_over_one_shows_values_and_a_weak_hand_does_not():
    """The recognisable 2/1: a new suit at the TWO level promises real values,
    while the same shape with less in it bids at the one level instead."""
    strong = hand('QS 2S KH QH JH 10H 9H AD 10D 8D 7D AC 5C')
    # A two-over-one says "game-forcing" to any bridge player, so it needs the
    # points for that -- not just a long suit. Length alone is worth ~1.15 tricks
    # a card here, which let a 3-point hand clear the trick threshold.
    assert ai.eval_hand_sh(strong)['total_pts'] >= ai.TWO_OVER_ONE_TRICKS
    assert ai._points(ai.eval_hand_sh(strong)['groups']) >= ai.TWO_OVER_ONE_POINTS
    assert ai.ai_bid('South', strong, auction_after('1S', 'Pass')) == '2H'

    weak = hand('7S AH JH 10H 8H 7H 4H KD 8D 7D 6D 3D 5C')
    assert ai._points(ai.eval_hand_sh(weak)['groups']) < ai.TWO_OVER_ONE_POINTS
    assert ai.ai_bid('South', weak, auction_after('1S', 'Pass')) != '2H'


def test_a_two_over_one_is_only_a_lower_ranking_suit():
    """A two-over-one exists only when responder's suit ranks BELOW opener's.

    That is what forces it to the two level in the first place. A higher-ranking
    suit can be shown at the one level, so bidding it at the two is a JUMP SHIFT
    -- a different call with a different meaning, and a level of bidding room
    thrown away. The AI reached 1D - 2S alerted as "Forcing" before this rule
    existed; over 1D, spades belong in 1S.

    Note that over 1C there is no two-over-one at all: every other suit is
    available at the one level.
    """
    for opener, responder in (('S', 'H'), ('S', 'D'), ('S', 'C'),
                              ('H', 'D'), ('H', 'C'), ('D', 'C')):
        assert ai._is_two_over_one(responder, opener), \
            f"1{opener} - 2{responder} is a two-over-one"
    for opener, responder in (('D', 'S'), ('D', 'H'), ('C', 'D'),
                              ('C', 'H'), ('C', 'S'), ('H', 'S')):
        assert not ai._is_two_over_one(responder, opener), \
            f"1{opener} - 2{responder} is a jump shift, not a two-over-one"

    # In GIB a jump to 2S over 1D IS a call -- the strong (Soloway) jump
    # shift, 17+ points, 4+ controls, a good suit -- and it says so.
    strong_spades = hand('AS KS QS 10S 2S KH QH 3H AD 5D 4C 3C 2C')
    call, why = ai.ai_bid_explained('South', strong_spades, auction_after('1D', 'Pass'))
    assert call == '2S' and 'Strong jump shift' in why, (call, why)

    # Without the strength, spades are shown at the one level.
    modest_spades = hand('AS KS 9S 10S 2S 8H 7H 3H 6D 5D 4C 3C 2C')
    call = ai.ai_bid('South', modest_spades, auction_after('1D', 'Pass'))
    assert call == '1S', f"answered 1D with {call}"

    # The same strength in a LOWER-ranking suit is a genuine two-over-one.
    strong_hearts = hand('QS 2S KH QH JH 10H 9H AD 10D 8D 7D AC 5C')
    assert ai.ai_bid('South', strong_hearts, auction_after('1S', 'Pass')) == '2H'


def test_no_bid_alerted_forcing_is_actually_a_jump_shift():
    """Whole-auction guard: every two-level new suit in answer to an
    uncontested one-level opening is either a genuine two-over-one (a
    lower-ranking suit, or 1D-2C), alerted game forcing, or a higher-ranking
    suit alerted as GIB's strong jump shift -- never one passed off as the
    other."""
    import random
    from card import deal
    from game import PLAYERS
    random.seed(29)
    seen = 0
    # Enough boards to reach UNCONTESTED two-over-ones: in competition the
    # alert no longer says "Forcing" (it may be a free bid), so those
    # are not this test's subject any more.
    for index in range(300):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        guard = 0
        while not auction.is_complete and guard < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)
            bids = [(w, c) for w, c in auction.calls if c != 'Pass']
            mine = parse_bid(call)
            if (len(bids) == 1 and bids[0][0] == PARTNERS[who] and mine
                    and mine[0] == 2 and mine[1] in 'CDHS'
                    and parse_bid(bids[0][1])[0] == 1):
                opener = parse_bid(bids[0][1])[1]
                if mine[1] != opener and opener in 'CDHS':
                    seen += 1
                    if ai._is_two_over_one(mine[1], opener):
                        assert 'Game forcing' in why or 'Drury' in why, (call, why)
                    else:
                        assert 'Strong jump shift' in why, (
                            f"1{opener} - {call} is a jump shift: {why}")
            auction.apply_call(who, call)
            guard += 1
    assert seen, "no two-over-one exercised -- the alert vocabulary moved"


def test_promises_are_read_off_what_partner_actually_bid():
    """A flat promise is what made the old auction uninformative: nothing partner
    did changed what you assumed about them."""
    opened = ai._partner_promise('South', 'North', auction_after('1S', 'Pass'), 'S')
    assert opened == ai.PROMISE_OPENED

    raised = auction_after('1D', 'Pass', '1S', 'Pass', '2S', 'Pass')
    assert ai._partner_promise('South', 'North', raised, 'S') == ai.PROMISE_RAISED
    assert ai.PROMISE_RAISED < opened


def test_no_preempt_in_fourth_seat():
    """After three passes there is nobody to obstruct: a weak hand passes the
    board out, and a two-level opening shows 11-15 with six cards instead."""
    weak = hand('KS QS 10S 9S 8S 5S 8H 5H 2H 7D 4D 6C 3C')        # 7 points
    sound = hand('KS QS JS 9S 8S 5S AH 5H 2H KD 4D 6C 3C')        # 15 points
    assert ai._points(ai.eval_hand_sh(weak)['groups']) == 7
    assert ai._points(ai.eval_hand_sh(sound)['groups']) == 15

    assert ai.ai_bid('North', weak, auction_after()) == '2S'
    assert ai.ai_bid('North', weak, auction_after('Pass', 'Pass', dealer='South')) == '2S'
    fourth = auction_after('Pass', 'Pass', 'Pass', dealer='East')
    assert ai.ai_bid('North', weak, fourth) == 'Pass'
    call, alert = ai.ai_bid_explained('North', sound, fourth)
    assert call == '2S' and 'Fourth seat' in alert
    assert ai.ai_bid('North', sound, auction_after()) == '1S'


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nLevel discipline verified.")
