"""Shared tracing for the gap analysis: which part of the robots produced a call.

Wraps gib.gib_bid, gib.contested, gib.continuation and ai._previous_system so
one ai_bid_explained call leaves a record of what each layer returned. Research
only; the app never imports this. Run with python3.12 from the repo root.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ai   # noqa: E402
import gib  # noqa: E402
from game import AuctionState  # noqa: E402

PARTNER = {'North': 'South', 'South': 'North', 'East': 'West', 'West': 'East'}
SIDE = {'North': 'N/S', 'South': 'N/S', 'East': 'E/W', 'West': 'E/W'}
TRACE: dict = {}

_gib_bid, _contested, _continuation, _prev = gib.gib_bid, gib.contested, gib.continuation, ai._previous_system


def _w_gib_bid(*a, **k):
    r = _gib_bid(*a, **k)
    TRACE.setdefault('gib', []).append(r)
    return r


def _w_contested(*a, **k):
    r = _contested(*a, **k)
    TRACE.setdefault('contested', []).append(r)
    return r


def _w_continuation(*a, **k):
    r = _continuation(*a, **k)
    TRACE.setdefault('cont', []).append(r)
    return r


def _w_prev(*a, **k):
    r = _prev(*a, **k)
    TRACE.setdefault('prev', []).append(r)
    return r


gib.gib_bid, gib.contested, gib.continuation, ai._previous_system = \
    _w_gib_bid, _w_contested, _w_continuation, _w_prev

#: Words in partner's alert that say the call is not to play.
ARTIFICIAL = re.compile(r'artificial|forcing|takeout|asks|cuebid|michaels|unusual|'
                        r'relay|transfer|stayman|keycard|blackwood|gerber|'
                        r'game try|invit|two-suit|two suit|support double|negative|'
                        r'responsive|snapdragon|lebensohl|puppet|good raise|limit raise',
                        re.I)


_FILES = ('gib.py', 'ai.py')
_RETURNS: list = []


def _prof(frame, event, arg):
    if event == 'return' and type(arg) is tuple and len(arg) == 2 and arg[0] == 'Pass' \
            and frame.f_code.co_filename.endswith(_FILES):
        _RETURNS.append((frame.f_code.co_filename.rsplit('/', 1)[-1][:-3],
                         frame.f_code.co_name, frame.f_lineno, arg[1]))


def origin(why):
    """file:function:line of the return statement that first produced this
    Pass alert (alert strings pass up the layers by identity)."""
    for f, fn, ln, w in _RETURNS:
        if w is why:
            return f"{f}:{fn}:{ln}"
    for f, fn, ln, w in _RETURNS:
        if w == why:
            return f"{f}:{fn}:{ln}"
    return '?'


def decide(p, hand, a, alerts):
    """(call, alert, source). source: 'handoff' (GIB had no rule; the old
    system's call), 'catchall' (GIB's contested tables had nothing and its
    generic continuation answered), 'rule' (a GIB or ai.py rule made it)."""
    TRACE.clear()
    _RETURNS.clear()
    sys.setprofile(_prof)
    try:
        call, why = ai.ai_bid_explained(p, hand, a, alerts)
    finally:
        sys.setprofile(None)
    src = 'rule'
    gibs = TRACE.get('gib', [])
    if gibs and gibs[-1] is None and TRACE.get('prev') and TRACE['prev'][-1][0] == call:
        src = 'handoff'
    elif (TRACE.get('contested') and TRACE['contested'][-1] is None and TRACE.get('cont')
          and TRACE['cont'][-1][0] == call and gibs and gibs[-1] and gibs[-1][0] == call):
        src = 'catchall'
    return call, why, src, (origin(why) if call == 'Pass' else None)


def pattern(player, calls):
    """Calls from the first bid on, opponents bracketed, from player's seat."""
    out, started = [], False
    for w, c in calls:
        if not started and c == 'Pass':
            continue
        started = True
        out.append(c if w in (player, PARTNER[player]) else f'({c})')
    return ' '.join(out + ['?']) if out else '?'


def family(pat):
    names = {}

    def sub(m):
        lvl, s = m.group(1), m.group(2)
        if s == 'NT':
            return lvl + 'NT'
        if s not in names:
            names[s] = 'xyzw'[len(names)]
        return lvl + names[s]
    return re.sub(r'(\d)(NT|[CDHS])', sub, pat).replace('Pass', 'P')


def contested(player, calls):
    """Opponents have made a call other than Pass."""
    return any(w not in (player, PARTNER[player]) and c != 'Pass' for w, c in calls)


def partner_last(player, calls):
    """Index of partner's last non-pass call, or None."""
    for i in range(len(calls) - 1, -1, -1):
        w, c = calls[i]
        if w == PARTNER[player] and c != 'Pass':
            return i
    return None
