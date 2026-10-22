"""Guards on the fitted bidding calibration in ai.py.

ai.py's thresholds are no longer quantile-matched against high card points. They
are expressed in EXPECTED TRICKS and fitted to solved double dummy results — see
research/hand_value.py and "Hand evaluation and bidding research" in docs/BIDDING.md. These
tests fail loudly if a change to eval_hand_sh or to a threshold quietly undoes
one of the findings the calibration rests on, without pinning exact frequencies
that a larger dataset is expected to move.

Under guard:
  * Notrump is never bid. Over 172 solved (deal, side) comparisons the side's own
    suit fit beat notrump 91% of the time, tied 9%, and lost 0 times, and a
    deliberate search for a viable niche found none.
  * Contracts settle low. Undoubled overtricks score exactly what contracted
    tricks score, so the only prize for bidding higher is the game bonus — and
    game is rare (4M makeable 28%, 5m 11%, 3NT 10%).
  * Boards are not passed out wholesale. An earlier scale mismatch left 41.5% of
    all-AI boards passed out, which is the failure this file originally caught.
  * The ace is not an honour. It cannot win a contested trick, and the fit puts
    it with the tens, below kings and queens.
"""
from __future__ import annotations
import random
import sys
from collections import Counter
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import ai
import gib
from card import Card, deal, parse_bid
from game import AuctionState, PARTNERS, PLAYERS


def _hand(text: str) -> list:
    """'AS 10H 2C' -> [Card('S','A'), Card('H','10'), Card('C','2')]."""
    return [Card(token[-1], token[:-1]) for token in text.split()]


def _auctions(deals: int, seed: int):
    """Run whole all-AI auctions and hand back the finished AuctionStates."""
    random.seed(seed)
    for index in range(deals):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        guard = 0
        while not auction.is_complete and guard < 60:
            who = auction.current_player()
            auction.apply_call(who, ai.ai_bid(who, hands[who], auction))
            guard += 1
        yield auction


def test_thresholds_are_ordered_sensibly():
    """The constants have to stay in a consistent relationship to each other."""
    assert 0 < ai.OPEN_TRICKS < ai.GAME_TRICKS
    assert ai.PARTSCORE_LEVEL + 6 < ai.GAME_TRICKS, \
        "game must need more tricks than the partscore it replaces"
    # A 2/1 shows more than an opening, which shows more than a raise. That
    # ordering is the information the auction carries.
    assert ai.PROMISE_RAISED < ai.PROMISE_OPENED < ai.PROMISE_TWO_OVER_ONE, (
        "a 2/1 promises more than an opening, which promises more than a raise")
    # ... and every promise must sit BELOW what the action really holds. Using
    # the measured values scored -16.0 per board (t = -2.55): with +/-1.14
    # tricks of estimate error, bidding at true capability overshoots half the
    # time, and overshooting is punished while undershooting is nearly free.
    assert ai.PROMISE_SHIFT > 0, "promises must be conservative, not accurate"
    assert ai.PROMISE_OPENED < 4.66, "opening promise drifted to its measured value"
    assert ai.SUPPORT_LENGTH < ai.OPEN_SUIT_LENGTH
    assert ai.OPEN_SUIT_LENGTH < ai.PREEMPT_LENGTH
    assert ai.TRUMP_CARD > max(ai.HONOUR_VALUE.values()), \
        "a trump card outweighs any single honour; that is the whole finding"


def test_the_ace_is_not_an_honour():
    """Q and K carry the hand; the ace sits with the tens."""
    assert ai.HONOUR_VALUE['Q'] > ai.HONOUR_VALUE['A']
    assert ai.HONOUR_VALUE['K'] > ai.HONOUR_VALUE['A']
    assert ai.HONOUR_VALUE['A'] == ai.HONOUR_VALUE['10']

    aces = ai.eval_hand_sh(_hand('AS AH AD AC 5S 5H 5D 5C 6S 6H 6D 6C 7S'))
    queens = ai.eval_hand_sh(_hand('QS QH QD QC 5S 5H 5D 5C 6S 6H 6D 6C 7S'))
    assert queens['honour_pts'] > aces['honour_pts'], \
        "four queens must beat four aces on the same shape"


