"""The double dummy dataset generator, and the solver method it relies on.

A dataset that is subtly wrong is worse than none: it would be fitted, trusted,
and baked into the bidding. So these tests check the parts that could corrupt it
quietly: that value_from gives exactly value's answer, that strains, declarers
and leaders are chosen as documented, that a paired solve matches independent
solves, and that resuming never duplicates or loses a record.

Everything here runs on small positions or fake work, so it stays quick.
"""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from card import Card
from game import PLAYERS
from bridge.solver import search
from bridge.solver.bitstate import Position, tricks_available
from bridge.solver.convert import cards_to_mask, trump_to_index
from research import dd_dataset as ds
from tests.test_solver_exact import load_fixture, position_of


def hand(text: str) -> list:
    return [Card(token[-1], token[:-1]) for token in text.split()]


# ── value_from ───────────────────────────────────────────────────────────────

def test_value_from_matches_value_from_every_starting_guess():
    checked = 0
    for entry in load_fixture()['positions']:
        if entry['cards_each'] > 4:
            continue
        pos = position_of(entry)
        total = tricks_available(pos)
        for guess in range(-2, total + 3):          # includes out-of-range guesses
            got = search.Search(pos.trump).value_from(pos, guess)
            assert got == entry['ns_tricks'], (entry['id'], guess, got)
        checked += 1
    assert checked >= 100


def test_value_from_can_share_a_table_with_earlier_solves():
    for entry in load_fixture()['positions']:
        if entry['cards_each'] > 3:
            continue
        pos = position_of(entry)
        engine = search.Search(pos.trump)
        assert engine.value(pos) == entry['ns_tricks']
        assert engine.value_from(pos, 0) == entry['ns_tricks']
        assert engine.value_from(pos, tricks_available(pos)) == entry['ns_tricks']


# ── Strain, declarer, leader ─────────────────────────────────────────────────

def test_best_fit_prefers_length_then_honours_then_rank():
    # best_fit reads only the two hands of the side asked about, so tiny hands
    # keep each tiebreak visible at a glance. An earlier version used full deals
    # and quietly gave N/S nine diamonds, so it never tested a tiebreak at all.

    # Length beats honours: four small hearts outrank a lone spade ace
    longer = {'North': hand('AS 2H 3H'), 'South': hand('4H 5H')}
    assert ds.best_fit(longer, 'N/S') == 'H'

    # Equal length: honours beat rank, so A-K of diamonds beats two small spades
    honours = {'North': hand('AD 2S'), 'South': hand('KD 3S')}
    assert ds.best_fit(honours, 'N/S') == 'D'

    # Equal length and equal honours: only then does the higher-ranking suit win
    rank = {'North': hand('AD AS'), 'South': hand('2D 2S')}
    assert ds.best_fit(rank, 'N/S') == 'S'


def test_strains_are_both_fits_then_notrump_without_duplicates():
    hands = ds.deal_for(0)
    strains = [strain for strain, _ in ds.strains_to_solve(hands)]
    assert strains[-1] == 'NT'
    assert len(strains) == len(set(strains))
    assert 2 <= len(strains) <= 3
    assert set(strains[:-1]) == {ds.best_fit(hands, 'N/S'), ds.best_fit(hands, 'E/W')}


def test_declarer_is_the_longer_partner_and_the_lead_comes_from_their_left():
    hands = {
        'North': hand('AS KS QS JS 10S 2H 3H 4H 2D 3D 4D 2C 3C'),
        'South': hand('9S 8S 5H 6H 7H 5D 6D 7D 8D 4C 5C 6C 7C'),
        'East': hand('7S 6S 5S AH KH QH JH AD KD QD 8C 9C 10C'),
        'West': hand('4S 3S 2S 10H 9H 8H JD 10D 9D AC KC QC JC'),
    }
    assert ds.declarer_for(hands, 'N/S', 'S') == 'North'
    assert ds.leader_for('North') == 'East'
    assert ds.declarer_for(hands, 'E/W', 'NT') == 'East'      # more high-card points
    assert ds.leader_for('East') == 'South'
    for seat in PLAYERS:
        leader = ds.leader_for(seat)
        assert leader != seat and PLAYERS.index(leader) % 2 != PLAYERS.index(seat) % 2


# ── Paired solving ───────────────────────────────────────────────────────────

def test_solve_strain_matches_independent_solves():
    checked = 0
    for entry in load_fixture()['positions']:
        if entry['cards_each'] > 4 or entry['trick']:
            continue
        hands = ds.hands_from_text(entry['hands'])
        for strain in ('NT', ds.best_fit(hands, 'N/S')):
            solved = ds.solve_strain(hands, strain)
            assert [r['declaring_side'] for r in solved['results']] == ['N/S', 'E/W']
            for result in solved['results']:
                position = Position(
                    tuple(cards_to_mask(hands[seat]) for seat in PLAYERS),
                    PLAYERS.index(result['leader']), (), trump_to_index(strain))
                expected_ns = search.solve(position)
                total = tricks_available(position)
                assert result['ns_tricks'] == expected_ns, (entry['id'], strain, result)
                side_tricks = expected_ns if result['declaring_side'] == 'N/S' else total - expected_ns
                assert result['declarer_tricks'] == side_tricks, (entry['id'], strain, result)
                assert ds.leader_for(result['declarer']) == result['leader']
            checked += 1
    assert checked >= 50


