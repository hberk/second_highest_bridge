# Code analysis — 17 October 2026

A whole-repository review: correctness, security, tests, CI, documentation
accuracy and strategy. Line numbers refer to commit `e8da9f0` on
`felt-redesign`. The next commit, `b0a9795`, changed only five frontend view
and style files, so references outside those files still hold.

## Summary

The game core is sound. Scoring, the auction and trick resolution were each
checked against an independent re-implementation and matched on every case
tried. The solver's pruning is valid under the second-highest rule, the
TypeScript port reproduces even CPython's float summation, and neither app has
an injection hole. The problems are at the edges:

- **H1.** A human can make the robots crash in one specific auction
  (1M–2M–3NT), in both the Streamlit app and, very likely, the web app.
- **H2.** Challenge grading can compare a board against a double-dummy count
  that was solved with the other partner as declarer.
- **H3.** The Streamlit analysis panel is still uncapped, against the
  project's own guardrail.
- **H4.** Two tests fail intermittently, and one of them is keeping a
  Dependabot PR red.
- About a dozen documentation statements have gone stale.

## How this was done

Eleven reviewers ran in parallel, each scoped to one area:

- game core
- solver
- bidding
- card play and challenge mode
- the Streamlit app
- the Svelte app layer
- engine-port parity
- LIN and research code
- documentation accuracy
- tests, CI and repository hygiene
- strategy

Several of them wrote throwaway scripts to test claims by running code, not
just reading it. Every High finding was then re-checked by hand.

Each finding carries one of these statuses:

| status | meaning |
|---|---|
| **Reproduced** | the failure was triggered by running code during the audit |
| **Confirmed** | the code path was read and checked against the claim |
| **Likely** | reported from reading by one reviewer, not independently re-checked |

One reviewer reported that the parity gate never runs because the repository
is private. That is wrong: the repository is public, and CI runs on every push
and pull request.

## Test runs

| suite | result |
|---|---|
| `npm test` (frontend) | 53 / 53 pass |
| `npm run check` (svelte-check) | 0 errors, 0 warnings, 166 files |
| `python tests/run_all.py` | 222 / 223 pass; 1 intermittent failure (H4) |
| Rust solver (`cargo test`) | not run: no Rust toolchain on this machine |

The Python suite ran on 3.13 with Streamlit 1.66, in a scratch virtualenv. The
`.venv/` that CLAUDE.md describes doesn't exist on this machine, and 3.12 (the
reference) isn't installed. 3.13 sums floats the same way 3.12 does.

The five tests in `tests/test_solver_rust.py` return early when the binary
isn't built, and `run_all.py` counts them as passes (M6). So 222 includes
tests that never ran.

---

## High

### H1. Robot bidding crashes after a human 1M–2M–3NT