def test_the_evaluation_is_on_the_trick_scale():
    """total_pts is expected tricks in the hand's own best suit, not a point count."""
    values = [ai.eval_hand_sh(hand)['total_pts']
              for _ in range(150) for hand in deal().values()]
    average = sum(values) / len(values)
    assert 3.5 < average < 6.5, f"scale has drifted: mean {average:.2f}"
    assert all(1.0 < value < 11.0 for value in values)

    long_strong = ai.eval_hand_sh(_hand('KS QS JS 10S 9S 8S 7S KH QH KD QD KC QC'))
    flat_weak = ai.eval_hand_sh(_hand('4S 3S 2S 4H 3H 2H 4D 3D 2D 5C 4C 3C 2C'))
    assert long_strong['total_pts'] > flat_weak['total_pts'] + 3


def test_notrump_openings_are_gibs():
    """GIB opens 1NT on 15-17 and 2NT on 20-21, balanced. (The old system
    never bid notrump, on a measurement; GIB is the system now by choice.)"""
    random.seed(4)
    seen = Counter()
    for index in range(400):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        while not auction.is_complete and len(auction.calls) < 60:
            who = auction.current_player()
            call = ai.ai_bid(who, hands[who], auction)
            if call in ('1NT', '2NT') and all(c == 'Pass' for _, c in auction.calls):
                h = gib.Hand(hands[who])
                low, high = gib.NT1 if call == '1NT' else gib.NT2
                assert h.balanced and low <= h.hcp <= high, (
                    f"opened {call} on {h.hcp} HCP, shape {h.shape}")
                seen[call] += 1
            auction.apply_call(who, call)
    assert seen['1NT'] > 10, f"only {seen['1NT']} 1NT openings"


def test_slams_are_bid_only_on_slam_values():
    """GIB bids slams, so the regression to guard is a runaway: a six- or
    seven-level contract on values nowhere near it."""
    random.seed(5)
    contracts = 0
    for index in range(300):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        while not auction.is_complete and len(auction.calls) < 60:
            who = auction.current_player()
            auction.apply_call(who, ai.ai_bid(who, hands[who], auction))
        contract = auction.get_contract()
        if not contract:
            continue
        contracts += 1
        if contract['level'] >= 6:
            seats = [contract['declarer'], PARTNERS[contract['declarer']]]
            combined = sum(gib.Hand(hands[s]).hcp for s in seats)
            assert combined >= 27, (
                f"{contract['level']}{contract['strain']} on {combined} HCP: "
                f"{[c for _, c in auction.calls]}")
    assert contracts > 250


def test_all_ai_boards_are_not_passive():
    """The regression this file was written for: wholesale pass-outs.

    Both sides can take 7+ tricks in their own fit on 81% of deals, so passing a
    board out concedes a makeable partscore.
    """
    auctions = list(_auctions(120, seed=6))
    passed_out = sum(1 for auction in auctions if auction.get_contract() is None)
    assert passed_out / len(auctions) < 0.20, \
        f"{passed_out / len(auctions):.0%} of boards passed out"


def test_every_robot_bid_can_explain_itself():
    """Each call the AI makes is alerted at the table, so every branch has to
    produce an explanation, and it has to describe the call actually made."""
    random.seed(3)
    seen = 0
    for index in range(40):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        guard = 0
        while not auction.is_complete and guard < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)

            assert call == ai.ai_bid(who, hands[who], auction), (
                "ai_bid and ai_bid_explained disagreed on the call")
            assert why and why.strip(), f"{call} came with no explanation"
            # system-card style, so an alert may start with a length ("5+ ♠")
            assert len(why) < 70, f"alert is too long for a tooltip: {why!r}"
            assert why.endswith('.'), f"alert should be a complete phrase: {why!r}"

            parsed = parse_bid(call)
            if parsed and parsed[1] != 'NT' and 'Artificial' not in why:
                # alerts are written like a system card, in suit symbols; an
                # artificial call is about something else, and says so
                assert ai.SUIT_SYM[parsed[1]] in why, (
                    f"{call} explained without naming the suit: {why!r}")
            # an alert says what the bid SHOWS, never what the hand holds
            assert ('point' not in why or '+' in why or '-' in why
                    or 'Fewer' in why or 'under' in why), (
                f"alert states an exact holding: {why!r}")
            auction.apply_call(who, call)
            guard += 1
            seen += 1
    assert seen > 100, f"only exercised {seen} calls"