# ── Deals, records, resuming ─────────────────────────────────────────────────

def test_deals_are_reproducible_from_their_id():
    assert ds.hands_to_text(ds.deal_for(3)) == ds.hands_to_text(ds.deal_for(3))
    assert ds.hands_to_text(ds.deal_for(3)) != ds.hands_to_text(ds.deal_for(4))


def test_hands_round_trip_through_text():
    hands = ds.deal_for(7)
    back = ds.hands_from_text(ds.hands_to_text(hands))
    for seat in PLAYERS:
        assert set(back[seat]) == set(hands[seat]) and len(back[seat]) == 13


def test_plan_is_deterministic_and_puts_notrump_in_every_deal():
    first, second = ds.plan(6), ds.plan(6)
    assert first == second
    for deal_id in range(6):
        strains = [strain for d, strain, _ in first if d == deal_id]
        assert 'NT' in strains and 2 <= len(strains) <= 3


def _fake_work(task):
    deal_id, strain, why = task
    return {'deal_id': deal_id, 'strain': strain, 'why': why, 'results': [], 'seconds': 0}


def test_run_resumes_without_duplicating_or_losing_records():
    tasks = [(d, s, ['test']) for d in range(3) for s in ('S', 'NT')]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'data.jsonl'
        silent = lambda message: None

        assert ds.run(tasks[:4], out, workers=1, work=_fake_work, log=silent) == 4
        assert ds.run(tasks, out, workers=1, work=_fake_work, log=silent) == 2   # only the rest
        assert ds.run(tasks, out, workers=1, work=_fake_work, log=silent) == 0   # nothing left

        records = [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()]
        keys = [(r['deal_id'], r['strain']) for r in records]
        assert sorted(keys) == sorted((d, s) for d, s, _ in tasks)
        assert len(keys) == len(set(keys))


def test_run_recovers_from_a_record_cut_off_mid_write():
    tasks = [(d, 'NT', ['test']) for d in range(3)]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'data.jsonl'
        silent = lambda message: None
        ds.run(tasks[:2], out, workers=1, work=_fake_work, log=silent)

        # Simulate a hard kill partway through writing the second record
        text = out.read_text(encoding='utf-8')
        out.write_text(text[: len(text) - 15], encoding='utf-8')
        assert ds.completed(out) == {(0, 'NT')}

        ds.run(tasks, out, workers=1, work=_fake_work, log=silent)
        parsed = []
        for line in out.read_text(encoding='utf-8').splitlines():
            try:
                parsed.append(json.loads(line))
            except json.JSONDecodeError:
                pass                                  # the cut-off fragment stays behind
        keys = sorted((r['deal_id'], r['strain']) for r in parsed)
        assert keys == [(0, 'NT'), (1, 'NT'), (2, 'NT')]


def test_run_works_through_a_process_pool():
    """The real run uses a pool, and Windows starts its workers by spawn, which
    fails at runtime on work that cannot be pickled or re-imported. Every other
    test here uses a single worker, so none of them would catch that."""
    tasks = [(d, 'NT', ['test']) for d in range(3)]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'data.jsonl'
        written = ds.run(tasks, out, workers=2, work=_fake_work, log=lambda message: None)
        assert written == 3
        records = [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()]
        assert sorted((r['deal_id'], r['strain']) for r in records) == [(0, 'NT'), (1, 'NT'), (2, 'NT')]


def test_extra_fits_adds_next_best_suits_and_leaves_the_default_alone():
    """--extra-fits widens the plan without invalidating data already on disk.

    The default must stay exactly what it was: an existing .jsonl resumes by
    (deal, strain), so if the default set ever changed, every finished deal would
    silently re-solve. The wider set has to be a superset for the same reason.
    """
    hands = ds.deal_for(0)
    base = [strain for strain, _ in ds.strains_to_solve(hands)]
    wider = [strain for strain, _ in ds.strains_to_solve(hands, extra_fits=1)]

    assert base == [strain for strain, _ in ds.strains_to_solve(hands, 0)]
    assert set(base) <= set(wider), "resume would re-solve finished deals"
    assert 'NT' in wider

    for side in ('N/S', 'E/W'):
        ranked = ds.ranked_fits(hands, side)
        assert ranked[0] == ds.best_fit(hands, side), "ranked_fits[0] must be best_fit"
        assert len(ranked) == 4 and len(set(ranked)) == 4
        assert ranked[0] in wider and ranked[1] in wider

    assert len(ds.plan(4, 1)) > len(ds.plan(4))
    assert ds.plan(4, 0) == ds.plan(4)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nDataset generator verified.")
