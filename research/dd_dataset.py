"""Double dummy dataset for fitting bidding: raw deals and trick counts.

For each deal this records how many tricks each partnership takes, double dummy,
in the strains bidding actually chooses between: each side's best fit, and
notrump. It stores raw hands and trick counts, not features, so the data outlives
any particular feature design. Strain and declarer choice use only suit lengths
and high-card points, never ai.py, so the dataset does not depend on the
evaluation it exists to replace.

Cost, measured on this machine: a full 13-card solve in pure Python is about
ten minutes and about half a gigabyte of transposition table. Both declaring
sides of a strain share one table, and the second solve starts from the
first one's answer; that measured 1.45x cheaper than two separate solves, with
identical results. Slow deals are never skipped or timed out, because that
would bias the data towards easy deals.

An optional Rust engine (research/solver-rs/, `--engine rust`) is a straight
port of bridge/solver/search.py's production configuration, called as a
subprocess per (deal, strain) task. It is not a redesign: same algorithm, same
transposition table, same trick-first move ordering — the value is entirely
from removing Python's interpreter overhead. Measured against bridge/solver's
own trusted search on 50 random endings (6-10 cards each, tests/test_dd_dataset.py):
identical answers throughout, 63-72x faster. On the exact full 13-card deal
this module's Python engine was benchmarked on (seed 0): identical node count
(55,633,842), identical table size (3,620,453 entries), identical answer
(N/S=2/13), 67.0x faster (603.9s -> 9.0s). Build it once with
`cargo build --release` in research/solver-rs/ before using --engine rust; a
missing binary fails fast with a clear message rather than a confusing one.

Output is JSON Lines, one record per (deal, strain), appended as each finishes,
so a run can be stopped at any point and resumed without losing finished work:

    python research/dd_dataset.py --deals 25
    python research/dd_dataset.py --deals 25 --workers 6            # more, if RAM allows
    python research/dd_dataset.py --deals 300 --engine rust         # ~67x faster per solve
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
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from card import Card, SUITS, deal
from game import PLAYERS
from bridge.solver.bitstate import Position, tricks_available
from bridge.solver.convert import (
    cards_to_mask, mask_to_cards, mask_to_text, text_to_mask, trump_to_index,
)
from bridge.solver.search import Search

HCP = {'A': 4, 'K': 3, 'Q': 2, 'J': 1}
SIDE_SEATS = {'N/S': ('North', 'South'), 'E/W': ('East', 'West')}

#: Deal seeds start far from any seed the test suite uses.
SEED_BASE = 900_000

#: Memory budget per worker. One full-deal table measured ~0.54 GB of Python
#: allocations; a worker holds both declaring sides in one table, plus the
#: interpreter. Deliberately generous: an unattended run that swaps is far
#: slower than one that uses fewer workers.
GB_PER_WORKER = 1.2

DEFAULT_OUT = ROOT / 'research' / 'data' / 'dd_pilot.jsonl'

#: The compiled Rust engine. Built separately (`cargo build --release` in
#: research/solver-rs/); this module never builds it, only calls it.
RUST_EXE = (Path(os.environ.get('CARGO_TARGET_DIR') or ROOT / 'research' / 'solver-rs' / 'target')
            / 'release' / ('solver-rs.exe' if os.name == 'nt' else 'solver-rs'))

#: Generous rather than tight: a timeout here should only ever catch a genuine
#: hang, never a slow-but-legitimate solve. At the measured ~67x speedup even a
#: full 13-card deal is ~10-40s, so this has wide headroom.
RUST_TIMEOUT_SECONDS = 1800

Hands = Dict[str, List[Card]]
Task = Tuple[int, str, List[str]]          # (deal id, strain, why it is solved)


# ── Deals ────────────────────────────────────────────────────────────────────

def deal_for(deal_id: int) -> Hands:
    """The deal for an id. Reproducible: the same id always gives the same cards.
    The global RNG is put back afterwards, since tests import this module."""
    state = random.getstate()
    try:
        random.seed(SEED_BASE + deal_id)
        return {seat: list(cards) for seat, cards in deal().items()}
    finally:
        random.setstate(state)


def hands_to_text(hands: Hands) -> Dict[str, str]:
    return {seat: mask_to_text(cards_to_mask(hands[seat])) for seat in PLAYERS}


def hands_from_text(text: Dict[str, str]) -> Hands:
    return {seat: mask_to_cards(text_to_mask(text[seat])) for seat in PLAYERS}


# ── Which strains, and who declares ──────────────────────────────────────────

def _hcp(cards: Iterable[Card]) -> int:
    return sum(HCP.get(card.rank, 0) for card in cards)


def _in_suit(cards: Iterable[Card], suit: str) -> List[Card]:
    return [card for card in cards if card.suit == suit]


def ranked_fits(hands: Hands, side: str) -> List[str]:
    """Every suit, best fit first: combined length, then combined high-card points
    in the suit, then the higher-ranking suit. The sort keys are unique (the suit
    index breaks every tie), so the order is total and element 0 is exactly what
    `best_fit` used to return by `max`."""
    first, second = SIDE_SEATS[side]

    def strength(suit: str) -> tuple:
        cards = _in_suit(hands[first], suit) + _in_suit(hands[second], suit)
        return len(cards), _hcp(cards), SUITS.index(suit)

    return sorted(SUITS, key=strength, reverse=True)


def best_fit(hands: Hands, side: str) -> str:
    """The suit a partnership holds most of."""
    return ranked_fits(hands, side)[0]


def strains_to_solve(hands: Hands, extra_fits: int = 0) -> List[Tuple[str, List[str]]]:
    """Each side's best fit, then notrump, without duplicates, with the reasons.

    `extra_fits` additionally solves each side's next-best suits. Solving only the
    single best fit leaves most contracts a real auction can reach unscorable, and
    makes strain choice ("our 8-card heart fit, or our 7-card spade fit?")
    unanswerable. Each extra fit costs roughly a third more compute per deal.

    The default stays 0 so an existing dataset keeps its shape and its resume
    behaviour unless the extra strains are explicitly asked for.
    """
    reasons: Dict[str, List[str]] = {}
    for side in ('N/S', 'E/W'):
        ranked = ranked_fits(hands, side)
        reasons.setdefault(ranked[0], []).append(f"{side} best fit")
        for place, suit in enumerate(ranked[1:1 + extra_fits], start=2):
            reasons.setdefault(suit, []).append(f"{side} fit #{place}")
    reasons.setdefault('NT', []).append('notrump')
    return list(reasons.items())


def declarer_for(hands: Hands, side: str, strain: str) -> str:
    """The partner who would declare: longer in the suit, or more high-card
    points in notrump. Ties go to North for N/S and East for E/W."""
    first, second = SIDE_SEATS[side]

    def claim(seat: str) -> tuple:
        if strain == 'NT':
            return (_hcp(hands[seat]),)
        suit_cards = _in_suit(hands[seat], strain)
        return len(suit_cards), _hcp(suit_cards)

    return max((first, second), key=claim)      # max keeps the first on a tie


def leader_for(declarer: str) -> str:
    """The opening lead comes from declarer's left."""
    return PLAYERS[(PLAYERS.index(declarer) + 1) % 4]


