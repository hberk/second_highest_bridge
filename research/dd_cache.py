"""Double dummy results, solved once and kept for every research script.

A full deal's opening-lead value (N/S's tricks with perfect play, for one strain
and one opening leader) is the same whichever script asks for it, so it is
stored once, here, keyed by the cards: `research/data/dd_cache.jsonl`. A line
holds one deal's answers, N/S's tricks by strain and opening leader (North,
East, South, West, null when not solved); a deal can have several lines, which
add up. About 170 bytes a deal. `solve_leads` answers what the cache knows and
sends only the rest to the Rust engine, in one call, so the leaders still
share a transposition table.

Only values are cached, never nodes or times: those depend on what else shared
the table. A cached answer comes back with `nodes` None.

The cache is valid for one set of rules. Its first line records a hash of the
frozen solver fixture's answers (`tests/fixtures/endings.json`), which changes
exactly when the rules do; a cache from other rules is refused, not used.

    python research/dd_cache.py --seed       # import every deal already solved
    python research/dd_cache.py --seed --from path/to/other.jsonl
    python research/dd_cache.py              # what the cache holds

Records are appended under a file lock and fsynced, so several workers can add
to it at once. A line cut off by a hard kill is ignored and repaired. Two
answers for the same question that disagree stop everything: that is a solver
bug or a rules change, never something to paper over.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.solver.convert import text_to_mask  # noqa: E402

CACHE = ROOT / 'research' / 'data' / 'dd_cache.jsonl'
FIXTURE = ROOT / 'tests' / 'fixtures' / 'endings.json'
DATA = ROOT / 'research' / 'data'

SEATS = ('North', 'East', 'South', 'West')
STRAINS = ('C', 'D', 'H', 'S', 'NT')
SIDE_OF = {'North': 'N/S', 'South': 'N/S', 'East': 'E/W', 'West': 'E/W'}

Question = Tuple[str, str, str]           # (deal key, strain, leader)


def rules_version() -> str:
    """A hash of the fixture's answers: it moves exactly when the rules do."""
    positions = json.loads(FIXTURE.read_text(encoding='utf-8'))['positions']
    answers = json.dumps([[p['id'], p['ns_tricks']] for p in positions])
    return hashlib.sha256(answers.encode()).hexdigest()[:16]


def deal_key(hands: Dict[str, str]) -> str:
    """52 letters, one per card (clubs 2 to spades A), naming the seat that
    holds it. Full deals only: a position part-way through a hand is not cached."""
    owner = ['?'] * 52
    for seat in SEATS:
        mask = text_to_mask(hands[seat])
        if bin(mask).count('1') != 13:
            raise ValueError(f"{seat} holds {bin(mask).count('1')} cards; only full deals are cached")
        for index in range(52):
            if mask >> index & 1:
                if owner[index] != '?':
                    raise ValueError(f"card {index} is dealt twice")
                owner[index] = seat[0]
    return ''.join(owner)


