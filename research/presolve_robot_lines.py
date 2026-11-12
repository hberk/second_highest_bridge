"""Presolve the robot table's play on every challenge deal, card by card.

For each of the 400 deals in data/solved_deals.json, the robot table is run at
all 16 board positions (dealer and vulnerability come from the board number,
and the robots bid differently on them). Identical lines are solved once. For
every decision of every distinct line, the Rust `line_values` binary scores
every legal card: N/S's tricks for the hand if that card is played and the
play is perfect after it. That's BBO's double dummy display, ready to ship,
and it shows exactly where the robots give tricks away.

Records go to research/data/robot_lines.jsonl, one per distinct line, appended
and fsynced as they finish. Rerunning skips lines already done, so a stopped
run just resumes. Slow lines are never skipped or timed out: that would bias
any summary towards easy deals.

Every record carries `robot_version`, a hash of the code that decides the
robots' play. A change to ai.py or gib.py changes the robots' lines, so rerun
after any such change: --out keeps one version's lines at a time.

A line's values depend only on the deal and its cards, never on the code that
chose them. So every solved line also goes into a shared value cache
(research/data/robot_line_values.jsonl, committed), and a line found there,
from any robot version, is copied rather than solved again. A robot change
that alters a few dozen lines only solves those. The cache is tied to a hash
of the Rust solver's source (`solver_version`); change the solver and nothing
in it is reused. A copied line is checked like a solved one (`check`).

Lines still to solve start slowest first, by the solve times stored for the
same deal and contract, so one slow deal doesn't run alone at the end while
the other workers sit idle.

    python research/presolve_robot_lines.py --deals 10       # first 10 deals
    python research/presolve_robot_lines.py                  # all 400
    python research/presolve_robot_lines.py --no-cache       # solve every line afresh

Build the binary first: `cargo build --release` in research/solver-rs/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
import time
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import challenge
from bridge.solver.convert import card_to_index, cards_to_mask, index_to_text, mask_to_text
from game import DEALER_ROTATION, VUL_ROTATION
from research.dd_dataset import free_memory_gb

LINE_EXE = ROOT / 'research' / 'solver-rs' / 'target' / 'release' / (
    'line_values.exe' if os.name == 'nt' else 'line_values')
DEFAULT_OUT = ROOT / 'research' / 'data' / 'robot_lines.jsonl'
DEFAULT_CACHE = ROOT / 'research' / 'data' / 'robot_line_values.jsonl'
SOLVER_SOURCES = ROOT / 'research' / 'solver-rs' / 'src'

#: Files whose code decides what the robot table bids and plays.
ROBOT_SOURCES = ('ai.py', 'gib.py', 'game.py', 'card.py', 'challenge.py',
                 'bridge/trick.py', 'bridge/auction.py')

#: Memory per worker. Before the solver's table was capped, deal 197 (2NT by
#: South) grew one process to 8.9 GB and two at once swapped the machine
#: (2026-10-18). `MAX_TABLE_ENTRIES` in research/solver-rs/src/search.rs now
#: holds a process to about 2.4 GB at worst (3.1 GB measured on that deal
#: under the earlier, 50M-entry cap).
GB_PER_WORKER = 4.0

BOARDS = 16


def _source_bytes(path: Path) -> bytes:
    # Line endings normalised: a Windows checkout (CRLF) and a Linux one hash alike.
    return path.read_bytes().replace(b'\r\n', b'\n')


def robot_version() -> str:
    digest = hashlib.sha256()
    for name in ROBOT_SOURCES:
        digest.update(name.encode())
        digest.update(_source_bytes(ROOT / name))
    return digest.hexdigest()[:12]


def solver_version() -> str:
    """A hash of the Rust solver's source: the cache's values are only reused
    under the solver that computed them."""
    digest = hashlib.sha256()
    for path in sorted(SOLVER_SOURCES.rglob('*.rs')):
        digest.update(path.relative_to(SOLVER_SOURCES).as_posix().encode())
        digest.update(_source_bytes(path))
    return digest.hexdigest()[:12]


def text(card) -> str:
    return index_to_text(card_to_index(card))


def plan(deal_ids: Sequence[int]) -> List[dict]:
    """Every distinct robot line on these deals, with the boards that give it."""
    lines: Dict[str, dict] = {}
    for deal_id in deal_ids:
        hands = challenge.hands_for(deal_id)
        for board in range(1, BOARDS + 1):
            dealer = DEALER_ROTATION[(board - 1) % 4]
            vulnerability = VUL_ROTATION[(board - 1) % 16]
            table = challenge.robot_table(deal_id, dealer, vulnerability)
            contract = table['contract']
            if contract is None:
                continue
            plays = [text(card) for trick in table['tricks_log'] for _, card in trick['plays']]
            key = hashlib.sha256(json.dumps(
                [deal_id, contract['strain'], contract['leader'], plays]).encode()).hexdigest()[:16]
            line = lines.setdefault(key, {
                'key': key,
                'deal_id': deal_id,
                'contract': {k: contract[k] for k in ('level', 'strain', 'declarer', 'leader', 'side', 'doubled')},
                'ns_tricks': table['ns_tricks'],
                'hands': {seat: mask_to_text(cards_to_mask(cards)) for seat, cards in hands.items()},
                'plays': plays,
                'boards': [],
            })
            line['boards'].append({'board': board, 'dealer': dealer, 'vulnerability': vulnerability})
    return list(lines.values())


#: What a line's values depend on, and all the cache keeps beside them.
POSITION = ('deal_id', 'hands', 'plays')
VALUES = ('decisions', 'seconds', 'nodes', 'table_entries')


def same_position(line: dict, cached: dict) -> bool:
    return (all(line[k] == cached[k] for k in POSITION)
            and line['contract']['strain'] == cached['strain']
            and line['contract']['leader'] == cached['leader'])


def read_jsonl(path: Path) -> List[dict]:
    records = []
    if path.exists():
        for raw in path.read_text(encoding='utf-8').splitlines():
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError:
                continue   # a line cut off by a hard kill
    return records


def load_cache(path: Path, solver: str) -> Dict[str, dict]:
    """The cache's lines solved by this solver, by key."""
    return {r['key']: r for r in read_jsonl(path) if r.get('solver_version') == solver}


