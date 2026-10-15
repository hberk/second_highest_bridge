"""Game-flow tests: drive the real Streamlit app headlessly with streamlit's AppTest."""
from __future__ import annotations
import re
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from streamlit.testing.v1 import AppTest
from card import SUIT_SYMBOLS
from game import clockwise_from, PARTNERS, PARTNERSHIP

APP = str(root_dir / 'app.py')


def _start_play_as(declarer: str, auto_play: bool = False) -> AppTest:
    """A fresh app with a 2♠ contract by `declarer`, just after clicking Start play.

    Auto-play (on by default in the app) is switched off unless asked for:
    these tests click cards themselves, and a forced card played for them
    would leave nothing to click."""
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    if not auto_play:
        at.checkbox(key='auto_play_choice').uncheck().run()
    leader = clockwise_from(declarer)[1]
    at.session_state['contract'] = {
        'level': 2, 'strain': 'S', 'declarer': declarer, 'dummy': PARTNERS[declarer],
        'leader': leader, 'tricks_needed': 8, 'trump': 'S', 'doubled': 'None',
        'vulnerability': 'None', 'side': PARTNERSHIP[declarer],
    }
    at.session_state['trump'] = 'S'
    at.session_state['leader'] = leader
    at.session_state['order'] = clockwise_from(leader)
    at.session_state['phase'] = 'auction_done'
    at.run()
    at.button(key='start_play_btn').click().run()
    return at


def _card_buttons(at: AppTest, seat: str) -> list:
    """Enabled (clickable) card buttons in `seat`'s hand."""
    return [b for b in at.button if (b.key or '').startswith(f'play_{seat}_') and not b.disabled]


def _play_out(at: AppTest) -> None:
    """Click through tricks to the result screen, asserting the game never waits on a card."""
    for _ in range(40):
        if any(b.label.startswith('Deal Next Board') for b in at.button):
            return
        assert at.session_state['phase'] == 'trick_done', "stuck waiting for a card choice"
        assert not _card_buttons(at, 'North') and not _card_buttons(at, 'South')
        nxt = next(b for b in at.button if b.label.startswith(('Next trick', 'See final')))
        nxt.click().run()
    raise AssertionError("hand never finished")


def test_south_declarer_plays_dummy_from_north():
    at = _start_play_as('South')            # West leads, then it's dummy's turn
    assert at.session_state['phase'] == 'playing'
    north = _card_buttons(at, 'North')
    assert north, "declarer should be able to click dummy's (North's) cards"
    assert not _card_buttons(at, 'South')

    north[0].click().run()                  # dummy plays; East (AI) follows; South is next
    seats = [p for p, _ in at.session_state['trick']]
    assert seats == ['West', 'North', 'East'], seats
    assert _card_buttons(at, 'South')


def test_defending_south_plays_only_own_hand():
    for declarer in ('East', 'West'):
        at = _start_play_as(declarer)
        assert _card_buttons(at, 'South'), f"{declarer} declares: South should be on play"
        assert not _card_buttons(at, 'North'), f"{declarer} declares: North is an AI defender"


def test_north_declarer_plays_both_hands():
    at = _start_play_as('North')            # South is dummy: no card is ever the human's
    headers = [m.value for m in at.markdown if 'hand-header' in m.value]
    assert any('North plays this hand' in h for h in headers)
    _play_out(at)
    taken = at.session_state['tricks_taken']
    assert taken['N/S'] + taken['E/W'] == 13


def test_history_tab_renders_after_hand():
    at = _start_play_as('North')
    _play_out(at)
    assert len(at.selectbox(key='hist_board_sel').options) == 1


def _face_up(at) -> set:
    """The (rank, suit-symbol) of every card rendered face-up on the page."""
    blob = "\n".join(m.value for m in at.markdown)
    return set(re.findall(
        r'class="pcard-rank"[^>]*>([^<]+)</span>'
        r'<span class="pcard-suit"[^>]*>([^<]+)</span>', blob))


def _cards(hand) -> set:
    return {(c.rank, SUIT_SYMBOLS[c.suit]) for c in hand}


