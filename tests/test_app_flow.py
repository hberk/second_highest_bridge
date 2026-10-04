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


def _start_play_as(declarer: str) -> AppTest:
    """A fresh app with a 2♠ contract by `declarer`, just after clicking Start play."""
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
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


def test_only_the_dummy_is_face_up():
    """The human sees their own hand and the dummy — never a concealed defender.

    South's own cards render as buttons rather than card faces while South is on
    play, so the card faces on the page are exactly the dummy's hand. North is an
    AI defender in both of these auctions and must not be visible at all. North
    and the dummy hold the same number of cards, so this asserts on identity
    rather than on a count, which would pass either way.
    """
    for declarer in ('East', 'West'):
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

    toggle_key = f"dd_on_{board}"
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
