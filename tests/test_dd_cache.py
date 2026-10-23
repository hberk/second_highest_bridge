"""The shared double dummy cache (research/dd_cache.py).

A cache that returned a wrong answer would corrupt every measurement built on
it, silently. So these check what could do that: that a deal's key names every
card's holder, that two answers which disagree stop everything, that a cache
from other rules is refused, that a line cut off by a kill or appended by
another process is handled, that every stored record format seeds the same
answers, and that the committed cache agrees with the challenge library.

No solver runs here; `test_solver_rust.py` re-solves cached deals with the engine.
"""
from __future__ import annotations
import json
import multiprocessing
import sys
import tempfile
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from research import dd_cache as dc
from research import dd_dataset as ds


def _hands(deal_id: int = 0) -> dict:
    return ds.hands_to_text(ds.deal_for(deal_id))


def _temp_cache(directory: str) -> dc.DDCache:
    return dc.DDCache(Path(directory) / 'cache.jsonl')


def test_a_deal_key_names_the_holder_of_every_card():
    hands = _hands()
    key = dc.deal_key(hands)
    assert len(key) == 52 and sorted(set(key)) == ['E', 'N', 'S', 'W']
    assert all(key.count(seat[0]) == 13 for seat in dc.SEATS)
    assert dc.deal_key(_hands(1)) != key
    swapped = dict(hands, North=hands['South'], South=hands['North'])
    assert dc.deal_key(swapped) == key.translate(str.maketrans('NS', 'SN'))


def test_only_full_deals_are_keyed():
    hands = _hands()
    short = dict(hands, North=' '.join(hands['North'].split()[1:]))
    try:
        dc.deal_key(short)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_answers_round_trip_through_the_file():
    with tempfile.TemporaryDirectory() as tmp:
        cache = _temp_cache(tmp)
        hands = _hands()
        assert cache.get(hands, 'S', 'East') is None
        assert cache.add([(hands, 'S', 'East', 9), (hands, 'NT', 'North', 4)]) == 2
        assert cache.add([(hands, 'S', 'East', 9)]) == 0          # known: nothing written
        reread = _temp_cache(tmp)
        assert reread.get(hands, 'S', 'East') == 9
        assert reread.get(hands, 'NT', 'North') == 4
        assert reread.get(hands, 'S', 'West') is None
        lines = (Path(tmp) / 'cache.jsonl').read_text().splitlines()
        assert json.loads(lines[0]) == {'rules': dc.rules_version()}
        assert len(lines) == 2                                     # one line for the deal


def test_two_answers_that_disagree_stop_everything():
    with tempfile.TemporaryDirectory() as tmp:
        cache = _temp_cache(tmp)
        cache.add([(_hands(), 'H', 'South', 7)])
        for fresh in (cache, _temp_cache(tmp)):
            try:
                fresh.add([(_hands(), 'H', 'South', 8)])
                raise AssertionError("expected RuntimeError")
            except RuntimeError as error:
                assert 'disagree' in str(error)


def test_a_cache_from_other_rules_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'cache.jsonl'
        path.write_text(json.dumps({'rules': 'not-these-rules'}) + '\n')
        try:
            dc.DDCache(path)
            raise AssertionError("expected RuntimeError")
        except RuntimeError as error:
            assert 'other rules' in str(error)


def test_a_line_cut_off_by_a_kill_is_ignored_and_repaired():
    with tempfile.TemporaryDirectory() as tmp:
        cache = _temp_cache(tmp)
        cache.add([(_hands(0), 'C', 'North', 6)])
        path = Path(tmp) / 'cache.jsonl'
        with path.open('a') as sink:
            sink.write('{"deal":"NNNN')                            # no newline: killed
        reread = _temp_cache(tmp)
        assert reread.get(_hands(0), 'C', 'North') == 6
        reread.add([(_hands(1), 'C', 'North', 5)])
        again = _temp_cache(tmp)
        assert again.get(_hands(1), 'C', 'North') == 5
        assert again.get(_hands(0), 'C', 'North') == 6


