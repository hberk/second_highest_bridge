"""GIB 2/1, the robots' default system (gib.py), pinned call by call.

Each test builds the auction a convention lives in and a hand that should
use it, then checks the call AND that its alert names the convention -- so a
reader at the table and a robot partner read the same meaning. The sweep at
the end holds the whole module to zero illegal calls.
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
from card import Card, deal
from game import AuctionState, PLAYERS


def hand(text: str) -> list:
    return [Card(token[-1], token[:-1]) for token in text.split()]


def after(*calls: str, dealer: str = 'North') -> AuctionState:
    auction = AuctionState(dealer=dealer, vulnerability='None')
    for call in calls:
        auction.apply_call(auction.current_player(), call)
    return auction


def bid(cards: str, *calls: str, dealer: str = 'North') -> tuple:
    auction = after(*calls, dealer=dealer)
    return ai.ai_bid_explained(auction.current_player(), hand(cards), auction)


# ── Openings ──────────────────────────────────────────────────────────────────

def test_openings():
    assert bid('AS KS 4S QH JH 3H KD 9D 4D 2D AC 7C 3C')[0] == '1NT'      # 16 bal
    assert bid('AS KS 4S QH JH 3H AD QD 4D 2D AC 7C 3C')[0] == '2NT'      # 20 bal
    call, why = bid('AS KS QS JS AH KH 3H AD KD 4D 2D 7C 3C')              # 25
    assert call == '2C' and 'Strong' in why
    assert bid('AS KS 9S 7S 3S 4H 2H 3D AC QC 9C 7C 3C')[0] == '1S'       # 5-5 black
    assert bid('QS 9S 7S KH 2H KD JD 4D 2D AC 9C 7C 3C')[0] == '1D'       # 4-4 minors
    assert bid('AS QS 7S 2S KH 9H 2H 4D 3D 2D AC 9C 3C')[0] == '1C'       # 3-3 minors
    call, why = bid('8S 4S KH QH 10H 9H 6H 5H 7D 4D 2D 9C 3C')
    assert call == '2H' and 'Weak two' in why
    # GIB's 2C is strong, so six weak clubs are no weak two.
    assert bid('8S 4S 9H 6H 5H 7D 4D KC QC 10C 9C 7C 3C')[0] == 'Pass'


# ── Notrump: Stayman, transfers, Texas, Gerber, quantitative ─────────────────

def test_stayman():
    call, why = bid('KS 7S 3S AH 10H 7H 2H JD 9D 6D 9C 5C 3C', '1NT', 'Pass')
    assert call == '2C' and 'Stayman' in why
    call, why = bid('AS KS 4S QH JH 3H 2H KD 9D 4D AC 7C 3C', '1NT', 'Pass', '2C', 'Pass')
    assert call == '2H', why
    # Level is judged on this game's card values (gib.Hand.judge): kings and
    # queens count, aces barely. 8 judgement points opposite 15-17 invite;
    # 10 bid game.
    invite = 'KS 7S 3S AH 10H 7H 2H JD 9D 6D 9C 5C 3C'
    assert gib.Hand(hand(invite)).judge == 8
    assert bid(invite, '1NT', 'Pass', '2C', 'Pass', '2H', 'Pass')[0] == '3H'
    game = 'KS 7S 3S AH 10H 7H 2H QD 9D 6D JC 5C 3C'
    assert gib.Hand(hand(game)).judge == 10
    assert bid(game, '1NT', 'Pass', '2C', 'Pass', '2H', 'Pass')[0] == '4H'


def test_jacoby_and_texas_transfers():
    call, why = bid('7S 3S QH 10H 8H 7H 2H 9D 6D 5D 9C 5C 3C', '1NT', 'Pass')
    assert call == '2D' and 'Transfer' in why
    # Super-accept: a maximum, judged the variant's way, and four of the major.
    call, why = bid('KS QS 4S KH QH 3H 2H KD QD 4D QC 7C 3C', '1NT', 'Pass', '2D', 'Pass')
    assert call == '3H' and 'Super-accept' in why
    # Aces and kings make 17 HCP but a poor maximum here: just complete.
    call, _ = bid('AS KS 4S QH JH 3H 2H KD 9D 4D AC 7C 3C', '1NT', 'Pass', '2D', 'Pass')
    assert call == '2H'
    call, why = bid('KS QS 9S 8S 7S 3S 4H 2H AD 6D KC 5C 3C', '1NT', 'Pass')
    assert call == '4H' and 'Texas' in why
    assert bid('AS JS 4S QH JH 3H KD 9D 4D 2D AC 7C 3C',
               '1NT', 'Pass', '4H', 'Pass')[0] == '4S'


def test_systems_on_over_our_1nt_overcall():
    """(1x)-1NT is played like a 1NT opening, every round, while they pass:
    the overcaller answers Stayman and completes transfers. It used to read
    partner's transfer as natural and pass it, leaving us in their suit."""
    overcall = ('1D', '1NT', 'Pass')
    nt = 'AS KS 4S QH JH 3H KD 9D 4D 2D AC 7C 3C'                 # no 4-card major
    call, why = bid(nt, *overcall, '2D', 'Pass')
    assert call == '2H' and 'transfer' in why, (call, why)
    call, why = bid(nt, *overcall, '2H', 'Pass')
    assert call == '2S' and 'transfer' in why, (call, why)
    call, why = bid(nt, *overcall, '2C', 'Pass')
    assert call == '2D' and 'No 4-card major' in why, (call, why)
    weak5 = 'KS 7S 3S QH 10H 9H 7H 2H 9D 6D JC 5C 3C'
    assert bid(weak5, *overcall)[0] == '2D'
    # Every call matches the same seat's call after a 1NT opening.
    for cards, tail in ((weak5, ('2D', 'Pass', '2H', 'Pass')),
                        ('KS 7S 3S AH 10H 7H 2H QD 9D 6D JC 5C 3C',
                         ('2C', 'Pass', '2H', 'Pass'))):
        assert bid(cards, *overcall, *tail)[0] == bid(cards, '1NT', 'Pass', *tail)[0]
    # Once they bid again, systems are off.
    a = after('1D', '1NT', 'Pass', '2D', '2S')
    assert not gib.Ctx(a.current_player(), hand(nt), a).nt_overcall


