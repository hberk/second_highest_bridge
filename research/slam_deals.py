"""Slam deals for bidding work: random deals, filtered, screened, then fully solved.

Slams are rare in random deals (26 slam hands in the 400 of dd_pilot.jsonl), so
solving random deals in full costs about 2,100 CPU-seconds per slam found. This
spends the solver only where a slam is likely, without building hands by hand:

1. Deal at random from a seed of its own (`SEED_BASE`, far from dd_dataset's), and
   keep each side holding a 9+ card fit. Dealing costs microseconds, so rejecting
   deals is free, and the deals kept are exactly as random as any deal with such a
   fit. Building hands on purpose (planting a void, say) would change which hands
   come out. The filter caught 23 of the 26 slams in the 400 deals.
2. Screen: solve each kept side's two best fits, that side declaring only. These
   held the side's best result on all 26 slam hands, and cost about 28% of a full
   deal.
3. Finish every deal where the screen finds 12+ tricks: all five strains, both
   declaring sides, exactly as dd_dataset solves them. The opponents cannot be
   skipped: with our slam they still take 5 to 11 tricks in their best fit, and a
   doubled sacrifice beats the slam on 13 to 20 of the 26 hands, by vulnerability.

Measured 2026-10-22 on 200 fresh deals: 6.5% of the screened sides make slam,
matching the 400 deals; about 600 CPU-seconds per finished slam deal.

Two JSON Lines files, appended and fsynced one deal at a time, so a run can stop
anywhere and resume (just rerun):

- `dd_slam_screen.jsonl`: one line per deal dealt. The sides kept, their screen
  results and whether the deal was finished. The screened deals that fall short
  of slam are the near misses, labelled for free.
- `dd_slam.jsonl`: the finished deals, one record per (deal, strain), in the
  shape of dd_pilot.jsonl plus the filter that picked them.

These deals are NOT a random sample. Keep them out of anything that averages
over deals (the challenge library, gib_h2h), or weight them by the screen file's
acceptance counts.

    python research/slam_deals.py --slams 100 --workers 4
"""
from __future__ import annotations
import argparse
import json
import multiprocessing
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from card import SUITS, deal
from research.dd_dataset import (
    RUST_EXE, RUST_TIMEOUT_SECONDS, SIDE_SEATS, Hands, _end_with_newline, _in_suit,
    declarer_for, hands_to_text, leader_for, ranked_fits, solve_strain_rust,
)

#: Deal seeds of their own, far from dd_dataset's (900,000 up).
SEED_BASE = 2_000_000

#: The filter: a side holding at least this many cards in one suit.
MIN_FIT = 9
FILTER = f'fit>={MIN_FIT}'

#: Fits screened per kept side, best first.
SCREEN_FITS = 2

STRAINS = ('C', 'D', 'H', 'S', 'NT')
DATA = ROOT / 'research' / 'data'
DEFAULT_OUT = DATA / 'dd_slam.jsonl'
DEFAULT_SCREEN = DATA / 'dd_slam_screen.jsonl'


def deal_for(deal_id: int) -> Hands:
    """The deal for an id, reproducibly; the global RNG is put back afterwards."""
    state = random.getstate()
    try:
        random.seed(SEED_BASE + deal_id)
        return {seat: list(cards) for seat, cards in deal().items()}
    finally:
        random.setstate(state)


def longest_fit(hands: Hands, side: str) -> int:
    first, second = SIDE_SEATS[side]
    return max(len(_in_suit(hands[first], s)) + len(_in_suit(hands[second], s)) for s in SUITS)


def kept_sides(hands: Hands) -> List[str]:
    return [side for side in ('N/S', 'E/W') if longest_fit(hands, side) >= MIN_FIT]


def solve_one_rust(hands: Hands, strain: str, side: str) -> dict:
    """One strain, one declaring side, through the Rust engine."""
    if not RUST_EXE.exists():
        raise FileNotFoundError(
            f"Rust engine not built at {RUST_EXE}. Run `cargo build --release` "
            f"in research/solver-rs/ first.")
    declarer = declarer_for(hands, side, strain)
    leader = leader_for(declarer)
    payload = {'hands': hands_to_text(hands), 'strain': strain,
               'queries': [{'leader': leader, 'trick': []}]}
    started = time.perf_counter()
    proc = subprocess.run([str(RUST_EXE)], input=json.dumps(payload), capture_output=True,
                          text=True, timeout=RUST_TIMEOUT_SECONDS)
    if proc.returncode != 0:
        raise RuntimeError(f"Rust engine failed on strain {strain}: {proc.stderr.strip()}")
    raw = json.loads(proc.stdout)['results'][0]
    return {
        'declaring_side': side, 'strain': strain, 'declarer': declarer, 'leader': leader,
        'declarer_tricks': raw['ns_tricks'] if side == 'N/S' else 13 - raw['ns_tricks'],
        'nodes': raw['nodes'], 'seconds': round(time.perf_counter() - started, 2),
    }


