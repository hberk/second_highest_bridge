"""Auction presentation: the call grid, and the bidding box the human bids from.

Both were previously inlined in app.py (and the grid duplicated in
replayer_view.py). They live here so the live table, the post-auction recap and
the hand-history replayer all render an auction the same way.
"""
from __future__ import annotations
import streamlit as st
from card import LEVELS, STRAINS, STRAIN_SYMBOLS, STRAIN_NAMES
from game import PLAYERS
from web.card_component import call_badge

# The four columns of a written auction, in the order hand records print them.
_AUCTION_COLUMNS = ['West', 'North', 'East', 'South']


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


def render_bidding_box(legal_calls: list[str], on_call) -> None:
    """The bidding box: every bid from 1C to 7NT laid out as seven level rows by
    five strain columns, with Pass / Double / Redouble above it.

    This is the layout BBO, RealBridge, IntoBridge and FunBridge all use. The
    whole ladder stays on screen with bids that are no longer available greyed
    out, so a player can see at a glance how much bidding room is left — which
    is the point of a bidding box, and what a level-then-strain picker hides.
    """
    st.markdown(
        '<div class="bidding-box-container">'
        '<div class="bidding-box-title">Your call</div>',
        unsafe_allow_html=True
    )

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
                    on_call(call)
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
                        on_call(call)
                        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