def test_opener_reopens_with_a_double_when_short_in_their_suit():
    """1x (y) P (P): responder may be sitting with a penalty double, so opener
    reopens with a double on 0-1 cards in their suit, or 2 with 15+ HCP. Every
    hand here is one the robots used to rebid or pass on."""
    for cards, auction in (
            ('AS KS 9S 8S AH KH QH 7H 5H 9D 10C 6C 2C', ('1H', '2D')),   # 16, singleton
            ('AS JS 10S 3S AH KH 9H 7H 2H 3D JC 7C 2C', ('1H', '2D')),   # 13: it passed
            ('AH QH 8H 6H AD 8D 4D AC QC JC 8C 5C 3C', ('1C', '1S')),    # void
            ('KS 8S AH 9H 7H AD KD QD 4D 3D 9C 5C 3C', ('1D', '1S'))):   # 2 cards, 16
        call, why = bid(cards, *auction, 'Pass', 'Pass')
        assert call == 'X' and 'Reopening' in why, (cards, call, why)
    # Not with a doubleton and a minimum, nor a long suit on a minimum.
    assert bid('KS 8S QH 9H 7H AD KD 8D 4D 3D 9C 5C 3C', '1D', '1S', 'Pass', 'Pass')[0] != 'X'
    assert bid('10S AH 3H AD KD JD 6D 5D 4D 3D 9C 5C 3C', '1D', '1S', 'Pass', 'Pass')[0] == '2D'
    # Responder converts with length and honours in their suit, else answers.
    after_x = ('1H', '2D', 'Pass', 'Pass', 'X', 'Pass')
    call, why = bid('QS 7S 3S 9H 4H KD QD 10D 8D 5D 9C 8C 2C', *after_x)
    assert call == 'Pass' and 'Penalty' in why
    assert bid('QS 10S 7S 3S 4H 9D 8D 5D KC 9C 8C 7C 2C', *after_x)[0] == '2S'
    assert bid('9S 7S 3S QH 4H 9D 8D 5D 6C 10C 8C 7C 2C', *after_x)[0] == '2H'


