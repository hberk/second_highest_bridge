# Roadmap

Written 2026-10-14 for the next working sessions. Each item says what to do,
where, how to verify it, and **which decisions belong to the user**: stop and
ask at those points rather than choosing. Work top to bottom unless the user
picks otherwise. Tick items off here (or delete them) as they land, so this
file stays the current list.

The user is a bridge player who audits auctions hand by hand. Show real
hands and real auctions, not only aggregates, before changing how the robots
bid, and get a yes on the bridge before writing code.

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

**2026-10-16: the Felt redesign** (branch `felt-redesign`, see FRONTEND.md)
replaced the tabbed layout with a phone-first home page and table, and the
bidding box with a two-tap pad that explains each call. Items 2.1-2.5 below
were about the old layout and are settled by it: the hand sits above the bid
pad (2.1), the hand is one overlapping fan with every card visible (2.2), the
tabs and scoreboard are gone (2.3), the strength line shows HCP and shape
only on phones (2.4; the desktop layout shows the "2nd-highest value" too,
to one decimal), and the table is a 520px column on phones with its own
desktop layout from 1200px (2.5; mocked on the design canvas and approved
2026-10-16).

Follow-ups from the redesign:

- [ ] **2.6 History and Challenge** sit in the new frame and colours but keep
  their old, busier layout (emoji headings, wide tables). Redesign them in
  the Felt style.
- [ ] **2.7 How to play** still draws its examples with the old
  `FeltTable`. Draw them with `TrickFelt` so they match the table.
- [ ] **2.8 Safari with its toolbars showing** leaves ~660-750px of height;
  the bidding screen needs ~770, so it scrolls a little there. Added to the
  home screen (full screen) it fits an 844px iPhone with room to spare.
- [ ] **2.9 Bid meanings run on the main thread** (`callMeanings`, 4,000
  sampled hands, ~100 ms on a laptop) just after the pad appears. If a phone
  shows a stutter, move it to a Web Worker.
- [ ] **2.10 Streamlit** has no bid meanings or two-tap box; it stays the
  reference engine with its old look unless the user asks.

The original notes, from screenshots of the old built site (desktop
1400x1000, phone 390x844):

- [x] **2.0 Screenshot the rest first**: card play, result screen,
  Challenge tab with its review, History tab, Display menu, desktop and
  phone. Chrome headless shell is installed under
  `%LOCALAPPDATA%/ms-playwright/` and serves static screenshots
  (`--screenshot --window-size=...` against `npx vite preview`), but it can't
  click. To reach play, drive it with Playwright (`npx playwright`) or over
  the DevTools protocol. Add what you find to this section.
- [x] **2.1 The bidding box is too tall** (biggest issue). On desktop the
  35-button grid pushes **your hand below the fold**, so you can't see your
  cards while you bid. **User decides** between:
  (a) hide rows where every bid is already illegal (small change, gets
  shorter as the auction rises); or
  (b) BBO-style two-step box: a row of levels 1-7, then the strains (most
  compact, familiar to BBO players).
  Either way, also consider moving your hand above the box on desktop.
- [x] **2.2 Phone: a suit splits across two rows.** With 13 cards the hand
  wraps mid-suit (clubs J8 on one row, 432 on the next). Keep each suit
  unbroken: wrap between suits, or overlap the cards slightly as BBO does.
  The user's standing rule: show every card at once, never clip or scroll a
  suit.
- [x] **2.3 Phone: small layout breaks.** The tab label is cut off
  ("Hand History (0 bo"); "NORTH · DEALER" wraps onto two lines in the
  auction header; the scoreboard's HIGH BID cell drops to a row of its own.
- [x] **2.4 "2nd-highest value 4.905"**: show one decimal (4.9). Check
  whether Streamlit's `hand_summary_html` should match.
- [x] **2.5 Desktop: wasted space.** The seat panels are large for a card
  count, and there's empty space around the auction. Lower priority; revisit
  after 2.1.

For each: `npm run check`, `npm test` (`game.test.ts` renders every view at
every step), then a fresh screenshot at both sizes. UI changes go to the
Svelte app; the Streamlit app is the reference engine and needs matching UI
changes only where the user asks.

## 3. Housekeeping (small)

- [x] **3.1** `docs/ONLINE_PLAN.md` still says the app is "deployed to Azure
  Static Web Apps" (status line) and draws "Azure SWA" in its diagram;
  `staticwebapp.config.json` no longer exists. Update to GitHub Pages and the
  `<meta>` CSP in `frontend/index.html`.
- [x] **3.2** `requirements.txt`'s comment quotes "155 tests" and old
  Streamlit versions; the suite has 220 tests and Dependabot now raises the
  floor (PR #6). Refresh the comment.
- [x] **3.3** CLAUDE.md quotes "217 tests" under Commands; now 220.

## 3b. Minor issues from the 2026-10-14 code review

The review's four real bugs are fixed (passed-out challenge boards, LIN
imports evicting played boards, tabs overwriting saves, claims lost on LIN
export). These were left, each small:

- [x] **3.4** (fixed 2026-10-18: imports skipped, the deal compared) The challenge review finds "your board" by `board_num`
  (`ChallengeView.svelte`, the Challenge tab in `app.py`). An imported LIN
  board with the same number, added later, would be shown in its place.
  Match on the deal too, as `saves.boardKey` does.
