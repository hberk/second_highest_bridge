from __future__ import annotations
import html
import streamlit as st
from card import Card, SUIT_SYMBOLS, STRAIN_SYMBOLS
from game import PLAYERS, PARTNERSHIP
from web.card_component import card_text_html, doubled_suffix, seat_box_html, strain_html
from web.auction_view import render_auction_grid
from web.felt_table import render_felt_table
from web.analysis_view import render_analysis
from bridge.lin import MAX_LIN_BYTES, LinError, from_lin_file, to_lin, to_lin_file


def _role(contract: dict, seat: str) -> str:
    if contract['declarer'] == seat:
        return 'Declarer'
    if contract['dummy'] == seat:
        return 'Dummy'
    return 'Defender'


def _render_lin_import(hand_history: list[dict], key: str) -> None:
    """Paste LIN or open a .lin file; boards are appended to the history.

    Free text enters the app here. `from_lin` rebuilds every field from fixed
    vocabularies (seats, cards, legal calls, vulnerabilities) or integers, so
    the only text that survives into a record is alert text, which reaches the
    page only through `call_badge` (escaped). Error messages can quote the
    input, so they are shown with `st.code`, as plain text.
    """
    with st.expander("📥 Import LIN", expanded=False):
        st.caption("Paste LIN text or open a .lin file. Each board is replayed under "
                   "second-highest rules; one played under ordinary rules will usually "
                   "be refused, because its tricks go to different hands.")
        text = st.text_area("LIN text", key=f"{key}_lin_text", height=100,
                            max_chars=MAX_LIN_BYTES,
                            placeholder="pn|...|md|3SAKQ...|sv|o|mb|1S|...")
        upload = st.file_uploader("…or a .lin file", type=['lin', 'txt'], key=f"{key}_lin_file")
        if st.button("Import", key=f"{key}_lin_import", disabled=not (text.strip() or upload)):
            try:
                if upload and upload.size > MAX_LIN_BYTES:
                    raise LinError(f"The file is {upload.size:,} bytes; "
                                   f"at most {MAX_LIN_BYTES:,} are read")
                # utf-8-sig: a file saved with a byte-order mark reads the same.
                source = upload.getvalue().decode('utf-8-sig', errors='replace') if upload else text
                boards = from_lin_file(source)
            except LinError as e:
                st.session_state[f"{key}_lin_msg"] = ('error', str(e))
            except Exception:  # anything the parser didn't anticipate: refuse, don't crash
                st.session_state[f"{key}_lin_msg"] = ('error', 'This is not readable LIN.')
            else:
                # Importing the same file twice adds nothing the second time.
                held = [_identity(h) for h in hand_history if h.get('imported')]
                new = [b for b in boards if _identity(b) not in held]
                for b in new:
                    b['label'] = f"Imported #{b['board_num']}"
                    b['imported'] = True
                hand_history.extend(new)
                n, again = len(new), len(boards) - len(new)
                note = f"Imported {n} board{'s' if n != 1 else ''}."
                if again:
                    note += f" {again} already imported, skipped."
                st.session_state[f"{key}_lin_msg"] = ('ok', note)
            st.rerun()
        msg = st.session_state.get(f"{key}_lin_msg")
        if msg and msg[0] == 'error':
            st.error("Not imported:")
            st.code(msg[1], language=None, wrap_lines=True)
        elif msg:
            st.success(msg[1])


def _identity(board: dict) -> tuple:
    """What makes two boards the same board (`saves.boardKey` in the web app)."""
    return (board['board_num'], board['dealer'], board['initial_hands'],
            list(board['auction_calls']))


def _render_lin_record(hb: dict, key: str, sel_idx: int) -> None:
    """This board as LIN: shown (st.code has a copy button) and downloadable."""
    lin = to_lin(hb)
    with st.expander("📄 LIN record", expanded=False):
        st.code(lin, language=None, wrap_lines=True)
        st.download_button("⬇ Download .lin", to_lin_file([hb]), file_name=f"board-{hb['board_num']}.lin",
                           mime="text/plain", key=f"{key}_lin_dl_{sel_idx}")
        st.caption("BBO's format. BBO's own hand viewer plays by ordinary rules, so it "
                   "would show these tricks going to the wrong hands.")


