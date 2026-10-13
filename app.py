from __future__ import annotations
import streamlit as st
from card import Card, SUIT_SYMBOLS, STRAIN_SYMBOLS, STRAIN_NAMES, deal
from game import (
    clockwise_from, legal_plays, resolve_trick, score_contract,
    AuctionState, PARTNERSHIP, DEALER_ROTATION, VUL_ROTATION
)
from ai import ai_play, ai_bid, ai_bid_explained, eval_hand_sh, hcp, visible_hands

from web.card_component import (
    DECKS, DECK_LABELS, DECK_HELP, deck_style_block, suit_colors, suit_colors_light,
    hand_html_static, show_interactive_hand, card_backs_html, hand_summary_html
)
from web.auction_view import clean_alert, live_alerts, render_auction_grid, render_bidding_box
from web.felt_table import render_felt_table
from web.replayer_view import render_history_tab
from web.challenge_view import render_breakdown, render_match_total, render_scoreline
from web.session_view import render_session_score
import time

HUMAN = {'South'}


import challenge

# ── Game State Management ─────────────────────────────────────────────────────

def init_game(next_board: bool = False, deal_id: int | None = None) -> None:
    board_num = st.session_state.get('board_num', 1)
    if next_board:
        board_num += 1

    dealer = DEALER_ROTATION[(board_num - 1) % 4]
    vul = VUL_ROTATION[(board_num - 1) % 16]
    # A challenge board comes from the solved library, so every contract it can
    # reach already has an exact trick count and the result can be graded
    # against perfect play without solving anything at run time.
    hands = challenge.hands_for(deal_id) if deal_id is not None else deal()
    # Snapshot initial 13 cards per player (list copy)
    initial_hands = {p: list(h) for p, h in hands.items()}
    auction = AuctionState(dealer=dealer, vulnerability=vul)

    # Every game key below is overwritten outright, so the old session is fully
    # replaced without clearing state wholesale — which would also throw away
    # the display settings and the hand history.
    st.session_state.update({
        'board_num':     board_num,
        'dealer':        dealer,
        'vulnerability': vul,
        'initial_hands': initial_hands,   # full 13-card snapshot
        'hands':         hands,
        'auction':       auction,
        'phase':         'bidding',   # 'bidding' | 'playing' | 'trick_done'
        'contract':      None,
        'trump':         None,
        'leader':        None,
        'order':         [],
        'trick':         [],
        'trick_num':     1,
        'tricks_taken':  {'N/S': 0, 'E/W': 0},
        'trick_winner':  None,
        'played':        [],
        'tricks_log':    [],           # list of completed trick dicts for replayer
        'game_over':     False,
        'result':        None,
        'bid_alerts':    {},           # call index -> why the robot bid it
        'challenge_id':  deal_id,      # None for a free board
        'challenge':     None,         # filled in when the board finishes
        'hand_history':  st.session_state.get('hand_history', []),
    })
    _advance_auction_ai()


def _advance_auction_ai() -> None:
    s = st.session_state
    auction: AuctionState = s['auction']
    while not auction.is_complete:
        curr_p = auction.current_player()
        if curr_p in HUMAN:
            return  # Wait for human input
        call, why = ai_bid_explained(curr_p, s['hands'][curr_p], auction)
        # key by position in the auction, so the grid can alert the right call
        s.setdefault('bid_alerts', {})[len(auction.calls)] = why
        auction.apply_call(curr_p, call)

    # Check if auction just completed
    _finalize_auction()


def _finalize_auction() -> None:
    s = st.session_state
    auction: AuctionState = s['auction']
    if not auction.is_complete:
        return

    if auction.passed_out:
        s['phase'] = 'bidding'
        # Not in hand_history (nothing to replay), but played: the session
        # scoreboard counts it.
        s['passed_out_count'] = s.get('passed_out_count', 0) + 1
        return

    contract = auction.get_contract()
    if contract is not None:
        s['contract'] = contract
        s['trump'] = contract['trump']
        s['leader'] = contract['leader']
        s['order'] = clockwise_from(contract['leader'])
        s['phase'] = 'auction_done'   # Pause here — show summary + "Start Play" button