# ── Solving ──────────────────────────────────────────────────────────────────

def solve_strain(hands: Hands, strain: str) -> dict:
    """Both declaring sides of one strain, sharing one transposition table.

    N/S declaring is solved first; E/W declaring then starts from that answer,
    since the two usually land within a trick of each other.
    """
    engine = Search(trump_to_index(strain))
    masks = tuple(cards_to_mask(hands[seat]) for seat in PLAYERS)
    started = time.perf_counter()
    results = []
    guess: Optional[int] = None

    for side in ('N/S', 'E/W'):
        declarer = declarer_for(hands, side, strain)
        leader = leader_for(declarer)
        position = Position(masks, PLAYERS.index(leader), (), trump_to_index(strain))

        solve_started = time.perf_counter()
        nodes_before = engine.nodes
        ns_tricks = engine.value(position) if guess is None else engine.value_from(position, guess)
        guess = ns_tricks

        total = tricks_available(position)
        results.append({
            'declaring_side': side,
            'declarer': declarer,
            'leader': leader,
            'declarer_tricks': ns_tricks if side == 'N/S' else total - ns_tricks,
            'ns_tricks': ns_tricks,
            'nodes': engine.nodes - nodes_before,
            'seconds': round(time.perf_counter() - solve_started, 2),
        })

    return {
        'strain': strain,
        'results': results,
        'table_entries': len(engine.table),
        'seconds': round(time.perf_counter() - started, 2),
        'engine': 'python',
    }