def test_opener_bids_the_fit_after_they_raise_over_a_negative_double():
    """1x (1y) X (2y): the negative double promised four in the unbid major.
    The fallback read partner as having passed and bid that fit 0 times in
    27 survey hands; these are some of them."""
    # Minimum: the cheapest bid in partner's suit.
    call, why = bid('KS 9S 8S 5S QH 9H 8H 7D 4D 2D AC KC 7C', '1C', '1H', 'X', '2H')
    assert call == '2S' and "partner's suit" in why, (call, why)
    assert bid('AS KS 8S 3S 8H 6H AD QD 9D 3D 9C 7C 2C', '1D', '1H', 'X', '2H')[0] == '2S'
    assert bid('8S 4S AH KH 7H 5H AD KD 10D 9D 3D 2D 3C', '1D', '1S', 'X', '2S')[0] == '3H'
    # 15-17 jumps; both majors promised, four of each: hearts, the cheaper.
    call, why = bid('AS 8S 5S 4S AH KH 6H 3H 4D KC QC 9C 6C', '1C', '1D', 'X', '2D')
    assert call == '3H' and '15+ HCP' in why, (call, why)
    # A jump that is already game reads the same as 18+ bidding game.
    assert bid('AH QH 7H 5H AD QD 9D 7D 3D AC 8C 4C 3C', '1D', '1S', 'X', '2S')[0] == '4H'
    # No fit: a six-card suit rebids; 17+ doubles; a minimum passes.
    assert bid('AS 4S AH KH 7H 8D 5D AC JC 10C 9C 8C 2C', '1C', '1S', 'X', '2S')[0] == '3C'
    call, why = bid('QS 7S 5S AH 7H 6H KD 6D AC KC QC JC 2C', '1C', '1H', 'X', '2H')
    assert call == 'X' and 'extra values' in why, (call, why)
    assert bid('QS 7S 5S AH 7H 6H 8D 6D AC JC 9C 4C 2C', '1C', '1H', 'X', '2H')[0] == 'Pass'
    # Responder answers opener's double: penalty with their suit, else bids.
    after_x = ('1C', '1H', 'X', '2H', 'X', 'Pass')
    call, why = bid('KS 9S 8S 5S QH JH 10H 8H 7D 4D 2D 7C 3C', *after_x)
    assert call == 'Pass' and 'Penalty' in why
    assert bid('KS 9S 8S 5S 3S 9H 8H 7D 4D 2D 7C 3C 4C', *after_x)[0] == '2S'


def test_gerber_answers_aces():
    call, why = bid('AS JS 4S QH JH 3H KD 9D 4D 2D AC 7C 3C', '1NT', 'Pass', '4C', 'Pass')
    assert call == '4S' and '2 aces' in why


# ── Major-suit raises ─────────────────────────────────────────────────────────

def test_jacoby_2nt_and_splinters():
    call, why = bid('KS QS 7S 3S AH 10H 7H KD 9D 6D 9C AC 3C', '1S', 'Pass')
    assert call == '2NT' and 'Jacoby' in why
    call, why = bid('KS QS 7S 3S AH 10H 7H 2H KD 9D 6D AC 3C'.replace('2H', '5H')
                    .replace('3C', '4D'), '1S', 'Pass')
    assert call == '4C' and 'Splinter' in why
    # Jacoby rebid: shortness is shown first.
    call, why = bid('AS KS 9S 7S 3S KH 4H 3H AD 9D 8D 4D 2C', '1S', 'Pass', '2NT', 'Pass')
    assert call == '3C' and 'Shortness' in why


def test_drury_by_a_passed_hand():
    call, why = bid('KS JS 3S QH 9H 7H AD 9D 6D 5D 9C 5C 3C',
                    'Pass', 'Pass', '1H', 'Pass', dealer='South')
    # South passed, North opened 1H in third seat: 10 HCP and three hearts.
    assert call == '2C' and 'Drury' in why