def human_bids(player: str, call: str, alert: str = '') -> None:
    """`alert` is the player's own explanation of the call, as a self-alert on
    BBO. The robots don't read it; it goes into the record and the LIN."""
    s = st.session_state
    auction: AuctionState = s['auction']
    if auction.current_player() == player and not auction.is_complete:
        why = clean_alert(alert)
        if why:
            s.setdefault('bid_alerts', {})[len(auction.calls)] = why
        auction.apply_call(player, call)
        _advance_auction_ai()


def _is_human_turn(player: str) -> bool:
    """True if the human picks this seat's card: South, plus North when North is South's
    dummy. When North declares, South is dummy and the North AI plays both hands."""
    contract = st.session_state.get('contract')
    declarer = contract['declarer'] if contract else None
    if player == 'South':
        return declarer != 'North'
    return player == 'North' and declarer == 'South'


def _start_play() -> None:
    """Transition from auction_done → playing and let AI move first if needed."""
    s = st.session_state
    s['phase'] = 'playing'
    _advance_ai()


def _forced_card(player: str) -> Card | None:
    """The human's only legal card when auto-play is on; otherwise None."""
    s = st.session_state
    if not s.get('auto_play'):
        return None
    led = s['trick'][0][1].suit if s['trick'] else None
    legal = legal_plays(s['hands'][player], led)
    return legal[0] if len(legal) == 1 else None


def _advance_ai() -> None:
    s = st.session_state
    if s['phase'] not in ('playing',):
        return
    already_played = {p for p, _ in s['trick']}
    for player in s['order']:
        if player in already_played:
            continue
        if _is_human_turn(player):
            # Human turn (either South or North when N/S declared), unless
            # auto-play takes a card that is the only legal one.
            forced = _forced_card(player)
            if forced is None:
                return
            s['hands'][player].remove(forced)
            s['trick'].append((player, forced))
            already_played.add(player)
            continue
        card = ai_play(player, s['hands'][player], s['trick'], s['trump'], s['played'],
                       visible=visible_hands(player, s['contract'], s['hands']),
                       history=[e['plays'] for e in s['tricks_log']])
        s['hands'][player].remove(card)
        s['trick'].append((player, card))
        already_played.add(player)
    _end_trick()


def _end_trick() -> None:
    s = st.session_state
    winner = resolve_trick(s['trick'], s['trump'])
    side = PARTNERSHIP[winner]
    s['tricks_taken'][side] += 1
    s['trick_winner'] = (winner, side)
    s['phase'] = 'trick_done'
    s['trick_num'] += 1
    s['leader'] = winner

    # Log this trick for the replayer
    trick_num_completed = s['trick_num'] - 1
    s['tricks_log'].append({
        'trick_num':    trick_num_completed,
        'leader':       s['trick'][0][0],
        'plays':        list(s['trick']),      # [(player, Card), ...]
        'winner':       winner,
        'winning_card': dict(s['trick'])[winner],
    })

    if s['trick_num'] > 13:
        s['game_over'] = True
        s['result'] = score_contract(s['contract'], s['tricks_taken'])
        _grade_challenge()
        # Save completed board to session history
        s['hand_history'].append({
            'board_num':     s['board_num'],
            'dealer':        s['dealer'],
            'vulnerability': s['vulnerability'],
            'initial_hands': s['initial_hands'],
            'auction_calls': list(s['auction'].calls),
            'bid_alerts':    dict(s.get('bid_alerts', {})),
            'contract':      s['contract'],
            'passed_out':    False,
            'tricks_log':    list(s['tricks_log']),
            'tricks_taken':  dict(s['tricks_taken']),
            'result':        s['result'],
            'challenge':     s.get('challenge'),
        })


