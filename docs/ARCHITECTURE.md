# Architecture

How the Python codebase is layered: the domain engine, the Streamlit presentation, robot alerts and the HTML-escaping audit, and deploying the Streamlit app.

Moved verbatim from `CLAUDE.md` on 2026-10-13, so it is read when the work needs it instead of loading into every session. [CLAUDE.md](../CLAUDE.md) keeps the guardrails and links here.

The codebase is cleanly layered into pure domain engine, web presentation, styles, and tests:

**`bridge/`** — pure domain logic (zero UI dependencies):
- `bridge/auction.py`: `AuctionState`, seating order, bidding ladder legal calls, pass-outs, declarer determination.
- `bridge/trick.py`: `legal_plays()`, `resolve_trick()` (Second-Highest winning mechanic).
- `bridge/scoring.py`: `score_contract()` (full duplicate bridge scoring engine).

**`bridge/solver/`** — double dummy solver. Answers "how many tricks do N/S take with optimal play by both sides", which is unsolved for this variant, so the layering exists to keep correctness checkable:
- `bridge/solver/bitstate.py`: packed-int core. One 52-bit mask per seat, card index `suit * 13 + rank`. Deliberately free of `Card` objects so the hot loops stay cheap and the core stays portable.
- `bridge/solver/convert.py`: the *only* module that translates between domain objects and solver ints. Nothing else under `bridge/solver/` may import `card` or `bridge.auction`.
- `bridge/solver/brute.py`: exhaustive enumeration, no pruning or memoisation. Defines what a correct answer is; kept permanently, never optimised.
- `bridge/solver/api.py`: **the layer the app and replayer should call.** Speaks seat names,
  `Card` and strain strings; validates positions and refuses malformed ones rather than
  answering them. `solve_deal`, `card_values`, `best_cards`, `single_dummy`.
- `bridge/solver/search.py`: the fast solver — zero-window alpha-beta, transposition table, rank-equivalence reduction, move ordering. Every reduction is sound, and each is independently switchable so a disagreement can be bisected.

**`research/`** — tooling that informs the engine, not the app:
- `research/dd_dataset.py`: generates double dummy trick counts for fitting bidding. For each deal it solves each side's best fit and notrump, with both sides declaring. Output is JSON Lines, one record per (deal, strain), at `research/data/dd_pilot.jsonl`, with progress in `research/data/dd_pilot.log`. Supports `--engine {python,rust}`.
- `research/hand_value.py`: fits hand evaluation and bidding policy to that dataset —
  rank values, the cross-validated point count, the notrump verdict, and score-ranked
  bidding policies, plus what the current `ai_bid` scores over the same deals. Read-only
  analysis; it never writes to the dataset. Conclusions are recorded under "Hand
  evaluation and bidding research" in [BIDDING.md](BIDDING.md) so they survive without re-running it.
- `research/solver-rs/`: a Rust port of `bridge/solver`'s production search (bitstate + search, hard-coded to the winning ablation settings — no `use_table`/`ordering` switches), built as a standalone CLI (`src/main.rs`) that `dd_dataset.py --engine rust` shells out to per (deal, strain) task. Not a redesign — same algorithm, same transposition table, same trick-first ordering. **Measured 63-72x faster** than the Python engine (identical answers; see Solver invariants in [SOLVER.md](SOLVER.md)). Build with `cargo build --release` in that directory; nothing else in the project builds or requires it, and the app never touches it. `tests/test_solver_rust.py` cross-validates it against the trusted Python search past the frozen fixture's depth, and skips cleanly (not a failure) if it isn't built.

**`card.py`** — pure card & deck primitives (`Card`, `deal()`, constants `SUITS`, `STRAINS`, `RANKS`, `bid_index`, `parse_bid`).

**`game.py`** — high-level domain facade re-exporting `bridge` engine components for backwards compatibility.