def test_two_over_one_is_game_forcing():
    call, why = bid('KS 3S AH 7H 2H QD 10D 9D 6D 5D AC 5C 3C', '1S', 'Pass')
    assert call == '2D' and 'Game forcing' in why
    # With four of each minor, the lower: 2C.
    call, why = bid('KS 3S AH 7H 2H QD 10D 9D 6D AC 5C 4C 3C', '1S', 'Pass')
    assert call == '2C' and 'Game forcing' in why


# ── Competition ───────────────────────────────────────────────────────────────

def test_negative_double():
    call, why = bid('7S 3S KH QH 7H 2H AD 9D 6D 5D 9C 5C 3C', '1C', '1S')
    assert call == 'X' and 'Negative' in why


def test_answers_to_a_negative_double_say_what_they_show():
    """A user's correction: the answer is a description, not "answering"."""
    # 1D (1H) X (P): five diamonds, three spades -> 2D, denying four spades.
    call, why = bid('K9S 7S QS AD QD JD 9D 4D 8H 3H AC 9C 2C'.replace('K9S', 'KS'),
                    '1D', '1H', 'X', 'Pass')
    assert call == '2D' and why == "5+ \u2666, fewer than 4 \u2660 or \u2663.", (call, why)
    # Four spades: shown at the cheapest level.
    call, why = bid('KS 9S 7S 2S AD QD JD 4D 8H 3H AC 9C 2C', '1D', '1H', 'X', 'Pass')
    assert call == '1S' and why == "4+ \u2660.", (call, why)


def test_support_double():
    call, why = bid('AS 4S KH 8H 3H KD QD 9D 7D 2D QC 5C 3C', '1D', 'Pass', '1H', '2C')
    assert call == 'X' and 'Support double' in why


def test_michaels_and_unusual():
    call, why = bid('KS QS 9S 7S 3S AH JH 8H 6H 2H 4D 2D 3C', '1C')
    assert call == '2C' and 'Michaels' in why
    call, why = bid('3S 2S 4H 9D KD QD 8D 6D AC JC 8C 6C 2C', '1S')
    assert call == '2NT' and 'Unusual' in why
    # Partner picks between the two suits shown.
    call, why = bid('8S 4S 3S 2S 9H 3H JD 8D 6D 5D 4C 3C 2C', '1S', '2NT', 'Pass')
    assert call == '3D' and "partner's two suits" in why


def test_weak_jump_overcall():
    call, why = bid('KS QS 10S 9S 8S 3S 4H 2H 7D 6D 9C 5C 3C', '1H')
    assert call == '2S' and 'Weak jump overcall' in why


def test_weak_jump_shift_over_their_takeout_double():
    """1C (X): a jump in a new suit is weak. A user's West passed this hand."""
    call, why = bid('KS JS 9S 8S 7S 3S 2S 10H 4H 5D 4D 3D 5C', '1C', 'X')
    assert call == '2S' and 'Weak jump shift' in why
    # Only at the two level: six clubs over 1D would jump to 3C, so no.
    call, why = bid('9S 3S 10H 4H 2H 5D 4D KC JC 9C 8C 7C 3C', '1D', 'X')
    assert call != '3C', (call, why)


def test_lebensohl_sign_off_is_passed():
    """1NT-(2H)-2NT-(P)-3C-(P)-3D: after the relay, responder's suit is to play.
    A user caught opener bidding 3NT over it."""
    opener = 'AS 9S 4S AH 8H 4H KD 9D 4D 2D KC QC 3C'          # 16, heart stopper
    call, why = bid(opener, '1NT', '2H', '2NT', 'Pass', '3C', 'Pass', '3D', 'Pass')
    assert call == 'Pass', (call, why)


def test_cappelletti_over_their_1nt():
    call, why = bid('AS KS 9S 7S 3S KH 10H 8H 6H 4D 2D 9C 3C', '1NT')
    assert call == '2D' and 'Artificial' in why