def _grade_challenge() -> None:
    """Replay this deal with robots in all four seats and compare.

    Only the HUMAN's side is graded: North is a robot in both runs, so what the
    comparison isolates is South. Running the robot table costs milliseconds --
    `ai_bid` and `ai_play` are pure evaluation with no solver behind them.
    """
    s = st.session_state
    deal_id = s.get('challenge_id')
    if deal_id is None:
        return

    side = 'N/S'
    mine = challenge.grade(deal_id, side, s['contract'],
                           s['tricks_taken'][s['contract']['side']],
                           s['vulnerability'])
    table = challenge.robot_table(deal_id, s['dealer'], s['vulnerability'])
    theirs = challenge.grade(deal_id, side, table['contract'],
                             table['declarer_tricks'], s['vulnerability'])

    s['challenge'] = {
        'deal_id':   deal_id,
        'board_num': s['board_num'],
        'you':       mine,
        'robot':     theirs,
        'robot_contract': table['contract'],
        'robot_calls':    table['calls'],
        # A full replayable record, so the robots' board can be stepped through
        # card by card beside your own.
        'robot_record': challenge.as_history_record(
            table, s['board_num'], "🤖 Robots' board"),
        'margin':    mine['actual'] - theirs['actual'],
    }
    s['challenge_log'] = s.get('challenge_log', []) + [{
        'deal_id': deal_id,
        'board_num': s['board_num'],
        'you':     mine['actual'],
        'robot':   theirs['actual'],
        'margin':  mine['actual'] - theirs['actual'],
        'your_bidding_loss': mine['bidding_loss'],
        'your_play_loss':    mine['play_loss'],
        'robot_bidding_loss': theirs['bidding_loss'],
        'robot_play_loss':    theirs['play_loss'],
    }]


def next_trick() -> None:
    s = st.session_state
    s['played'].extend(c for _, c in s['trick'])
    s['trick'] = []
    s['order'] = clockwise_from(s['leader'])
    s['phase'] = 'playing'
    _advance_ai()


def human_plays(player: str, card: Card) -> None:
    s = st.session_state
    s['hands'][player].remove(card)
    s['trick'].append((player, card))
    _advance_ai()


def whose_turn() -> str | None:
    s = st.session_state
    played = {p for p, _ in s['trick']}
    for player in s['order']:
        if player not in played:
            return player if _is_human_turn(player) else None
    return None


# ── Page Configuration & CSS ──────────────────────────────────────────────────

st.set_page_config(page_title="Second-Highest Bridge", layout="wide")

try:
    with open("styles.css", "r", encoding="utf-8") as _f:
        st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass


# ── Display settings ──────────────────────────────────────────────────────────
# Rendered before anything else that draws a card, so the deck choice is in
# session state by the time the suit colours are needed.

st.sidebar.markdown("### Display")

_deck_keys = list(DECKS)
_deck_choice = st.sidebar.radio(
    "Card deck",
    _deck_keys,
    index=_deck_keys.index(st.session_state.get('deck', 'four')),
    format_func=lambda k: DECK_LABELS[k],
    key="deck_choice",
)
st.session_state['deck'] = _deck_choice
st.sidebar.caption(DECK_HELP[_deck_choice])

st.session_state['trump_first'] = st.sidebar.checkbox(
    "Sort trump suit first",
    value=st.session_state.get('trump_first', False),
    key="trump_first_choice",
    help="Off: hands always read spades, hearts, diamonds, clubs, as in a printed "
         "hand record. On: the trump suit moves to the left once play starts.",
)

show_hand_strength = st.sidebar.checkbox(
    "Show hand strength",
    value=True,
    key="hand_strength_choice",
    help="High-card points, this variant's own valuation, and your shape.",
)

st.session_state['auto_play'] = st.sidebar.checkbox(
    "Auto-play forced cards",
    value=True,
    key="auto_play_choice",
    help="When you have only one legal card, it is played for you, as on BBO.",
)
fast_play = st.sidebar.checkbox(
    "Fast play (next trick automatically)",
    value=False,
    key="fast_play_choice",
    help="Each finished trick stays on the table for a moment, then the next "
         "one starts by itself.",
)
#: How long a finished trick stays on the table under fast play.
FAST_PLAY_SECONDS = 1.2

