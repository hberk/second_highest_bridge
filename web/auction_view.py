"""Auction presentation: the call grid, and the bidding box the human bids from.

Both were previously inlined in app.py (and the grid duplicated in
replayer_view.py). They live here so the live table, the post-auction recap and
the hand-history replayer all render an auction the same way.
"""
from __future__ import annotations
import re
import streamlit as st
from card import LEVELS, STRAINS, STRAIN_SYMBOLS, STRAIN_NAMES
from game import PLAYERS
from web.card_component import call_badge

# The four columns of a written auction, in the order hand records print them.
_AUCTION_COLUMNS = ['West', 'North', 'East', 'South']

#: The longest alert, the robots' own limit: it has to fit a tooltip.
ALERT_MAX = 70


def clean_alert(text: str | None) -> str:
    """A self-alert as one line of plain text, at most ALERT_MAX characters.

    This is NOT the XSS defence -- `call_badge` escapes every alert it renders,
    and that is the only place alert text reaches markup. It only keeps the
    tooltip one tidy line. Port: `cleanAlert` in frontend/src/lib/game.svelte.ts.
    """
    text = re.sub(r'[\x00-\x1f\x7f]+', ' ', text or '')
    return re.sub(r'\s+', ' ', text).strip()[:ALERT_MAX]


def live_alerts(calls: list[tuple[str, str]], alerts: dict | None,
                humans: tuple[str, ...] = ('South',)) -> dict:
    """The alerts the table may see while the board is still being played.

    A robot's pass explains WHY it passed ("Fewer than 6 points", "Fewer than
    3 spades and no five-card suit"), and the reason differs from hand to hand
    for the same pass in the same auction, so it reads the robot's cards out.
    A real table never alerts a natural pass. Those reasons are kept in the
    record and shown once the board is over; bids keep their alerts, which
    depend only on the auction and the call (tests/test_bidding_calibration.py).

    A human's own alert is shown even on a pass: it is a self-alert the player
    chose to make (a forcing pass, say), not a robot's reasoning.
    """
    return {i: why for i, why in (alerts or {}).items()
            if i < len(calls) and (calls[i][1] != 'Pass' or calls[i][0] in humans)}


def render_auction_grid(dealer: str, calls: list[tuple[str, str]],
                        show_dealer_tag: bool = True,
                        alerts: dict | None = None) -> None:
    """The auction as a four-column table, West to South, with leading blanks so
    each call sits under the seat that made it.

    `alerts` maps a call's index in `calls` to an explanation of what the bid
    shows. Alerted calls get a marker and reveal the explanation on hover, which
    is how a real table finds out what a convention means.
    """
    cols = st.columns(4)
    for i, seat in enumerate(_AUCTION_COLUMNS):
        is_dealer = (seat == dealer)
        tag = " · dealer" if (is_dealer and show_dealer_tag) else ""
        cls = "auction-head dealer-col" if is_dealer else "auction-head"
        cols[i].markdown(f'<div class="{cls}">{seat}{tag}</div>', unsafe_allow_html=True)

    lead_blanks = (PLAYERS.index(dealer) - PLAYERS.index('West')) % 4
    # carry each call's index alongside it, so an alert stays attached to its own
    # call once the leading blanks have shifted everything along
    display = [('—', None)] * lead_blanks + [(call, i) for i, (_, call) in enumerate(calls)]

    for row_start in range(0, len(display), 4):
        row_cols = st.columns(4)
        for i, (call, index) in enumerate(display[row_start:row_start + 4]):
            if call == '—':
                row_cols[i].markdown('<span class="bid-empty">—</span>', unsafe_allow_html=True)
            else:
                alert = (alerts or {}).get(index)
                row_cols[i].markdown(call_badge(call, alert), unsafe_allow_html=True)


def render_bidding_box(legal_calls: list[str], on_call, alert_key: str = 'self_alert') -> None:
    """The bidding box: every bid from 1C to 7NT laid out as seven level rows by
    five strain columns, with Pass / Double / Redouble above it.

    This is the layout BBO, RealBridge, IntoBridge and FunBridge all use. The
    whole ladder stays on screen with bids that are no longer available greyed
    out, so a player can see at a glance how much bidding room is left — which
    is the point of a bidding box, and what a level-then-strain picker hides.

    The alert box is a self-alert, as on BBO: type the explanation, then make
    the call, and `on_call(call, alert)` gets both. Pass an `alert_key` that
    changes with every call (app.py uses the auction's length), so the box is
    empty again for the next call: Streamlit can't clear a widget from the
    same run that read it.
    """
    st.markdown(
        '<div class="bidding-box-container">'
        '<div class="bidding-box-title">Your call</div>',
        unsafe_allow_html=True
    )

    alert = st.text_input(
        "Alert", key=alert_key, max_chars=ALERT_MAX,
        placeholder="Optional: explain your next call",
        help="Shown with your call as an alert. The robots don't read it.",
    )
    if alert.strip():
        st.caption("Your next call will be alerted.")

    with st.container(key="bidgrid"):
        # Pass / Double / Redouble first: Pass is the most-used call in any
        # auction, so it should never need a scroll to reach.
        act_cols = st.columns(3)
        actions = [('Pass', 'Pass', 'pass'), ('Double', 'X', 'dbl'), ('Redouble', 'XX', 'rdbl')]
        for col, (label, call, key_part) in zip(act_cols, actions):
            with col:
                if st.button(label, key=f"bidact_{key_part}",
                             disabled=(call not in legal_calls),
                             use_container_width=True):
                    on_call(call, alert)
                    st.rerun()

        st.markdown(
            '<div class="bid-grid-head">'
            + ''.join(
                f'<span class="{strain.lower()}" title="{STRAIN_NAMES[strain]}">'
                f'{STRAIN_SYMBOLS[strain]}</span>'
                for strain in STRAINS
            )
            + '</div>',
            unsafe_allow_html=True
        )

        for level in LEVELS:
            level_cols = st.columns(5)
            for col, strain in zip(level_cols, STRAINS):
                with col:
                    call = f"{level}{strain}"
                    label = f"{level}{STRAIN_SYMBOLS[strain]}"
                    # Key is <strain><level>, not <level><strain>, so one CSS
                    # prefix selector per strain can colour a whole column.
                    if st.button(label, key=f"bid_btn_{strain}{level}",
                                 disabled=(call not in legal_calls),
                                 use_container_width=True):
                        on_call(call, alert)
                        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