def solve_strain_rust(hands: Hands, strain: str) -> dict:
    """Same contract and shape as `solve_strain`, run through the Rust engine.

    Sends both declaring sides as one call, so the Rust process shares its own
    transposition table across them exactly as `solve_strain` shares its
    Python one — same pairing win, same reason it works (both leaders are
    positions over the SAME cards, so lines transpose heavily between them).
    """
    if not RUST_EXE.exists():
        raise FileNotFoundError(
            f"Rust engine not built at {RUST_EXE}. Run `cargo build --release` "
            f"in research/solver-rs/ first, or use --engine python."
        )

    sides = [(side, declarer_for(hands, side, strain)) for side in ('N/S', 'E/W')]
    payload = {
        'hands': hands_to_text(hands),
        'strain': strain,
        'queries': [{'leader': leader_for(declarer), 'trick': []} for _, declarer in sides],
    }

    started = time.perf_counter()
    proc = subprocess.run(
        [str(RUST_EXE)], input=json.dumps(payload), capture_output=True,
        text=True, timeout=RUST_TIMEOUT_SECONDS,
    )
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        raise RuntimeError(f"Rust engine failed on strain {strain}: {proc.stderr.strip()}")
    out = json.loads(proc.stdout)

    # The CLI reports total seconds only, not per-query; split proportionally
    # by node count as a reasonable approximation, not a measured figure.
    node_counts = [r['nodes'] for r in out['results']]
    total_nodes = sum(node_counts) or 1

    results = []
    for (side, declarer), query_leader, raw in zip(sides, payload['queries'], out['results']):
        leader = query_leader['leader']
        ns_tricks = raw['ns_tricks']
        # tricks_available is the same for both sides of one strain (same
        # cards_left, same trump); recomputed here rather than re-derived from
        # the Rust output, which doesn't carry it.
        total = sum(len(hands[seat]) for seat in PLAYERS) // 4
        results.append({
            'declaring_side': side,
            'declarer': declarer,
            'leader': leader,
            'declarer_tricks': ns_tricks if side == 'N/S' else total - ns_tricks,
            'ns_tricks': ns_tricks,
            'nodes': raw['nodes'],
            'seconds': round(elapsed * raw['nodes'] / total_nodes, 2),
        })

    return {
        'strain': strain,
        'results': results,
        'table_entries': out['table_entries'],
        'seconds': round(elapsed, 2),
        'engine': 'rust',
    }


def task_record(deal_id: int, strain: str, why: Sequence[str], engine: str = 'python') -> dict:
    """Solve one (deal, strain) and package it as one line of the dataset."""
    hands = deal_for(deal_id)
    solver = solve_strain if engine == 'python' else solve_strain_rust
    return {
        'version': 1,
        'deal_id': deal_id,
        'seed': SEED_BASE + deal_id,
        'why': list(why),
        'hands': hands_to_text(hands),
        **solver(hands, strain),
    }


def _work(task: Task) -> dict:
    """Pool entry point (Python engine). Top level, so it pickles under Windows' spawn."""
    return task_record(*task, engine='python')


def _work_rust(task: Task) -> dict:
    """Pool entry point (Rust engine)."""
    return task_record(*task, engine='rust')


# ── Planning and resuming ────────────────────────────────────────────────────

def plan(deals: int, extra_fits: int = 0) -> List[Task]:
    """Every (deal, strain) to solve, in deal order so early deals finish first."""
    tasks: List[Task] = []
    for deal_id in range(deals):
        for strain, why in strains_to_solve(deal_for(deal_id), extra_fits):
            tasks.append((deal_id, strain, why))
    return tasks


def completed(path: Path) -> Set[Tuple[int, str]]:
    """(deal, strain) pairs already written. A half-written last line is ignored."""
    done: Set[Tuple[int, str]] = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue                      # killed mid-write; that task simply reruns
        done.add((record['deal_id'], record['strain']))
    return done


def _end_with_newline(path: Path) -> None:
    """Terminate a line cut off by a hard kill, so the next record starts cleanly."""
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open('rb') as handle:
        handle.seek(-1, os.SEEK_END)
        last = handle.read(1)
    if last != b'\n':
        with path.open('ab') as handle:
            handle.write(b'\n')


