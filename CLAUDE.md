# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

It holds what every session needs. The detail lives in `docs/`, one topic per file. **Read the
doc for the area you're changing before you change it**; the guardrails below say why.

## Commands

```bash
# The game is the web app in frontend/ (commands below). The Python code is
# its reference engine, with no UI and no third-party dependencies.

# Run every test and report all failures (doesn't stop at the first one)
python tests/run_all.py

# Individual suites
python tests/test_rules.py      # second-highest trick rule + follow-suit
python tests/test_scoring.py    # duplicate scoring: minors, slams, doubled/redoubled
python tests/test_bidding.py    # auction rules/errors, scoring basics, 40 seeded AI games
python tests/test_sim.py        # smoke test: one seeded AI vs AI game with invariants
python tests/test_bidding_calibration.py  # interim threshold calibration guards
python tests/test_bidding_rebids.py       # agreed-suit rebids, minor-suit game
python tests/test_gib.py                  # GIB 2/1 conventions, call by call
python tests/test_lin.py                  # LIN hand records: round trips, BBO variants, refusals
python tests/test_challenge.py            # challenge grading: par = bidding + play loss
python tests/test_card_play_rules.py      # the card-play rules from deals 92, 156, 174
python tests/test_slam_deals.py           # slam deal generator: filter, screen, finish, resume
```

