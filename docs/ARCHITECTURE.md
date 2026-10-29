# Architecture

How the Python codebase is layered: the domain engine the web app is ported from and held to, the solver, research tooling, and the rules for robot alerts.

Moved verbatim from `CLAUDE.md` on 2026-10-13, so it is read when the work needs it instead of loading into every session. [CLAUDE.md](../CLAUDE.md) keeps the guardrails and links here.

The Python code is the engine and nothing else: no UI. It is the reference the web app's
TypeScript port (`frontend/`, see [FRONTEND.md](FRONTEND.md)) is held to by fixtures, and
what every robot change is made and measured in first. The Streamlit app that used to sit
on it (`app.py`, `web/`, `styles.css`) was retired on 2026-10-21, once the web app had
everything it did, double dummy analysis included.

**`bridge/`** — pure domain logic (zero UI dependencies):
- `bridge/auction.py`: `AuctionState`, seating order, bidding ladder legal calls, pass-outs, declarer determination.
- `bridge/trick.py`: `legal_plays()`, `resolve_trick()` (Second-Highest winning mechanic).
- `bridge/scoring.py`: `score_contract()` (full duplicate bridge scoring engine).
- `bridge/lin.py`: LIN hand records, written and read back by replaying the board (see [FRONTEND.md](FRONTEND.md), LIN).

**`bridge/solver/`** — double dummy solver. Answers "how many tricks do N/S take with optimal play by both sides", which is unsolved for this variant, so the layering exists to keep correctness checkable:
- `bridge/solver/bitstate.py`: packed-int core. One 52-bit mask per seat, card index `suit * 13 + rank`. Deliberately free of `Card` objects so the hot loops stay cheap and the core stays portable.
- `bridge/solver/convert.py`: the *only* module that translates between domain objects and solver ints. The packed-int core (`bitstate`, `brute`, `search`) never imports `card`, `game` or `bridge.auction`; the domain-facing layer (`api`, `replay`) works in `Card`s and seat names and goes through `convert` for the ints.
- `bridge/solver/brute.py`: exhaustive enumeration, no pruning or memoisation. Defines what a correct answer is; kept permanently, never optimised.
- `bridge/solver/api.py`: **the layer the app and replayer should call.** Speaks seat names,
  `Card` and strain strings; validates positions and refuses malformed ones rather than
  answering them. `solve_deal`, `card_values`, `best_cards`, `single_dummy`.
- `bridge/solver/replay.py`: turns a finished board into the decisions worth
  reviewing, latest trick first, and analyses each through `api`. The values
  the web app's WebAssembly solver is checked against (`export_ts_fixtures.py`
  writes them for `dd.test.ts`); tested by `tests/test_solver_replay.py`.
- `bridge/solver/search.py`: the fast solver — zero-window alpha-beta, transposition table, rank-equivalence reduction, move ordering. Every reduction is sound, and each is independently switchable so a disagreement can be bisected.

**`research/`** — tooling that informs the engine, not the app:
- `research/dd_dataset.py`: generates double dummy trick counts for fitting bidding. For each deal it solves each side's best fit and notrump, with both sides declaring. Output is JSON Lines, one record per (deal, strain), at `research/data/dd_pilot.jsonl`, with progress in `research/data/dd_pilot.log`. Supports `--engine {python,rust}`.
- `research/slam_deals.py`: slam deals for bidding work. Random deals from seeds of its own, kept when a side holds a 9+ card fit, screened by solving that side's two best fits with it declaring, and solved in full (all five strains, both sides) when the screen finds 12+ tricks. Finished deals go to `research/data/dd_slam.jsonl` in `dd_pilot.jsonl`'s shape; every deal dealt, with its screen, to `research/data/dd_slam_screen.jsonl`. Not a random sample: keep it out of the challenge library and anything that averages over deals. Rust engine only.
- `research/hand_value.py`: fits hand evaluation and bidding policy to that dataset —
  rank values, the cross-validated point count, the notrump verdict, and score-ranked
  bidding policies, plus what the current `ai_bid` scores over the same deals. Read-only
  analysis; it never writes to the dataset. Conclusions are recorded under "Hand
  evaluation and bidding research" in [BIDDING.md](BIDDING.md) so they survive without re-running it.
- `research/solver-rs/`: a Rust port of `bridge/solver`'s production search (bitstate + search, hard-coded to the winning ablation settings — no `use_table`/`ordering` switches), built as a standalone CLI (`src/main.rs`) that `dd_dataset.py --engine rust` shells out to per (deal, strain) task. Not a redesign — same algorithm, same transposition table, same trick-first ordering. **Measured 63-72x faster** than the Python engine (identical answers; see Solver invariants in [SOLVER.md](SOLVER.md)). Build with `cargo build --release` in that directory. Its search also ships, as WebAssembly: `research/solver-rs/wasm` is the web app's History replayer solver (`npm run wasm`, [FRONTEND.md](FRONTEND.md)). The Python code never imports any of it. `tests/test_solver_rust.py` cross-validates it against the trusted Python search past the frozen fixture's depth, and skips cleanly (not a failure) if it isn't built.