def test_dummy_stays_hidden_until_the_opening_lead():
    """East declares, so South makes the opening lead -- blind, as in real bridge.
    An earlier version laid dummy face-up the moment the auction ended."""
    at = _start_play_as('East')
    assert not at.session_state['trick'] and _card_buttons(at, 'South')
    assert not (_face_up(at) & _cards(at.session_state['hands']['West'])), (
        "dummy is face-up before the opening lead")

    _card_buttons(at, 'South')[0].click().run()
    remaining = _cards(at.session_state['hands']['West'])
    assert remaining and remaining <= _face_up(at), "dummy did not go down after the lead"


def test_only_the_dummy_is_face_up():
    """The human sees their own hand and the dummy — never a concealed defender.

    South's own cards render as buttons rather than card faces while South is on
    play, so the card faces on the page are exactly the dummy's hand. North is an
    AI defender here and must not be visible at all. North and the dummy hold
    the same number of cards, so this asserts on identity rather than on a
    count, which would pass either way. West declares, so North has already led
    and dummy is down by South's turn; the East-declares case, where South leads
    with dummy still hidden, is the test above.
    """
    for declarer in ('West',):
        at = _start_play_as(declarer)
        dummy = PARTNERS[declarer]
        shown = _face_up(at)
        expected = {(c.rank, SUIT_SYMBOLS[c.suit]) for c in at.session_state['hands'][dummy]}
        concealed = {(c.rank, SUIT_SYMBOLS[c.suit]) for c in at.session_state['hands']['North']}
        assert not (shown & concealed), (
            f"{declarer} declares: North is a defender, but {sorted(shown & concealed)} "
            f"are face-up")
        assert shown == expected, (
            f"{declarer} declares: expected dummy {dummy}'s hand face-up; "
            f"missing {sorted(expected - shown)}, extra {sorted(shown - expected)}")


def test_declaring_side_sees_its_dummy():
    """South declares, North is dummy: North's hand is face-up and clickable."""
    at = _start_play_as('South')
    assert _card_buttons(at, 'North'), "dummy should be playable by the declarer"


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
    print("All app-flow tests passed.")


def _play_to_history(declarer: str) -> AppTest:
    """Play a whole board to completion, clicking any card the human is offered."""
    at = _start_play_as(declarer)
    for _ in range(200):
        if any(b.label.startswith('Deal Next Board') for b in at.button):
            return at
        for seat in ('North', 'South'):
            buttons = _card_buttons(at, seat)
            if buttons:
                buttons[0].click().run()
                break
        else:
            advance = [b for b in at.button
                       if b.label.startswith(('Next trick', 'See final'))]
            if not advance:
                raise AssertionError("hand stalled with nothing to click")
            advance[0].click().run()
    raise AssertionError("hand never finished")


def test_analysis_panel_produces_results_when_switched_on():
    """Guards the double dummy post-mortem end to end.

    The panel caches failures so it never retries them, which means a broken
    analysis reports itself as 'nothing analysed yet' indefinitely. This asserts
    real results appear, so that state cannot ship unnoticed.
    """
    at = _play_to_history('South')
    board = at.session_state['hand_history'][-1]['board_num']

    toggle_key = f"hist_dd_on_{board}"
    assert toggle_key in [t.key for t in at.toggle], "analysis toggle not rendered"

    at.toggle(key=toggle_key).set_value(True).run()
    assert not at.exception, at.exception

    warnings = [w.value for w in at.warning]
    assert not any('Nothing analysed' in w for w in warnings), warnings
    # The app shows its own st.error for a failed contract; only analysis
    # failures name decisions, so match on that rather than on any error.
    errors = [e.value for e in at.error if 'could not be analysed' in e.value]
    assert not errors, f"analysis reported errors: {errors}"

    labels = {m.label: m.value for m in at.metric}
    assert 'Decisions reviewed' in labels, labels
    reviewed, _, total = labels['Decisions reviewed'].partition(' of ')
    assert int(reviewed) > 0 and int(reviewed) == int(total), labels


# ── Self-alerts, LIN, last trick, auto-play, fast play, session score ────────

def _south_to_call(at: AppTest) -> bool:
    auction = at.session_state['auction']
    return not auction.is_complete and auction.current_player() == 'South'


def _alert_box(at: AppTest):
    n = len(at.session_state['auction'].calls)
    return at.text_input(key=f"self_alert_{at.session_state['board_num']}_{n}")


