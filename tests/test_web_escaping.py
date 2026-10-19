"""Every string that reaches the page through `unsafe_allow_html` is escaped.

The app renders its own markup: 42 `unsafe_allow_html` call sites and 1,256
lines of hand-written CSS (counted 2026-10-18). A few of those sites are static
literals and cannot inject anything; the rest build HTML from data.

**The app now takes free text in two places, both reviewed** (see
`REVIEWED_INPUTS` below): the self-alert box and LIN import. Both deliver only
alert text to the page, through `call_badge`, which escapes it; everything else
interpolated is still a seat name from a fixed list, a `Card` from a fixed
52-card deck, an integer, or alert text `ai.py` generates. There is no current
vulnerability, and the end-to-end tests here push hostile text through both
inputs in the running app to keep it that way.

The risk is the NEXT change. A player name, a saved-board label, a shareable
URL parameter or a chat line would reach those sites by a new path. This
file is the guardrail for that day: it pushes a hostile payload through every
public function in `web/` that returns or renders HTML, fails if the payload
survives raw, and fails on any input widget not in `REVIEWED_INPUTS`.

A function that REFUSES hostile input (raises) passes too: failing closed is a
valid defence. What must not happen is the payload arriving on the page intact.
"""
from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from card import Card
from web import card_component as cc
from web import felt_table

#: Payloads chosen to cover the three ways markup escapes a template: closing a
#: tag, breaking out of an attribute value, and surviving as a bare event
#: handler. If any arrives unescaped, the page can run script.
PAYLOADS = [
    '<script>alert(1)</script>',
    '"><img src=x onerror=alert(1)>',
    "' onmouseover='alert(1)",
    '</div><iframe src="javascript:alert(1)">',
]

#: What must never appear in rendered output. These are TAG OPENINGS, not
#: keywords: once `<` and `"` are entities, a string like `onerror=alert(1)` is
#: inert text content and perfectly safe to display. An earlier version of this
#: list banned the keywords too and failed on correctly-escaped output, which is
#: the classic way an over-strict security test gets switched off.
#:
#: Injection needs one of exactly two things: opening a new element (caught
#: here), or breaking out of an attribute value with a raw quote (caught by the
#: verbatim check below, since escaping turns ' and " into entities).
FORBIDDEN = ['<script', '<img', '<iframe', '<svg', '<object', '<embed']


def _assert_clean(html: str, payload: str, where: str) -> None:
    """The payload may appear escaped; it may not appear as live markup."""
    assert isinstance(html, str), f"{where} returned {type(html)!r}"
    lowered = html.lower()
    for bad in FORBIDDEN:
        assert bad not in lowered, (
            f"{where} let {bad!r} through from payload {payload!r}:\n{html[:400]}")
    # The raw payload must not survive verbatim either -- escaping it turns the
    # angle brackets into entities, so an exact match means it was interpolated.
    assert payload not in html, (
        f"{where} interpolated the payload verbatim: {html[:400]}")


def test_alert_text_cannot_inject_markup():
    """`call_badge`'s alert is the one string a non-trivial function generates,
    and the only place escaping exists today."""
    for payload in PAYLOADS:
        html = cc.call_badge('1S', payload)
        _assert_clean(html, payload, 'call_badge(alert=...)')


def test_every_string_parameter_that_reaches_html_is_escaped():
    """Push each payload through every public `web/` function that takes a str
    and returns markup. These are the functions a future player-name or
    saved-board-label feature would flow into."""
    hand = [Card('S', 'A'), Card('H', '10'), Card('C', '2')]
    checked = 0

    for payload in PAYLOADS:
        # (callable, kwargs, label) -- each exercises one str parameter.
        cases = [
            (cc.call_badge, {'call': payload}, 'call_badge(call=...)'),
            (cc.card_backs_html, {'count': 3, 'seat': payload},
             'card_backs_html(seat=...)'),
            (cc.seat_box_html, {'seat': payload, 'role': 'Declarer', 'hand': hand},
             'seat_box_html(seat=...)'),
            (cc.seat_box_html, {'seat': 'North', 'role': payload, 'hand': hand},
             'seat_box_html(role=...)'),
            (cc.suit_label, {'suit': payload}, 'suit_label(...)'),
            (felt_table.card_slot_html, {'player': payload, 'trick_dict': {}},
             'card_slot_html(player=...)'),
        ]
        for fn, kwargs, label in cases:
            try:
                out = fn(**kwargs)
            except Exception:
                continue          # refusing hostile input is a valid defence
            if out is None:
                continue
            _assert_clean(out, payload, label)
            checked += 1

    assert checked >= len(PAYLOADS) * 3, (
        f"only {checked} string parameters were actually exercised -- the "
        f"signatures moved and this test stopped covering them")