def cache_entry(record: dict, solver: str) -> dict:
    return {'key': record['key'], **{k: record[k] for k in POSITION},
            'strain': record['contract']['strain'], 'leader': record['contract']['leader'],
            **{k: record[k] for k in VALUES}, 'solver_version': solver}


def append_line(handle, record: dict) -> None:
    # One write per line, so two runs sharing the cache don't interleave mid-line.
    handle.write(json.dumps(record) + '\n')
    handle.flush()
    os.fsync(handle.fileno())


def end_with_newline(path: Path) -> None:
    if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b'\n'):
        with path.open('ab') as handle:
            handle.write(b'\n')


def estimate(line: dict, timings: Dict[Tuple, float]) -> float:
    """Expected solve time: the slowest stored line with the same deal and
    contract, else the same deal; a deal never solved counts as slowest."""
    c = line['contract']
    for k in ((line['deal_id'], c['strain'], c['leader']), (line['deal_id'],)):
        if k in timings:
            return timings[k]
    return float('inf')


def timings_from(records) -> Dict[Tuple, float]:
    out: Dict[Tuple, float] = {}
    for r in records:
        strain = r['strain'] if 'strain' in r else r['contract']['strain']
        leader = r['leader'] if 'leader' in r else r['contract']['leader']
        for k in ((r['deal_id'], strain, leader), (r['deal_id'],)):
            out[k] = max(out.get(k, 0.0), r['seconds'])
    return out


def solve(line: dict) -> dict:
    """Run line_values on one line and check what comes back."""
    payload = {'hands': line['hands'], 'strain': line['contract']['strain'],
               'leader': line['contract']['leader'], 'plays': line['plays']}
    proc = subprocess.run([str(LINE_EXE)], input=json.dumps(payload),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"line_values failed on deal {line['deal_id']}: {proc.stderr.strip()}")
    out = json.loads(proc.stdout)
    check(line, out['decisions'])
    return {**line, 'decisions': out['decisions'], 'seconds': out['seconds'],
            'nodes': out['nodes'], 'table_entries': out['table_entries'],
            'robot_version': robot_version(), 'solver_version': solver_version()}


def reuse(line: dict, cached: dict, version: str, solver: str) -> dict:
    """A line already solved, under another robot version or another run."""
    record = {**line, **{k: cached[k] for k in VALUES}, 'reused': True,
              'robot_version': version, 'solver_version': solver}
    check(line, record['decisions'])
    return record


def check(line: dict, decisions: List[dict]) -> None:
    """Values must chain: the card played at one decision is worth exactly the
    best available at the next, and the last card played is worth what the
    robots actually took. A break means a bug in the solver or this wiring."""
    def best(decision: dict) -> int:
        values = [v for _, v in decision['values']]
        return max(values) if decision['seat'] in ('North', 'South') else min(values)

    def played_value(decision: dict) -> int:
        return dict(decision['values'])[decision['played']]

    if len(decisions) != len(line['plays']):
        raise AssertionError(f"deal {line['deal_id']}: {len(decisions)} decisions for {len(line['plays'])} plays")
    for i in range(len(decisions) - 1):
        if played_value(decisions[i]) != best(decisions[i + 1]):
            raise AssertionError(f"deal {line['deal_id']} line {line['key']}: value chain breaks at card {i + 1}")
    if played_value(decisions[-1]) != line['ns_tricks']:
        raise AssertionError(f"deal {line['deal_id']} line {line['key']}: last card worth "
                             f"{played_value(decisions[-1])}, robots took {line['ns_tricks']}")