**`card.py`** — pure card & deck primitives (`Card`, `deal()`, constants `SUITS`, `STRAINS`, `RANKS`, `bid_index`, `parse_bid`).

**`game.py`** — domain facade re-exporting the `bridge` engine. Not just for
backwards compatibility: `ai.py`, `challenge.py`, the solver's `api`/`replay` and
the tests import from it. (`bridge/__init__.py` re-exports the same names and is
unused.)

**`main.py`** — the original terminal game, kept but not maintained: no auction,
a fixed two-level contract, South always declares. It is what keeps
`card.auto_contract`, `bridge.scoring.score()` and `game.CONTRACT_LEVEL` alive,
and `tests/test_sim.py` exercises only it; the auction-driven game is covered by
`test_bidding.test_full_ai_game_simulation`.

**`ai.py`** — AI decision making (`eval_hand_sh` hand valuation, `ai_play` trick strategy, and `ai_bid`: GIB first, then the previous system's logic as the fallback for contested auctions).

**`tests/`** — modular test suite. `tests/fixtures/endings.json` is frozen ground truth for the solver, rebuilt only by `tests/fixtures/generate_endings.py`.

## Robot alerts

Robot bids are **alerted**: `ai.ai_bid_explained` returns `(call, explanation)`
alongside `ai_bid`'s bare call, and the web app stores each explanation against
its index in the auction and shows it on the call. The explanation is generated
on the decision path itself, not reconstructed afterwards, so it cannot drift
from what the AI actually did. `tests/test_bidding_calibration.py` checks that
every branch produces an explanation naming the suit it bid.

Alerts are written in the style of a real system card ("5+ ♠, 10+ points.") and
state what the call SHOWS, never what the hand holds — an earlier version said
"Opening — 5 spades, 14 points", which handed the reader partner's and the
opponents' actual cards. Two rules are machine-checked, because both were
broken by hand at some point:
- **Every number an alert quotes must be true of the bidding hand.**
  `test_every_number_an_alert_quotes_is_true_of_the_hand` parses each alert
  back out (length floors, point floors, ranges, "fewer than" and "or fewer"
  forms) and checks it against the hand. It caught a simple raise claiming the
  card's "6-9 points" on an 11-point hand 29 times, and a length-based rebid
  claiming "12+ points" on 9 points 19 times. An alert may quote a floor the
  branch **enforces**; it may not quote a range the branch does not. Where the
  call cannot distinguish two of the card's tiers (12-15 against 16-17 for a
  rebid), the alert quotes the floor — saying "16+" would leak strength the bid
  itself never showed.
- **A bid's alert depends only on the auction and the call, never on the
  hand.** `test_a_bid_alert_depends_only_on_the_auction_and_the_call` plays
  1,500 auctions and fails if the same call in the same auction ever reads
  two ways. It found five leaks at once: a rebid alerted "6+" or "12+" by
  branch, 1m alerted "3+/4+/5+" by the real minor lengths, a contested
  two-level bid "Forcing" or "Free bid", and an answer to a takeout double
  quoting the actual length and band. Each now quotes the floor every hand
  making that call shares. The Svelte app's bidding box depends on this:
  it explains any call by sampling hands and reading the robots' alert for
  it (`frontend/src/lib/meanings.ts`, see [FRONTEND.md](FRONTEND.md)), so a
  hand-dependent alert would show a player a meaning that is only true of
  some hands. The robots read each other's alerts too: the penalty double
  takes partner's point range from them, and a robot passes partner's
  double alerted "Penalty" (`ai_bid_explained`'s `alerts`, BIDDING.md).
- **Pass reasons are hidden while the board is live** (`Game.liveAlerts` in
  the web app, tested in `lin.test.ts`). "Fewer than 6
  points" versus "Fewer than 3 ♠ and no five-card suit" reads a robot's cards
  out, and a real table never alerts a natural pass. They stay in
  `bid_alerts` and appear on the result screen and in history.
- Alerts stay under 70 characters so they fit a tooltip.

Alert text reaches the page only as text: the web app renders no raw HTML
(`{@html}` is banned by `lin.test.ts`), so Svelte escapes it. The same holds for
the other places the app accepts text: the self-alert box, LIN import, and at a
multiplayer table your name (`cleanName`: one line, no invisible characters, 20
at most) and the "Report a problem" note. The note (`cleanNote`, 500 at most) is
never shown in the app at all: it goes to the server's game log and comes out
JSON-escaped in an export.