st.sidebar.markdown("---")
show_all = st.sidebar.checkbox("Show all hands (Debug / X-Ray)", value=False)

# Re-point the CSS suit variables at the chosen deck.
st.markdown(deck_style_block(), unsafe_allow_html=True)


# ── Header & Setup ────────────────────────────────────────────────────────────

if 'hands' not in st.session_state:
    init_game()

# Auto-play switched on while a forced card is waiting: play it now. Harmless
# otherwise -- _advance_ai stops at the first human choice.
if st.session_state.get('auto_play') and st.session_state['phase'] == 'playing':
    _advance_ai()

s = st.session_state
auction: AuctionState = s['auction']
board_num = s['board_num']
dealer = s['dealer']
vul = s['vulnerability']
sort_trump_first = s.get('trump_first', False)

st.markdown(
    '<div class="masthead">'
    '<span class="masthead-title"><span class="pip">♠</span> Second-Highest Bridge</span>'
    '<span class="masthead-sub">Second-highest card takes the trick</span>'
    '</div>',
    unsafe_allow_html=True
)


def scoreboard(cells: list[tuple[str, str]]) -> None:
    """Renders the header strip: a row of label/value cells."""
    html = ''.join(
        f'<div class="score-cell"><div class="score-label">{label}</div>'
        f'<div class="score-value">{value}</div></div>'
        for label, value in cells
    )
    st.markdown(f'<div class="scoreboard">{html}</div>', unsafe_allow_html=True)


def strain_html(level: int, strain: str) -> str:
    """Contract text with the suit symbol in that suit's ink for the active deck.
    These sit on dark panels, so they use the light inks."""
    sym = STRAIN_SYMBOLS[strain]
    color = suit_colors_light().get(strain, 'inherit')
    name = STRAIN_NAMES.get(strain, strain)
    return (f'{level}<span style="color:{color}" aria-hidden="true">{sym}</span>'
            f'<span class="sr-only"> {name}</span>')


def vul_pills_html(vulnerability: str) -> str:
    """Vulnerability as two labelled pills, the way the board panel shows it in
    every online client. Filled vs outlined carries the state as well as the
    red does, so it survives colour blindness."""
    def pill(label: str, is_vul: bool) -> str:
        cls = 'vul-on' if is_vul else 'vul-off'
        state = 'vulnerable' if is_vul else 'not vulnerable'
        return (f'<span class="vul-pill {cls}">'
                f'<span aria-hidden="true">{label}</span>'
                f'<span class="sr-only">{label} {state}. </span></span>')
    return ('<div class="vul-pills">'
            + pill('N-S', vulnerability in ('N/S', 'Both'))
            + pill('E-W', vulnerability in ('E/W', 'Both'))
            + '</div>')


def ai_seat_panel(seat: str, role: str, role_cls: str, note: str = '',
                  backs: bool = True) -> str:
    """A seat panel: name, role, card count, and — for a concealed hand — a fan
    of card backs. A face-up seat keeps the same chrome but drops the backs,
    which would otherwise sit above the very cards they claim to hide."""
    count = len(s['hands'][seat])
    return (
        f'<div class="ai-player-box">'
        f'<div class="seat-name">{seat}</div>'
        f'<div class="seat-role{role_cls}">{role}</div>'
        f'{card_backs_html(count, seat) if backs else ""}'
        f'<div class="seat-count"><strong>{count} cards</strong>{note}</div>'
        f'</div>'
    )


def south_hand_summary() -> None:
    """The strength strip beside your own hand."""
    if not show_hand_strength:
        return
    hand = s['hands']['South']
    ev = eval_hand_sh(hand)
    st.markdown(
        hand_summary_html(hcp(hand), ev['total_pts'], ev['lengths']),
        unsafe_allow_html=True
    )