`run_all.py` reports a test that raises `unittest.SkipTest` as SKIP (the Rust
solver tests, when the binary isn't built), never as a pass.

Solver, dataset and Rust engine commands: [docs/SOLVER.md](docs/SOLVER.md#commands).

```bash
cd frontend
npm install
rustup target add wasm32-unknown-unknown   # once: the History replayer's solver
npm run wasm       # build it (dev, test and build run this first, and fail without Rust)
npm run fixtures   # export the Python engine's behaviour (needs Python 3.12+)
npm test           # TS engine parity with Python + headless table flow + WASM solver
npm run check      # svelte-check
npm run dev        # local dev server
npm run build      # static site in frontend/dist, deployed to GitHub Pages
```

## Environment

Python 3.9 or newer, standard library only. Developed on 3.9.13, and the full suite
(236 tests as of 2026-10-22) passes unchanged on **3.12.10** — no source edits were
needed, because every file already starts with `from __future__ import annotations`.
`.python-version` pins 3.12, the reference (below) and what CI and the fixtures use.
A 3.12 virtualenv lives in `.venv/` (gitignored); `./.venv/Scripts/python.exe`
runs it on Windows.

The environment is Windows; use `$env:PYTHONIOENCODING='utf-8'` in PowerShell if
running CLI commands that print suit symbols.

**Python 3.9 and 3.12 do not evaluate hands identically.** From 3.12, `sum()`
over floats is compensated (Neumaier), so `eval_hand_sh` can differ in the last
bit: one hand sums to 0.22100000000000006 on 3.9 and 0.22100000000000009 on
3.12. No decision in 1,200 test games moved, but a hand landing exactly on a
threshold could bid differently on the two. 3.12 is the reference.

## Game Rules

This is a Contract Bridge variant where **the second-highest card in the winning suit wins each trick** (not the highest). The winning suit is trump if any trump was played, otherwise the led suit (including in No-Trump contracts). If only one card of the winning suit is played it wins outright.

Full Bridge Bidding (Auction) from 1♣ to 7NT with Pass, Double (X), and Redouble (XX), Dealer and Vulnerability rotations, and complete duplicate Bridge scoring. Human plays South; North, East, and West bid via AI. If N/S wins the contract, dummy is revealed and played by the human declarer.

## Where things are

| path | what | detail |
|---|---|---|
| `card.py` | `Card`, `deal()`, suits/strains/ranks, bid parsing | [ARCHITECTURE](docs/ARCHITECTURE.md) |
| `bridge/` | auction, trick (the rules oracle), scoring, LIN | [ARCHITECTURE](docs/ARCHITECTURE.md) |
| `bridge/solver/` | double dummy solver | [SOLVER](docs/SOLVER.md) |
| `gib.py`, `ai.py` | robot bidding (GIB first, the previous system as fallback), hand evaluation, card play | [BIDDING](docs/BIDDING.md), [CHALLENGE](docs/CHALLENGE.md) |
| `challenge.py`, `data/solved_deals.json` | head-to-head mode on 400 solved deals | [CHALLENGE](docs/CHALLENGE.md) |
| `frontend/` | the game: the phone-first web app (Svelte), a static site | [FRONTEND](docs/FRONTEND.md) |
| `research/` | dataset, fitting, the Rust solver; never imported by the Python app. The web app's History replayer runs `research/solver-rs/wasm` as WebAssembly | [SOLVER](docs/SOLVER.md), [BIDDING](docs/BIDDING.md), [FRONTEND](docs/FRONTEND.md) |
| `tests/` | the Python suites; `tests/fixtures/endings.json` is frozen solver ground truth | |

## Key Invariants

- `Card.__eq__` and `__hash__` are both defined (hashable, usable in sets/dicts).
- All files start with `from __future__ import annotations` for Python 3.9 union type compatibility.
- `deal()` returns hands already sorted high-to-low within each suit — don't re-sort in display code.
- The `played` list passed to `ai_play` is cumulative across the full game; it grows after each completed trick in the game loop (`Game` in the web app, `main.py`, the tests).

## Guardrails

Each of these was measured or learned the hard way. The linked doc has the evidence; read
it before going against one.

**Rules and the solver** ([SOLVER](docs/SOLVER.md))
- `bridge/trick.py` is the rules oracle; the solver never redefines the rules.
- A change to `ns_tricks` in `tests/fixtures/endings.json` means a rules change or a bug,
  **never** a speedup. A solver port (the Rust one) is checked against it before it's trusted.
- Only `bridge/solver/convert.py` translates between domain objects and solver ints.
- Don't run `brute.py` on more than 5 cards per hand.
- The dataset never skips or times out slow deals, and `--engine rust` never silently falls
  back to Python.

**Bidding** ([BIDDING](docs/BIDDING.md))
- GIB was adopted by choice and measures worse than the previous system. **Do not "fix" GIB
  toward the measured system.** The previous system stays behind `ai.USE_GIB = False`.
- Never quote a declaring-side figure for a competitive decision; use the head-to-head metric.
- Most constant-tuning is below the noise floor. Don't tune against an unpaired mean.
- `LENGTH_BONUS` and `GAME_TRICKS` are on the same scale and move together.
- The hand evaluator is at the information ceiling of card counting, and the notrump
  evaluation isn't worth improving. Don't reopen either without a new idea.

**Alerts and escaping** ([ARCHITECTURE](docs/ARCHITECTURE.md))
- An alert states what the call *shows*: every number it quotes must be true of the hand, it
  depends only on the auction and the call, it stays under 70 characters, and pass reasons are
  hidden while the board is live. The first two are machine-checked. The web app's bidding box
  explains every call by reading the robots' alerts, so it relies on the second.
- No `{@html}` in Svelte (a test bans it), so every string the app shows is escaped. The app
  takes text in two places, the self-alert box and LIN import; a new one needs the same care.

**Determinism** ([CHALLENGE](docs/CHALLENGE.md))
- `ai.py` imports no RNG, so the robot table and the benchmark cannot drift. `hands_for`
  rebuilds deals from stored text and must never reseed the global RNG.

**The Svelte port** ([FRONTEND](docs/FRONTEND.md))
- `frontend/src/lib/engine/` is a line-for-line port held to the Python by fixtures, with exact
  equality, floats included. **Change `ai.py` or `gib.py` and the port fails until it follows.**
- The History replayer's double dummy solver is `research/solver-rs` as WebAssembly, checked
  against the Python solver (`dd.test.ts`). It has no fallback, and its table is capped for
  phones (`TABLE_LIMIT`, 4M slots, 102 MB); a smaller cap costs time, never a value.

## Docs

| doc | read it when |
|---|---|
| [ROADMAP.md](docs/ROADMAP.md) | starting work without a specific request: the ordered list of next updates |
| [ROBOT_PROGRESS.md](docs/ROBOT_PROGRESS.md) | after measuring a robot change: add its row, kept or not |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | changing the Python modules, alerts or escaping |
| [BIDDING.md](docs/BIDDING.md) | touching `gib.py`, `ai_bid`, hand evaluation or any bidding constant |
| [CHALLENGE.md](docs/CHALLENGE.md) | touching challenge mode, grading or robot card play |
| [SOLVER.md](docs/SOLVER.md) | touching `bridge/solver/`, `research/solver-rs/` or the dataset |
| [FRONTEND.md](docs/FRONTEND.md) | working in `frontend/` |
| [HOSTING_AND_LOCAL_SAVES.md](docs/HOSTING_AND_LOCAL_SAVES.md) | changing the GitHub Pages deployment or browser-saved games |
| [ONLINE_PLAN.md](docs/ONLINE_PLAN.md) | planning accounts, saved hands or live tables |

When state changes, update the doc that owns it rather than growing this file.