def _add_from_another_process(args):
    path, deal_id, ns = args
    dc.DDCache(Path(path)).add([(_hands(deal_id), 'D', 'West', ns)])
    return deal_id


def test_processes_appending_at_once_lose_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / 'cache.jsonl')
        jobs = [(path, deal_id, deal_id % 14) for deal_id in range(24)]
        with multiprocessing.Pool(4) as pool:
            assert sorted(pool.map(_add_from_another_process, jobs)) == list(range(24))
        cache = dc.DDCache(Path(path))
        for _, deal_id, ns in jobs:
            assert cache.get(_hands(deal_id), 'D', 'West') == ns
        rules_lines = [line for line in Path(path).read_text().splitlines() if '"rules"' in line]
        assert len(rules_lines) == 1


def test_a_cache_sees_what_another_process_added_before_it_writes():
    with tempfile.TemporaryDirectory() as tmp:
        first, second = _temp_cache(tmp), _temp_cache(tmp)
        first.add([(_hands(), 'S', 'North', 3)])
        assert second.add([(_hands(), 'S', 'North', 3)]) == 0
        try:
            second.add([(_hands(), 'S', 'North', 4)])
            raise AssertionError("expected RuntimeError")
        except RuntimeError:
            pass


def test_every_record_format_gives_the_same_answers():
    """One deal, one strain, stored the way each script stores it."""
    hands = _hands(3)
    declarer = ds.declarer_for(ds.hands_from_text(hands), 'N/S', 'S')
    other = ds.declarer_for(ds.hands_from_text(hands), 'E/W', 'S')
    ns_by_leader = {dc.leader_of(declarer): 8, dc.leader_of(other): 6}
    formats = [
        {'hands': hands, 'strain': 'S', 'results': [
            {'leader': dc.leader_of(declarer), 'ns_tricks': 8},
            {'leader': dc.leader_of(other), 'ns_tricks': 6}]},
        {'hands': hands, 'screen': [
            {'strain': 'S', 'declaring_side': 'N/S', 'leader': dc.leader_of(declarer), 'declarer_tricks': 8},
            {'strain': 'S', 'declaring_side': 'E/W', 'leader': dc.leader_of(other), 'declarer_tricks': 7}]},
        {'hands': hands, 'tricks': {'S:N/S': 8, 'S:E/W': 7}},
        {'hands': hands, 'tricks': {f'S:{declarer}': 8, f'S:{other}': 7}},
        {'id': 3, 'strain': 'S', 'tricks': {declarer: 8, other: 7}},
    ]
    for record in formats:
        found = {leader: ns for _, strain, leader, ns in dc.answers_in(record, {3: hands})}
        assert found == ns_by_leader, record


def test_a_cached_answer_never_starts_the_engine():
    real = ds.RUST_EXE
    with tempfile.TemporaryDirectory() as tmp:
        cache = _temp_cache(tmp)
        cache.add([(_hands(), 'NT', 'East', 5), (_hands(), 'NT', 'West', 6)])
        try:
            ds.RUST_EXE = Path(tmp) / 'no-engine-here'
            solved = dc.solve_leads(_hands(), 'NT', ['West', 'East'], cache)
            assert solved['results'] == [{'ns_tricks': 6, 'nodes': None},
                                         {'ns_tricks': 5, 'nodes': None}]
            assert solved['seconds'] == 0.0
            try:
                dc.solve_leads(_hands(), 'NT', ['North'], cache)
                raise AssertionError("expected FileNotFoundError")
            except FileNotFoundError:
                pass
        finally:
            ds.RUST_EXE = real


def test_the_committed_cache_agrees_with_the_challenge_library():
    if not dc.CACHE.exists():
        return
    cache = dc.DDCache(dc.CACHE)
    library = json.loads((root_dir / 'data' / 'solved_deals.json').read_text(encoding='utf-8'))
    checked = 0
    for hands, strain, leader, ns in dc.answers_in(library, {}):
        assert cache.get(hands, strain, leader) == ns, (strain, leader)
        checked += 1
    assert checked == 400 * 20


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
