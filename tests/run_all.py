"""Run every test_* function in every tests/test_*.py file and report all failures.

A test that raises unittest.SkipTest (the Rust engine not built, say) is
reported as SKIP, not counted as a pass. A module that fails to import is a
failure of its own and the run carries on to the next one.

The tests run in parallel, one per process, on every core: the robots search
from five cards a hand, which made the suite several times slower one at a time.
"""
from __future__ import annotations
import importlib
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest import SkipTest

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def run_test(stem: str, name: str | None) -> tuple[str, int, list[str], list]:
    """Run one test, or import one file when `name` is None:
    (line to print, passed, skipped, failures)."""
    try:
        module = importlib.import_module(f'tests.{stem}')
    except Exception:
        return f"FAIL {stem} (import)", 0, [], [(f"{stem} (import)", traceback.format_exc())]
    if name is None:
        return '', 0, [], []
    try:
        getattr(module, name)()
        return f"PASS {stem}.{name}", 1, [], []
    except SkipTest as why:
        return f"SKIP {stem}.{name} ({why})", 0, [f"{stem}.{name}"], []
    except Exception:
        return f"FAIL {stem}.{name}", 0, [], [(f"{stem}.{name}", traceback.format_exc())]


def main() -> int:
    tests = []
    for path in sorted(Path(__file__).parent.glob('test_*.py')):
        try:
            module = importlib.import_module(f'tests.{path.stem}')
        except Exception:
            tests.append((path.stem, None))      # reported as a failure by the worker
            continue
        tests += [(path.stem, name) for name, fn in list(vars(module).items())
                  if name.startswith('test_') and callable(fn)]
    passed, skipped, failures = 0, [], []
    with ProcessPoolExecutor(os.cpu_count()) as pool:
        for line, n, skips, fails in pool.map(run_test, *zip(*tests)):
            if line:
                print(line, flush=True)
            passed += n
            skipped += skips
            failures += fails

    for name, tb in failures:
        print(f"\n── {name} ──\n{tb}")
    print(f"\n{passed} passed, {len(skipped)} skipped, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
