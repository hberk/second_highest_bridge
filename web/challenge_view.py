"""Head-to-head panel: you and the robots on the same deal.

Shows three numbers per board -- what you scored, what the all-robot table
scored on the identical cards, and par -- and then the part a single score
cannot tell you: how much of the gap was the AUCTION and how much was the CARD
PLAY.

That split is what makes "is the robot good at bidding" and "is it good at
declaring" separate questions. Measured over the 372 library boards the robots
can reach a contract on, they are very different questions: the auction gives
away a mean of 144 points a board, the card play 32, and the median play loss is
ZERO -- more than half of all boards are played perfectly. The robot declares
well and bids badly, and this panel is where a player can see that for
themselves rather than take it on trust.
"""
from __future__ import annotations

import html

import streamlit as st

from card import STRAIN_SYMBOLS

#: Strain glyphs, falling back to the bare letter for anything unexpected.
def _strain(sym: str) -> str:
    return STRAIN_SYMBOLS.get(sym, html.escape(str(sym), quote=True))


def _contract_label(contract: dict | None) -> str:
    if contract is None:
        return 'passed out'
    return f"{contract['level']}{_strain(contract['strain'])} by {contract['declarer']}"


def _signed(n: int) -> str:
    return f"{n:+d}"


def render_scoreline(challenge: dict) -> None:
    """The headline: you against the robots on this board."""
    you, robot = challenge['you'], challenge['robot']
    margin = challenge['margin']

    if margin > 0:
        verdict, tone = f"You beat the robots by {margin}", 'won'
    elif margin < 0:
        verdict, tone = f"The robots beat you by {-margin}", 'lost'
    else:
        verdict, tone = "Dead level with the robots", 'level'

    st.markdown(
        f'<div class="challenge-verdict is-{tone}">{html.escape(verdict)}</div>',
        unsafe_allow_html=True)

    cols = st.columns(3)
    cols[0].metric("You", _signed(you['actual']))
    cols[1].metric("Robots", _signed(robot['actual']),
                   delta=_signed(margin), delta_color='inverse')
    cols[2].metric("Par (best available)", _signed(you['par']['score']),
                   help="The most this deal offered your side with perfect "
                        "bidding and perfect play. It ignores whether the "
                        "opponents would have competed over it, so treat it as "
                        "a ceiling rather than a score anyone could guarantee.")


def render_breakdown(challenge: dict) -> None:
    """Where the points went: the auction, or the cards."""
    you, robot = challenge['you'], challenge['robot']

    st.markdown('<div class="section-title">Where the points went</div>',
                unsafe_allow_html=True)

    rows = [
        ("Contract reached", _contract_label(
            None if you.get('passed_out') else st.session_state.get('contract')),
         _contract_label(challenge.get('robot_contract'))),
        ("Lost in the auction", _signed(-you['bidding_loss']),
         _signed(-robot['bidding_loss'])),
        ("Lost in the card play", _signed(-you['play_loss']),
         _signed(-robot['play_loss'])),
        ("Final score", _signed(you['actual']), _signed(robot['actual'])),
    ]
    body = ''.join(
        f'<tr><th>{html.escape(label)}</th>'
        f'<td>{html.escape(str(mine))}</td>'
        f'<td>{html.escape(str(theirs))}</td></tr>'
        for label, mine, theirs in rows)
    st.markdown(
        f'<table class="challenge-table">'
        f'<thead><tr><th></th><th>You</th><th>Robots</th></tr></thead>'
        f'<tbody>{body}</tbody></table>',
        unsafe_allow_html=True)

    st.caption(
        "A loss is points given away against par. The two add up to the whole "
        "gap exactly, so they separate bidding judgement from card play."
    )


def render_match_total(log: list[dict]) -> None:
    """Running totals across every challenge board this session."""
    if not log:
        return
    boards = len(log)
    you = sum(r['you'] for r in log)
    robot = sum(r['robot'] for r in log)
    won = sum(1 for r in log if r['margin'] > 0)
    drawn = sum(1 for r in log if r['margin'] == 0)

    st.markdown('<div class="section-title">Match</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].metric("Boards", boards)
    cols[1].metric("Your total", _signed(you))
    cols[2].metric("Robot total", _signed(robot))
    cols[3].metric("Margin", _signed(you - robot))
    st.caption(f"Won {won}, drew {drawn}, lost {boards - won - drawn}. "
               f"Across the library the robots give away a mean of 149 points a "
               f"board in the auction and 28 in the play — the auction is where "
               f"they are beatable.")

    your_bid = sum(r['your_bidding_loss'] for r in log) / boards
    your_play = sum(r['your_play_loss'] for r in log) / boards
    bot_bid = sum(r['robot_bidding_loss'] for r in log) / boards
    bot_play = sum(r['robot_play_loss'] for r in log) / boards
    st.markdown(
        f'<table class="challenge-table">'
        f'<thead><tr><th>Mean loss per board</th><th>You</th><th>Robots</th></tr></thead>'
        f'<tbody>'
        f'<tr><th>Auction</th><td>{your_bid:.0f}</td><td>{bot_bid:.0f}</td></tr>'
        f'<tr><th>Card play</th><td>{your_play:.0f}</td><td>{bot_play:.0f}</td></tr>'
        f'</tbody></table>',
        unsafe_allow_html=True)