def test_bids_that_name_a_strength_actually_have_it():
    """A points threshold has to gate on POINTS. The trick-count thresholds are
    met by length alone -- a card of length is worth about 1.15 tricks here -- so
    gating a two-over-one or an overcall on tricks produced a "game-forcing" 2/1
    on 3 points and overcalls on 3. Both are bids no player would make, and both
    tell partner something false.

    This matched on `why.startswith('Two-over-one')` until the alerts were
    rewritten into system-card style, at which point neither prefix existed any
    more and both assertions silently stopped running -- the test that caught the
    8-point two-over-one was passing vacuously. The counters below exist so that
    cannot happen quietly again: if the vocabulary moves, the test fails for
    having found nothing rather than passing for the same reason.
    """
    random.seed(9)
    seen = Counter()
    for index in range(200):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        guard = 0
        while not auction.is_complete and guard < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)
            hcp = gib.Hand(hands[who]).hcp
            if '12+ HCP. Game forcing' in why:
                seen['2/1'] += 1
                assert hcp >= gib.TWO_OVER_ONE, f"two-over-one on {hcp} HCP: {why}"
            if 'Overcall' in why:
                seen['overcall'] += 1
                assert hcp >= gib.OVERCALL_1[0], f"overcall on {hcp} HCP: {why}"
            if 'Takeout' in why:
                seen['double'] += 1
                assert hcp >= gib.TAKEOUT_MIN, f"takeout double on {hcp} HCP: {why}"
            auction.apply_call(who, call)
            guard += 1
    for label in ('2/1', 'overcall', 'double'):
        assert seen[label], (
            f"no {label} was exercised -- the alert vocabulary moved and this "
            f"assertion stopped running. Match on the new wording.")


def test_points_are_counted_the_guide_way():
    """High cards PLUS length points, minus one for a flat 4-3-3-3.

    The system card's thresholds are written in this count, not in raw HCP, and
    the difference is not cosmetic: counting the guide's way moved this AI's
    median opening from 11 to exactly 12, which is what let the alerts quote a
    recognisable number without lying about it.
    """
    # AKQJ AKQ AKQ + three small clubs: 28 high cards in a 4-3-3-3, so the
    # card docks one and no suit is long enough to earn a length point.
    flat = _hand('AS KS QS JS AH KH QH AD KD QD 2C 3C 4C')
    assert ai._points(ai.eval_hand_sh(flat)['groups']) == 28 - 1

    # A six-card suit earns two length points (one per card past the fourth).
    six = _hand('AS KS 5S 4S 3S 2S 4H 3H 2H 4D 3D 2D 2C')
    groups = ai.eval_hand_sh(six)['groups']
    assert len(groups['S']) == 6
    assert ai._points(groups) == 7 + 2, "a six-card suit is worth two length points"

    # Nothing longer than four cards: no length points at all, and not flat.
    square = _hand('AS KS QS JS 2H 3H 4H 5H 2D 3D 4D 2C 3C')
    assert ai._points(ai.eval_hand_sh(square)['groups']) == 10

    # Shortness counts only opposite a fit, and never in the trump suit itself.
    short = _hand('AS KS QS JS 10S 2H 2D 3D 4D 2C 3C 4C 5C')
    assert ai._dist_points(ai.eval_hand_sh(short)['groups'], 'S') == 3, \
        "a singleton heart is worth 3; the diamonds and clubs are not short"


