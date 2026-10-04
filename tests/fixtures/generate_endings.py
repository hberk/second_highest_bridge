"""Regenerate tests/fixtures/endings.json by exhaustive enumeration.

Run this only when the fixture needs to be rebuilt from scratch:

    python tests/fixtures/generate_endings.py

It takes a few minutes, almost all of it in the 5-card positions. The output is
checked in and frozen: it is the ground truth every later optimisation is
validated against, so a change to these numbers means either a rules change or
a bug, never a speedup.

Enumeration cost measured at ~115x per extra card (3 cards ~2e3 nodes, 4 cards
~2e5, 5 cards ~2e7), which is what caps the fixture at 5.
"""
from __future__ import annotations
import json
import random
import sys
import time
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from card import deal
from game import PLAYERS
from bridge.solver.bitstate import Position, cards_in, legal_moves, resolve
from bridge.solver.brute import solve_with_nodes
from bridge.solver.convert import (
    hands_to_masks, index_to_text, mask_to_text, text_to_mask, trump_to_index,
)

FIXTURE = Path(__file__).resolve().parent / 'endings.json'
STRAINS = ['C', 'D', 'H', 'S', 'NT']

#: How many random positions per ending size. 5-card positions cost ~20s each.
SAMPLE_PLAN = [(1, 24), (2, 40), (3, 48), (4, 40), (5, 8)]


def random_ending(seed: int, cards_each: int, mid_trick: int = 0) -> Position:
    """A reachable position: deal, play down to `cards_each`, then `mid_trick` plays."""
    random.seed(seed)
    hands = list(hands_to_masks(deal()))
    rng = random.Random(seed * 7919 + 1)
    trump = trump_to_index(rng.choice(STRAINS))
    leader = rng.randrange(4)

    for _ in range(13 - cards_each):
        trick, seat, led = [], leader, None
        for i in range(4):
            options = list(cards_in(legal_moves(hands[seat], led)))
            card = options[rng.randrange(len(options))]
            hands[seat] &= ~(1 << card)
            trick.append(card)
            if i == 0:
                led = card // 13
            seat = (seat + 1) % 4
        leader = resolve(tuple(trick), leader, trump)

    pos = Position(tuple(hands), leader, (), trump)
    for _ in range(mid_trick):
        options = list(cards_in(pos.moves()))
        pos, _ = pos.play(options[rng.randrange(len(options))])
    return pos


# Hand-built worst cases. Random deals almost never produce these, and they are
# exactly where the Second-Highest mechanic and (later) equivalence reduction
# are most likely to break.
CRAFTED = [
    ('single-suit-nt', 'NT', 'North',
     ['AS KS QS', 'JS 10S 9S', '8S 7S 6S', '5S 4S 3S']),
    ('single-suit-trump', 'S', 'North',
     ['AS KS QS', 'JS 10S 9S', '8S 7S 6S', '5S 4S 3S']),
    ('single-suit-offtrump', 'H', 'East',
     ['AS KS QS', 'JS 10S 9S', '8S 7S 6S', '5S 4S 3S']),
    ('stranded-ace', 'NT', 'North',
     ['AS 2S', 'KS 3S', 'QS 4S', 'JS 5S']),
    ('stranded-ace-trump', 'S', 'South',
     ['AS 2S', 'KS 3S', 'QS 4S', 'JS 5S']),
    ('two-suit', 'NT', 'North',
     ['AS KS AH KH', 'QS JS QH JH', '10S 9S 10H 9H', '8S 7S 8H 7H']),
    ('two-suit-trump', 'H', 'West',
     ['AS KS AH KH', 'QS JS QH JH', '10S 9S 10H 9H', '8S 7S 8H 7H']),
    ('mutual-voids', 'NT', 'North',
     ['AS KS QS JS', 'AH KH QH JH', 'AD KD QD JD', 'AC KC QC JC']),
    ('mutual-voids-trump', 'D', 'North',
     ['AS KS QS JS', 'AH KH QH JH', 'AD KD QD JD', 'AC KC QC JC']),
    ('ruff-race', 'S', 'East',
     ['AS 2S AH', 'KS 3S KH', 'QS 4S QH', 'JS 5S JH']),
    ('one-defender-void', 'NT', 'North',
     ['AH KH QH', '2S 3S 4S', 'JH 10H 9H', '8H 7H 6H']),
    ('touching-honours', 'NT', 'North',
     ['AS KS QS', 'JS 10S 9H', '8S 7S 6H', '5S 4S 3H']),
]


def crafted_position(strain, leader, hand_texts):
    masks = tuple(text_to_mask(t) for t in hand_texts)
    seen = 0
    for mask in masks:
        assert seen & mask == 0, "crafted hands share a card"
        seen |= mask
    sizes = {bin(m).count('1') for m in masks}
    assert len(sizes) == 1, "crafted hands differ in length"
    return Position(masks, PLAYERS.index(leader), (), trump_to_index(strain))


def record(entry_id: str, pos: Position) -> dict:
    start = time.perf_counter()
    value, nodes = solve_with_nodes(pos)
    elapsed = time.perf_counter() - start
    cards_each = max(bin(h).count('1') for h in pos.hands)
    print(f"  {entry_id:<28} ns={value}  nodes={nodes:>12,}  {elapsed:7.2f}s", flush=True)
    return {
        'id': entry_id,
        'cards_each': cards_each,
        'strain': 'NT' if pos.trump is None else 'CDHS'[pos.trump],
        'leader': PLAYERS[pos.leader],
        'hands': {PLAYERS[i]: mask_to_text(h) for i, h in enumerate(pos.hands)},
        'trick': ' '.join(index_to_text(c) for c in pos.trick),
        'ns_tricks': value,
        'nodes': nodes,
    }


def main() -> int:
    positions = []
    started = time.perf_counter()

    print("crafted positions")
    for name, strain, leader, hand_texts in CRAFTED:
        pos = crafted_position(strain, leader, hand_texts)
        positions.append(record(f'crafted-{name}', pos))
        # The same shape with a trick already in progress, to exercise a
        # mid-trick root rather than only trick boundaries.
        opening = sorted(cards_in(pos.moves()))[0]
        mid, _ = pos.play(opening)
        positions.append(record(f'crafted-{name}-mid', mid))

    for cards_each, samples in SAMPLE_PLAN:
        print(f"random {cards_each}-card endings")
        for i in range(samples):
            mid_trick = i % 4 if cards_each > 1 else 0
            pos = random_ending(i, cards_each, mid_trick)
            positions.append(record(f'random-{cards_each}-{i:02d}', pos))

    payload = {
        'note': (
            'Ground truth for the Second-Highest double dummy solver. Produced '
            'by exhaustive enumeration with no pruning or memoisation. Frozen: '
            'a change to ns_tricks means a rules change or a bug, never a speedup.'
        ),
        'generator': 'tests/fixtures/generate_endings.py',
        'solver': 'bridge/solver/brute.py',
        'ns_tricks': 'tricks taken by North/South with optimal play by both sides',
        'nodes': 'nodes visited by exhaustive enumeration, a cost baseline for later stages',
        'positions': positions,
    }
    FIXTURE.write_text(json.dumps(payload, indent=1) + '\n', encoding='utf-8')

    elapsed = time.perf_counter() - started
    total_nodes = sum(p['nodes'] for p in positions)
    print(f"\nwrote {len(positions)} positions to {FIXTURE}")
    print(f"{total_nodes:,} nodes enumerated in {elapsed:.1f}s")
    return 0


if __name__ == '__main__':
    sys.exit(main())
