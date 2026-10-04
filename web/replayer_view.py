from __future__ import annotations
import streamlit as st
from card import Card, SUIT_SYMBOLS, STRAIN_SYMBOLS
from game import PLAYERS, PARTNERSHIP
from web.card_component import seat_box_html
from web.auction_view import render_auction_grid
from web.felt_table import render_felt_table
from web.analysis_view import render_analysis


def _role(contract: dict, seat: str) -> str:
    if contract['declarer'] == seat:
        return 'Declarer'
    if contract['dummy'] == seat:
        return 'Dummy'
    return 'Defender'


def render_history_tab(hand_history: list[dict]) -> None:
    """Renders the entire Hand History & Card-by-Card Replayer view."""
    if not hand_history:
        st.info("📭 No completed hands yet. Play a board and then return here to review it!")
        return

    # ── Board Selector ────────────────────────────────────────────────────────
    def board_label(h: dict) -> str:
        # A record may carry its own label -- challenge mode uses this to put
        # "your board" and "the robots' board" side by side on the same deal.
        prefix = h.get('label') or f"Board #{h['board_num']}"
        if h['passed_out']:
            return f"{prefix} — Passed Out"
        c = h['contract']
        r = h['result']
        strain_sym = STRAIN_SYMBOLS[c['strain']]
        made_str = "Made" if r['made'] else "Down"
        pts_str = f"+{r['points']}" if r['winner'] == c['side'] else f"-{r['points']}"
        return (f"{prefix}: {c['level']}{strain_sym} by {c['declarer']} "
                f"({c['doubled']}) — {made_str} {pts_str}pts")

    board_options = [board_label(h) for h in reversed(hand_history)]
    board_indices = list(reversed(range(len(hand_history))))
    selected_label = st.selectbox("📋 Select a board to review:", board_options, key="hist_board_sel")
    sel_idx = board_indices[board_options.index(selected_label)]
    hb = hand_history[sel_idx]

    if hb['passed_out']:
        st.warning(f"🛑 **Board #{hb['board_num']}** — Passed Out (4 passes, no contract)")
        return

    h_contract = hb['contract']
    h_result = hb['result']
    h_trump = h_contract['trump']
    h_tricks = hb['tricks_log']
    c_sym = STRAIN_SYMBOLS[h_contract['strain']]

    st.divider()

    # ── Result Summary Card ───────────────────────────────────────────────────
    r_cols = st.columns([2, 1])
    with r_cols[0]:
        st.subheader(f"Board #{hb['board_num']}  |  Dealer: {hb['dealer']}  |  Vul: {hb['vulnerability']}")
        st.markdown(
            f"**Contract:** {h_contract['level']}{c_sym} by {h_contract['declarer']} ({h_contract['doubled']}) &nbsp;|&nbsp; "
            f"**Target:** {h_contract['tricks_needed']} tricks &nbsp;|&nbsp; "
            f"**Tricks Won:** N/S {hb['tricks_taken']['N/S']} — E/W {hb['tricks_taken']['E/W']}"
        )
        msg = ("✅ Made! " if h_result['made'] else "❌ Down. ") + h_result['detail']
        (st.success if h_result['made'] else st.error)(msg)
    with r_cols[1]:
        pts_sign = "+" if h_result['winner'] == h_contract['side'] else "−"
        st.markdown(
            f'<div class="result-panel">'
            f'<div class="result-eyebrow">Score</div>'
            f'<div class="result-points">{pts_sign}{h_result["points"]}</div>'
            f'<div class="result-to">points to {h_result["winner"]}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.divider()

    # ── Double Dummy Post-Mortem ──────────────────────────────────────────────
    render_analysis(hb)

    st.divider()

    # ── Auction Replay ────────────────────────────────────────────────────────
    with st.expander("📋 Auction Sequence", expanded=True):
        # Pass the alerts through: without them the auction is just a grid of
        # calls, and the explanation is the whole point of reviewing it.
        render_auction_grid(hb['dealer'], hb['auction_calls'],
                            alerts=hb.get('bid_alerts'))

    st.divider()

    # ── Interactive Card-by-Card Replayer ─────────────────────────────────────
    st.subheader("🎬 Card-by-Card Replayer")

    initial = hb['initial_hands']
    flat_plays: list[tuple[int, str, Card, str]] = []
    for trick in h_tricks:
        t_winner = trick['winner']
        for (player, card) in trick['plays']:
            flat_plays.append((trick['trick_num'], player, card, t_winner))

    total_steps = len(flat_plays)

    rep_key = f"rep_step_{sel_idx}"
    if rep_key not in st.session_state:
        st.session_state[rep_key] = 0
    rep_step = st.session_state[rep_key]

    # Controls
    ctrl_cols = st.columns([1, 1, 1, 1, 4])
    with ctrl_cols[0]:
        if st.button("⏮ Start", key=f"rep_start_{sel_idx}", use_container_width=True):
            st.session_state[rep_key] = 0
            st.rerun()
    with ctrl_cols[1]:
        if st.button("◀ Prev", key=f"rep_prev_{sel_idx}", disabled=(rep_step == 0), use_container_width=True):
            st.session_state[rep_key] = max(0, rep_step - 1)
            st.rerun()
    with ctrl_cols[2]:
        if st.button("Next ▶", key=f"rep_next_{sel_idx}", disabled=(rep_step >= total_steps), use_container_width=True):
            st.session_state[rep_key] = min(total_steps, rep_step + 1)
            st.rerun()
    with ctrl_cols[3]:
        if st.button("⏭ End", key=f"rep_end_{sel_idx}", use_container_width=True):
            st.session_state[rep_key] = total_steps
            st.rerun()

    new_step = st.slider(
        "Step through cards played:",
        min_value=0, max_value=total_steps, value=rep_step,
        format="Card %d / " + str(total_steps),
        key=f"rep_slider_{sel_idx}"
    )
    if new_step != rep_step:
        st.session_state[rep_key] = new_step
        rep_step = new_step

    st.caption("Jump to trick:")
    trick_jump_cols = st.columns(13)
    for tj in range(1, 14):
        with trick_jump_cols[tj - 1]:
            trick_start_step = (tj - 1) * 4
            if trick_start_step <= total_steps:
                if st.button(f"T{tj}", key=f"rep_tj_{sel_idx}_{tj}", use_container_width=True):
                    st.session_state[rep_key] = trick_start_step
                    st.rerun()

    st.divider()

    # Reconstruct State at rep_step
    played_so_far = flat_plays[:rep_step]

    remaining_hands: dict[str, list[Card]] = {p: list(initial[p]) for p in PLAYERS}
    for (_, player, card, _) in played_so_far:
        if card in remaining_hands[player]:
            remaining_hands[player].remove(card)

    current_trick_num = (rep_step // 4) + 1 if rep_step < total_steps else 13
    trick_start = (rep_step // 4) * 4
    trick_end = rep_step
    current_trick_plays = [(player, card) for (_, player, card, _) in flat_plays[trick_start:trick_end]]

    trick_just_completed = (rep_step > 0 and rep_step % 4 == 0 and rep_step <= total_steps)
    if trick_just_completed:
        completed_trick_idx = (rep_step // 4) - 1
        if completed_trick_idx < len(h_tricks):
            current_trick_plays = list(h_tricks[completed_trick_idx]['plays'])
            current_trick_num = h_tricks[completed_trick_idx]['trick_num']
            trick_winner_at_step = h_tricks[completed_trick_idx]['winner']
        else:
            trick_winner_at_step = None
    else:
        trick_winner_at_step = None

    # Trick count as it stood at this step, so the replayer shows the same
    # running tally the live table does.
    tally_at_step = {'N/S': 0, 'E/W': 0}
    for trick in h_tricks[:rep_step // 4]:
        tally_at_step[PARTNERSHIP[trick['winner']]] += 1

    if rep_step == 0:
        step_label = "Before opening lead — showing all original hands"
    elif rep_step == total_steps:
        step_label = "Hand complete — all 13 tricks played"
    elif trick_just_completed:
        step_label = f"Trick {current_trick_num} complete — winner: {trick_winner_at_step}"
    else:
        last_t_num, last_player, last_card, _ = flat_plays[rep_step - 1]
        step_label = f"Trick {last_t_num}: {last_player} played {last_card.rank}{SUIT_SYMBOLS[last_card.suit]} ({len(current_trick_plays)}/4 cards)"

    st.info(f"📍 **Step {rep_step}/{total_steps}** — {step_label}")

    # Replayer Felt Table + Hands
    def seat_box(seat: str) -> None:
        st.markdown(seat_box_html(seat, _role(h_contract, seat), remaining_hands[seat]),
                    unsafe_allow_html=True)

    _, rep_n_col, _ = st.columns([1, 1, 1])
    with rep_n_col:
        seat_box('North')

    rep_w_col, rep_table_col, rep_e_col = st.columns([1, 1.8, 1], gap="medium",
                                                     vertical_alignment="center")
    with rep_w_col:
        seat_box('West')
    with rep_table_col:
        render_felt_table(
            trick=current_trick_plays,
            trump=h_trump,
            winner=trick_winner_at_step,
            display_num=current_trick_num,
            contract=h_contract,
            tricks_taken=tally_at_step,
        )
    with rep_e_col:
        seat_box('East')

    _, rep_s_col, _ = st.columns([1, 1, 1])
    with rep_s_col:
        seat_box('South')

    # Trick Log Table
    st.divider()
    with st.expander("📊 Full Trick Log", expanded=False):
        log_header = st.columns([0.5, 1, 1, 1, 1, 1, 1])
        for col_obj, lbl in zip(log_header, ["#", "Leader", "West", "North", "East", "South", "Winner"]):
            col_obj.markdown(f"**{lbl}**")
        for tlog in h_tricks:
            trick_dict = dict(tlog['plays'])
            def card_str(p: str) -> str:
                if p in trick_dict:
                    c2 = trick_dict[p]
                    star = " ⭐" if p == tlog['winner'] else ""
                    return f"{c2.rank}{SUIT_SYMBOLS[c2.suit]}{star}"
                return "—"
            row_cols = st.columns([0.5, 1, 1, 1, 1, 1, 1])
            row_data = [str(tlog['trick_num']), tlog['leader'],
                        card_str('West'), card_str('North'),
                        card_str('East'), card_str('South'), tlog['winner']]
            for col_obj, val in zip(row_cols, row_data):
                col_obj.markdown(val)