def leader_of(declarer: str) -> str:
    """The opening lead comes from declarer's left."""
    return SEATS[(SEATS.index(declarer) + 1) % 4]


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """An exclusive lock on a side file, held while appending."""
    lock = path.with_suffix(path.suffix + '.lock')
    with lock.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:      # LK_LOCK gives up after ten seconds; keep waiting
                    continue
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class DDCache:
    """Opening-lead values by (deal, strain, leader), backed by a JSON Lines file."""

    def __init__(self, path: Path = CACHE):
        self.path = Path(path)
        self.rules = rules_version()
        self.known: Dict[Question, int] = {}
        self._read_to = 0
        self._refresh()

    def _refresh(self) -> None:
        """Read whatever other processes appended since the last read."""
        if not self.path.exists():
            return
        with self.path.open('rb') as handle:
            handle.seek(self._read_to)
            data = handle.read()
        end = data.rfind(b'\n') + 1
        for number, raw in enumerate(data[:end].splitlines()):
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue                  # a line cut off by a kill, since repaired
            if 'rules' in record:
                if record['rules'] != self.rules:
                    raise RuntimeError(
                        f"{self.path} was solved under other rules ({record['rules']}, "
                        f"now {self.rules}): move it aside, don't mix them")
                continue
            for strain, by_leader in record['ns'].items():
                for leader, ns in zip(SEATS, by_leader):
                    if ns is not None:
                        self._learn((record['deal'], strain, leader), ns)
        self._read_to += end

    def _learn(self, question: Question, ns: int) -> bool:
        """Remember an answer; True if it is new. A different answer is a bug."""
        known = self.known.get(question)
        if known is None:
            self.known[question] = ns
            return True
        if known != ns:
            raise RuntimeError(f"double dummy answers disagree on {question}: {known} and {ns}")
        return False

    def get(self, hands: Dict[str, str], strain: str, leader: str) -> Optional[int]:
        return self.known.get((deal_key(hands), strain, leader))

    def add(self, answers: Iterable[Tuple[Dict[str, str], str, str, int]]) -> int:
        """Store (hands, strain, leader, N/S tricks) answers; returns how many were new."""
        new: Dict[str, Dict[str, List[Optional[int]]]] = {}
        with _locked(self.path):
            self._refresh()
            fresh = not self.path.exists() or self.path.stat().st_size == 0
            for hands, strain, leader, ns in answers:
                if strain not in STRAINS or leader not in SEATS or not 0 <= ns <= 13:
                    raise ValueError(f"not a full-deal answer: {strain} {leader} {ns}")
                key = deal_key(hands)
                if self._learn((key, strain, leader), ns):
                    by_strain = new.setdefault(key, {})
                    by_strain.setdefault(strain, [None] * 4)[SEATS.index(leader)] = ns
            lines = [json.dumps({'deal': key, 'ns': {s: by_strain[s] for s in STRAINS if s in by_strain}},
                                separators=(',', ':'))
                     for key, by_strain in new.items()]
            if not lines:
                return 0
            if fresh:
                lines.insert(0, json.dumps({'rules': self.rules}))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('ab') as sink:
                if sink.tell() > 0:
                    with self.path.open('rb') as check:
                        check.seek(-1, os.SEEK_END)
                        if check.read(1) != b'\n':
                            sink.write(b'\n')
                sink.write(('\n'.join(lines) + '\n').encode())
                sink.flush()
                os.fsync(sink.fileno())
                self._read_to = sink.tell()
        return sum(ns is not None for by_strain in new.values()
                   for by_leader in by_strain.values() for ns in by_leader)


_shared: Dict[Path, DDCache] = {}


def shared(path: Path = CACHE) -> DDCache:
    """One cache per process and file, read once and topped up on each write."""
    path = Path(path)
    if path not in _shared:
        _shared[path] = DDCache(path)
    return _shared[path]


def solve_leads(hands: Dict[str, str], strain: str, leaders: Sequence[str],
                cache: Optional[DDCache] = None, use_cache: bool = True) -> dict:
    """N/S's tricks from the opening lead for each leader, cached ones first.

    Returns `results`, one dict per leader in order (`ns_tricks`, and `nodes`,
    None when it came from the cache), `seconds` the engine ran and its
    `table_entries` (None when nothing was solved). The leaders the cache
    doesn't know go to the Rust engine in one call, sharing one table, and
    their answers are stored. `cache=None` uses the shared cache;
    `use_cache=False` neither reads nor writes one (and allows part-played
    hands, which are never cached).
    """
    from research.dd_dataset import RUST_EXE, RUST_TIMEOUT_SECONDS
    if use_cache and cache is None:
        cache = shared()
    results: List[Optional[dict]] = []
    missing: List[str] = []
    for leader in leaders:
        ns = cache.get(hands, strain, leader) if use_cache else None
        results.append(None if ns is None else {'ns_tricks': ns, 'nodes': None})
        if ns is None and leader not in missing:
            missing.append(leader)
    if not missing:
        return {'results': results, 'seconds': 0.0, 'table_entries': None}

    if not RUST_EXE.exists():
        raise FileNotFoundError(f"Rust engine not built at {RUST_EXE}. Run `cargo build --release` "
                                f"in research/solver-rs/ first.")
    payload = {'hands': hands, 'strain': strain,
               'queries': [{'leader': leader, 'trick': []} for leader in missing]}
    started = time.perf_counter()
    proc = subprocess.run([str(RUST_EXE)], input=json.dumps(payload), capture_output=True,
                          text=True, timeout=RUST_TIMEOUT_SECONDS)
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        raise RuntimeError(f"Rust engine failed on strain {strain}: {proc.stderr.strip()}")
    out = json.loads(proc.stdout)
    solved = dict(zip(missing, out['results']))
    if use_cache:
        cache.add((hands, strain, leader, raw['ns_tricks']) for leader, raw in solved.items())
    return {
        'results': [r if r is not None else {'ns_tricks': solved[leader]['ns_tricks'],
                                             'nodes': solved[leader]['nodes']}
                    for leader, r in zip(leaders, results)],
        'seconds': elapsed,
        'table_entries': out['table_entries'],
    }