def test_the_takeout_double_shows_the_shape_it_claims():
    """The guide's double: 12+ points (14+ over a two-level bid), two or fewer
    cards in their suit, three or more in every other suit.

    Shape is the whole point of the call -- it says "no suit of my own, but I can
    play any of the others". Before it existed a 15-point hand with no five-card
    suit simply passed, so the entire class went unbid. Adding it measured
    +9.8 points per board (t = +2.13), which paid for every other change here.
    """
    random.seed(11)
    doubles = 0
    for index in range(200):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        guard = 0
        while not auction.is_complete and guard < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)
            if call == 'X' and why.startswith('Takeout'):
                doubles += 1
                groups = ai.eval_hand_sh(hands[who])['groups']
                theirs = ai._their_suit(who, auction)
                assert theirs is not None, "doubled with no opponent bid to double"
                h = gib.Hand(hands[who])
                shaped = (len(groups[theirs]) <= 2 and all(
                    len(groups[s]) >= 3 for s in 'SHDC' if s != theirs))
                # GIB: the shape, or any 18+ hand too strong to overcall
                assert shaped or h.hcp >= 18, f"doubled without the shape: {why}"
                assert h.hcp >= gib.TAKEOUT_MIN
            auction.apply_call(who, call)
            guard += 1
    assert doubles >= 5, f"only {doubles} takeout doubles -- branch unreachable?"


def test_a_takeout_double_is_answered_not_passed_out():
    """A double asks a question, and leaving it in converts it to a PENALTY
    double -- a different call entirely. A hand with values has to answer."""
    auction = AuctionState(dealer='North', vulnerability='None')
    auction.apply_call('North', '1H')
    auction.apply_call('East', 'X')
    auction.apply_call('South', 'Pass')
    west = _hand('AS KS 8S 4S 3H 2H AD 9D 4D 3D KC 7C 2C')
    call, why = ai.ai_bid_explained('West', west, auction)
    assert call != 'Pass', f"left partner's takeout double in: {why}"
    assert parse_bid(call), f"answered a takeout double with {call}"
    assert parse_bid(call)[1] != 'H', "answered a takeout double in THEIR suit"


def test_a_cuebid_is_alerted_as_one_and_still_understood():
    """GIB cuebids -- Michaels, cuebid raises, unusual-vs-unusual. (The old
    system did not, on a measurement of -4.1 per board head to head; GIB is
    the system now by choice.) A bid in the opponents' suit must say what it
    is, never pass itself off as length there.
    """
    random.seed(13)
    seen = 0
    for index in range(300):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        while not auction.is_complete and len(auction.calls) < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)
            parsed = parse_bid(call)
            if parsed and parsed[1] != 'NT' and ai._is_cuebid(who, auction, parsed[1]):
                seen += 1
                assert any(word in why for word in (
                    'Cuebid', 'Michaels', 'Artificial', 'Both minors',
                    "partner's two suits")), (
                    f"{who} bid their suit {call} without saying why: {why}")
            auction.apply_call(who, call)
    assert seen, "no cuebid exercised"

    # ... but partner's cuebid is read as support, never as length in their suit.
    cued = AuctionState(dealer='North', vulnerability='None')
    cued.apply_call('North', '1H')
    cued.apply_call('East', '1S')
    cued.apply_call('South', 'Pass')
    cued.apply_call('West', '2H')          # a cuebid: support for spades
    assert ai._is_cuebid('East', cued, 'H'), "failed to recognise the cuebid"
    call, why = ai.ai_bid_explained(
        'East', _hand('AS KS QS 9S 4S 3H 2H AD 9D 4D KC 7C 2C'), cued)
    assert parse_bid(call) is None or parse_bid(call)[1] != 'H', (
        f"played in the opponents' suit after a cuebid: {call} -- {why}")