def test_a_self_alert_goes_with_the_call_and_shows_even_on_a_pass():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert _south_to_call(at)
    index = len(at.session_state['auction'].calls)
    _alert_box(at).input('  Forcing\n pass ').run()
    at.button(key='bidact_pass').click().run()
    assert not at.exception, at.exception
    assert at.session_state['bid_alerts'][index] == 'Forcing pass'
    page = "\n".join(m.value for m in at.markdown)
    assert 'Forcing pass' in page, "a human's alerted pass must show while the board is live"
    if _south_to_call(at):
        assert not _alert_box(at).value, "the alert box must be empty for the next call"


def _drive(at: AppTest, max_steps: int = 400) -> None:
    """Pass every call and click the first card offered, to the result screen.
    A passed-out board counts as finished."""
    for _ in range(max_steps):
        assert not at.exception, at.exception
        if any(b.label.startswith('Deal Next Board') for b in at.button):
            return
        if _south_to_call(at):
            at.button(key='bidact_pass').click().run()
        elif any(b.key == 'start_play_btn' for b in at.button):
            at.button(key='start_play_btn').click().run()
        elif _card_buttons(at, 'North') or _card_buttons(at, 'South'):
            (_card_buttons(at, 'North') or _card_buttons(at, 'South'))[0].click().run()
        else:
            nxt = [b for b in at.button if b.label.startswith(('Next trick', 'See final'))]
            assert nxt, "stalled with nothing to click"
            nxt[0].click().run()
    raise AssertionError("board never finished")


def _real_board() -> AppTest:
    """A board with a real auction (South passes throughout) played to the
    end. `_start_play_as` fakes the contract without finishing the auction,
    which LIN rightly refuses to import."""
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    at.checkbox(key='auto_play_choice').uncheck().run()
    for _ in range(10):
        _drive(at)
        if at.session_state['hand_history']:
            return at
        next(b for b in at.button if b.label.startswith('Deal Next Board')).click().run()
    raise AssertionError("ten boards in a row passed out")


def test_lin_export_and_import_through_the_app():
    from bridge.lin import to_lin
    at = _real_board()
    board = at.session_state['hand_history'][-1]
    assert to_lin(board) in [c.value for c in at.code], "History should show the board's LIN"

    at.text_area(key='hist_lin_text').input(to_lin(board)).run()
    at.button(key='hist_lin_import').click().run()
    assert not at.exception, at.exception
    history = at.session_state['hand_history']
    assert len(history) == 2 and history[-1]['imported']
    assert history[-1]['result'] == board['result']
    assert history[-1]['tricks_taken'] == board['tricks_taken']
    assert any('Imported' in o for o in at.selectbox(key='hist_board_sel').options)

    # Imported boards are not part of your session score.
    labels = [e.label for e in at.expander if e.label.startswith('Session')]
    boards = 1 + at.session_state.get('passed_out_count', 0)
    assert labels and f"· {boards} board" in labels[0], labels


def test_bad_lin_is_refused_without_crashing():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    at.text_area(key='hist_lin_text').input('md|1SAKQ|this is not a deal').run()
    at.button(key='hist_lin_import').click().run()
    assert not at.exception, at.exception
    assert any('Not imported' in e.value for e in at.error)
    assert at.session_state['hand_history'] == []


def test_last_trick_shows_the_previous_trick_and_drops_on_the_next_card():
    at = _start_play_as('South')
    for _ in range(12):
        if at.session_state['phase'] == 'playing' and at.session_state['tricks_log']:
            break
        if _card_buttons(at, 'North') or _card_buttons(at, 'South'):
            (_card_buttons(at, 'North') or _card_buttons(at, 'South'))[0].click().run()
        else:
            next(b for b in at.button if b.label.startswith('Next trick')).click().run()
    assert at.session_state['tricks_log'], "never reached trick 2"
    at.button(key='last_trick_btn').click().run()
    assert at.button(key='last_trick_btn').label.startswith('↩')
    last = at.session_state['tricks_log'][-1]
    assert any(f"Trick {last['trick_num']}:" in c.value for c in at.caption)

    (_card_buttons(at, 'North') or _card_buttons(at, 'South'))[0].click().run()
    btn = [b for b in at.button if b.key == 'last_trick_btn']
    assert not btn or btn[0].label.startswith('👁'), "playing a card should end the peek"