def test_takeout_doubles_stop_at_4h():
    strong = 'AS KS QH JH 7H 2H AD QD 9D 6D AC 5C 3C'
    assert bid(strong, '4H')[0] == 'X'
    assert bid(strong.replace('AS KS', 'AH KH').replace('QH JH 7H 2H', 'QS JS 7S 2S'),
               '4S')[0] != 'X'


# ── Slam conventions ──────────────────────────────────────────────────────────

def test_keycard_blackwood_0314():
    # 1S - 2NT (Jacoby) - 4S (minimum) - 4NT: opener answers keycards for spades.
    one_key = 'KS QS 9S 7S 3S KH 4H 3H AD 9D 8D 4D 2C'     # A + trump K = 2, Q
    call, why = bid(one_key, '1S', 'Pass', '2NT', 'Pass', '4S', 'Pass', '4NT', 'Pass')
    assert call == '5S' and 'trump queen' in why
    no_queen = one_key.replace('QS', 'JS')
    call, why = bid(no_queen, '1S', 'Pass', '2NT', 'Pass', '4S', 'Pass', '4NT', 'Pass')
    assert call == '5H' and 'no trump queen' in why


def test_agreed_trump_reads_conventions():
    assert gib.agreed_trump(['1S', '2NT']) == 'S'           # Jacoby
    assert gib.agreed_trump(['1H', '4C']) == 'H'            # splinter
    assert gib.agreed_trump(['1NT', '4D', '4H']) == 'H'     # Texas
    assert gib.agreed_trump(['1NT', '2C', '2H']) is None    # Stayman shows nothing yet
    assert gib.agreed_trump(['1D', '1S', '2S']) == 'S'


# ── Card play: who sees what ───────────────────────────────────────────────────

def test_declarer_sees_its_own_two_hands_and_never_a_defender():
    """Declarer plays dummy AND its own hand, so it sees both -- and nothing
    else. Defenders see dummy only. Nobody plays double dummy."""
    hands = {s: [Card('S', r)] for s, r in zip(PLAYERS, '2345')}
    contract = {'declarer': 'East', 'dummy': 'West'}
    for seat in ('East', 'West'):
        assert set(ai.visible_hands(seat, contract, hands)) == {'East', 'West'}
    for seat in ('North', 'South'):
        assert set(ai.visible_hands(seat, contract, hands)) == {'West'}


def _users_board_before_trick_11():
    """A user's 2D by East, ten tricks in; North has led the 8C to trick 11."""
    tricks = [
        'South 9S West 3S North 2S East 6S', 'East JH South AH West KH North 3H',
        'West JC North 6C East KC South 5C', 'West QS North 5S East 10S South KS',
        'West 9C North 2C East 4D South 9D', 'East 10H South 9H West 8H North 7H',
        'South 7S West 4S North 4C East JS', 'South 5H West 3C North 6D East 6H',
        'North 10C East 5D South 2D West 7C', 'South 4H West 8S North 7D East QH']
    history = []
    for line in tricks:
        parts = line.split()
        history.append([(parts[i], Card(parts[i + 1][-1], parts[i + 1][:-1]))
                        for i in range(0, 8, 2)])
    played = [c for t in history for _, c in t]
    return history, played


def test_the_endgame_is_searched_not_guessed():
    """Every ruff lost trick 11, so one trick of look-ahead threw the J♦ and kept
    A♦ K♦. Keeping J♦ A♦ wins trick 12: a middle card under the queen is
    second-highest. The search ruffs with the king."""
    history, played = _users_board_before_trick_11()
    east, west = hand('AD KD JD'), hand('AS QC 8D')
    view = ai.visible_hands('East', {'declarer': 'East', 'dummy': 'West'},
                            {'East': east, 'West': west})
    card = ai.ai_play('East', east, [('North', Card('C', '8'))], 'D', played,
                      visible=view, history=history)
    assert str(card) == 'K♦', card