def test_a_hostile_card_cannot_inject_markup():
    """`Card` is a plain value object with no validation, so a future feature
    that builds one from outside data (a saved board, an imported PBN file)
    could carry markup in its rank or suit."""
    for payload in PAYLOADS:
        for card in (Card('S', payload), Card(payload, 'A')):
            try:
                html = cc.card_face_html(card)
            except Exception:
                continue
            _assert_clean(html, payload, 'card_face_html(...)')


#: Every free-text input the app has, each reviewed. The review, in full:
#:
#: - The self-alert box (`web/auction_view.py`, text_input) yields alert text.
#:   It is stored in `bid_alerts` and reaches markup in exactly one place,
#:   `call_badge`, which escapes it.
#: - LIN import (`web/replayer_view.py`, text_area and file_uploader) yields a
#:   record rebuilt by `bridge.lin.from_lin`, where every field comes from a
#:   fixed vocabulary (seats, the 52 cards, legal calls, vulnerabilities) or is
#:   an integer -- player names and board titles in the LIN are read past, not
#:   kept. The one free-text field that survives is alert text: `call_badge`
#:   again. Parse errors can quote the input, so they are shown with `st.code`.
#:
#: So the data-driven `unsafe_allow_html` sites still only ever see fixed
#: values, plus alert text through the one escaping function. The tests below
#: check that end to end in the running app.
REVIEWED_INPUTS = {
    ('auction_view.py', 'text_input'),
    ('replayer_view.py', 'text_area'),
    ('replayer_view.py', 'file_uploader'),
}


def test_every_free_text_input_has_been_reviewed():
    """Fails the moment an input appears that the review above doesn't cover:
    each new one needs its own trace through the `unsafe_allow_html` sites."""
    watched = ['text_input', 'text_area', 'chat_input', 'file_uploader',
               'query_params', 'experimental_get_query_params']
    sources = [root_dir / 'app.py'] + sorted((root_dir / 'web').glob('*.py'))
    found = set()
    for path in sources:
        text = path.read_text(encoding='utf-8')
        for widget in watched:
            if f'.{widget}' in text:
                found.add((path.name, widget))
    unreviewed = found - REVIEWED_INPUTS
    assert not unreviewed, (
        "New free-text input: " + "; ".join(f"{f} uses st.{w}" for f, w in sorted(unreviewed))
        + ". Trace where its value can reach unsafe_allow_html, escape it there "
        "(html.escape(value, quote=True)), then add it to REVIEWED_INPUTS.")


def _page(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def test_a_hostile_self_alert_is_escaped_on_the_live_page():
    from streamlit.testing.v1 import AppTest
    for payload in PAYLOADS:
        at = AppTest.from_file(str(root_dir / 'app.py'), default_timeout=30)
        at.run()
        auction = at.session_state['auction']
        n = len(auction.calls)
        at.text_input(key=f"self_alert_{at.session_state['board_num']}_{n}").input(payload).run()
        at.button(key='bidact_pass').click().run()
        assert not at.exception, at.exception
        stored = at.session_state['bid_alerts'][n]
        html = _page(at)
        assert 'bid-alert-tip' in html, "the alert was not rendered at all"
        _assert_clean(html, stored, 'self-alert on the live page')


def test_a_hostile_alert_in_imported_lin_is_escaped():
    from streamlit.testing.v1 import AppTest
    from tests.test_lin import _boards
    from bridge.lin import to_lin
    board = next(b for b in _boards() if len(b['tricks_log']) == 13)
    for payload in PAYLOADS:
        lin = to_lin({**board, 'bid_alerts': {0: payload}},
                     names={'South': payload, 'North': payload})   # names are read past
        at = AppTest.from_file(str(root_dir / 'app.py'), default_timeout=30)
        at.run()
        at.text_area(key='hist_lin_text').input(lin).run()
        at.button(key='hist_lin_import').click().run()
        assert not at.exception, at.exception
        imported = at.session_state['hand_history'][-1]
        assert imported.get('imported'), "the board was not imported"
        html = _page(at)
        assert 'bid-alert-tip' in html, "the imported alert was not rendered"
        _assert_clean(html, imported['bid_alerts'][0], 'imported LIN alert')
        _assert_clean(html, payload, 'imported LIN player name')


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nHTML escaping verified.")