# ── Tabs ─────────────────────────────────────────────────────────────────────
hand_history = s.get('hand_history', [])
history_label = f"📜 Hand History ({len(hand_history)} board{'s' if len(hand_history) != 1 else ''})"
challenge_log = s.get('challenge_log', [])
challenge_label = ("⚔️ Challenge"
                   + (f" ({len(challenge_log)})" if challenge_log else ""))
tab_game, tab_challenge, tab_history = st.tabs(
    ["🎮 Bridge Table", challenge_label, history_label])

# Rendered before the game tab because the game tab calls st.stop() on its end screens.
with tab_history:
    render_history_tab(hand_history, allow_import=True)

with tab_challenge:
    st.markdown("### Challenge the robots")
    st.markdown(
        f"A challenge board is dealt from the **{len(challenge.deal_ids())} "
        "deals this project has solved exactly**, so whatever contract you reach, the number of tricks "
        "it takes with perfect play on both sides is already known. You play "
        "South; the same deal is then played out by an all-robot table, and the "
        "two results are compared.\n\n"
        "Because every contract can be priced against perfect play, the gap "
        "splits in two: what the **auction** cost and what the **card play** "
        "cost. Those are separate skills, and the robots are far better at one "
        "than the other."
    )

    ids = challenge.deal_ids()
    played_ids = {r['deal_id'] for r in challenge_log}
    remaining = [i for i in ids if i not in played_ids]

    col_a, col_b = st.columns([1, 2])
    with col_a:
        if st.button("Deal a challenge board →", use_container_width=True,
                     type="primary", disabled=not remaining):
            import random as _random
            init_game(next_board=True, deal_id=_random.choice(remaining))
            st.rerun()
    with col_b:
        st.caption(f"{len(remaining)} of {len(ids)} solved boards unplayed. "
                   f"Finish the board on the Bridge Table tab, then come back "
                   f"here for the comparison.")

    if s.get('challenge_id') is not None and not s.get('game_over'):
        st.info(f"Challenge board in play on the **Bridge Table** tab. "
                f"Finish it to see how the robots did with the same cards.")

    # ── step through either board, card by card ──────────────────────────────
    last = s.get('challenge')
    if last and last.get('robot_record'):
        st.divider()
        st.markdown("### Review the deal")
        st.caption(
            "Both boards, the same 52 cards. Switch between them to see where "
            "the auctions diverged and which card turned the play. Hover any "
            "robot call for what it was supposed to show."
        )
        yours = next((h for h in reversed(hand_history)
                      if h.get('board_num') == last.get('board_num')), None)
        records = []
        if yours is not None:
            records.append({**yours, 'label': "🧑 Your board"})
        records.append(last['robot_record'])
        render_history_tab(records, key='chal')

    render_match_total(challenge_log)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: BRIDGE TABLE (Live Game)
# ══════════════════════════════════════════════════════════════════════════════