def process_deal(deal_id: int,
                 solve_one: Callable[[Hands, str, str], dict] = solve_one_rust,
                 solve_strain: Callable[[Hands, str], dict] = solve_strain_rust) -> dict:
    """Filter, screen and, on a slam, finish one deal. Returns its screen line and,
    when finished, its full records under 'full'."""
    hands = deal_for(deal_id)
    sides = kept_sides(hands)
    screen = [solve_one(hands, strain, side)
              for side in sides for strain in ranked_fits(hands, side)[:SCREEN_FITS]]
    slam_sides = sorted({r['declaring_side'] for r in screen if r['declarer_tricks'] >= 12})
    line = {'version': 1, 'deal_id': deal_id, 'seed': SEED_BASE + deal_id, 'filter': FILTER,
            'kept_sides': sides, 'screen': screen, 'slam_sides': slam_sides,
            'finished': bool(slam_sides)}
    if sides:
        line['hands'] = hands_to_text(hands)
    if not slam_sides:
        return line

    full = []
    for strain in STRAINS:
        solved = solve_strain(hands, strain)
        full.append({'version': 1, 'deal_id': deal_id, 'seed': SEED_BASE + deal_id,
                     'why': ['slam screen'], 'filter': FILTER, 'hands': hands_to_text(hands),
                     **solved})
    # The screen and the full solve ask the same questions: they must agree.
    found = {(rec['strain'], r['declaring_side']): r['declarer_tricks']
             for rec in full for r in rec['results']}
    for r in screen:
        if found[(r['strain'], r['declaring_side'])] != r['declarer_tricks']:
            raise RuntimeError(f"deal {deal_id}: screen and full solve disagree on {r}")
    line['full'] = full
    return line


def _work(deal_id: int) -> dict:
    """Pool entry point, top level so it pickles under Windows' spawn."""
    return process_deal(deal_id)


def done_deals(screen_path: Path) -> Set[int]:
    """Deals already written; a line cut off by a hard kill is ignored and reruns."""
    done: Set[int] = set()
    if screen_path.exists():
        for text in screen_path.read_text(encoding='utf-8').splitlines():
            try:
                done.add(json.loads(text)['deal_id'])
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def finished_count(screen_path: Path) -> int:
    count = 0
    if screen_path.exists():
        for text in screen_path.read_text(encoding='utf-8').splitlines():
            try:
                count += bool(json.loads(text).get('finished'))
            except json.JSONDecodeError:
                continue
    return count


def _append(path: Path, records: Sequence[dict]) -> None:
    with path.open('a', encoding='utf-8') as sink:
        for record in records:
            sink.write(json.dumps(record) + '\n')
        sink.flush()
        os.fsync(sink.fileno())


def run(slams: int, out: Path, screen_path: Path, workers: int,
        work: Callable[[int], dict] = _work, log: Callable[[str], None] = print,
        max_deals: Optional[int] = None) -> int:
    """Deal ids in order, skipping those done, until `slams` deals are finished.

    The full records of a deal are written before its screen line, so a deal is
    only counted done once both are on disk; a deal cut off between the two is
    redone, and `out` may then hold its records twice (identical, deterministic).
    Returns the number of finished deals on disk.
    """
    for path in (out, screen_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        _end_with_newline(path)
    done = done_deals(screen_path)
    have = finished_count(screen_path)
    log(f"{len(done)} deals screened, {have} finished; target {slams}, {workers} worker(s)")
    if have >= slams:
        return have

    started = time.perf_counter()
    screened = 0
    next_id = 0

    def next_task() -> Optional[int]:
        nonlocal next_id
        while next_id in done:
            next_id += 1
        if max_deals is not None and next_id >= max_deals:
            return None
        next_id += 1
        return next_id - 1

    def record(line: dict) -> None:
        nonlocal have, screened
        full = line.pop('full', [])
        if full:
            _append(out, full)
        _append(screen_path, [line])
        screened += 1
        have += bool(line['finished'])
        if line['kept_sides']:
            tricks = ' '.join(f"{r['declaring_side']} {r['strain']}:{r['declarer_tricks']}"
                              for r in line['screen'])
            log(f"deal {line['deal_id']:>5}  {tricks:<40s} "
                f"{'SLAM ' if line['finished'] else ''}"
                f"[{have}/{slams} slams, {screened} dealt, "
                f"{(time.perf_counter() - started) / 60:.1f}m]")

    if workers == 1:
        while have < slams:
            deal_id = next_task()
            if deal_id is None:
                break
            record(work(deal_id))
        return have

    pool = multiprocessing.Pool(workers)
    pending: List = []
    try:
        while True:
            while have < slams and len(pending) < workers * 2:
                deal_id = next_task()
                if deal_id is None:
                    break
                pending.append(pool.apply_async(work, (deal_id,)))
            if not pending:
                break
            ready = [p for p in pending if p.ready()]
            if not ready:
                time.sleep(0.2)
                continue
            for p in ready:
                pending.remove(p)
                record(p.get())
            if have >= slams and not pending:
                break
    finally:
        pool.terminate()
        pool.join()
    return have


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--slams', type=int, default=100,
                        help="stop once this many deals are finished (default 100)")
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--screen', type=Path, default=DEFAULT_SCREEN)
    args = parser.parse_args(argv)
    if not RUST_EXE.exists():
        print(f"error: needs the Rust engine at {RUST_EXE}\n"
              f"  run: cd research/solver-rs && cargo build --release", flush=True)
        return 1
    have = run(args.slams, args.out, args.screen, args.workers,
               log=lambda m: print(m, flush=True))
    print(f"done: {have} finished slam deals in {args.out}", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
