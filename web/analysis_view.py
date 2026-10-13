"""Progressive double dummy post-mortem for a finished board.

Analysis cost collapses towards the end of a hand: the last few tricks are
microseconds, eight cards each is about a second, ten cards is half a minute,
and the opening lead is hours. So this fills in **backwards from the last
trick**, a time slice at a time, and stops at a depth the user chooses. The
endgame appears at once and earlier tricks arrive while the page is read.

The fill is cooperative rather than threaded: each run does a bounded slice of
work, then asks Streamlit to rerun. That keeps every write on the script thread
(no ScriptRunContext problems) and keeps the page responsive, at the cost of
one rerun per slice.
"""
from __future__ import annotations
import time
from typing import Dict, List

import streamlit as st

from card import SUIT_SYMBOLS
from game import PARTNERSHIP
from bridge.solver import replay

#: Work done per rerun. Small enough to feel live, big enough to make progress.
SLICE_SECONDS = 1.5

#: Depth choices, as hand size at the start of the trick. The cost estimates
#: are measured, not guessed — see CLAUDE.md.
DEPTH_CHOICES = {
    'Endgame only — last 5 tricks (instant)': 5,
    'Most of the hand — last 8 tricks (~15s)': 8,
    'Deeper — last 9 tricks (~1 min)': 9,
    'Deepest affordable — last 10 tricks (~5 min)': 10,
}
DEFAULT_DEPTH = 'Most of the hand — last 8 tricks (~15s)'


#: Bumped whenever the analysis code changes. A Streamlit server outlives many
#: edits, and st.cache_resource outlives a hot reload — so without this, results
#: (including failures) cached by an older build stick around forever and the
#: panel keeps reporting them. This is why a stale error can look permanent.
_CACHE_VERSION = 3


@st.cache_resource(show_spinner=False)
def _analysis_cache() -> Dict[tuple, dict]:
    """Survives reruns, shared across boards. Keyed by version + board/trick/seat."""
    return {}


def _key(record: dict, decision) -> tuple:
    return (_CACHE_VERSION,) + replay.key_of(record, decision)


def _card_text(card) -> str:
    return f"{card.rank}{SUIT_SYMBOLS[card.suit]}"


def _human_seats(record: dict) -> List[str]:
    """Seats the player was actually responsible for on this board."""
    contract = record['contract']
    seats = ['South']
    if contract['declarer'] == 'South':
        seats.append(contract['dummy'])     # declarer plays dummy too
    elif contract['dummy'] == 'South':
        seats = [contract['declarer']]      # North declared and played both
    return sorted(set(seats))


def render_analysis(record: dict, key: str = 'dd') -> None:
    """Draw the analysis panel for one finished board."""
    if record.get('passed_out'):
        return

    cache = _analysis_cache()
    seats = _human_seats(record)

    with st.expander("🔍 Double Dummy Analysis — what else could you have played?",
                     expanded=False):
        st.caption(
            f"Every card was visible once the hand finished, so this is exact: no "
            f"guessing about the other hands. Reviewing **{' and '.join(seats)}**. "
            f"Analysis runs backwards from the last trick, because the endgame is "
            f"cheap to solve and the opening lead is not."
        )

        controls = st.columns([2, 1])
        with controls[0]:
            depth_label = st.selectbox(
                "How far back to analyse", list(DEPTH_CHOICES),
                index=list(DEPTH_CHOICES).index(DEFAULT_DEPTH),
                key=f"{key}_depth_{record['board_num']}",
                help="Earlier tricks cost dramatically more. Times are for a whole board.",
            )
        with controls[1]:
            running = st.toggle("Analyse", key=f"{key}_on_{record['board_num']}")

        max_cards = DEPTH_CHOICES[depth_label]
        decisions = replay.decisions(record, seats=seats, max_cards=max_cards)

        if not decisions:
            st.info("No real choices in that range — every play was forced.")
            return

        done = [d for d in decisions if _key(record, d) in cache]
        pending = [d for d in decisions if _key(record, d) not in cache]

        if not running and pending:
            st.info(f"{len(decisions)} decisions to review. "
                    f"Switch **Analyse** on to start.")
            if not done:
                return

        # ── One bounded slice of work, then hand control back ────────────────
        if running and pending:
            progress = st.progress(
                len(done) / len(decisions),
                text=f"Analysing… {len(done)} of {len(decisions)} decisions, "
                     f"working back from trick {decisions[0].trick_num}",
            )
            deadline = time.perf_counter() + SLICE_SECONDS
            while pending and time.perf_counter() < deadline:
                decision = pending.pop(0)
                key = _key(record, decision)
                try:
                    cache[key] = replay.analyse(decision)
                except Exception as error:        # never retry a failure forever
                    cache[key] = {'error': str(error),
                                  'trick_num': decision.trick_num,
                                  'seat': decision.seat}
                done.append(decision)
            progress.progress(len(done) / len(decisions))
            if pending:
                st.rerun()

        results = [cache[_key(record, d)] for d in decisions
                   if _key(record, d) in cache]
        usable = [r for r in results if 'error' not in r]
        broken = [r for r in results if 'error' in r]

        # Report failures before returning, and let them be retried. A cached
        # failure is never retried on its own, so without this the panel would
        # report the same stale problem for the life of the server.
        if broken:
            st.error(
                f"{len(broken)} of {len(results)} decisions could not be analysed. "
                f"First error — trick {broken[0].get('trick_num')}, "
                f"{broken[0].get('seat')}: {broken[0]['error']}"
            )
            if st.button("Clear results and retry",
                         key=f"{key}_retry_{record['board_num']}"):
                for decision in decisions:
                    cache.pop(_key(record, decision), None)
                st.rerun()

        if not usable:
            st.warning(
                "Nothing analysed yet. If an error is shown above, use "
                "**Clear results and retry** — results cached by an earlier "
                "version of the app are kept until then."
            )
            return

        _render_summary(usable, len(decisions))
        _render_rows(usable)


def _render_summary(results: List[dict], total: int) -> None:
    mistakes = [r for r in results if not r['was_best']]
    given_away = sum(r['loss'] for r in mistakes)

    cols = st.columns(3)
    cols[0].metric("Decisions reviewed", f"{len(results)} of {total}")
    cols[1].metric("Played the best card", f"{len(results) - len(mistakes)}")
    cols[2].metric("Tricks given away", given_away,
                   delta=None if not given_away else f"-{given_away}",
                   delta_color="inverse")

    if not mistakes:
        st.success("✅ Every reviewed play was as good as anything available.")


def _render_rows(results: List[dict]) -> None:
    st.divider()
    header = st.columns([0.6, 1, 0.8, 1.4, 0.8])
    for col, label in zip(header, ["Trick", "Seat", "Played", "Best instead", "Cost"]):
        col.markdown(f"**{label}**")

    # Worst first: the point of a post-mortem is the mistakes
    for row in sorted(results, key=lambda r: (-r['loss'], r['trick_num'])):
        cols = st.columns([0.6, 1, 0.8, 1.4, 0.8])
        cols[0].markdown(str(row['trick_num']))
        cols[1].markdown(row['seat'])
        cols[2].markdown(f"`{_card_text(row['played'])}`")
        if row['was_best']:
            cols[3].markdown("— *best available*")
            cols[4].markdown("—")
        else:
            alternatives = " ".join(f"`{_card_text(c)}`" for c in row['best_cards'][:4])
            cols[3].markdown(alternatives)
            trick_word = "trick" if row['loss'] == 1 else "tricks"
            cols[4].markdown(f"**−{row['loss']}** {trick_word}")
