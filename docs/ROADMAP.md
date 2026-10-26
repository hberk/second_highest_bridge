# Roadmap

Written 2026-10-14 for the next working sessions; re-ordered 2026-10-26 after
PRs #26-#32. Each item says what to do, where, how to verify it, and **which
decisions belong to the user**: stop and ask at those points rather than
choosing. Work in the order of "Now" unless the user picks otherwise. Tick
items off here (or delete them) as they land, so this file stays the current
list. Every item serves a requirement in [REQUIREMENTS.md](REQUIREMENTS.md).

The user is a bridge player who audits auctions hand by hand. Show real
hands and real auctions, not only aggregates, before changing how the robots
bid, and get a yes on the bridge before writing code. Don't open a PR for a
robot change or a UI change until the user has seen the results (or a phone
screenshot) and said so.

## Now (2026-10-26)

The robots lose 240.8 points a board in the auction and 6.0 in the play
(ROBOT_PROGRESS, measured after PR #30/#31). Against two-sided par, 60% of the
auction's loss is in competitive auctions, and the robots almost never double
for penalty, so that comes first.

- [x] **0.1 Seed the flaky calibration test** (E5, 2026-10-26).
- [ ] **0.2 Rerun `research/challenge_losses.py`** after PR #32 and add the
  row to ROBOT_PROGRESS's "Where the robots stand".
- [ ] **0.3 Competitive doubling (B7).** Of 6,356 library contracts, 2,960
  fail double dummy and 28 were doubled; 1,600 go two or more down undoubled;
  a perfect-knowledge doubling ceiling is ~117 a board. Shipped: the penalty
  double where X is free (+4.34, PR #30). Next: the **trap pass** and
  **converting partner's takeout double** for penalty. Show real hands first
  (scripts in project files, `competitive-review/`), then measure on fresh
  deals with `research/gib_fresh_h2h.py`. Mind B4: one call keeps one
  meaning per auction.
- [ ] **0.4 GIB handoff gaps (B2):** section 1 below, starting with 1.6 (rerun
  the survey), since PRs #28-#32 changed contested bidding.
- [ ] **0.5 Tricks 1-2 in the background (A3).** The user's choice
  (2026-10-24): a worker solves the whole board when it ends, the values are
  saved with the board (~1 KB), solving resumes on reopen, History shows
  progress, the tap button goes. Mockups in project files, `dd-background/`.
  **User decides** before building: the mockup, whether LIN imports solve only
  when opened, and whether the battery cost is acceptable.
- [ ] **0.6 The six-card endgame search (K5, P2):** +26.8 a board measured,
  but 4.6 s a board and up to 17.5 s a move on a desktop. A worker stops the
  stutter, not the wait; it needs the WASM solver or a faster search first.

**Open for the user** (proposed 2026-10-25, not yet answered):

- The order above.
- The shared double dummy cache (branch `claude/project-thread-0exu2e`):
  recommended as a PR; the search-bounds experiment beside it (1.1-1.27x)
  recorded as rejected in SOLVER.md.
- The branch `jump-overcall-game` (WIP 2026-10-20: responder bids game over a
  three-level jump overcall): recommended dropped unless the 1.6 survey shows
  that family losing points.
- Online play: Cloudflare-only as P2, or kept in Later.

## 1. Robot bidding: close GIB's handoff gaps

**Why first:** it's where the robots measurably lose points, and each fix
improves the challenge table too. When `gib.gib_bid` returns None, `ai.py`'s
previous system bids instead. That system never doubles and often misreads
the auction. On 4,000 random boards, 14.9% of robot calls, on 48% of boards,
are made that way, nearly all second-round calls in contested auctions.
Background: "Where GIB hands off" in [BIDDING.md](BIDDING.md).

**Tools** (both in `research/`, both read-only, the app imports neither):

```bash
python research/gib_handoffs.py survey 4000 research/data/handoffs.json
python research/gib_handoffs.py roles    research/data/handoffs.json
python research/gib_handoffs.py families research/data/handoffs.json 40
python research/gib_handoffs.py hands    research/data/handoffs.json "1x (1y) X (2y) ?"
python research/gib_h2h.py <gib function names of the new branch>
```

**The loop, for each gap** (the reopening double, commit `65ca5a7`, is the
worked example to copy):

1. Pull real hands for the family with `hands`, and show the user the hands
   where the robot's call looks wrong, next to what standard bidding (GIB's
   notes) says.
2. **User decides** the rule, including thresholds.
3. Implement in `gib.py` **and** `frontend/src/lib/engine/gib.ts`, line for
   line. Keep the alert rules: an alert depends only on the auction and the
   call (one text per call per auction, even across branches), and every
   number it quotes must be true of the hand.
4. Add a test to `tests/test_gib.py` using the survey's hands.
5. `python tests/run_all.py`, then in `frontend/`: `npm run fixtures`,
   `npm run check`, `npm test`.
6. `python research/gib_h2h.py <new functions>`; show the user the number
   and the biggest losing deal. A loss can be this variant's rules rather than
   a bug (deal 303: a textbook trump-stack penalty pass loses here).
7. Record the measurement in [BIDDING.md](BIDDING.md) under GIB, and commit.

**The gaps, in order** (counts from the 4,000-board survey):

- [x] **1.1 `1x (1y) X (2y) ?`: opener after partner's negative double and
  their raise** (69 handoffs; 47 passes). Confirmed bug: the fallback reads
  partner as having **passed**. Its alert says "Partner has passed; not
  enough to bid again alone" after a negative double. Opener holding
  ♠K985 after `1♣ (1♥) X (2♥)` passes, where the double promised four
  spades. Likely rule: opener bids the promised major with four (jumping
  with extras), otherwise rebids a long suit or passes. Check the related
  families too: `1x (1y) X (2y) P (P) ?` (45) and `1x (1y) X (2x) ?` (21).
- [x] **1.2 `1x (P) 1y (2z) ?`: opener's rebid after the overcall cuts in
  above responder's suit** (64; fallback bids 42 times, passes 22). Check
  support doubles here: GIB plays them through 2♥, so a support double may
  already apply to some of these.
- [ ] **1.3 `1x (2y) 3x (P) ?` and `1x (1y) 3x (P) ?`: opener after
  partner's raise over interference** (97 + 53, nearly all passes). Probably
  fine if GIB's jump raise in competition is pre-emptive. Confirm against
  the notes, and if so record it as covered instead of adding a branch.
- [ ] **1.4 The overcaller's second call** (14% of handoffs), e.g.
  `(1x) 1y (X) 2y (P) ?` and `(1x) 1y (X) P (2z) ?`. Survey `hands` first;
  no bug is known yet.
- [ ] **1.5 Systems over interference after our 1NT overcall**, e.g.
  `(1♦) 1NT (2♠) ?`. Today that falls back to `ai.py`. **User decides**
  whether they play anything here (a double for Stayman, Lebensohl as over a
  1NT opening, or nothing).
- [ ] **1.6 Re-run the survey** after 1.1-1.4 and update the numbers in
  BIDDING.md.

Out of scope: do **not** "fix" GIB toward the old measured system. The user
chose GIB knowing it scores worse here (see BIDDING.md).

## 2. Web app UI

Done: the Felt redesign (2026-10-16, FRONTEND.md) settled 2.0-2.5 (the
bidding box, the split suit, the small-layout breaks, one decimal, desktop
space); 2.6 History and Challenge in the Felt style (2026-10-23, PR #27) and
their compass layout (PR #29); 2.10 Streamlit retired (2026-10-21).

Open:

- [ ] **2.7 How to play** still draws its examples with the old
  `FeltTable`. Draw them with `TrickFelt` so they match the table.
- [ ] **2.8 Safari with its toolbars showing** leaves ~660-750px of height;
  the bidding screen needs ~770, so it scrolls a little there. Added to the
  home screen (full screen) it fits an 844px iPhone with room to spare.
- [ ] **2.9 Bid meanings run on the main thread** (`callMeanings`, 4,000
  sampled hands, ~100 ms on a laptop) just after the pad appears. If a phone
  shows a stutter, move it to a Web Worker.

For each: `npm run check`, `npm test` (`game.test.ts` renders every view at
every step), then a fresh phone screenshot for the user to approve.

## 3. Housekeeping and the code reviews

Done: 3.1-3.3 (stale docs and counts), 3.4-3.6 from the 2026-10-14 code
review (the challenge review's board match, `gib.ILLEGAL`, per-board save
checks), and everything the 2026-10-17 code analysis
(`reports/2026-10-17-code-analysis.md`) left for the user: 3.7 responder over
1M-2M-3NT, 3.8 the 1♥-2♥-3♠ splinter, 3.9 grading by the partner who declared,
3.10 asking before a redeal, 3.12 the challenge loss figures (rerun after any
robot change kept).

- [ ] **3.11 Robot discards and leads.** Discards done 2026-10-19 (the user's
  rule: a void robot throws a trump only to ruff for a win; `ai.KEEP_TRUMPS`,
  head to head +0.003 tricks, t = +0.37, 88 of 6,356 boards changed); leads
  and returns done 2026-10-25 (PRs #31, #32; K6). Still open: `_lead`/`_gap`
  count dummy's cards as an opponent's, a card-play change to measure with
  `research/card_play_h2h.py`.

## 4. Bigger projects (only when the user asks)

- [x] **Double dummy panel in the web app** (2026-10-21): `research/solver-rs`
  as WebAssembly in the History replayer, tricks 3-13 at once and 1-2 on a
  tap. See "Double dummy in the History replayer" in [FRONTEND.md](FRONTEND.md).
  The robots' five-card endgame search shipped on its own (PR #23, +22.8
  points a board); six cards is 0.6 in "Now".
- **Online play with friends.** Designed in [ONLINE_PLAN.md](ONLINE_PLAN.md)
  and [HOSTING_AND_LOCAL_SAVES.md](HOSTING_AND_LOCAL_SAVES.md). The user has
  a Cloudflare account, and Cloudflare-only is the recommended backend;
  whether to promote it to P2 is open (see "Now"). Suggested waiting until
  the Cloudflare analytics show people are using the site.

## For the user, outside the code

- Merge Dependabot PRs once their checks are green. The open pip PR for
  Streamlit can be closed: Streamlit is retired, and Dependabot no longer
  watches pip.
- Stop the Streamlit Community Cloud deployment (its dashboard), since the
  app it ran is gone from the repository.
- GitHub settings, if not done: CodeQL default setup, private vulnerability
  reporting and Dependabot security updates (Settings → Advanced Security);
  a ruleset on the default branch blocking force pushes and deletion; "Keep
  my email addresses private" in account settings.
- Delete the merged branches on GitHub: `mobile-ui`, `pages-local-saves`,
  `claude-md-restructure`, and the merged
  `claude/project-thread-*` branches (3eomzu, 5a2rvz, 8u8fku and older).

## Declined or settled (don't re-propose)

- A coloured board dropdown in History: native dropdowns can't be coloured;
  the Contract line under it is coloured instead.
- Reviewing past challenge boards beyond the latest: the user found the
  existing review sufficient.
- Dropping responder's penalty pass of a reopening double: measured as
  indistinguishable (+1.74 against +1.64); kept by the user's choice.
- A slam bidding rule (2026-10-23): even seeing both hands the best slam cells
  make 24-50%, under the ~50% a small slam needs (BIDDING.md).
- A singleton opening lead (2026-10-25): +0.43 tricks double dummy but -0.42
  points seated; off.
