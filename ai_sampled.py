"""Sampled look-ahead for the middle game (experiment, tricks 6 to 8).

`ai_play` has no rule that looks past the current trick. From 5 cards a hand it
searches every layout; before that (8, 7 and 6 cards a hand) every layout is too
many. Here the cards the player can't see are dealt to the two hidden hands
SAMPLES times -- hand sizes, suits shown out and the auction's shown lengths
respected -- each layout is solved double dummy by the Rust `sample_values`
binary, and the card with the best average wins.

Determinism: the layouts come from a private `random.Random` seeded by a hash of
the position, so the same position always draws the same layouts. This module is
the only place with an RNG; `ai.py` still imports none. It shells out to a native
binary, so it is research only (the web port would call the WebAssembly solver).
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
from pathlib import Path

from game import PARTNERSHIP, PLAYERS

EXE = Path(__file__).resolve().parent / 'research' / 'solver-rs' / 'target' / 'release' / 'sample_values'

SAMPLES = int(os.environ.get('SAMPLED_SAMPLES', '40'))
#: Hand sizes (cards each, before this trick's card) that get the search.
MIN_CARDS = int(os.environ.get('SAMPLED_MIN', '6'))
MAX_CARDS = int(os.environ.get('SAMPLED_MAX', '8'))
#: Only change the rule's card when the search's average gain is at least this.
MARGIN = float(os.environ.get('SAMPLED_MARGIN', '0'))


def _text(c) -> str:
    return f"{c.rank}{c.suit}"


def sampled_choice(player, hand, trick, trump, played, visible, history, shown,
                   legal, choice, count, order_key):
    """The legal card with the best average over sampled layouts, or None."""
    if not EXE.exists():
        raise RuntimeError(f'{EXE} is not built: cargo build --release in research/solver-rs')
    known = {player: list(hand)}
    for seat, cards in visible.items():
        if seat != player:
            known[seat] = list(cards)
    hidden = [p for p in PLAYERS if p not in known]
    if len(hidden) != 2:
        return None
    size = {p: count.size(p) for p in PLAYERS}
    unseen = list(count.unseen)
    if len(unseen) != size[hidden[0]] + size[hidden[1]]:
        return None
    out = count.out
    a, b = hidden
    key = repr((player, sorted(map(_text, hand)), [(s, _text(c)) for s, c in trick],
                [[(s, _text(c)) for s, c in t] for t in history]))
    rnd = random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:12], 16))
    # The hands as they were when this trick began.
    start = {p: list(cs) for p, cs in known.items()}
    for s, c in trick:
        if s in start:
            start[s].append(c)
    on_table = {s: c for s, c in trick}
    layouts = []
    tries = 0
    while len(layouts) < SAMPLES and tries < 40 * SAMPLES:
        tries += 1
        rnd.shuffle(unseen)
        ha, hb = unseen[:size[a]], unseen[size[a]:]
        if any(c.suit in out[a] for c in ha) or any(c.suit in out[b] for c in hb):
            continue
        if tries < 20 * SAMPLES and not (count.fits_auction(a, ha) and count.fits_auction(b, hb)):
            continue
        lay = {p: list(cs) for p, cs in start.items()}
        for s, h in ((a, ha), (b, hb)):
            lay[s] = list(h) + ([on_table[s]] if s in on_table else [])
        layouts.append({s: ' '.join(_text(c) for c in cs) for s, cs in lay.items()})
    if not layouts:
        return None
    leader = trick[0][0] if trick else player
    payload = {'strain': trump or 'NT', 'leader': leader,
               'trick': [_text(c) for _, c in trick], 'layouts': layouts}
    proc = subprocess.run([str(EXE)], input=json.dumps(payload), capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    sums = {c: v for c, v in json.loads(proc.stdout)['sums']}
    ns = PARTNERSHIP[player] == 'N/S'
    n = len(layouts)
    totals = {}
    for c in legal:
        v = sums[_text(c)] / n
        totals[c] = v if ns else -v
    best = max(totals.values())
    if totals.get(choice, -99) >= best - MARGIN - 1e-9:
        return choice
    tied = [c for c in legal if totals[c] >= best - 1e-9]
    return min(tied, key=order_key)