def run(tasks: Sequence[Task], out: Path, workers: int,
        work: Callable[[Task], dict] = _work,
        log: Callable[[str], None] = print) -> int:
    """Solve every task not already in `out`, appending records as they finish.

    Returns how many records were written. Each worker process is replaced after
    every task: Python does not reliably return a multi-gigabyte table to the OS,
    so a long-lived worker would creep upward in memory.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    done = completed(out)
    todo = [task for task in tasks if (task[0], task[1]) not in done]
    log(f"{len(tasks)} solve pairs planned, {len(tasks) - len(todo)} already done, "
        f"{len(todo)} to go, {workers} worker(s)")
    if not todo:
        return 0

    _end_with_newline(out)
    started = time.perf_counter()
    written = 0

    if workers == 1:
        results = map(work, todo)
        pool = None
    else:
        pool = multiprocessing.Pool(workers, maxtasksperchild=1)
        results = pool.imap_unordered(work, todo, chunksize=1)

    try:
        with out.open('a', encoding='utf-8') as sink:
            for record in results:
                sink.write(json.dumps(record) + '\n')
                sink.flush()
                os.fsync(sink.fileno())
                written += 1

                elapsed = time.perf_counter() - started
                remaining = elapsed / written * (len(todo) - written)
                tricks = '  '.join(f"{r['declaring_side']} {r['declarer_tricks']:>2}"
                                   for r in record.get('results', []))
                log(f"[{written}/{len(todo)}] deal {record['deal_id']:>3} {record['strain']:>2}  "
                    f"{tricks}  {record.get('seconds', 0):>7.0f}s   "
                    f"elapsed {elapsed / 60:5.1f}m  eta {remaining / 60:6.1f}m")
    except BaseException:
        # A failed task (or Ctrl-C) ends the run now. close() + join() would
        # first wait for every queued solve, then throw those answers away;
        # what was written is kept and a rerun resumes after it.
        if pool is not None:
            pool.terminate()
            pool.join()
            pool = None
        raise
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    return written


# ── Command line ─────────────────────────────────────────────────────────────

def free_memory_gb() -> Optional[float]:
    """Physical memory free right now, on Windows; None where it cannot be read."""
    try:
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                        ('total_phys', ctypes.c_ulonglong), ('avail_phys', ctypes.c_ulonglong),
                        ('total_page', ctypes.c_ulonglong), ('avail_page', ctypes.c_ulonglong),
                        ('total_virtual', ctypes.c_ulonglong), ('avail_virtual', ctypes.c_ulonglong),
                        ('avail_extended', ctypes.c_ulonglong)]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return status.avail_phys / 2 ** 30
    except Exception:
        return None


def safe_workers() -> int:
    """Workers that fit in free memory, leaving two CPUs for the rest of the machine."""
    by_cpu = max(1, (os.cpu_count() or 2) - 2)
    free = free_memory_gb()
    if free is None:
        return min(by_cpu, 4)
    return max(1, min(by_cpu, int(free * 0.8 / GB_PER_WORKER)))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--deals', type=int, default=25, help="deals to solve (default 25)")
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT, help="JSON Lines output file")
    parser.add_argument('--workers', type=int, default=None,
                        help="parallel solves (default: as many as free memory allows)")
    parser.add_argument('--extra-fits', type=int, default=0, metavar='N',
                        help="also solve each side's next N best suits (default 0). "
                             "Needed to score the contracts a real auction reaches and "
                             "to compare strain choices; costs about a third more "
                             "compute per deal per extra fit")
    parser.add_argument('--engine', choices=('python', 'rust'), default='python',
                        help="'rust' is a verified drop-in port, ~67x faster per solve "
                             "(measured; see this file's module docstring) -- requires "
                             "`cargo build --release` in research/solver-rs/ first")
    args = parser.parse_args(argv)

    if args.engine == 'rust' and not RUST_EXE.exists():
        print(f"error: --engine rust requires a build at {RUST_EXE}\n"
              f"  run: cd research/solver-rs && cargo build --release", flush=True)
        return 1

    safe = safe_workers()
    workers = args.workers or safe
    if args.workers and args.workers > safe:
        print(f"warning: {args.workers} workers may exhaust memory; "
              f"about {safe} fit in the RAM free right now"
              + (" (measured: Rust workers peak around 1.06 GB, close to the same "
                 "budget -- native structs are NOT markedly cheaper here)"
                 if args.engine == 'rust' else ''), flush=True)

    work_fn = _work if args.engine == 'python' else _work_rust
    written = run(plan(args.deals, args.extra_fits), args.out, workers, work=work_fn,
                 log=lambda m: print(m, flush=True))
    print(f"done: {written} record(s) written to {args.out} (engine: {args.engine})", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
