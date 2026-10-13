"""Reconstructing decisions from a finished board, and scoring them.

The reconstruction is the risky part: an off-by-one in which cards are still
held would produce a confident, wrong analysis rather than an error. So these
tests check the rebuilt positions against the recorded play directly, and only
then check the scoring on top.
"""
from __future__ import annotations
import random
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from card import deal
from game import PLAYERS, clockwise_from, legal_plays, resolve_trick
from bridge.solver import api, replay


def synthetic_board(seed: int, strain: str = 'S', board_num: int = 1) -> dict:
    """A fully played board in the shape app.py stores in hand_history."""
    random.seed(seed)
    initial = {seat: list(cards) for seat, cards in deal().items()}
    hands = {seat: list(cards) for seat, cards in initial.items()}
    rng = random.Random(seed + 77)

    leader, log, taken = 'West', [], {'N/S': 0, 'E/W': 0}
    for trick_num in range(1, 14):
        plays = []
        for seat in clockwise_from(leader):
            led = plays[0][1].suit if plays else None
            options = sorted(legal_plays(hands[seat], led), key=str)
            card = options[rng.randrange(len(options))]
            hands[seat].remove(card)
            plays.append((seat, card))
        winner = resolve_trick(plays, strain)
        log.append({
            'trick_num': trick_num,
            'leader': leader,
            'plays': plays,
            'winner': winner,
            'winning_card': dict(plays)[winner],
        })
        taken['N/S' if winner in ('North', 'South') else 'E/W'] += 1
        leader = winner

    return {
        'board_num': board_num,
        'passed_out': False,
        'initial_hands': initial,
        'tricks_log': log,
        'tricks_taken': taken,
        'contract': {'strain': strain, 'trump': strain, 'declarer': 'South',
                     'dummy': 'North', 'side': 'N/S', 'level': 3},
    }


# ── Reconstruction ───────────────────────────────────────────────────────────

def test_every_play_is_reconstructed_as_legal():
    """The card actually played must be legal in the rebuilt position."""
    for seed in range(6):
        board = synthetic_board(seed)
        found = replay.decisions(board, skip_forced=False)
        assert len(found) == 52, f"expected one decision per play, got {len(found)}"

        for d in found:
            led = d.trick_so_far[0].suit if d.trick_so_far else None
            legal = legal_plays(d.hands[d.seat], led)
            assert d.played in legal, (seed, d.trick_num, d.seat, d.played)


def test_reconstructed_hands_are_internally_consistent():
    """Positions must survive the API's own validation, which is strict."""
    for seed in range(4):
        board = synthetic_board(seed)
        for d in replay.decisions(board, skip_forced=False):
            # _position raises on duplicates, uneven hands, or trick/hand overlap
            api._position(d.hands, d.strain, d.leader, d.trick_so_far)


def test_card_counts_shrink_by_exactly_one_per_play():
    board = synthetic_board(1)
    by_trick = {}
    for d in replay.decisions(board, skip_forced=False):
        by_trick.setdefault(d.trick_num, []).append(d)

    for trick_num, group in by_trick.items():
        total = {sum(len(h) for h in d.hands.values()) for d in group}
        # Four decisions per trick, each with one fewer card on the table
        assert len(total) == 4, (trick_num, sorted(total))
        assert max(total) == 52 - 4 * (trick_num - 1)


def test_decisions_run_latest_trick_first():
    board = synthetic_board(2)
    numbers = [d.trick_num for d in replay.decisions(board, skip_forced=False)]
    assert numbers == sorted(numbers, reverse=True)
    assert numbers[0] == 13 and numbers[-1] == 1


def test_seat_and_depth_filters():
    board = synthetic_board(3)
    south = replay.decisions(board, seats=['South'], skip_forced=False)
    assert len(south) == 13
    assert {d.seat for d in south} == {'South'}

    shallow = replay.decisions(board, max_cards=4, skip_forced=False)
    assert shallow
    assert all(d.cards_each <= 4 for d in shallow)
    assert {d.trick_num for d in shallow} <= {10, 11, 12, 13}


def test_forced_plays_are_skipped_by_default():
    board = synthetic_board(4)
    everything = replay.decisions(board, skip_forced=False)
    choices = replay.decisions(board, skip_forced=True)
    assert len(choices) < len(everything)
    assert all(d.choices > 1 for d in choices)
    # The last trick is always forced: one card left, nothing to decide
    assert 13 not in {d.trick_num for d in choices}


def test_passed_out_board_has_nothing_to_analyse():
    assert replay.decisions({'passed_out': True}) == []


# ── Scoring ──────────────────────────────────────────────────────────────────

def test_analysis_is_self_consistent():
    board = synthetic_board(5)
    for d in replay.decisions(board, max_cards=4):
        out = replay.analyse(d)
        assert out['played_value'] in out['values'].values()
        assert out['loss'] >= 0, "a loss can never be negative"
        assert out['was_best'] == (out['loss'] == 0)
        assert out['best_cards']
        assert out['played'] == d.played
        if out['was_best']:
            assert d.played in out['best_cards']


def test_loss_is_measured_from_the_mover_s_own_side():
    """N/S maximise N/S tricks; E/W minimise them. Loss is positive either way."""
    board = synthetic_board(6)
    for d in replay.decisions(board, max_cards=4):
        out = replay.analyse(d)
        values = list(out['values'].values())
        if out['side'] == 'N/S':
            assert out['best_value'] == max(values)
            assert out['loss'] == out['best_value'] - out['played_value']
        else:
            assert out['best_value'] == min(values)
            assert out['loss'] == out['played_value'] - out['best_value']


def test_best_cards_really_are_best():
    board = synthetic_board(7)
    for d in replay.decisions(board, max_cards=3):
        out = replay.analyse(d)
        for card in out['best_cards']:
            assert out['values'][card] == out['best_value'], (d.trick_num, card)


def test_cache_key_is_stable_and_distinct():
    board = synthetic_board(8)
    found = replay.decisions(board, skip_forced=False)
    keys = [replay.key_of(board, d) for d in found]
    assert len(keys) == len(set(keys)), "keys must identify a decision uniquely"
    assert keys[0] == replay.key_of(board, found[0]), "keys must be stable"

    # The same board NUMBER with a different play is a different key: the
    # cache is shared by every session, and board 1 recurs in each.
    other = dict(board, tricks_log=[dict(e) for e in board['tricks_log']])
    first = other['tricks_log'][0]
    first['plays'] = list(reversed(first['plays']))
    assert replay.key_of(other, found[0]) != keys[0]


def test_cards_dealt_before_a_module_reload_still_compare_equal():
    """Streamlit re-imports every project module when a source file changes.
    A board dealt before that holds the OLD Card class; with an isinstance
    test it equalled no new Card, and the analysis panel rejected all seven
    of a user's decisions as "not legal"."""
    import importlib
    import card
    old = card.Card('H', '2')
    importlib.reload(card)
    new = card.Card('H', '2')
    assert type(old) is not type(new)
    assert old == new and new == old and hash(old) == hash(new)
    assert new in {old: 1}


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nReplay reconstruction and scoring verified.")