def test_auto_play_never_leaves_a_forced_card_to_the_human():
    at = _start_play_as('South', auto_play=True)
    for _ in range(80):
        assert not at.exception, at.exception
        if any(b.label.startswith('Deal Next Board') for b in at.button):
            return
        offered = _card_buttons(at, 'North') or _card_buttons(at, 'South')
        if at.session_state['phase'] == 'playing':
            assert len(offered) > 1, "a forced card was left to the human"
            offered[0].click().run()
        else:
            next(b for b in at.button if b.label.startswith(('Next trick', 'See final'))).click().run()
    raise AssertionError("hand never finished")


def test_fast_play_moves_on_by_itself():
    """North declares, so every card is a robot's: after Start play, fast play
    should run the board to the end with no further clicks (~16 s)."""
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.checkbox(key='fast_play_choice').check().run()
    at.session_state['contract'] = {
        'level': 2, 'strain': 'S', 'declarer': 'North', 'dummy': 'South',
        'leader': 'East', 'tricks_needed': 8, 'trump': 'S', 'doubled': 'None',
        'vulnerability': 'None', 'side': 'N/S',
    }
    at.session_state['trump'] = 'S'
    at.session_state['leader'] = 'East'
    at.session_state['order'] = clockwise_from('East')
    at.session_state['phase'] = 'auction_done'
    at.run()
    at.button(key='start_play_btn').click().run()
    assert not at.exception, at.exception
    assert at.session_state['game_over'], "fast play should run the board to the end"


def test_session_scoreboard_counts_boards():
    at = _play_to_history('South')
    labels = [e.label for e in at.expander if e.label.startswith('Session')]
    assert labels and '· 1 board ·' in labels[0], labels


def test_a_finished_challenge_board_renders_both_reviews():
    """The challenge review renders the history view a second time in the
    same run; its widget keys must not collide with the History tab's."""
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.checkbox(key='auto_play_choice').uncheck().run()
    for _ in range(10):
        next(b for b in at.button if b.label.startswith('Deal a challenge board')).click().run()
        _drive(at)
        # A passed-out board is graded too, but has no history to review.
        if at.session_state.get('challenge') and at.session_state['hand_history']:
            break
    assert at.session_state.get('challenge'), "no challenge board reached play"
    assert not at.exception, at.exception
    assert at.selectbox(key='chal_board_sel').options
    assert at.selectbox(key='hist_board_sel').options


def _deal_passed_out_by_everyone(board_num: int) -> int:
    """A library deal the robots pass out when South passes too, for the
    dealer and vulnerability board `board_num` gets."""
    import ai
    import challenge
    from game import AuctionState, DEALER_ROTATION, VUL_ROTATION
    for deal_id in challenge.deal_ids():
        hands = challenge.hands_for(deal_id)
        a = AuctionState(dealer=DEALER_ROTATION[(board_num - 1) % 4],
                         vulnerability=VUL_ROTATION[(board_num - 1) % 16])
        while not a.is_complete:
            p = a.current_player()
            a.apply_call(p, 'Pass' if p == 'South' else ai.ai_bid(p, hands[p], a))
        if a.passed_out:
            return deal_id
    raise AssertionError("no library deal passes out")


def test_a_passed_out_challenge_board_is_graded():
    """Passing out scores 0 against whatever the robots made of the cards.
    It used to skip grading: no comparison, the deal could be dealt again,
    and the Challenge tab said the board was still in play."""
    import random
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    target = _deal_passed_out_by_everyone(at.session_state['board_num'] + 1)
    choice = random.choice
    random.choice = lambda seq: target
    try:
        next(b for b in at.button if b.label.startswith('Deal a challenge board')).click().run()
    finally:
        random.choice = choice
    assert at.session_state['challenge_id'] == target
    while _south_to_call(at):
        at.button(key='bidact_pass').click().run()
    assert not at.exception, at.exception
    assert at.session_state['auction'].passed_out
    ch = at.session_state.get('challenge')
    assert ch, "a passed-out challenge board was not graded"
    assert ch['you']['passed_out'] and ch['you']['actual'] == 0
    assert at.session_state['challenge_log'][-1]['deal_id'] == target
    page = "\n".join(m.value for m in at.markdown)
    assert 'Where the points went' in page
    assert not any('Challenge board in play' in i.value for i in at.info)
    options = at.selectbox(key='chal_board_sel').options
    assert any(o.startswith('🧑 Your board') for o in options), options