**`ai.py`** — AI decision making (`eval_hand_sh` hand valuation, `ai_play` trick strategy, and `ai_bid`: GIB first, then the previous system's logic as the fallback for contested auctions).

**`web/`** — Streamlit presentation components:
- Robot bids are **alerted**: `ai.ai_bid_explained` returns `(call, explanation)`
  alongside `ai_bid`'s bare call, `app.py` stores each explanation against its index
  in the auction, and `call_badge(call, alert=...)` renders a marker plus a hover
  tooltip. The explanation is generated on the decision path itself, not
  reconstructed afterwards, so it cannot drift from what the AI actually did.
  Alert text reaches the page through `unsafe_allow_html` and is escaped in
  `call_badge`; `tests/test_bidding_calibration.py` guards both the escaping and
  that every branch produces an explanation naming the suit it bid.
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
    making that call shares.
  - **Pass reasons are hidden while the board is live** (`live_alerts` in
    `web/auction_view.py`, `Game.liveAlerts` in the port). "Fewer than 6
    points" versus "Fewer than 3 ♠ and no five-card suit" reads a robot's cards
    out, and a real table never alerts a natural pass. They stay in
    `bid_alerts` and appear on the result screen and in history.
  - Alerts stay under 70 characters so they fit a tooltip.
- **`unsafe_allow_html` and why it is currently safe** (`tests/test_web_escaping.py`).
  The app renders its own markup: 33 `unsafe_allow_html` sites and 1,187 lines of
  hand-written CSS. Seven sites are static literals; 26 build HTML from data.
  **No current vulnerability exists, and the reason is structural, not careful
  coding.** Until self-alerts and LIN import, the app had no text input at all.
  It now has exactly three, each reviewed (`REVIEWED_INPUTS`): the self-alert
  `text_input`, and LIN import's `text_area` and `file_uploader`. Both features
  deliver only **alert text** to the page, and only through `call_badge`,
  which escapes it. `from_lin` rebuilds every other field from a fixed
  vocabulary (seats, the 52 cards, legal calls, vulnerabilities) or an
  integer, and reads past LIN player names and board titles. LIN parse errors
  can quote the input, so they are shown with `st.code`. Everything else
  interpolated is still a seat name from a fixed list, a `Card` from a fixed
  deck, an integer, or alert text that `ai.py` generates.
  That is a snapshot, not a guarantee, so it is now enforced:
  - Every caller-supplied string that reaches markup is escaped with
    `html.escape(value, quote=True)`. Writing the test found **two genuinely
    unescaped paths** that the audit by eye had missed — `_call_inner`'s fallback
    branch (`<span class="bid-pill">{call}</span>`) and `seat_box_html`'s seat and
    role — plus raw ranks in `hand_diagram_html` and `felt_table`. None was
    reachable with hostile data; all are escaped now.
  - Values from a dict lookup keyed by suit (colours, pips, suit names) are
    deliberately NOT escaped: an unknown suit raises `KeyError`, which fails closed.
  - `test_every_free_text_input_has_been_reviewed` fails the moment an input
    widget appears that is not in `REVIEWED_INPUTS`: each new one needs its own
    trace through the 26 data-driven sites. Two end-to-end tests type hostile
    payloads into the self-alert box and into an imported LIN (as alerts and as
    player names) in the running app, and check the page.
  - The escaping test asserts on **tag openings** (`<script`, `<img`, …), not on
    keywords. An earlier version banned `onerror=` and failed on correctly-escaped
    output — once `<` and `"` are entities, `onerror=alert(1)` is inert text. An
    over-strict security test is one that gets switched off.
- `web/card_component.py`: styled card chips, static hands, and interactive hand clickers.
- `web/felt_table.py`: central green felt table canvas, card slots, and dynamic role badges.
- `web/replayer_view.py`: hand history selector, compass deal diagram, card-by-card
  replayer controls, and trick log. It renders any record of the hand-history
  shape, which is why challenge mode can step through a ROBOT board with no
  changes here: `challenge.as_history_record` shapes one identically, and a
  record may carry its own `label` so "your board" and "the robots' board" sit
  in the same selector on the same deal. It was also dropping `bid_alerts` when
  it drew the auction, so a reviewed board showed a grid of calls with no
  explanation — the alerts are passed through now, on both human and robot
  boards.

**`app.py`** — primary Streamlit web application state machine orchestrating game phases and rendering tabs.

**`styles.css`** — CSS theme for card chips, green felt canvas, auction badges, and responsive tables.

**`tests/`** — modular test suite. `tests/fixtures/endings.json` is frozen ground truth for the solver, rebuilt only by `tests/fixtures/generate_endings.py`.

## Deploying the Streamlit app

**Deployment.** The app's only third-party dependency is `streamlit`
(`requirements.txt`); it writes nothing to disk, keeps all game state in
`st.session_state`, and holds no mutable module-level state, so concurrent
players cannot interfere. The deployable footprint is about 420 KB (the deal library grew from 96 to 130 KB at 400 deals) — `research/` is
not imported by the app and `research/solver-rs/target/` (49 MB) is gitignored.
The one deployment hazard is `web/analysis_view.py`: it runs the double dummy
solver interactively, offers a depth costed at ~5 minutes, and caches results in
an `@st.cache_resource` dict that Streamlit shares across **all** sessions and
never evicts. Cap the depth and bound that cache before exposing it publicly.