# ── Seeding from what was already solved ────────────────────────────────────

def answers_in(record: dict, library: Dict[int, Dict[str, str]]) -> Iterator[Tuple[Dict[str, str], str, str, int]]:
    """Every opening-lead answer in one stored record, whichever script wrote it."""
    if 'deals' in record:                                   # data/solved_deals.json
        for deal in record['deals']:
            yield from answers_in(deal, library)
        return
    hands = record.get('hands')
    if hands is None and 'id' in record and 'strain' in record:   # declarer_tricks.jsonl
        hands = library[record['id']]
    if hands is None:
        return
    if 'results' in record:                                 # dd_dataset / slam full solves
        for r in record['results']:
            yield hands, record['strain'], r['leader'], r['ns_tricks']
    for r in record.get('screen', []):                      # slam screen
        ns = r['declarer_tricks'] if r['declaring_side'] == 'N/S' else 13 - r['declarer_tricks']
        yield hands, r['strain'], r['leader'], ns
    for f in record.get('full', []):
        yield from answers_in(f, library)
    tricks = record.get('tricks', {})
    if 'strain' in record:                                  # {declarer: declarer's tricks}
        for declarer, got in tricks.items():
            ns = got if SIDE_OF[declarer] == 'N/S' else 13 - got
            yield hands, record['strain'], leader_of(declarer), ns
        return
    for name, got in tricks.items():                        # 'S:North' or 'S:N/S'
        strain, who = name.split(':')
        if who in SIDE_OF:
            declarer = who
        else:
            from research.dd_dataset import declarer_for, hands_from_text
            declarer = declarer_for(hands_from_text(hands), who, strain)
        ns = got if SIDE_OF[declarer] == 'N/S' else 13 - got
        yield hands, strain, leader_of(declarer), ns


def default_sources() -> List[Path]:
    return [ROOT / 'data' / 'solved_deals.json', DATA / 'declarer_tricks.jsonl',
            DATA / 'dd_pilot.jsonl', DATA / 'dd_slam.jsonl', DATA / 'dd_slam_screen.jsonl']


def seed(sources: Sequence[Path], cache: DDCache, log=print) -> int:
    library = {d['id']: d['hands'] for d in
               json.loads((ROOT / 'data' / 'solved_deals.json').read_text(encoding='utf-8'))['deals']}
    total = 0
    for source in sources:
        text = source.read_text(encoding='utf-8')
        if source.suffix == '.json':
            records = [json.loads(text)]
        else:
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        answers = [a for record in records for a in answers_in(record, library)]
        added = cache.add(answers)
        total += added
        log(f"{source.name}: {len(answers)} answers, {added} new")
    return total


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--seed', action='store_true', help='import the deals already solved')
    parser.add_argument('--from', dest='sources', type=Path, action='append',
                        help='import this file instead of the default sources')
    parser.add_argument('--cache', type=Path, default=CACHE)
    args = parser.parse_args(argv)
    cache = DDCache(args.cache)
    if args.seed:
        seed(args.sources or default_sources(), cache)
    deals = {key for key, _, _ in cache.known}
    full = sum(1 for key in deals
               if all((key, s, l) in cache.known for s in STRAINS for l in SEATS))
    print(f"{args.cache}: {len(cache.known)} answers over {len(deals)} deals, "
          f"{full} solved for every strain and leader (rules {cache.rules})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