def test_the_endgame_search_never_peeks_at_hidden_cards():
    """Fair play: the robot sees its own hand, dummy, the cards played and who
    has shown out -- never the hidden hands. So swapping the defenders' unseen
    cards must not change its choice. `ai_play` is not even given them."""
    import inspect
    assert 'hands' not in inspect.signature(ai.ai_play).parameters
    history, played = _users_board_before_trick_11()
    east, west = hand('AD KD JD'), hand('AS QC 8D')
    view = ai.visible_hands('East', {'declarer': 'East', 'dummy': 'West'},
                            {'East': east, 'West': west})
    # The call carries no defender's cards at all: the view is East and West only.
    assert set(view) == {'East', 'West'}


def test_second_hand_covers_to_promote_dummy():
    """A user's 3NT: North leads the 8C, East holds K64 with dummy's 9C still to
    play. Covering with the king makes the nine second-highest; low lets the
    eight hold. Declarer sees dummy, so it can find this -- fairly."""
    initial = {'North': hand('QS 10S 8S 7S 4S 10H 2H AC QC 8C 7C 5C 3C'),
               'East': hand('AS KS 2S AH 8H 6H 9D 6D 4D KC JC 6C 4C'),
               'South': hand('9S 3S KH QH JH 9H 3H KD QD JD 7D 5D 10C'),
               'West': hand('JS 6S 5S 7H 5H 4H AD 10D 8D 3D 2D 9C 2C')}
    tricks = ['South JH West 4H North 10H East 6H', 'North QC East JC South 10C West 2C',
              'East KS South 3S West JS North QS', 'North 8S East 2S South 9S West 5S',
              'North 7S East AS South KH West 6S', 'North 4S East 4D South QH West 2D']
    history = []
    for line in tricks:
        parts = line.split()
        history.append([(parts[i], Card(parts[i + 1][-1], parts[i + 1][:-1]))
                        for i in range(0, 8, 2)])
    hands = {s: list(c) for s, c in initial.items()}
    for plays in history:
        for seat, card in plays:
            hands[seat].remove(card)
    played = [c for plays in history for _, c in plays]
    view = ai.visible_hands('East', {'declarer': 'East', 'dummy': 'West'}, hands)
    card = ai.ai_play('East', hands['East'], [('North', Card('C', '8'))], None, played,
                      visible=view, history=history)
    assert str(card) == 'K♣', card


def test_fourth_hand_plays_for_partner():
    """A user's 3H: North led the 7H, East the 8H, South the 2H. Dummy's king
    makes East's eight second-highest; the four let the seven win. Fourth
    hand used to ask only whether IT won the trick."""
    trick = [('North', Card('H', '7')), ('East', Card('H', '8')), ('South', Card('H', '2'))]
    west = hand('AH KH 4H QC 9C 7S')
    assert str(ai._play_last(ai.legal_plays(west, 'H'), trick, 'H')) == 'K\u2665'


def test_a_three_level_cuebid_raise_needs_more():
    """1H-(2C): a cuebid raise here forces 3H. On three trumps and 10 HCP the
    same user's board went two down; the hand now raises to 2H instead."""
    west = '7S 6S 5S 3S AH KH 4H 10D 8D 4D QC JC 9C'
    call, why = bid(west, 'Pass', '1H', '2C', dealer='North')
    assert call == '2H' and why == "3+ \u2665, 6+ HCP.", (call, why)
    # Four trumps still cuebid.
    four = '7S 6S 5S AH KH 4H 3H 10D 8D 4D QC JC 9C'
    call, why = bid(four, 'Pass', '1H', '2C', dealer='North')
    assert call == '3C' and 'Cuebid' in why, (call, why)


# ── Robustness ────────────────────────────────────────────────────────────────

def test_no_illegal_call_over_many_auctions():
    gib.ILLEGAL.clear()
    random.seed(41)
    for index in range(600):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        while not auction.is_complete and len(auction.calls) < 80:
            who = auction.current_player()
            auction.apply_call(who, ai.ai_bid(who, hands[who], auction))
        assert auction.is_complete
    assert not gib.ILLEGAL, f"illegal calls caught by the guard: {gib.ILLEGAL[:3]}"


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nGIB 2/1 verified.")
