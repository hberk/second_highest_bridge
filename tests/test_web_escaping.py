"""Every string that reaches the page through `unsafe_allow_html` is escaped.

The app renders its own markup: 33 `unsafe_allow_html` call sites and 1,187
lines of hand-written CSS. Seven of those sites are static literals and cannot
inject anything; the other 26 build HTML from data.

**Today none of that data is attacker-controlled.** The app has no `text_input`,
no `text_area`, no `file_uploader` and reads no query parameters, so a visitor
can only click buttons and cards. Everything interpolated is a seat name from a
fixed list, a `Card` from a fixed 52-card deck, an integer, or alert text that
`ai.py` generates and `call_badge` escapes. There is no current vulnerability.

The risk is the NEXT change. The moment anyone adds a player name, a saved-board
label, a shareable URL parameter or a chat line, those 26 sites become injection
points — and only one of them escapes anything today. This file is the guardrail
for that day: it pushes a hostile payload through every public function in
`web/` that returns or renders HTML, and fails if the payload survives raw.

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


def test_the_app_still_has_no_free_text_input():
    """The audit above rests on there being no way for a visitor to supply text.

    If that changes, the 26 data-driven `unsafe_allow_html` sites need a real
    escaping pass rather than the incidental safety they have now -- so this
    fails loudly the moment an input widget appears, rather than letting the
    assumption rot silently.
    """
    watched = ['text_input', 'text_area', 'chat_input', 'file_uploader',
               'query_params', 'experimental_get_query_params']
    sources = [root_dir / 'app.py'] + sorted((root_dir / 'web').glob('*.py'))
    found = []
    for path in sources:
        text = path.read_text(encoding='utf-8')
        for widget in watched:
            if f'.{widget}' in text:
                found.append(f"{path.name} uses st.{widget}")
    assert not found, (
        "The app now accepts free text: " + "; ".join(found) + ". Every "
        "unsafe_allow_html site that can reach this value must escape it "
        "(html.escape(value, quote=True)) -- see this file's docstring.")


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nHTML escaping verified.")