def completed(records: List[dict], version: str) -> set:
    return {r['key'] for r in records if r.get('robot_version') == version}


def safe_workers() -> int:
    by_cpu = max(1, (os.cpu_count() or 2) - 2)
    free = free_memory_gb()
    if free is None:
        return 1
    return max(1, min(by_cpu, int(free * 0.8 / GB_PER_WORKER)))


def adopt(paths: Sequence[Path], cache_path: Path) -> int:
    solver = solver_version()
    cache = load_cache(cache_path, solver)
    added = 0
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    end_with_newline(cache_path)
    with cache_path.open('a', encoding='utf-8') as store:
        for path in paths:
            for record in read_jsonl(path):
                if record.get('solver_version', solver) != solver or record['key'] in cache:
                    continue
                check(record, record['decisions'])
                entry = cache_entry(record, solver)
                append_line(store, entry)
                cache[record['key']] = entry
                added += 1
    print(f"{added} lines added; the cache holds {len(cache)} under solver {solver}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--deals', type=int, default=None, help="first N deals (default: all)")
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--workers', type=int, default=None, help="default: what free memory allows")
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE,
                        help="solved values shared across robot versions (read, and appended to)")
    parser.add_argument('--no-cache', action='store_true',
                        help="solve every line afresh: no values copied from the cache or added to it "
                             "(its solve times still order the work)")
    parser.add_argument('--adopt', type=Path, nargs='+', default=None, metavar='JSONL',
                        help="add the lines in these presolve outputs to the cache, then stop. Lines "
                             "written before the cache existed carry no solver version and are taken "
                             "as this solver's (the solver hasn't changed since 2026-10-22)")
    args = parser.parse_args(argv)

    if args.adopt:
        return adopt(args.adopt, args.cache)

    if not LINE_EXE.exists():
        print(f"{LINE_EXE} is missing: run `cargo build --release` in research/solver-rs/")
        return 1

    deal_ids = challenge.deal_ids()[:args.deals] if args.deals else challenge.deal_ids()
    version = robot_version()
    started = time.perf_counter()
    workers = args.workers or safe_workers()
    if workers > 1:
        # Playing 16 boards a deal is a few seconds of Python; spread it too.
        with multiprocessing.Pool(workers) as pool:
            lines = [line for found in pool.map(plan, [[d] for d in deal_ids], chunksize=1)
                     for line in found]
    else:
        lines = plan(deal_ids)
    previous = read_jsonl(args.out)
    done = completed(previous, version)
    todo = [line for line in lines if line['key'] not in done]
    solver = solver_version()
    stored = load_cache(args.cache, solver)
    cache = {} if args.no_cache else stored
    hits = [line for line in todo if line['key'] in cache and same_position(line, cache[line['key']])]
    hit_keys = {line['key'] for line in hits}
    todo = [line for line in todo if line['key'] not in hit_keys]
    timings = timings_from(list(stored.values()) + previous)   # times only, even with --no-cache
    todo.sort(key=lambda line: -estimate(line, timings))
    print(f"{len(deal_ids)} deals, {len(lines)} distinct robot lines "
          f"(planned in {time.perf_counter() - started:.0f}s), "
          f"{len(lines) - len(todo) - len(hits)} already done, {len(hits)} copied from the cache, "
          f"{len(todo)} to solve, {workers} worker(s), robot version {version}, "
          f"solver {solver}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    end_with_newline(args.out)
    with args.out.open('a', encoding='utf-8') as sink:
        for line in hits:
            append_line(sink, reuse(line, cache[line['key']], version, solver))
    if not todo:
        return 0
    if not args.no_cache:
        args.cache.parent.mkdir(parents=True, exist_ok=True)
        end_with_newline(args.cache)

    started = time.perf_counter()
    pool = multiprocessing.Pool(workers) if workers > 1 else None
    # Lines are handed out in list order (slowest first); results come back as they finish.
    results = pool.imap_unordered(solve, todo, chunksize=1) if pool else map(solve, todo)
    try:
        with args.out.open('a', encoding='utf-8') as sink:
            for n, record in enumerate(results, 1):
                append_line(sink, record)
                if not args.no_cache:
                    with args.cache.open('a', encoding='utf-8') as store:
                        append_line(store, cache_entry(record, solver))
                elapsed = time.perf_counter() - started
                c = record['contract']
                print(f"[{n}/{len(todo)}] deal {record['deal_id']:>3} {c['level']}{c['strain']:<2} by "
                      f"{c['declarer']:<5} {record['seconds']:7.1f}s  elapsed {elapsed / 60:5.1f}m  "
                      f"eta {elapsed / n * (len(todo) - n) / 60:6.1f}m", flush=True)
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    return 0


if __name__ == '__main__':
    sys.exit(main())
