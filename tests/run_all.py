"""Run every test_* function in every tests/test_*.py file and report all failures.

A test that raises unittest.SkipTest (the Rust engine not built, say) is
reported as SKIP, not counted as a pass. A module that fails to import is a
failure of its own and the run carries on to the next one.
"""
from __future__ import annotations
import importlib
import sys
import traceback
from pathlib import Path
from unittest import SkipTest

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def main() -> int:
    passed, skipped, failures = 0, [], []
    for path in sorted(Path(__file__).parent.glob('test_*.py')):
        try:
            module = importlib.import_module(f'tests.{path.stem}')
        except Exception:
            failures.append((f"{path.stem} (import)", traceback.format_exc()))
            print(f"FAIL {path.stem} (import)")
            continue
        for name, fn in list(vars(module).items()):
            if not (name.startswith('test_') and callable(fn)):
                continue
            try:
                fn()
                passed += 1
                print(f"PASS {path.stem}.{name}")
            except SkipTest as why:
                skipped.append(f"{path.stem}.{name}")
                print(f"SKIP {path.stem}.{name} ({why})")
            except Exception:
                failures.append((f"{path.stem}.{name}", traceback.format_exc()))
                print(f"FAIL {path.stem}.{name}")

    for name, tb in failures:
        print(f"\n── {name} ──\n{tb}")
    print(f"\n{passed} passed, {len(skipped)} skipped, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
