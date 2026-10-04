"""Run every test_* function in every tests/test_*.py file and report all failures."""
from __future__ import annotations
import importlib
import sys
import traceback
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def main() -> int:
    passed, failures = 0, []
    for path in sorted(Path(__file__).parent.glob('test_*.py')):
        module = importlib.import_module(f'tests.{path.stem}')
        for name, fn in list(vars(module).items()):
            if not (name.startswith('test_') and callable(fn)):
                continue
            try:
                fn()
                passed += 1
                print(f"PASS {path.stem}.{name}")
            except Exception:
                failures.append((f"{path.stem}.{name}", traceback.format_exc()))
                print(f"FAIL {path.stem}.{name}")

    for name, tb in failures:
        print(f"\n── {name} ──\n{tb}")
    print(f"\n{passed} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
