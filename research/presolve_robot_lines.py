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
robots' play. A change to ai.py or gib.py changes the robots' lines; records
from another version are not reused, so rerun after any such change.

    python research/presolve_robot_lines.py --deals 10       # first 10 deals
    python research/presolve_robot_lines.py                  # all 400

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
from typing import Dict, List, Optional, Sequence

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

#: Files whose code decides what the robot table bids and plays.
ROBOT_SOURCES = ('ai.py', 'gib.py', 'game.py', 'card.py', 'challenge.py',
                 'bridge/trick.py', 'bridge/auction.py')

#: Memory per worker. Before the solver's table was capped, deal 197 (2NT by
#: South) grew one process to 8.9 GB and two at once swapped the machine
#: (2026-10-18). `MAX_TABLE_ENTRIES` in research/solver-rs/src/search.rs now
#: holds a process to about 3.3 GB at worst (3.1 GB measured on that deal).
GB_PER_WORKER = 4.0

BOARDS = 16


def robot_version() -> str:
    digest = hashlib.sha256()
    for name in ROBOT_SOURCES:
        digest.update(name.encode())
        digest.update((ROOT / name).read_bytes())
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
            'robot_version': robot_version()}


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


def completed(out: Path, version: str) -> set:
    done = set()
    if out.exists():
        for raw in out.read_text(encoding='utf-8').splitlines():
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue   # a line cut off by a hard kill; solved again
            if record.get('robot_version') == version:
                done.add(record['key'])
    return done


def safe_workers() -> int:
    by_cpu = max(1, (os.cpu_count() or 2) - 2)
    free = free_memory_gb()
    if free is None:
        return 1
    return max(1, min(by_cpu, int(free * 0.8 / GB_PER_WORKER)))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--deals', type=int, default=None, help="first N deals (default: all)")
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--workers', type=int, default=None, help="default: what free memory allows")
    args = parser.parse_args(argv)

    if not LINE_EXE.exists():
        print(f"{LINE_EXE} is missing: run `cargo build --release` in research/solver-rs/")
        return 1

    deal_ids = challenge.deal_ids()[:args.deals] if args.deals else challenge.deal_ids()
    version = robot_version()
    started = time.perf_counter()
    lines = plan(deal_ids)
    done = completed(args.out, version)
    todo = [line for line in lines if line['key'] not in done]
    workers = args.workers or safe_workers()
    print(f"{len(deal_ids)} deals, {len(lines)} distinct robot lines "
          f"(planned in {time.perf_counter() - started:.0f}s), {len(lines) - len(todo)} already done, "
          f"{len(todo)} to solve, {workers} worker(s), robot version {version}", flush=True)
    if not todo:
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists() and args.out.stat().st_size and not args.out.read_bytes().endswith(b'\n'):
        with args.out.open('ab') as handle:
            handle.write(b'\n')

    started = time.perf_counter()
    pool = multiprocessing.Pool(workers) if workers > 1 else None
    results = pool.imap_unordered(solve, todo, chunksize=1) if pool else map(solve, todo)
    try:
        with args.out.open('a', encoding='utf-8') as sink:
            for n, record in enumerate(results, 1):
                sink.write(json.dumps(record) + '\n')
                sink.flush()
                os.fsync(sink.fileno())
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