- [x] **3.5** (the claim corrected in ARCHITECTURE.md, and the illegal calls a human at the table caused fixed, 2026-10-18) `gib.ILLEGAL` (and the port's) is module-level mutable state
  that grows when a branch produces an illegal call. CLAUDE.md says the
  Streamlit app holds none, so concurrent players can't interfere. Harmless
  (tests keep it empty), but either cap it or correct the claim.
- [ ] **3.6** `loadGames` checks a save's shape only at the top level. One
  malformed board inside would load, then break the History view, without
  being copied to `shb-games-backup`. Validate each record, or skip bad ones.

## 3c. Left open by the 2026-10-17 code analysis (`reports/2026-10-17-code-analysis.md`)

Fixed 2026-10-18 on branch `code-analysis-fixes`:

- the 1M-2M-3NT crash (H1) and illegal calls with a human at the table (M4):
  a fuzz test with a random human seat now holds `gib.ILLEGAL` at zero;
- the flaky tests (H4): seeded deals in the web app's tests and in the
  self-alert app-flow test;
- the Streamlit analysis panel (H3): depth capped at 8, cache bounded (LRU);
- "your board" in the challenge review (M1, 3.4 above);
- the 13th trick shown before the score in Streamlit (M2);
- the LIN parsers (M5): one hostile-input fixture both must agree on, size and
  board limits, imported alerts cleaned, re-imports skipped;
- `run_all.py` (M6): SKIP is reported, and an import failure no longer ends the run;
- the dataset pool (M7) and `deal_for` restoring the global RNG;
- the pass-out count after a failed save (M8);
- the covering robot's own cards (M3): a correctness fix that changed 0 of
  6,356 boards head to head;
- dead code and unused imports, `Card.__eq__`, the future import in every
  `__init__.py`, CI timeouts and main deploys never cancelled, and the stale
  docs and comments.

Still open, **each the user's call**:

- [x] **3.7 Responder over 1M-2M-3NT.** (2026-10-19, the user's call: a choice
  of games.) Responder passes with three trumps and no short suit, else bids
  4M. See "After a single raise" in BIDDING.md.
- [x] **3.8 1♥-2♥-3♠.** (2026-10-19, the user's call: a splinter, short in
  spades, game forcing.) Opener now bids it too, with 18+ HCP (also 4♣/4♦, and
  1♠-2♠-4♣/4♦/4♥), and responder bids game. 1 of 1,600 auctions changed.
- [ ] **3.9 Challenge grading uses one declarer per strain and side (H2).**
  22.5% of robot boards are declared by the other partner (CHALLENGE.md). Solve
  both declarers, or flag mismatched boards.
- [ ] **3.10 Dealing a challenge board throws away the board in play (M9)**,
  with no confirmation, and the deal goes back in the pool. Intended?
- [ ] **3.11 Robot discards and leads.** Discards done 2026-10-19 (the user's
  rule: a void robot throws a trump only to ruff for a win; `ai.KEEP_TRUMPS`,
  head to head +0.003 tricks, t = +0.37, 88 of 6,356 boards changed). Still
  open: `_lead`/`_gap` count dummy's cards as an opponent's, a card-play
  change to measure with `research/card_play_h2h.py`.
- [x] **3.12 The challenge loss figures** (2026-10-19): re-measured by the new
  `research/challenge_losses.py` over all 16 board positions, 234 in the
  auction and 7 in the play (with the card-play rules merged from main), now quoted by both apps' captions, the
  Streamlit docstring and CHALLENGE.md. Rerun it after any robot change.

## 4. Bigger projects (only when the user asks)

- **Double dummy panel in the web app.** Compile `research/solver-rs` to
  WebAssembly; don't port `bridge/solver`. Interactive per-card analysis is
  viable for roughly the last six tricks (see [SOLVER.md](SOLVER.md)).
- **Online play with friends.** Designed in [ONLINE_PLAN.md](ONLINE_PLAN.md)
  and [HOSTING_AND_LOCAL_SAVES.md](HOSTING_AND_LOCAL_SAVES.md). Blocked on a
  user decision (accounts on Supabase or Cloudflare). Suggested waiting
  until the Cloudflare analytics show people are using the site.

## For the user, outside the code

- Merge Dependabot PRs once their checks are green (#6 Streamlit and #7
  frontend were open on 2026-10-14).
- GitHub settings, if not done: CodeQL default setup, private vulnerability
  reporting and Dependabot security updates (Settings → Advanced Security);
  a ruleset on the default branch blocking force pushes and deletion; "Keep
  my email addresses private" in account settings.
- Delete the merged branches `mobile-ui`, `pages-local-saves` and
  `claude-md-restructure` on GitHub.

## Declined or settled (don't re-propose)

- A coloured board dropdown in History: native dropdowns can't be coloured;
  the Contract line under it is coloured instead.
- Reviewing past challenge boards beyond the latest: the user found the
  existing review sufficient.
- Dropping responder's penalty pass of a reopening double: measured as
  indistinguishable (+1.74 against +1.64); kept by the user's choice.
