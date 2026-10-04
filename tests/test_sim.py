"""Automated smoke test: play a full game with all-AI players and verify invariants."""
from __future__ import annotations
import random
import sys
from pathlib import Path

# Ensure root directory is on python path when running tests from tests/ directory
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from card import deal, auto_contract, SUIT_SYMBOLS, SUIT_NAMES
from game import clockwise_from, legal_plays, resolve_trick, score
from ai import ai_play


def test_smoke_sim():
    random.seed(2024)
    hands = deal()
    trump = auto_contract(hands['North'], hands['South'])
    played = []
    print("Trump:", SUIT_SYMBOLS[trump], SUIT_NAMES[trump])

    # Verify each player has 13 cards
    for p, h in hands.items():
        assert len(h) == 13, f"{p} has {len(h)} cards"

    # Verify all 52 cards are distinct
    all_cards = [(c.suit, c.rank) for h in hands.values() for c in h]
    assert len(set(all_cards)) == 52, "Duplicate cards detected"

    ns, ew = 0, 0
    leader = 'West'

    for trick_num in range(1, 14):
        order = clockwise_from(leader)
        trick = []
        for player in order:
            led = trick[0][1].suit if trick else None
            card = ai_play(player, hands[player], trick, trump, played)
            assert card in legal_plays(hands[player], led), f"{player} played {card}, which is not a legal play"
            hands[player].remove(card)
            trick.append((player, card))

        assert len(trick) == 4, "Trick does not have 4 cards"
        winner = resolve_trick(trick, trump)
        assert winner in ('North', 'East', 'South', 'West'), "Invalid winner"

        if winner in ('North', 'South'):
            ns += 1
        else:
            ew += 1

        played.extend(c for _, c in trick)
        line = "  ".join(str(dict(trick)[p]) for p in order)
        print("Trick %2d: %s  ->  %s" % (trick_num, line, winner))
        leader = winner

    assert ns + ew == 13, "Tricks don't add up to 13"
    print("\nFinal:  N/S=%d  E/W=%d  (total=%d)" % (ns, ew, ns + ew))
    result = score(ns, trump)
    print("Result:", result['winner'], "wins.", result['detail'])
    print("\nAll assertions passed.")


if __name__ == '__main__':
    test_smoke_sim()