def test_an_opener_never_describes_its_rebid_as_an_overcall():
    """A hand that opened, whose partner then passed, used to fall through every
    branch into the OVERCALL code. It re-bid its own suit alerted as "Overcall",
    and where the opponents had only doubled rather than bid it reached the
    OPENING branch instead and passed with "No suit worth opening" -- having
    opened that very suit two calls earlier. Both were one missing branch."""
    random.seed(17)
    for index in range(60):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        guard = 0
        while not auction.is_complete and guard < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)
            if [c for w, c in auction.calls if w == who and parse_bid(c)]:
                assert 'Overcall' not in why, (
                    f"{who} had already bid, so this is a rebid: {call} -- {why}")
                assert 'No suit worth opening' not in why, (
                    f"{who} had already opened a suit: {call} -- {why}")
            auction.apply_call(who, call)
            guard += 1


def test_no_alert_denies_a_suit_the_hand_is_holding():
    """An alert may not claim the hand has no long suit when it has one.

    Found by a user on two boards: a hand with EIGHT diamonds passed alerting
    "no five-card suit", and another with six did the same. The cause was a
    missing branch -- once an overcall removed the one-level response, a long
    suit had no home and fell through to a pass whose text denied it. It was
    false 141 times across 300 deals.

    The overcall pass says "outside theirs", which is a different and true
    claim: `best_suit` there is chosen from suits the opponents have not bid,
    so that one is checked against the hand's suits minus theirs.
    """
    random.seed(31)
    checked = 0
    for index in range(70):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        guard = 0
        while not auction.is_complete and guard < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)
            groups = ai.eval_hand_sh(hands[who])['groups']

            if 'No 4-card major' in why or 'no 4-card major' in why:
                assert len(groups['H']) < 4 and len(groups['S']) < 4, (
                    f"alert denies a 4-card major the hand holds: {why!r}")
                checked += 1
            if 'no five-card suit' in why and 'outside theirs' not in why:
                longest = max(len(cards) for cards in groups.values())
                assert longest < ai.OPEN_SUIT_LENGTH, (
                    f"alert denies a five-card suit but the hand holds "
                    f"{longest}: {why!r}")
                checked += 1
            elif 'outside theirs' in why:
                partner = PARTNERS[who]
                theirs = {s for s in 'SHDC'
                          if ai._first_namer(auction, s) not in (None, who, partner)}
                mine = [len(cards) for suit, cards in groups.items()
                        if suit not in theirs]
                assert not mine or max(mine) < ai.OPEN_SUIT_LENGTH, (
                    f"alert denies a five-card suit outside theirs, but the "
                    f"hand holds one: {why!r}")
                checked += 1
            auction.apply_call(who, call)
            guard += 1
    assert checked > 3, f"only checked {checked} such alerts"


