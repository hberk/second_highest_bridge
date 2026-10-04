from __future__ import annotations
import html
import streamlit as st
from card import Card, SUIT_SYMBOLS, SUIT_NAMES
from web.card_component import suit_colors, suit_colors_light


def card_slot_html(player: str, trick_dict: dict[str, Card], winner: str | None = None) -> str:
    """Renders a card on the green felt table or an empty slot."""
    if player in trick_dict:
        c = trick_dict[player]
        color = suit_colors()[c.suit]
        is_winner = (winner == player)
        win_class = "winner-card" if is_winner else ""
        badge = '<div class="winner-badge">★ 2nd Highest</div>' if is_winner else ""
        safe_rank = html.escape(str(c.rank), quote=True)
        return (
            f'<div class="felt-card {win_class}">'
            f'  <div class="felt-card-rank" style="color:{color}">{safe_rank}</div>'
            f'  <div class="felt-card-suit" style="color:{color}" aria-hidden="true">'
            f'{SUIT_SYMBOLS[c.suit]}</div>'
            f'  <span class="sr-only">{safe_rank} of {SUIT_NAMES[c.suit]}'
            f'{", wins the trick" if is_winner else ""}</span>'
            f'  {badge}'
            f'</div>'
        )
    safe_player = html.escape(str(player), quote=True)
    return (f'<div class="empty-felt-slot">'
            f'<span class="slot-letter" aria-hidden="true">{safe_player[:1]}</span>'
            f'<span class="sr-only">{safe_player} has not played yet</span></div>')


def render_felt_table(
    trick: list[tuple[str, Card]],
    trump: str | None,
    winner: str | None = None,
    display_num: int = 1,
    contract: dict | None = None,
    tricks_taken: dict[str, int] | None = None
) -> None:
    """Renders the central green felt Bridge table with North, West, East, South played cards."""
    pm = dict(trick)
    led_suit = trick[0][1].suit if trick else None
    if led_suit:
        led_ink = suit_colors_light()[led_suit]
        led_badge = (f'<span class="led-tag">'
                     f'<span aria-hidden="true">Led: '
                     f'<span style="color:{led_ink}">{SUIT_SYMBOLS[led_suit]}</span></span>'
                     f'<span class="sr-only">Led: {SUIT_NAMES[led_suit]}</span></span>')
    else:
        led_badge = ''

    # Running trick count, which the online clients keep beside the table so a
    # declarer never has to look away to know where the contract stands.
    if tricks_taken:
        tally = (f'<div class="felt-tally">'
                 f'<span class="us">N/S {tricks_taken.get("N/S", 0)}</span>'
                 f'<span>E/W {tricks_taken.get("E/W", 0)}</span>'
                 f'</div>')
    else:
        tally = ''

    def seat_role(p: str) -> str:
        if not contract:
            return p.upper()
        if contract.get('dummy') == p:
            return f"{p.upper()} (Dummy)"
        if contract.get('declarer') == p:
            return f"{p.upper()} (Declarer)"
        return f"{p.upper()} (Defender)"

    html = f"""
    <div class="bridge-felt-container">
        <div class="felt-top">
            <div class="seat-label">{seat_role('North')}</div>
            {card_slot_html('North', pm, winner)}
        </div>
        <div class="felt-middle">
            <div class="felt-west-side">
                <div class="seat-label">{seat_role('West')}</div>
                {card_slot_html('West', pm, winner)}
            </div>
            <div class="felt-center-info">
                <div class="trick-title">TRICK {display_num} / 13</div>
                <div class="trick-sub">{led_badge}</div>
                <div class="felt-rule">2nd-Highest in winning suit wins</div>
                {tally}
            </div>
            <div class="felt-east-side">
                <div class="seat-label">{seat_role('East')}</div>
                {card_slot_html('East', pm, winner)}
            </div>
        </div>
        <div class="felt-bottom">
            {card_slot_html('South', pm, winner)}
            <div class="seat-label">{seat_role('South')}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
