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

From screenshots of the built site (desktop 1400x1000, phone 390x844). Only
the **bidding screen** has been reviewed so far.

- [ ] **2.0 Screenshot the rest first**: card play, result screen,
  Challenge tab with its review, History tab, Display menu, desktop and
  phone. Chrome headless shell is installed under
  `%LOCALAPPDATA%/ms-playwright/` and serves static screenshots
  (`--screenshot --window-size=...` against `npx vite preview`), but it can't
  click. To reach play, drive it with Playwright (`npx playwright`) or over
  the DevTools protocol. Add what you find to this section.
- [ ] **2.1 The bidding box is too tall** (biggest issue). On desktop the
  35-button grid pushes **your hand below the fold**, so you can't see your
  cards while you bid. **User decides** between:
  (a) hide rows where every bid is already illegal (small change, gets
  shorter as the auction rises); or
  (b) BBO-style two-step box: a row of levels 1-7, then the strains (most
  compact, familiar to BBO players).
  Either way, also consider moving your hand above the box on desktop.
- [ ] **2.2 Phone: a suit splits across two rows.** With 13 cards the hand
  wraps mid-suit (clubs J8 on one row, 432 on the next). Keep each suit
  unbroken: wrap between suits, or overlap the cards slightly as BBO does.
  The user's standing rule: show every card at once, never clip or scroll a
  suit.
- [ ] **2.3 Phone: small layout breaks.** The tab label is cut off
  ("Hand History (0 bo"); "NORTH · DEALER" wraps onto two lines in the
  auction header; the scoreboard's HIGH BID cell drops to a row of its own.
- [ ] **2.4 "2nd-highest value 4.905"**: show one decimal (4.9). Check
  whether Streamlit's `hand_summary_html` should match.
- [ ] **2.5 Desktop: wasted space.** The seat panels are large for a card
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

- [ ] **3.4** The challenge review finds "your board" by `board_num`
  (`ChallengeView.svelte`, the Challenge tab in `app.py`). An imported LIN
  board with the same number, added later, would be shown in its place.
  Match on the deal too, as `saves.boardKey` does.
- [ ] **3.5** `gib.ILLEGAL` (and the port's) is module-level mutable state
  that grows when a branch produces an illegal call. CLAUDE.md says the
  Streamlit app holds none, so concurrent players can't interfere. Harmless
  (tests keep it empty), but either cap it or correct the claim.
- [ ] **3.6** `loadGames` checks a save's shape only at the top level. One
  malformed board inside would load, then break the History view, without
  being copied to `shb-games-backup`. Validate each record, or skip bad ones.

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