def render_history_tab(hand_history: list[dict], allow_import: bool = False,
                       key: str = 'hist') -> None:
    """Renders the entire Hand History & Card-by-Card Replayer view.

    `key` prefixes every widget key: the challenge review renders this view a
    second time in the same run, and Streamlit refuses duplicate keys.
    `allow_import` adds LIN import and download-all (the History tab only).
    """
    if allow_import:
        _render_lin_import(hand_history, key)
        if hand_history:
            st.download_button("⬇ Download all boards (.lin)", to_lin_file(hand_history),
                               file_name="second-highest-session.lin", mime="text/plain",
                               key=f"{key}_lin_dl_all")
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
        return (f"{prefix}: {c['level']}{strain_sym}{doubled_suffix(c['doubled'])} "
                f"by {c['declarer']} — {made_str} {pts_str}pts")

    board_options = [board_label(h) for h in reversed(hand_history)]
    board_indices = list(reversed(range(len(hand_history))))
    selected_label = st.selectbox("📋 Select a board to review:", board_options, key=f"{key}_board_sel")
    sel_idx = board_indices[board_options.index(selected_label)]
    hb = hand_history[sel_idx]

    if hb['passed_out']:
        st.warning(f"🛑 **Board #{hb['board_num']}** — Passed Out (4 passes, no contract)")
        _render_lin_record(hb, key, sel_idx)
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
            f"**Contract:** {strain_html(h_contract['level'], h_contract['strain'])}"
            f"{doubled_suffix(h_contract['doubled'])} by {html.escape(h_contract['declarer'], quote=True)} &nbsp;|&nbsp; "
            f"**Target:** {h_contract['tricks_needed']} tricks &nbsp;|&nbsp; "
            f"**Tricks Won:** N/S {hb['tricks_taken']['N/S']} — E/W {hb['tricks_taken']['E/W']}",
            unsafe_allow_html=True,
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
    if len(h_tricks) == 13:
        render_analysis(hb, key=f"{key}_dd")
    else:
        st.caption("Double dummy analysis needs a board played to the last trick; "
                   "this one ended in a claim.")

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

    rep_key = f"{key}_rep_step_{sel_idx}"
    if rep_key not in st.session_state:
        st.session_state[rep_key] = 0
    rep_step = st.session_state[rep_key]

    # Controls
    ctrl_cols = st.columns([1, 1, 1, 1, 4])
    with ctrl_cols[0]:
        if st.button("⏮ Start", key=f"{key}_rep_start_{sel_idx}", use_container_width=True):
            st.session_state[rep_key] = 0
            st.rerun()
    with ctrl_cols[1]:
        if st.button("◀ Prev", key=f"{key}_rep_prev_{sel_idx}", disabled=(rep_step == 0), use_container_width=True):
            st.session_state[rep_key] = max(0, rep_step - 1)
            st.rerun()
    with ctrl_cols[2]:
        if st.button("Next ▶", key=f"{key}_rep_next_{sel_idx}", disabled=(rep_step >= total_steps), use_container_width=True):
            st.session_state[rep_key] = min(total_steps, rep_step + 1)
            st.rerun()
    with ctrl_cols[3]:
        if st.button("⏭ End", key=f"{key}_rep_end_{sel_idx}", use_container_width=True):
            st.session_state[rep_key] = total_steps
            st.rerun()

    new_step = st.slider(
        "Step through cards played:",
        min_value=0, max_value=total_steps, value=rep_step,
        format="Card %d / " + str(total_steps),
        key=f"{key}_rep_slider_{sel_idx}"
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
                if st.button(f"T{tj}", key=f"{key}_rep_tj_{sel_idx}_{tj}", use_container_width=True):
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
        played = len(h_tricks)
        step_label = ("Hand complete — all 13 tricks played" if played == 13 else
                      f"Hand complete — {played} tricks played, the rest claimed")
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
                    return f"{card_text_html(c2)}{star}"
                return "—"
            row_cols = st.columns([0.5, 1, 1, 1, 1, 1, 1])
            # Rendered as HTML for the suit inks: the cards come through
            # `card_text_html`, and the seat names are escaped like every other
            # interpolated string (see tests/test_web_escaping.py).
            row_data = [str(int(tlog['trick_num'])), html.escape(tlog['leader'], quote=True),
                        card_str('West'), card_str('North'),
                        card_str('East'), card_str('South'),
                        html.escape(tlog['winner'], quote=True)]
            for col_obj, val in zip(row_cols, row_data):
                col_obj.markdown(val, unsafe_allow_html=True)

    _render_lin_record(hb, key, sel_idx)