def test_every_number_an_alert_quotes_is_true_of_the_hand():
    """An alert is a promise. A false number inside a believable format is worse
    than no alert at all, and two got in exactly that way: a simple raise
    claiming the card's "6-9 points" on an 11-point hand (29 times), and a
    length-based rebid claiming "12+ points" on 9 (19 times). Both are the same
    class of bug as the earlier leak of exact holdings.

    So parse every alert back out and check it against the hand that bid it. An
    alert may quote a FLOOR the branch enforces; it may not quote a range the
    branch does not.
    """
    import re
    sym_to_suit = {v: k for k, v in ai.SUIT_SYM.items()}
    suits = '[♠♥♦♣]'
    re_len = re.compile(r'(\d+)\+ (' + suits + ')')
    re_maxlen = re.compile(r'(\d+) or fewer (' + suits + ')')
    re_min = re.compile(r'(\d+)\+ points')
    re_range = re.compile(r'(\d+)-(\d+) points')
    re_under = re.compile(r'under (\d+) points')
    re_fewer = re.compile(r'Fewer than (\d+) points')
    re_fewer_suit = re.compile(r'Fewer than (\d+) (' + suits + ')')
    re_hcp_min = re.compile(r'(\d+)\+ HCP')
    re_hcp_range = re.compile(r'(\d+)-(\d+) HCP')
    re_hcp_under = re.compile(r'(?:under|Fewer than) (\d+) HCP')
    re_exact = re.compile(r'exactly (\d+) (' + suits + ')')

    random.seed(23)
    checked = 0
    for index in range(90):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        guard = 0
        while not auction.is_complete and guard < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)
            groups = ai.eval_hand_sh(hands[who])['groups']
            points = ai._points(groups)
            hcp = gib.Hand(hands[who]).hcp
            held = {s: len(c) for s, c in groups.items()}
            for num in re_hcp_min.findall(why):
                assert hcp >= int(num), f"claimed {num}+ HCP holding {hcp}: {why!r}"
                checked += 1
            for low, high in re_hcp_range.findall(why):
                assert int(low) <= hcp <= int(high), (
                    f"claimed {low}-{high} HCP holding {hcp}: {why!r}")
                checked += 1
            for num in re_hcp_under.findall(why):
                assert hcp < int(num), f"claimed under {num} HCP holding {hcp}: {why!r}"
                checked += 1
            for num, sym in re_exact.findall(why):
                assert held[sym_to_suit[sym]] == int(num), (
                    f"claimed exactly {num} {sym}: {why!r}")
                checked += 1

            for num, sym in re_len.findall(why):
                assert held[sym_to_suit[sym]] >= int(num), (
                    f"claimed {num}+ {sym} holding {held[sym_to_suit[sym]]}: {why!r}")
                checked += 1
            for num, sym in re_maxlen.findall(why):
                assert held[sym_to_suit[sym]] <= int(num), (
                    f"claimed {num} or fewer {sym} holding "
                    f"{held[sym_to_suit[sym]]}: {why!r}")
                checked += 1
            for num in re_min.findall(why):
                assert points >= int(num), (
                    f"claimed {num}+ points holding {points}: {why!r}")
                checked += 1
            for low, high in re_range.findall(why):
                assert int(low) <= points <= int(high), (
                    f"claimed {low}-{high} points holding {points}: {why!r}")
                checked += 1
            for num in re_under.findall(why):
                assert points < int(num), (
                    f"claimed under {num} points holding {points}: {why!r}")
                checked += 1
            for num in re_fewer.findall(why):
                assert points < int(num), (
                    f"claimed fewer than {num} points holding {points}: {why!r}")
                checked += 1
            for num, sym in re_fewer_suit.findall(why):
                assert held[sym_to_suit[sym]] < int(num), (
                    f"claimed fewer than {num} {sym} holding "
                    f"{held[sym_to_suit[sym]]}: {why!r}")
                checked += 1
            auction.apply_call(who, call)
            guard += 1
    assert checked > 300, f"only checked {checked} claims"


def test_a_bid_alert_depends_only_on_the_auction_and_the_call():
    """An alert says what a call SHOWS, so it may depend on the auction so far
    and the call -- never on the cards. The same bid in the same auction must
    read the same whoever holds it; otherwise the wording itself is a leak.

    It was, five ways at once: a rebid alerted "6+" or "12+ points" by which
    branch fired, 1m "3+", "4+" or "5+" by the actual minor lengths, a contested
    two-level bid "Forcing" or "Free bid", and an answer to a takeout double
    quoted the suit's real length and point band. Passes are exempt here: their
    reasons are hand-dependent by nature and are hidden from the live table by
    the web app (`Game.liveAlerts`, tested in frontend/src/lib/lin.test.ts).
    """
    random.seed(21)
    seen: dict = {}
    for index in range(1500):
        hands = deal()
        auction = AuctionState(dealer=PLAYERS[index % 4], vulnerability='None')
        while not auction.is_complete and len(auction.calls) < 60:
            who = auction.current_player()
            call, why = ai.ai_bid_explained(who, hands[who], auction)
            if call != 'Pass':
                key = (tuple(c for _, c in auction.calls), call)
                first = seen.setdefault(key, why)
                assert first == why, (
                    f"same call, same auction, different alert -- it reads the "
                    f"hand out: {key}: {first!r} vs {why!r}")
            auction.apply_call(who, call)
    assert len(seen) > 1000, "too few bids exercised to mean anything"


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nFitted bidding calibration verified.")
