"""The session so far, from your side (N/S): every board you have played, free
and challenge, passed-out ones included.

Imported boards are not yours, so they are left out. Challenge boards also
carry the margin against the robots on the same deal; the Challenge tab splits
that into auction and card play.

Rendered with Streamlit's own markdown and metrics, not `unsafe_allow_html`:
every value here is a number or a contract built from fixed symbols, but
there is no reason to add a raw-HTML site for it.
Port: frontend/src/lib/components/SessionScore.svelte.
"""
from __future__ import annotations

import streamlit as st
from card import STRAIN_SYMBOLS


def _signed(n: int) -> str:
    return f"{n:+d}"


def ns_score(record: dict) -> int:
    """Points to N/S: positive when N/S scored, whoever declared."""
    r = record['result']
    return r['points'] if r['winner'] == 'N/S' else -r['points']


def session_rows(history: list[dict], challenge_log: list[dict]) -> list[dict]:
    """One row per board you played to the end, with the running N/S total."""
    margins = {r['board_num']: r['margin'] for r in challenge_log if 'board_num' in r}
    rows, running = [], 0
    for h in history:
        if h.get('imported') or not h.get('contract') or not h.get('result'):
            continue
        c, r = h['contract'], h['result']
        score = ns_score(h)
        running += score
        doubled = '' if c['doubled'] == 'None' else c['doubled']
        rows.append({
            'num': h['board_num'],
            'contract': f"{c['level']}{STRAIN_SYMBOLS[c['strain']]}{doubled} {c['declarer'][0]}",
            'result': ('=' if not r['overtricks'] else f"+{r['overtricks']}") if r['made']
                      else f"−{r['undertricks']}",
            'side': c['side'],
            'made': r['made'],
            'score': score,
            'running': running,
            'margin': margins.get(h['board_num']),
        })
    return rows


def render_session_score(history: list[dict], challenge_log: list[dict], passed_out: int) -> None:
    rows = session_rows(history, challenge_log)
    boards = len(rows) + passed_out
    if not boards:
        return
    total = rows[-1]['running'] if rows else 0
    declared = [r for r in rows if r['side'] == 'N/S']
    defended = [r for r in rows if r['side'] == 'E/W']
    vs_robots = sum(r['margin'] for r in challenge_log)

    label = f"Session · {boards} board{'s' if boards != 1 else ''} · N/S {_signed(total)}"
    if challenge_log:
        label += f" · vs robots {_signed(vs_robots)}"
    with st.expander(label, expanded=False):
        m = st.columns(4)
        m[0].metric("N/S total", _signed(total))
        m[1].metric("Per board", _signed(round(total / boards)))
        m[2].metric("Declaring", f"{sum(r['made'] for r in declared)}/{len(declared)} made")
        m[3].metric("Defending", f"{sum(not r['made'] for r in defended)}/{len(defended)} set")
        if passed_out:
            st.caption(f"{passed_out} passed out (0 each).")
        if rows:
            head = "| Board | Contract | Result | N/S | Running |"
            rule = "|---|---|---|---|---|"
            if challenge_log:
                head += " vs robots |"
                rule += "---|"
            lines = [head, rule]
            for r in rows:
                line = (f"| #{r['num']} | {r['contract']} | {r['result']} | "
                        f"{_signed(r['score'])} | {_signed(r['running'])} |")
                if challenge_log:
                    line += f" {'—' if r['margin'] is None else _signed(r['margin'])} |"
                lines.append(line)
            st.markdown("\n".join(lines))
        if challenge_log:
            st.caption('"vs robots" is your score minus the robots\' on the same challenge '
                       'deal. The Challenge tab splits it into auction and card play.')
