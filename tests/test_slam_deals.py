"""The slam deal generator: filter, screen, finish, resume.

The solver itself is tested elsewhere; these use fake solves, so they stay quick
and check what could quietly corrupt the slam set: which sides are screened, when
a deal is finished, that the screen and the full solve must agree, and that a
resumed run never loses or double-counts a deal.
"""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from research import dd_dataset as ds
from research import slam_deals as sd


def _fake_one(tricks_by_side):
    def solve_one(hands, strain, side):
        return {'declaring_side': side, 'strain': strain, 'declarer_tricks': tricks_by_side[side]}
    return solve_one


def _fake_strain(tricks_by_side):
    def solve_strain(hands, strain):
        return {'strain': strain, 'results': [
            {'declaring_side': side, 'declarer_tricks': tricks_by_side[side]}
            for side in ('N/S', 'E/W')]}
    return solve_strain


def _deal_with_both_sides_kept():
    for deal_id in range(500):
        if len(sd.kept_sides(sd.deal_for(deal_id))) == 2:
            return deal_id
    raise AssertionError("no deal with two 9-card fits in 500")


def _deal_with_no_side_kept():
    for deal_id in range(500):
        if not sd.kept_sides(sd.deal_for(deal_id)):
            return deal_id
    raise AssertionError("no unfiltered deal in 500")


def test_deals_are_reproducible_and_not_the_pilot_deals():
    assert ds.hands_to_text(sd.deal_for(5)) == ds.hands_to_text(sd.deal_for(5))
    assert ds.hands_to_text(sd.deal_for(5)) != ds.hands_to_text(sd.deal_for(6))
    pilot = {json.dumps(ds.hands_to_text(ds.deal_for(i))) for i in range(50)}
    assert not pilot & {json.dumps(ds.hands_to_text(sd.deal_for(i))) for i in range(50)}


def test_a_side_is_kept_exactly_when_it_holds_a_nine_card_fit():
    for deal_id in range(60):
        hands = sd.deal_for(deal_id)
        for side in ('N/S', 'E/W'):
            first, second = ds.SIDE_SEATS[side]
            longest = max(sum(1 for c in hands[first] + hands[second] if c.suit == s)
                          for s in 'SHDC')
            assert (side in sd.kept_sides(hands)) == (longest >= 9)


def test_unfiltered_deals_are_never_solved():
    def boom(*args):
        raise AssertionError("solved a deal the filter rejects")
    line = sd.process_deal(_deal_with_no_side_kept(), solve_one=boom, solve_strain=boom)
    assert line['kept_sides'] == [] and line['screen'] == [] and not line['finished']
    assert 'full' not in line


def test_screen_solves_the_two_best_fits_of_each_kept_side():
    deal_id = _deal_with_both_sides_kept()
    hands = sd.deal_for(deal_id)
    line = sd.process_deal(deal_id, solve_one=_fake_one({'N/S': 9, 'E/W': 8}),
                           solve_strain=_fake_strain({'N/S': 9, 'E/W': 8}))
    asked = [(r['declaring_side'], r['strain']) for r in line['screen']]
    expected = [(side, s) for side in ('N/S', 'E/W') for s in ds.ranked_fits(hands, side)[:2]]
    assert asked == expected
    assert not line['finished'] and 'full' not in line and 'hands' in line


def test_a_slam_in_the_screen_finishes_the_deal_in_every_strain():
    deal_id = _deal_with_both_sides_kept()
    tricks = {'N/S': 12, 'E/W': 1}
    line = sd.process_deal(deal_id, solve_one=_fake_one(tricks), solve_strain=_fake_strain(tricks))
    assert line['finished'] and line['slam_sides'] == ['N/S']
    assert [r['strain'] for r in line['full']] == list(sd.STRAINS)
    assert all(r['filter'] == sd.FILTER and r['deal_id'] == deal_id for r in line['full'])


def test_screen_and_full_solve_must_agree():
    deal_id = _deal_with_both_sides_kept()
    try:
        sd.process_deal(deal_id, solve_one=_fake_one({'N/S': 12, 'E/W': 1}),
                        solve_strain=_fake_strain({'N/S': 11, 'E/W': 2}))
    except RuntimeError:
        return
    raise AssertionError("a disagreement between screen and full solve went unnoticed")


def _fake_work(deal_id):
    """Every third deal is a slam."""
    line = {'deal_id': deal_id, 'kept_sides': ['N/S'], 'screen': [], 'finished': deal_id % 3 == 0}
    if line['finished']:
        line['full'] = [{'deal_id': deal_id, 'strain': s} for s in sd.STRAINS]
    return line


def _check_files(out, screen, slams):
    lines = [json.loads(t) for t in screen.read_text(encoding='utf-8').splitlines()]
    ids = [l['deal_id'] for l in lines]
    assert len(ids) == len(set(ids))
    finished = {l['deal_id'] for l in lines if l['finished']}
    assert len(finished) == slams
    full = [json.loads(t) for t in out.read_text(encoding='utf-8').splitlines()]
    assert {r['deal_id'] for r in full} == finished and len(full) == 5 * slams
    assert all('full' not in l for l in lines)


def test_run_stops_at_the_target_and_resumes_without_losing_or_repeating_a_deal():
    with tempfile.TemporaryDirectory() as tmp:
        out, screen = Path(tmp) / 'slam.jsonl', Path(tmp) / 'screen.jsonl'
        silent = lambda message: None
        assert sd.run(2, out, screen, workers=1, work=_fake_work, log=silent) == 2
        _check_files(out, screen, 2)
        assert sd.run(4, out, screen, workers=1, work=_fake_work, log=silent) == 4
        _check_files(out, screen, 4)
        assert sd.run(4, out, screen, workers=1, work=_fake_work, log=silent) == 4
        _check_files(out, screen, 4)


def test_run_works_through_a_process_pool():
    with tempfile.TemporaryDirectory() as tmp:
        out, screen = Path(tmp) / 'slam.jsonl', Path(tmp) / 'screen.jsonl'
        assert sd.run(3, out, screen, workers=2, work=_fake_work, log=lambda m: None) >= 3
        lines = [json.loads(t) for t in screen.read_text(encoding='utf-8').splitlines()]
        assert len({l['deal_id'] for l in lines}) == len(lines)