- **Where:** `responder_rebid` in [gib.py:716-717](../gib.py#L716-L717); the
  same branch in the port is
  [gib.ts:688-690](../frontend/src/lib/engine/gib.ts#L688-L690).
- **Status:** Python: Reproduced. TypeScript: Likely.

**What happens.** After opener's major is raised to two (1♠–2♠), the branch
`if ol == 3 and os_ != x` treats any three-level rebid by opener in another
strain as a help-suit game try. When opener rebids 3NT, `os_` is `'NT'`, and
`h.len['NT']` raises `KeyError`. Short-circuiting means this only happens when
responder's count is exactly 8:

- With 9 or more, responder bids 4M.
- Otherwise the branch returns 3M ("Declining the game try."). That is
  illegal over 3NT, so the guard turns it into a pass.

Robots never bid this sequence themselves; only a human South does.

**Impact.**

- In Streamlit, [app.py:83](../app.py#L83) calls `ai_bid_explained` with no
  error handling, so the user gets a script error.
- In the web app, `h.len['NT']` is `undefined`, the comparison is false, and
  `h.top('NT', …)` then reads a suit group that doesn't exist. That should
  throw a `TypeError`. The `as Suit` casts hide this from the type checker.
- The parity fixtures can't catch it. Both engines fail the same way, and the
  fixtures' random South only bids up to roughly 2♠.

**Reproduction** (29 of 300 random North hands crash):

```python
import ai
from card import Card
from bridge.auction import AuctionState

def hand(text): return [Card(t[-1], t[:-1]) for t in text.split()]

north = hand('AS 9S 7S KH 8H 4H 3H 2H 8D 7D 10C 9C 3C')
a = AuctionState(dealer='South')
for seat, call in [('South', '1S'), ('West', 'Pass'), ('North', '2S'),
                   ('East', 'Pass'), ('South', '3NT'), ('West', 'Pass')]:
    a.apply_call(seat, call)
ai.ai_bid_explained('North', north, a)   # KeyError: 'NT' at gib.py:717
```

**Fix.**

1. The minimal fix is to keep notrump out of the game-try branch
   (`os_ in SUITS`) in both `gib.py` and `gib.ts`.
2. What responder should do over 3NT is a system decision, normally pass or
   correct to 4M as a choice of games. It belongs with the other handoff work
   in ROADMAP §1.
3. Add the fuzz test described under M4, so the next branch like this is
   caught.

### H2. Challenge grade can use the wrong declarer's double-dummy count

- **Where:** [challenge.py:242](../challenge.py#L242);
  `declarer_for` in [research/dd_dataset.py:154-165](../research/dd_dataset.py#L154-L165).
- **Status:** Confirmed. The size of the error hasn't been measured.

**What's wrong.**

- The solved library stores tricks per strain and per side (`"C:N/S"`).
- The dataset solved each side with one declarer chosen by a rule: the longer
  partner in the suit, or the one with more HCP in notrump, with ties going to
  North or East. The opening lead came from that seat's left.
- `grade()` calls `dd_tricks(deal_id, strain, side)` and never looks at
  `contract['declarer']`.

When the auction puts the contract in the other hand, the opening leader is
different and the double-dummy count can change by a trick or more. That
difference is then reported as `play_loss`, and through `dd_score` it also
shifts `bidding_loss`. No doc mentions this.

**Fix.** Either solve both declarers per side and key the library by
`strain:declarer` (the Rust engine makes the doubled solve affordable), or
record which declarer was solved and flag mismatched boards in the grade.
Until then, CHALLENGE.md should state the limitation.

### H3. The Streamlit analysis panel is uncapped and its cache is unbounded

- **Where:**
  - [web/analysis_view.py:29-34](../web/analysis_view.py#L29-L34) (depth
    choices go up to 10 tricks, "~5 min")
  - [:45-48](../web/analysis_view.py#L45-L48) (`_analysis_cache()` is a
    plain `{}` under `st.cache_resource`, shared by every session and never
    evicted)
  - [:121-134](../web/analysis_view.py#L121-L134) (the slice loop)
  - It's reached from [web/replayer_view.py:151-152](../web/replayer_view.py#L151-L152)
    for any finished board in History, LIN imports included.
- **Status:** Confirmed (depth and cache); the effect on the game tab is Likely.

**What's wrong.**

- ARCHITECTURE.md's guardrail says to cap the depth and bound the cache before
  exposing the panel publicly. Neither has been done.
- The 1.5-second slice deadline is only checked between decisions, so one deep
  decision can hold the script thread far longer than a slice.
- Each slice ends in `st.rerun()`, which aborts the run before the Game tab
  renders. The table is unresponsive for the whole analysis.

This matters only if the Streamlit app is deployed publicly. `.python-version`
is pinned for Streamlit Community Cloud, which suggests it is or will be.

**Fix.**

- Cap the depth at 8 in deployed builds, for example behind an environment
  flag.
- Bound the cache with LRU by entry count.
- Consider limiting analysis to boards played at the table.

### H4. Two intermittent test failures

- **Status:** Reproduced (Python); on record in CI (TypeScript).

**The frontend test.** "last trick is offered from trick 2 on", in
[frontend/src/lib/qol.test.ts:65-81](../frontend/src/lib/qol.test.ts#L65-L81):

- `new Game()` deals through `Math.random`, ten boards are played, and the
  test asserts that "Last trick" was offered at least once.
- It failed CI on Dependabot PR #6 (the Streamlit floor bump, which can't
  affect the frontend) with `expected 0 to be greater than 0`. PR #6 is still
  red.
- Other tests in the same file use the same unseeded pattern.

**The Python test.**
`test_app_flow.test_a_self_alert_goes_with_the_call_and_shows_even_on_a_pass`:

- It failed 1 run in 7 locally ("a human's alerted pass must show while the
  board is live").
- `tests/test_app_flow.py` never seeds `random`, so each run plays different
  deals.

**Fix.** Give `Game` an injectable deal or RNG for tests, and seed `random`
at the top of each app-flow test, or pin the deals.

---

## Medium

### M1. The challenge review can show an imported board as "Your board"

- **Where:** [app.py:516-518](../app.py#L516-L518) and
  [frontend/src/lib/views/ChallengeView.svelte:16](../frontend/src/lib/views/ChallengeView.svelte#L16).
  The Svelte case is ROADMAP 3.4.
- **Status:** Likely. Two reviewers found it independently, one in each app.

The lookup matches on `board_num` alone, and imported LIN boards take their
number from the LIN `ah` tag. Finish challenge board 7, import a LIN whose
`ah` says "Board 7", and the review steps through the imported deal as your
play. `web/session_view.py:34` already filters out imported boards; this
lookup should too, and should also compare the deal (as `saves.boardKey`
does).

### M2. Streamlit never shows the 13th trick

- **Where:** [app.py:190-205](../app.py#L190-L205) and
  [app.py:568](../app.py#L568); dead branches at
  [788-796](../app.py#L788-L796) and 839-840.
- **Status:** Confirmed (the state flow).

`_end_trick` sets `phase = 'trick_done'` and then, after the 13th trick,
`game_over = True` in the same call. The game-over check at line 568 runs
before the phase branch, so the player goes straight to the result screen. The
last trick and its winner never appear on the felt, and the "See final score →"
button can never be shown.

### M3. Robot defenders treat their own cards as unseen when deciding to cover

- **Where:** [ai.py:1113](../ai.py#L1113), in `_cover_for_partner`; the TS
  twin is `coverForPartner` in `ai.ts`.
- **Status:** Confirmed.

The code is `seen = set(played) | {trick cards} | set(legal)`. That uses the
legal plays, not the whole hand, and `visible_hands`
([ai.py:1038-1050](../ai.py#L1038-L1050)) never includes the robot's own hand.
So when a defender follows suit, its off-suit cards become candidates for the
third player's ruff or discard (lines 1122-1127).

- **Why it matters:** under this rule the lower of two trumps wins, so
  modelling an opponent ruffing with a trump the robot itself holds changes
  the decision.
- **What the docs say:** CHALLENGE.md:46-48 says these candidates are "drawn
  only from cards the robot cannot see".
- **How the neighbours do it:** `_later_holdings` (line 997) and
  `_endgame_totals` (line 1218) correctly use `set(hand)`.

**Fix.** Pass `hand` in. The port must change in step, and the challenge
benchmark should be re-measured head to head.

### M4. GIB makes illegal calls when a human is in the auction

- **Where:** several branches in `gib.py` that have no `ctx.ok()` check; the
  guard is at [gib.py:207-225](../gib.py#L207-L225).
- **Status:** Reproduced (fuzz: about 840,000 robot calls).

| setup | illegal calls |
|---|---|
| 30,000 robot-only auctions | 0 |
| 60,000 auctions with a random human South or opponent | 72 |

The guard turns each one into a continuation or a pass, so play continues,
but the call's intended meaning is lost. Grouped by alert:

- **"5 ♠/♥, choice of games." (37 of them):** returns 3NT when 3NT has
  already been bid, e.g. 1NT–2♥–3NT, or 1NT–2♥–(X)–4♣.
- **"Invitational.":** returns 3♠ after 1NT–2♣–3♠.
- **"To play.":** returns 3NT after 1♦–3♦–4♦. It also returns 6♠ after
  East's 6NT interference over the robots' own keycard auction.
- **"Declining the game try.":** this is H1.

`gib.py:208` says "Tests assert this stays at zero". That holds only for
robot-only suites. The exported parity fixtures contain one such case too:
1NT–2♦–3NT, with the 3NT bid by the random South.

**Fix.** Add a fuzz test with a random human seat, or a random opponent, that
asserts no exception and an empty `gib.ILLEGAL`. Then fix the branches it
reports.

### M5. LIN import: the two parsers disagree, and hostile input isn't bounded

- **Status:** Confirmed for the first item; Likely for the rest.
- **Vulnerability lookup reaches the prototype**
  ([lin.ts:170](../frontend/src/lib/lin.ts#L170)). `VUL_FROM_LIN` is a plain
  object, so `sv|constructor|` and `sv|toString|` return a truthy built-in
  and are accepted. Python refuses them. Use `Object.hasOwn` or a `Map`.
- **Claims (`mc`) are parsed differently.** TypeScript uses `Number()`, so
  `mc||` imports as 0 tricks and `0x5` or `1e1` are accepted. Python's
  `int()` refuses all of these. Both should require `/^\d{1,2}$/`.
- **Board numbers (`ah`):** Python's `\d` matches Unicode digits, and an
  overlong digit run makes `int()` raise. TypeScript produces `Infinity`.
- **Byte-order mark:** Python decodes uploads as `utf-8`, not `utf-8-sig`
  ([web/replayer_view.py:38](../web/replayer_view.py#L38)), so a .lin file
  starting with a BOM is refused. TypeScript accepts it.
- **No size or board-count limit** in either app. Imported `an|` alerts also
  skip the 70-character, control-character cleanup that typed alerts get
  ([lin.ts:186-188](../frontend/src/lib/lin.ts#L186-L188),
  [lin.py:219-223](../bridge/lin.py#L219-L223)), so a large file can fill
  `localStorage`. Svelte escapes the text, so this is not XSS.
- **Re-importing the same LIN duplicates every board**
  ([game.svelte.ts:201-204](../frontend/src/lib/game.svelte.ts#L201-L204)).
- **What would catch these:** one hostile-input fixture run through both
  parsers, asserting the same accept or refuse outcome.

### M6. The test runner hides failures and skips

- **Where:** [tests/run_all.py:17-30](../tests/run_all.py#L17-L30);
  `tests/test_solver_rust.py`.
- **Status:** Confirmed.
- **Import outside the `try`:** `importlib.import_module` runs outside the
  `try`, so one module that fails to import ends the whole run with no
  summary. That breaks the runner's promise to report every failure.
- **Skips count as passes:** the five Rust tests `return` early when the
  binary is missing, and that counts as PASS.
- **No CI coverage for Rust:** no CI job builds or tests the Rust solver.
  `RUST_EXE` hard-codes `solver-rs.exe`, so on Ubuntu the tests would skip
  even if it were built. Dependabot's cargo PR (#4) is therefore checked by
  nothing.
- **Fix:** move the import inside the `try`, and add a real SKIP status. Then
  either build and test the solver in CI, or say plainly that it's untested
  there.

### M7. One worker failure throws away a whole dataset run

- **Where:** [research/dd_dataset.py:369-390](../research/dd_dataset.py#L369-L390).
- **Status:** Reproduced. In the reviewer's script, 8 tasks ran, task 0
  raised, the other seven finished, and **0 records** were written.
- **What's wrong:** on an exception, `finally: pool.close(); pool.join()` waits
  for every queued solve and then discards the results.
- **Fix:** call `pool.terminate()` on error, and write each record as it
  arrives.
- **Related:** `RUST_TIMEOUT_SECONDS = 1800` (lines 79-82, 239-242) contradicts
  "the dataset never times out". It aborts the run rather than skipping the
  deal, so the data isn't biased, but a deal slower than 30 minutes fails on
  every resume.

### M8. The web app can lose a pass-out from its count after a failed save

- **Where:** [frontend/src/lib/game.svelte.ts:184-196](../frontend/src/lib/game.svelte.ts#L184-L196).
- **Status:** Likely.
- **What's wrong:** `persist()` calls `adopt(merged)`, which advances
  `passedOutSynced`, before it knows whether `saveGames` succeeded.
- **Effect:** a pass-out recorded while storage is full is never stored, and
  the session scoreboard drops back on the next successful save.
- **Fix:** advance the marker only after a successful write.

### M9. Dealing a challenge board throws away the board in progress

- **Where:** [app.py:491-495](../app.py#L491-L495); `ChallengeView.svelte:20-22`
  → `game.svelte.ts:239-244`.
- **Status:** Likely. It may be intended.
- **What's wrong:** there is no confirmation and no record of the abandoned
  board.
- **Effect:** an unfinished challenge board goes back into the pool, so a
  player can look at a deal, abandon it, and replay it later knowing the
  cards.
- **Fix:** ask for confirmation, or disable the button, while a board is live.

### M10. Some research statistics overstate significance

- **Status:** Likely.
- **[research/gib_h2h.py:55-75](../research/gib_h2h.py#L55-L75):** the 1,600
  boards are 400 deals × 4 dealers, but the t-test treats them as independent.
  Boards from the same deal are correlated, so the standard error is too
  small. The quoted "+1.64, t=+2.06" rests on 28 boards that differ and is
  borderline once grouped by deal. Each new branch is also tested on the same
  400 deals its examples were taken from. Fix: average the four dealers per
  deal and test on n = 400.
- **[research/hand_value.py:290-340](../research/hand_value.py#L290-L340):**
  the policies use the in-sample fit, and the game threshold is picked on the
  same cases it is scored on. Use the out-of-fold predictions.
- **[research/evaluator_search.py:164-184](../research/evaluator_search.py#L164-L184):**
  the winner is the lowest of six CV errors with no nested CV, so its error is
  biased low.

This is consistent with the existing guardrail that most constant-tuning is
below the noise floor.

### M11. The analytics script is not pinned and not documented in the hosting doc

- **Where:** [frontend/index.html:34](../frontend/index.html#L34).
- **Status:** Likely (the `type="module"` effect is speculative).
- **What's wrong:**
  - The Cloudflare beacon has full DOM and `localStorage` access but loads
    without Subresource Integrity.
  - It loads as `type="module"`, whereas Cloudflare's snippet is a classic
    `defer` script, and module scripts need CORS headers. The beacon may be
    failing silently.
  - SECURITY.md describes the analytics, but HOSTING_AND_LOCAL_SAVES.md
    doesn't.

---

## Low: code quality

**Legacy and dead code**

- **The legacy terminal game:** `main.py` has no auction, a fixed 2-level
  contract, and South always declaring. It keeps `card.auto_contract`,
  `bridge/scoring.score()` and `game.CONTRACT_LEVEL`/`TRICKS_NEEDED` alive.
  `tests/test_sim.py` exercises only this path; the real auction-driven game
  is covered by `test_bidding.test_full_ai_game_simulation`.
- **Dead state:** `AuctionState.doubled_by` is written and never read
  (`ai.py:242` rescans the calls instead). After a redouble it holds the
  redoubler.
- **Unreachable code:** the declarer fallback at
  [bridge/auction.py:117-118](../bridge/auction.py#L117-L118) can never run.
- **Unused names:**
  - imports: `Card` (`auction.py:2`); `SUITS` and `LEVELS` (`scoring.py:2`)
  - unpacked variables: `high_level` and `high_strain` (`auction.py:45, 50`)
  - parameters: `trump` (`main.py:83`)
  - in `ai.py`: `level` and `word` in `_place`; `_strains_bid_by` has no
    callers; `_promise_name` feeds a `shown` variable that is never read.
- **Duplicate facades:** `game.py` and `bridge/__init__.py` both re-export
  the engine. Only `game.py` is used.

**Mutable state and untested paths**

- **Module-level lists that grow:** `gib.ILLEGAL` grows for the life of a
  Streamlit process (ROADMAP 3.5). `challenge.load_library` hands out one
  shared, mutable cached dict.
- **Paths never run in tests:**
  - `ai.USE_GIB = False`, the preserved previous system;
  - the option flags (`useGib`, `judgeByVariant`, `cueLimitAt3`,
    `lastHandForPartner`), which are never exported to the parity fixtures.
- **What the fixtures never exercise:**
  - a redoubled contract, or a contract above the 6 level;
  - a challenge grade for E/W, or for a contract a human reached.

**Stale comments and figures**

- **Wrong location:** `gib.py:10` and `ai.py:29` say the measurements are in
  CLAUDE.md. They moved to `docs/BIDDING.md`.
- **Out-of-date docstring:** `ai_bid` says a trump card is worth "about 1.15
  tricks" and "95%". `TRUMP_CARD` is 1.025, and the doc says 94%.
- **Python and TS disagree:** the cuebid cost is −16.4 a board in
  `ai.py:701-708` and −4.1 in `ai.ts:371`.
- **Challenge loss figures:** the caption the user sees is
  [web/challenge_view.py:116-119](../web/challenge_view.py#L116-L119)
  (149 / 28), its own docstring says 144 / 32, and CHALLENGE.md's table says
  143.7 / 31.8. All of these predate the card-play changes that CHALLENGE.md:51
  reports.
- **Shared-stylesheet comment:** `frontend/vite.config.ts:5-6` says the
  stylesheet is shared from the repo root, but `table.css` is now a ported
  copy.
- **Wrong test description:** the docstring of
  `test_rust_cli_agrees_on_a_slice_of_the_measured_full_deal` says it uses
  the seed-0 benchmark deal. It doesn't.

**Streamlit**

- **Shadowed variable:** `key` shadows the function parameter in
  [web/analysis_view.py:124](../web/analysis_view.py#L124), so the "Clear
  results and retry" button gets a key that the next run doesn't render, and
  its click is dropped.
- **Shared widget state:**
  - the analysis widgets are keyed by `board_num`, so an imported board #N
    shares state with your own #N;
  - `chal_rep_step_{sel_idx}` carries the replay step into the next challenge
    review.
- **Bidding-box keys never change**, so a double-click could apply a call
  twice (speculative).
- **No input limits:** the LIN `text_area` has no `max_chars`, and the
  uploader allows Streamlit's 200 MB default.
- **Escaping test misses the app's own helpers:**
  `tests/test_web_escaping.py` doesn't reach `app.py`'s HTML helpers
  (`scoreboard`, `ai_seat_panel`, `vul_pills_html`). Their inputs are all
  fixed today.

**Card play and challenge**

- **Discards waste trumps:** the "duck" fallback (`min` by card value, at
  `ai.py:1301, 1325`) ignores suit, so a void robot can throw its lowest trump
  instead of a low side card.
- **Leads ignore visible cards:** `_lead` and `_gap` don't take `visible`, so
  dummy's cards count as cards an opponent could hold.
- **Unflagged scoring:** if the 60-call guard trips, the incomplete auction is
  scored with no flag (`challenge.py:144-152`).
- **Inconsistent result shape:** the passed-out grade dict has no `dd_tricks`
  key.

**Solver**

- **A second copy of follow-suit:** `replay.py:41-48` re-implements the rule
  instead of calling `bridge.trick.legal_plays`.
- **Translation outside `convert.py`:** `api.py` and `replay.py` import `card`
  and `game`, and translate seats themselves (`PLAYERS.index`). That
  contradicts `convert.py:5-7` and ARCHITECTURE.md:16. `api.FULL_DECK` (a list
  of Cards) also shares a name with `bitstate.FULL_DECK` (an int).
- **Rust input validation (`main.rs`):**
  - uneven hands aren't rejected;
  - a trick with 4 or more cards panics;
  - the branch at lines 142-146 is unreachable.
- **Dataset reading:**
  - `zip()` at `dd_dataset.py:254` silently truncates a short result list;
  - `RUST_EXE` ignores `CARGO_TARGET_DIR` and doesn't detect a stale binary;
  - `dd_dataset.py:92` reseeds the global RNG and is imported by tests.

**Frontend**

- **Accessibility:**
  - `Sheet.svelte` sets `aria-modal` but doesn't trap focus or return it on
    close;
  - screen readers aren't told about the BidPad meaning box;
  - the `glow` animation (`table.css:262`) ignores `prefers-reduced-motion`.
- **Saves:** there is one backup slot, and each failed load overwrites it.
  The HistoryView selection is an array index that another tab's update can
  shift (speculative).
- **Install settings:** `manifest.webmanifest` locks orientation to portrait,
  even though a desktop layout exists.
- **Duplicated code:** the session-score calculation and `signed()` are
  repeated across `TableView`, `DesktopTableView` and `SessionScore`.

**Small invariant gaps**

- **Missing future import:** six non-empty `__init__.py` files lack
  `from __future__ import annotations`: `bridge/`, `bridge/solver/`,
  `research/`, `tests/`, `tests/fixtures/` and `web/`.
- **`Card` equality and hashing:** `Card.__eq__` should return
  `NotImplemented` for non-cards. `Card` is mutable but hashable.

**CI and repository**

- **Deploy workflow (`pages.yml`):**
  - `cancel-in-progress: true` applies to `main`, so a newer push can cancel a
    Pages deploy mid-flight;
  - actions are pinned by tag, not SHA;
  - no job sets `timeout-minutes`;
  - the build job runs the fixture export without `pip install`, which works
    only while the exporter needs nothing outside the standard library.
- **Waiting Dependabot PRs:** four have been open since 14 October: #4 cargo,
  #5 actions, #6 Streamlit (red, H4) and #7 frontend.
- **Untracked folders:**
  - `.playwright-mcp/` (about 1.7 MB of screenshots and logs) isn't ignored,
    so `git add -A` would commit it;
  - `research_notes/` is untracked.
- **Tracked files that may not belong:**
  - `second-highest-bridge.mp4` (2.18 MB, about 80 % of the git pack) is
    referenced by nothing and isn't in LFS;
  - `research/data/dd_pilot.log` is tracked.
- **Undeclared dependency:** Pillow, which `frontend/scripts/make_icons.py`
  needs, isn't declared anywhere.

---

## Documentation accuracy

Most of the documentation checks out:

- All 48 relative links and anchors resolve.
- Every named constant, function, command and npm script exists.
- Most counts hold: 400 solved deals, 1,200 fixture games, 40 seeded games,
  1,500 auctions, the 70-character alert cap and `MAX_SAVED_BOARDS = 500`.
- The ticked ROADMAP items are backed by commits.

These statements are wrong or stale:

| where | says | actually |
|---|---|---|
| CLAUDE.md:43, ROADMAP.md:155 | the suite has 220 tests | 223 |
| CLAUDE.md:48 | a 3.12 virtualenv lives in `.venv/` | not present on this machine (it's gitignored and machine-local) |
| CLAUDE.md:81 | all files start with `from __future__ import annotations` | six `__init__.py` files don't (see above) |
| CLAUDE.md:85 | "`main.py`'s game loop" | true, but `main.py` is an undocumented legacy game with no auction |
| ARCHITECTURE.md:16 | nothing under `bridge/solver/` but `convert.py` may import `card` or `bridge.auction` | `api.py:22-23` and `replay.py:18-19` import `card` and `game` |
| ARCHITECTURE.md:34 | `game.py` is a facade "for backwards compatibility" | it's a live dependency of `ai.py`, `challenge.py` and the solver |
| ARCHITECTURE.md:81 | 33 `unsafe_allow_html` sites, 1,187 lines of CSS | 42 sites, 1,256 lines (the same stale figures are in `tests/test_web_escaping.py:3, 141`) |
| ARCHITECTURE.md:134 | the app holds no mutable module-level state | `gib.ILLEGAL` (ROADMAP 3.5 also attributes this claim to CLAUDE.md; it's in ARCHITECTURE.md) |
| ARCHITECTURE.md:9-21 | module lists | omit `bridge/lin.py`, `bridge/solver/replay.py`, and the `analysis_view`, `auction_view`, `challenge_view` and `session_view` web modules |
| HOSTING_AND_LOCAL_SAVES.md:44-45 | "No routes: the tabs are component state, not URLs" | the redesign added hash routing (`App.svelte`), as FRONTEND.md describes |
| HOSTING_AND_LOCAL_SAVES.md:27-28 | the CI gate is the fixtures plus the npm steps | `pages.yml` also runs the Python suite, and deploy needs it |
| HOSTING_AND_LOCAL_SAVES.md:78 | Display → Saved on this device | "Display" is the desktop menu only; on phones it's the gear sheet |
| BIDDING.md:152 | `harness.run` | no `harness` module exists, now or in history |
| BIDDING.md:495 | `PARTNER_PROMISE` | no such name; `ai.py` has `PROMISE_SHIFT`, `PROMISE_OPENED`, … |
| ONLINE_PLAN.md:176 | a `SeatPanel` component | the components are `SeatBox` and `SeatCard` |
| requirements.txt:10 | solver-rs "is excluded from the repo" | its sources, `Cargo.lock` and tests are tracked; only `target/` is ignored |
| .gitignore:28 | `dd_pilot.jsonl` is 964 KB | 1,322,307 bytes |
| gib.py:208 | tests keep `ILLEGAL` at zero | only robot-only tests do (M4) |

Not documented anywhere:

- `bridge/solver/replay.py` and its tests;
- `web/challenge_view.py`;
- `main.py`;
- `.streamlit/config.toml`;
- `.github/dependabot.yml`;
- `frontend/src/lib/trickText.test.ts`.

`test_challenge.py`, `test_web_escaping.py` and `test_solver_replay.py` are
missing from the command lists in CLAUDE.md and SOLVER.md. The engine port has
no `trick.ts`: `legalPlays` and `resolveTrick` live in `auction.ts`.

---

## Strategy

**Implied goal.** Three layers:

1. A free, no-account game for bridge players.
2. A research instrument for a variant that had never been solved; the solved
   library and the par-split grading are genuinely novel.
3. Eventually, play with friends.

The roadmap serves the first two well and correctly waits on evidence before
starting the third.

**What's working**

- **The roadmap order is sound.** GIB's handoff gaps come first: 14.9 % of
  calls on 48 % of boards fall to a fallback that never doubles.
- **The GIB decision is coherent.** The cost is recorded honestly, the old
  system is preserved, and familiar bidding matters more than the measured
  score for this audience. GIB's alerts are also what power the bidding box's
  meanings.
- **The research has paid off for users.** The solved library is what
  challenge mode is built on.
- **Static Pages plus `localStorage` is the right stopping point** for now.

**Concerns**

1. **Running two engines costs more over time.** Every bidding fix is written
   twice with exact float equality, including emulation of CPython's
   behaviour. The online plan adds a third copy (a bundled server engine).
2. **Streamlit's role is drifting.** It lacks the redesign's features but
   still carries the escaping audit and the app-flow tests. The real reference
   is the Python engine and its tests, not the Streamlit UI.
3. **Multiplayer is half-decided** between Supabase and Cloudflare Durable
   Objects. Both under-weight auth support, moderation of free text (names,
   alerts, chat), and privacy once emails are stored. The idea that avoids
   most of this, guest tables with seat tokens, is buried as an aside.
4. **There's no distribution or feedback loop.** The only signal is cookieless
   page views; sharing is parked in Phase 3. The "wait until analytics show
   use" gate may never trigger.
5. **Research returns are now thin** by the docs' own account: the evaluator
   is at its ceiling and further solver ordering work has been measured and
   rejected. The remaining research with clear user payoff is a WASM solver
   for the per-card analysis panel.

**Top risks**

1. The parity requirement slows the highest-value work.
2. GIB's fallback hole is visible to exactly the audience GIB was chosen for.
3. Building multiplayer early brings operating costs out of proportion to a
   hobby project.
4. Nothing in the product generates the usage data the multiplayer decision
   depends on.
5. One maintainer, carrying a heavy process.

**Recommended next moves, in order**

1. Finish ROADMAP 1.3–1.6 (the remaining handoff gaps, then re-run the
   survey).
2. Ship the Felt follow-ups 2.6–2.8. The Safari height fix reaches every
   phone user.
3. Formally demote Streamlit to an engine test harness with a frozen UI. This
   is a docs-only change that stops parity scope creep.
4. Add a share and feedback loop before any backend: a share button (LIN
   export already exists), a feedback link, and a written usage threshold for
   multiplayer.
5. When multiplayer is triggered, build guest tables on Cloudflare first,
   with no accounts. Cap solver research at the WASM panel.

---

## Verified sound

These were checked and need no re-audit:

- **Duplicate scoring:** `score_contract` matches an independent scorer on all
  11,760 combinations of side, vulnerability, level, strain, doubling and
  tricks.
- **The auction:** 20,000 random auctions match an independent model at every
  step. That covers legal calls, double and redouble rules, completion,
  passed-out boards, declarer, dummy and the opening leader.
- **Trick resolution:** 100,000 random tricks across all leaders and strains
  match an independent `resolve_trick`.
- **Rank equivalence:** touching-card pruning holds under the second-highest
  rule, because "live" includes the current trick. 2,540 adversarial positions
  were checked against `brute.py` with 0 mismatches.
- **The transposition table:** it stores bounds, not exact values. Its key
  includes the leader. The Rust `u128` key is injective.
- **The Rust engine never falls back to Python:** `--engine rust` fails loudly
  when the binary is missing.
- **The alert contract** held across about 840,000 fuzzed robot calls:
  - no alert reached 70 characters;
  - no quoted number was false of the hand;
  - the same auction and call always gave the same text.
- **Determinism:** `ai.py` and `gib.py` import no RNG. Every set used in card
  play is used only for membership tests or counts.
- **The port matches Python's quirks:** `pythonSum` reproduces CPython 3.12's
  compensated `sum()`, `maxBy`/`minBy` keep the first tie, and sort stability
  and slicing match. A type-aware scan found no truthiness divergence.
- **No injection:** in Svelte there is no `{@html}`, `innerHTML` or `eval`,
  and a test enforces it. In Streamlit, every `unsafe_allow_html` site traced
  interpolates only escaped or fixed values.
- **Storage:** every `localStorage` access is wrapped in try/catch, and saves
  that are corrupt or from an unknown version are backed up.
- **CI:** deploy waits on both the Python suite and the frontend build, check
  and tests. Permissions are least-privilege. `npm audit` reports 0
  vulnerabilities.

---

## Suggested fix order

1. **H1:** guard the game-try branch in `gib.py` and `gib.ts`. Add the
   random-human fuzz test from M4, which also surfaces the remaining illegal
   branches.
2. **H4:** seed both flaky tests, which unblocks Dependabot PR #6. Then merge
   or close the other three Dependabot PRs.
3. **H3:** cap the analysis depth and bound the cache, or hide the panel in
   deployed builds.
4. **M1:** exclude imported boards from the "Your board" lookup in both apps
   (ROADMAP 3.4).
5. **H2:** decide how to handle the declarer mismatch (solve per declarer, or
   flag the boards) and say so in CHALLENGE.md.
6. **M6:** fix `run_all.py`'s import handling and give it a real SKIP status.
7. **M3:** fix the defender's view of its own cards, then re-measure the
   challenge benchmark head to head.
8. **Docs:** apply the corrections table above in one pass.

Any change to `ai.py` or `gib.py` must be mirrored in `frontend/src/lib/engine/`
in the same change, or the parity tests will fail.
