"""The presolve's value cache and its slowest-first order.

A robot line's values depend only on the deal and its cards, so
`presolve_robot_lines.py` copies a line it finds in the cache instead of
solving it. These tests run the script's main() with the planner and the
solver replaced: a cached line is copied and never solved, a line that isn't
cached is solved and goes into the cache, lines start slowest first, and a
different solver version reuses nothing. No Rust binary is needed.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from research import presolve_robot_lines as pre

#: One real solved line (deal 1, 4H by West) whose values chain correctly.
_LINE = {
    'key': '66d2566554254556', 'deal_id': 1,
    'contract': {'level': 4, 'strain': 'H', 'declarer': 'West', 'leader': 'North', 'side': 'E/W',
                 'doubled': 'None'},
}


def _real_record() -> dict:
    for raw in (ROOT / 'research' / 'data' / 'robot_lines.jsonl').read_text(encoding='utf-8').splitlines():
        record = json.loads(raw)
        if record['key'] == _LINE['key']:
            return record
    raise AssertionError("deal 1's line is missing from robot_lines.jsonl")


def _planned(record: dict, key: str, deal_id: int, strain: str = 'H') -> dict:
    line = {k: record[k] for k in ('hands', 'plays', 'ns_tricks')}
    contract = dict(record['contract'], strain=strain)
    return {**line, 'key': key, 'deal_id': deal_id, 'contract': contract, 'boards': record['boards']}


class _Patched:
    """main() with plan, solve and the binary check replaced."""

    def __init__(self, lines, solved_order):
        self.lines, self.order = lines, solved_order

    def __enter__(self):
        self.saved = (pre.plan, pre.solve, pre.LINE_EXE, pre.challenge.deal_ids)
        record = _real_record()

        def fake_solve(line):
            self.order.append(line['key'])
            return {**line, 'decisions': record['decisions'], 'seconds': 1.0, 'nodes': 1,
                    'table_entries': 1, 'robot_version': pre.robot_version(),
                    'solver_version': pre.solver_version()}

        pre.plan = lambda deal_ids: self.lines
        pre.solve = fake_solve
        pre.LINE_EXE = Path(__file__)          # exists
        pre.challenge.deal_ids = lambda: [1]
        return self

    def __exit__(self, *exc):
        pre.plan, pre.solve, pre.LINE_EXE, pre.challenge.deal_ids = self.saved


def _read(path: Path):
    return [json.loads(raw) for raw in path.read_text(encoding='utf-8').splitlines() if raw.strip()]


def test_cached_line_is_copied_not_solved():
    record = _real_record()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache, out = tmp / 'cache.jsonl', tmp / 'out.jsonl'
        cache.write_text(json.dumps(pre.cache_entry(record, pre.solver_version())) + '\n', encoding='utf-8')
        order = []
        with _Patched([_planned(record, record['key'], 1)], order):
            assert pre.main(['--workers', '1', '--out', str(out), '--cache', str(cache)]) == 0
        assert order == [], "a cached line was solved again"
        [copied] = _read(out)
        assert copied['decisions'] == record['decisions'] and copied['reused'] is True
        assert copied['robot_version'] == pre.robot_version()
        assert len(_read(cache)) == 1


def test_other_solver_version_reuses_nothing():
    record = _real_record()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache, out = tmp / 'cache.jsonl', tmp / 'out.jsonl'
        cache.write_text(json.dumps(pre.cache_entry(record, 'not-this-one')) + '\n', encoding='utf-8')
        order = []
        with _Patched([_planned(record, record['key'], 1)], order):
            pre.main(['--workers', '1', '--out', str(out), '--cache', str(cache)])
        assert order == [record['key']]
        assert [r['solver_version'] for r in _read(cache)] == ['not-this-one', pre.solver_version()]


def test_key_match_with_other_cards_is_solved():
    """A key is a short hash: the cache also compares the deal and the cards."""
    record = _real_record()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache, out = tmp / 'cache.jsonl', tmp / 'out.jsonl'
        entry = dict(pre.cache_entry(record, pre.solver_version()), plays=list(reversed(record['plays'])))
        cache.write_text(json.dumps(entry) + '\n', encoding='utf-8')
        order = []
        with _Patched([_planned(record, record['key'], 1)], order):
            pre.main(['--workers', '1', '--out', str(out), '--cache', str(cache)])
        assert order == [record['key']]


def test_slowest_first_and_unknown_deals_first():
    record = _real_record()
    solver = pre.solver_version()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache, out = tmp / 'cache.jsonl', tmp / 'out.jsonl'
        # Stored times: deal 2 in hearts 900 s, deal 3 10 s, deal 4 only in spades, 50 s.
        stored = []
        for key, deal_id, strain, seconds in (('old2', 2, 'H', 900.0), ('old3', 3, 'H', 10.0),
                                              ('old4', 4, 'S', 50.0)):
            solved = {**_planned(record, key, deal_id, strain), 'decisions': [], 'seconds': 0.0,
                      'nodes': 0, 'table_entries': 0}
            stored.append(dict(pre.cache_entry(solved, solver),
                               seconds=seconds, plays=['x']))   # never a hit
        cache.write_text(''.join(json.dumps(e) + '\n' for e in stored), encoding='utf-8')
        lines = [_planned(record, 'new3', 3), _planned(record, 'new4', 4), _planned(record, 'new2', 2),
                 _planned(record, 'new9', 9)]
        order = []
        with _Patched(lines, order):
            pre.main(['--workers', '1', '--out', str(out), '--cache', str(cache)])
        # Deal 9 was never solved: it may be the slowest, so it starts first. Deal 4
        # has no hearts line and falls back to the deal's slowest line.
        assert order == ['new9', 'new2', 'new4', 'new3'], order


def test_rerun_skips_lines_done_for_this_version():
    record = _real_record()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache, out = tmp / 'cache.jsonl', tmp / 'out.jsonl'
        order = []
        with _Patched([_planned(record, record['key'], 1)], order):
            pre.main(['--workers', '1', '--out', str(out), '--cache', str(cache)])
            pre.main(['--workers', '1', '--out', str(out), '--cache', str(cache)])
        assert order == [record['key']] and len(_read(out)) == 1


def test_no_cache_neither_reads_nor_writes():
    record = _real_record()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache, out = tmp / 'cache.jsonl', tmp / 'out.jsonl'
        cache.write_text(json.dumps(pre.cache_entry(record, pre.solver_version())) + '\n', encoding='utf-8')
        order = []
        with _Patched([_planned(record, record['key'], 1)], order):
            pre.main(['--workers', '1', '--out', str(out), '--cache', str(cache), '--no-cache'])
        assert order == [record['key']] and len(_read(cache)) == 1


def test_adopt_takes_old_outputs_once():
    record = _real_record()
    old = {k: v for k, v in record.items() if k != 'solver_version'}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cache, source = tmp / 'cache.jsonl', tmp / 'old.jsonl'
        source.write_text(json.dumps(old) + '\n', encoding='utf-8')
        pre.main(['--adopt', str(source), '--cache', str(cache)])
        pre.main(['--adopt', str(source), '--cache', str(cache)])
        [entry] = _read(cache)
        assert entry['decisions'] == record['decisions'] and entry['solver_version'] == pre.solver_version()


def test_committed_cache_values_chain():
    """Every line in the committed cache passes the solver's own check."""
    path = pre.DEFAULT_CACHE
    entries = pre.read_jsonl(path)
    assert entries, f"{path} is empty"
    for entry in entries:
        assert set(entry) >= {'key', 'deal_id', 'hands', 'plays', 'strain', 'leader', 'decisions',
                              'solver_version'}
        decisions = entry['decisions']
        for i in range(len(decisions) - 1):
            values = [v for _, v in decisions[i + 1]['values']]
            best = max(values) if decisions[i + 1]['seat'] in ('North', 'South') else min(values)
            assert dict(decisions[i]['values'])[decisions[i]['played']] == best, entry['key']


def test_versions_ignore_line_endings():
    data = b'a = 1\r\nb = 2\r\n'
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'x.py'
        path.write_bytes(data)
        assert pre._source_bytes(path) == b'a = 1\nb = 2\n'