with tab_game:

    render_session_score(hand_history, challenge_log, s.get('passed_out_count', 0))

    # ── Status Banner Metrics ─────────────────────────────────────────────────
    display_num = s['trick_num'] - 1 if s['phase'] == 'trick_done' else s['trick_num']

    if s['phase'] == 'bidding':
        curr_bid = auction.highest_bid
        if curr_bid:
            high = (f'{strain_html(curr_bid[0], curr_bid[1])} '
                    f'<span class="muted">by {curr_bid[2]}</span>')
            if auction.doubled != 'None':
                high += f' <span class="accent">{auction.doubled}</span>'
        else:
            high = '<span class="muted">—</span>'
        scoreboard([
            ("Board", f"#{board_num}"),
            ("Dealer", dealer),
            ("Vulnerable", vul_pills_html(vul)),
            ("High bid", high),
        ])
    else:
        c = s['contract']
        dbl = f' <span class="accent">{c["doubled"]}</span>' if c['doubled'] != 'None' else ''
        scoreboard([
            ("Board", f'#{board_num}'),
            ("Vulnerable", vul_pills_html(vul)),
            ("Contract", f'{strain_html(c["level"], c["strain"])}'
                         f'<span class="muted"> by {c["declarer"]}</span>{dbl}'),
            ("Trick", f'{display_num} <span class="muted">/ 13 · need {c["tricks_needed"]}</span>'),
            ("Tricks won", f'<span class="accent">N/S {s["tricks_taken"]["N/S"]}</span>'
                           f'<span class="muted">  ·  E/W {s["tricks_taken"]["E/W"]}</span>'),
        ])

    # ── Game Over Screen ──────────────────────────────────────────────────────
    if s['game_over']:
        r = s['result']
        contract_c = s['contract']
        c_str = f"{contract_c['level']}{STRAIN_SYMBOLS[contract_c['strain']]} by {contract_c['declarer']} ({contract_c['doubled']})"
        tricks_str = f"N/S {s['tricks_taken']['N/S']} — E/W {s['tricks_taken']['E/W']}"

        # Two-column result layout
        res_left, res_right = st.columns([2, 1])
        with res_left:
            st.subheader("🏁 Hand Complete!")
            st.write(f"**Contract:** {c_str} | **Vul:** {contract_c['vulnerability']}")
            st.write(f"**Tricks Won:** {tricks_str} (Target: {r['tricks_needed']})")
            msg = ("✅ Contract Made! " if r['made'] else "❌ Contract Down. ") + r['detail']
            (st.success if r['made'] else st.error)(msg)
            if st.button("Deal Next Board ➔", type="primary", key="deal_next"):
                init_game(next_board=True)
                st.rerun()
            # A challenge board carries its head-to-head comparison: the same
            # deal replayed by an all-robot table, and the gap split into what
            # the auction cost and what the card play cost.
            if s.get('challenge'):
                st.divider()
                render_scoreline(s['challenge'])
                render_breakdown(s['challenge'])

        with res_right:
            st.markdown(
                f'<div class="result-panel">'
                f'<div class="result-eyebrow">Board #{s["board_num"]} result</div>'
                f'<div class="result-contract">'
                f'{strain_html(contract_c["level"], contract_c["strain"])} by {contract_c["declarer"]}</div>'
                f'<div class="result-verdict {"made" if r["made"] else "down"}">'
                f'{"Contract made" if r["made"] else "Contract down"}</div>'
                f'<div class="result-points">'
                f'{"+" if r["winner"] == contract_c["side"] else "−"}{r["points"]}</div>'
                f'<div class="result-to">points to {r["winner"]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        with st.expander("Auction", expanded=False):
            render_auction_grid(dealer, auction.calls, alerts=st.session_state.get('bid_alerts'))
        st.stop()

    # ── PHASE 1: BIDDING (AUCTION) ────────────────────────────────────────────

    if s['phase'] in ('bidding', 'auction_done'):
        # If Passed Out
        if auction.passed_out:
            st.warning("🛑 **Auction Passed Out (4 Passes)** — No contract reached (0 points).")
            if st.button("Deal Next Board ➔", type="primary"):
                init_game(next_board=True)
                st.rerun()
            st.stop()

        b_col_left, b_col_center, b_col_right = st.columns([1.1, 3.8, 1.1], gap="medium")

        with b_col_center:
            # 1. North Hand (Concealed during auction - dummy is not yet known)
            if show_all:
                st.markdown('<div class="hand-header"><strong>North (Partner)</strong></div>',
                            unsafe_allow_html=True)
                st.markdown(hand_html_static(s['hands']['North'], None), unsafe_allow_html=True)
            else:
                st.markdown(
                    ai_seat_panel('North', 'Partner · AI', '',
                                  ' · concealed until play starts'),
                    unsafe_allow_html=True
                )

            # 2. Auction History Board
            st.markdown('<div class="section-title">Auction</div>', unsafe_allow_html=True)
            render_auction_grid(dealer, auction.calls,
                            alerts=live_alerts(auction.calls, st.session_state.get('bid_alerts')))

            # 3. Bidding box for the human (South)
            if auction.current_player() in HUMAN and not auction.is_complete:
                render_bidding_box(
                    auction.legal_calls(),
                    lambda call, alert: human_bids('South', call, alert),
                    # A fresh box for every call: see render_bidding_box.
                    alert_key=f"self_alert_{board_num}_{len(auction.calls)}",
                )

            # 3b. Auction finished — contract summary and the way into play
            if s['phase'] == 'auction_done':
                c = s['contract']
                dbl = f' <span class="cr-gold">{c["doubled"]}</span>' if c['doubled'] != 'None' else ''
                st.markdown(
                    f'<div class="contract-ready">'
                    f'<span class="cr-label">Contract</span>'
                    f'<span class="cr-contract">{strain_html(c["level"], c["strain"])}{dbl}</span>'
                    f'<span class="cr-detail">by <strong>{c["declarer"]}</strong> · dummy {c["dummy"]}'
                    f' · <span class="cr-gold">{c["leader"]}</span> leads'
                    f' · needs {c["tricks_needed"]} tricks</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                if st.button("Start play →", type="primary", use_container_width=True, key="start_play_btn"):
                    _start_play()
                    st.rerun()

            # 4. South Hand
            st.markdown('<div class="section-title">Your hand</div>', unsafe_allow_html=True)
            south_hand_summary()
            st.markdown(hand_html_static(s['hands']['South'], None), unsafe_allow_html=True)

        for col, seat in ((b_col_left, 'West'), (b_col_right, 'East')):
            with col:
                st.markdown(ai_seat_panel(seat, 'Opponent · AI', ''), unsafe_allow_html=True)
                if show_all:
                    st.markdown(hand_html_static(s['hands'][seat], None), unsafe_allow_html=True)


    # ── PHASE 2: TRICK PLAY ───────────────────────────────────────────────────

    elif s['phase'] in ('playing', 'trick_done'):
        c = s['contract']
        trump = s['trump']
        # Hands keep the fixed spades-hearts-diamonds-clubs order unless the
        # player has asked for trump first, so the layout they memorised during
        # the auction does not rearrange itself the moment play starts.
        display_trump = trump if sort_trump_first else None
        who = whose_turn() if s['phase'] == 'playing' else None
        led_suit = s['trick'][0][1].suit if s['trick'] else None
        display_num = s['trick_num'] - 1 if s['phase'] == 'trick_done' else s['trick_num']

        def seat_role(p: str) -> str:
            if c['declarer'] == p:
                return 'Declarer'
            if c['dummy'] == p:
                return 'Dummy'
            return 'Defender'

        # Dummy goes down only AFTER the opening lead: the leader chooses blind.
        dummy_down = bool(s['played'] or s['trick'])

        def face_up(p: str) -> bool:
            """South is the human's own hand and the dummy is public to the table
            once the opening lead is made; every other hand stays concealed
            unless X-ray is on."""
            return show_all or p == 'South' or (c['dummy'] == p and dummy_down)

        # An exposed dummy in a side seat needs more width than a card count does.
        col_widths = {'West': [2.1, 2.8, 1.1], 'East': [1.1, 2.8, 2.1]}.get(
            c['dummy'], [1.1, 3.8, 1.1])
        west_col, center_col, east_col = st.columns(col_widths, gap="medium",
                                                    vertical_alignment="center")

        with center_col:
            north_legal = legal_plays(s['hands']['North'], led_suit) if who == 'North' else None
            show_interactive_hand(
                label=f"North ({seat_role('North')})",
                hand=s['hands']['North'],
                trump=display_trump,
                is_turn=(who == 'North'),
                legal=north_legal,
                who='North',
                on_play=human_plays,
                concealed=not face_up('North'),
            )

            # Last trick: a peek belongs to the moment it was asked for. Any
            # card played or trick finished changes the key, so the felt goes
            # back to the live trick with nothing to reset.
            last_trick = s['tricks_log'][-1] if s['phase'] == 'playing' and s['tricks_log'] else None
            moment = (board_num, s['trick_num'], len(s['trick']))
            peeking = last_trick is not None and s.get('peek_key') == moment

            if peeking:
                render_felt_table(
                    trick=last_trick['plays'],
                    trump=trump,
                    winner=last_trick['winner'],
                    display_num=last_trick['trick_num'],
                    contract=c,
                    tricks_taken=s['tricks_taken'],
                )
            else:
                winner_name = s['trick_winner'][0] if (s['phase'] == 'trick_done' and s['trick_winner']) else None
                render_felt_table(
                    trick=s['trick'],
                    trump=trump,
                    winner=winner_name,
                    display_num=display_num,
                    contract=c,
                    tricks_taken=s['tricks_taken'],
                )
            if last_trick is not None:
                lt_btn, lt_text = st.columns([1, 3], vertical_alignment="center")
                with lt_btn:
                    if st.button("↩ Back to this trick" if peeking else "👁 Last trick",
                                 key="last_trick_btn", use_container_width=True):
                        s['peek_key'] = None if peeking else moment
                        st.rerun()
                if peeking:
                    w = last_trick['winning_card']
                    lt_text.caption(f"Trick {last_trick['trick_num']}: **{last_trick['winner']}** "
                                    f"won with {w.rank}{SUIT_SYMBOLS[w.suit]}")

            if s['phase'] == 'trick_done' and s['trick_winner']:
                winner, side = s['trick_winner']
                w_card = dict(s['trick'])[winner]
                w_ink = suit_colors()[w_card.suit]
                st.markdown(
                    f'<div class="trick-result">'
                    f'<span class="tr-winner">{winner}</span>'
                    f'<span class="tr-text">({side}) takes trick {display_num} with</span>'
                    f'<span class="tr-card" style="color:{w_ink}">'
                    f'{w_card.rank}{SUIT_SYMBOLS[w_card.suit]}</span>'
                    f'<span class="tr-text">— second-highest</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                btn_label = "See final score →" if s['game_over'] else "Next trick →"
                if fast_play:
                    btn_label += " (automatic)"
                if st.button(btn_label, type="primary", use_container_width=True):
                    if s['game_over']:
                        s['phase'] = 'playing'
                    else:
                        next_trick()
                    st.rerun()

            south_legal = legal_plays(s['hands']['South'], led_suit) if who == 'South' else None
            show_interactive_hand(
                label=("South (Dummy · North plays this hand)" if c['dummy'] == 'South'
                       else f"South ({seat_role('South')})"),
                hand=s['hands']['South'],
                trump=display_trump,
                is_turn=(who == 'South'),
                legal=south_legal,
                who='South',
                on_play=human_plays,
                concealed=not face_up('South'),
            )
            south_hand_summary()

            # The auction stays reachable during play. Bridge players refer back
            # to it constantly, and every other client keeps it on the table.
            with st.expander("Auction", expanded=False):
                st.markdown(
                    f'<div class="auction-recap-note">Board #{board_num} · dealer {dealer}'
                    f' · {c["declarer"]} declares</div>',
                    unsafe_allow_html=True
                )
                render_auction_grid(dealer, auction.calls,
                                    alerts=live_alerts(auction.calls, st.session_state.get('bid_alerts')))

        for col, seat in ((west_col, 'West'), (east_col, 'East')):
            with col:
                role = seat_role(seat)
                role_cls = {'Declarer': ' is-declarer', 'Dummy': ' is-dummy'}.get(role, '')
                seat_face_up = face_up(seat)
                st.markdown(ai_seat_panel(seat, role, role_cls, backs=not seat_face_up),
                            unsafe_allow_html=True)
                if seat_face_up:
                    st.markdown(hand_html_static(s['hands'][seat], display_trump),
                                unsafe_allow_html=True)

        # Fast play: the finished trick is on the page by now (Streamlit sends
        # elements as the script runs), so pause, then do what "Next trick"
        # does. A click during the pause interrupts this run, as it should.
        if fast_play and s['phase'] == 'trick_done':
            time.sleep(FAST_PLAY_SECONDS)
            if s['game_over']:
                s['phase'] = 'playing'
            else:
                next_trick()
            st.rerun()
