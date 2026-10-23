# Requirements

What the web app must do, ranked, and whether it does it yet. Drafted
2026-10-23 from the code, the docs and the user's asks so far; **the
priorities are a proposal until the user confirms them.**

How this file relates to the others:

- **REQUIREMENTS.md (this file)** says *what must be true* of the game, and
  how we know it is. A requirement stays here once met, so a change that
  breaks it is caught.
- [ROADMAP.md](ROADMAP.md) says *what to work on next*, step by step. Every
  open roadmap item should serve a requirement here; work that serves none
  needs a reason.
- The area docs ([FRONTEND](FRONTEND.md), [BIDDING](BIDDING.md),
  [CHALLENGE](CHALLENGE.md), [SOLVER](SOLVER.md)) say *how* it is done, with
  the measurements.

**Priorities.** **P0**: the game is wrong or unusable without it; never
regress. **P1**: the next things to build, in the order listed in "The
order to build" below. **P2**: wanted, after P1. **Later**: designed or
asked about, not planned. **Declined**: settled, don't re-propose.

**Status.** **Met** (with the check that holds it), **Partial**, **Open**.

## The order to build

The open P1 requirements, highest first. The reasoning: the auction is where
the robots lose points (235 a board against 6 in the play, ROBOT_PROGRESS),
and the user plays on a phone.

1. **B3** Robots reach makeable games and slams (the biggest single loss).
2. **B2** GIB's remaining handoff gaps (ROADMAP 1.3-1.6).
3. **C4** Challenge grading uses the declarer who actually played
   (flagged since 2026-10-23; exact counts still open).
4. **U6** History and Challenge in the Felt style (ROADMAP 2.6).
5. **A3** Tricks 1-2 of the double dummy analysis fast enough on a phone.

Done 2026-10-23: **S3** (a malformed saved board can't break History) and
**C5** (dealing a challenge board asks before throwing away the board in play).

## 1. Rules and scoring

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| R1 | The second-highest card of the winning suit wins the trick; the winning suit is trump if any was played, else the suit led (also in notrump); a lone card of the winning suit wins outright | P0 | Met | `tests/test_rules.py`; `bridge/trick.py` is the oracle |
| R2 | Follow suit when able; revokes are impossible | P0 | Met | `test_rules.py`, `legalPlays` fixtures |
| R3 | A full auction, 1♣ to 7NT, Pass, X, XX, with only legal calls offered | P0 | Met | `test_bidding.py`, legal-call fixtures |
| R4 | Dealer and vulnerability rotate by board number as in duplicate | P0 | Met | `test_bidding.py` |
| R5 | Complete duplicate scoring: partscores, games, slams, doubled and redoubled, overtricks, undertricks, vulnerability | P0 | Met | `test_scoring.py`, scoring fixtures |
| R6 | The web app's engine gives exactly the Python engine's results: calls, alerts, cards, scores, floats included | P0 | Met | `engine.test.ts` against fixtures CI regenerates |

## 2. Playing a board

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| P1 | The human sits South; robots bid and play North, East and West | P0 | Met | `game.test.ts` |
| P2 | When N/S declare, dummy goes face up and the human plays both hands, whichever of them is declarer | P0 | Met | `game.test.ts` |
| P3 | Only legal cards can be played; legal cards stand out, the rest are greyed | P0 | Met | `Fan`, `game.test.ts` |
| P4 | The table says who is winning the current trick, and why | P1 | Met | `trickText.ts`, `trickText.test.ts` |
| P5 | The last trick can be looked at again from trick 2 on | P1 | Met | `qol.test.ts` |
| P6 | Forced cards (only one legal) are **not** played for you unless you turn it on; off by default | P1 | Met (2026-10-15) | `settings.autoPlay`, `qol.test.ts` |
| P7 | Fast play: next trick after a short pause, opt-in | P2 | Met | `settings.fastPlay`, `qol.test.ts` |
| P8 | A passed-out board is recorded and counted | P1 | Met | `Game.passedOutCount` |
| P9 | A session scoreboard: N/S total, made and set, running total, margin against the robots on challenge boards | P2 | Met | `SessionScore.svelte` |
| P10 | Claim the rest of the tricks | Later | Open | not built; LIN imports claims already |

## 3. Bidding at the table

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| B1 | Every call is explained before you make it (two taps), from what the robots mean by it | P1 | Met | `BidPad`, `meanings.test.ts` |
| B2 | When GIB has no rule, the fallback doesn't misread the auction; close the measured handoff gaps | P1 | Partial: 1.1, 1.2 done; 1.3-1.6 open | ROADMAP 1, `research/gib_handoffs.py` |
| B3 | Robots reach makeable games and slams: bid game on a known fit, bid slam with fit and shortness. Measured head to head, never from one side | P1 | Open. LoTT and fit count shipped (+4.66 a board); robots bid slam on 8 of 3,008 makeable boards; 101 solved slam deals ready (PR #26) | `research/gib_h2h.py`, BIDDING.md |
| B4 | Alerts state what a call shows, true of the hand, from the auction and call only, under 70 characters; pass reasons hidden while the board is live | P0 | Met | machine-checked, ARCHITECTURE.md |
| B5 | You can alert your own calls; the text is cleaned and escaped | P1 | Met | `cleanAlert`, `lin.test.ts` bans `{@html}` |
| B6 | GIB stays the system; the old one only as fallback (`ai.USE_GIB`) | P0 | Met | the GIB guardrail in CLAUDE.md |

## 4. Robot card play

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| K1 | Robots see only what a player at the table would: their hand, dummy once down, the auction, cards played | P0 | Met | CHALLENGE.md; the opening leader doesn't see dummy |
| K2 | Robot play is deterministic for a deal: no RNG in `ai.py` | P0 | Met | the determinism guardrail |
| K3 | Robots search the endgame single dummy from 5 cards | P1 | Met (PR #23, +22.8 a board) | `DEEP_ENDGAME_CARDS`, ROBOT_PROGRESS |
| K4 | No robot move takes long enough to notice on a phone (target: under 0.5 s a board's search) | P1 | Met at 5 cards (0.18 s a board) | the TS bit-pattern search |
| K5 | Search from 6 cards (+26.8 a board measured) | P2 | Open: 4.6 s a board on the main thread; needs a worker or the WASM solver | robot-endgame notes |

## 5. Challenge mode

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| C1 | Play a library deal and compare with an all-robot table on the same deal | P1 | Met | `challenge.py`, `test_challenge.py` |
| C2 | Grade both against par, split exactly into what the auction lost and what the play lost | P1 | Met | `test_challenge.py` asserts the identity on every deal |
| C3 | The review shows double dummy for every card, and lists where tricks were lost, for you and the robots | P1 | Met (PR #24) | `dd.test.ts` |
| C4 | Grading uses the declarer who actually played, not one per strain and side | P1 | Partial (2026-10-23): a board declared by the partner the deal wasn't solved for says so under the grade; exact counts need ~6 h of solving (`research/solve_declarers.py`) | ROADMAP 3.9, `qol.test.ts`, `test_challenge.py` |
| C5 | Dealing a challenge board mid-board asks first | P2 | Met (2026-10-23) | `Game.inProgress`, `qol.test.ts` |

## 6. History and analysis

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| A1 | Every finished board is kept and can be replayed card by card, with all four hands | P1 | Met | `saves.ts`, HistoryView |
| A2 | Double dummy in the replayer: each legal card's outcome, signed and coloured; tricks 3-13 at once | P1 | Met | `dd.test.ts` against the Python solver |
| A3 | Tricks 1-2 of the analysis on a tap, fast enough on a phone (target to agree: e.g. under 30 s median on a recent phone) | P1 | Partial: works; ~38 s median natively on hard lines after the fixed table, phones slower | SOLVER.md, solver spike notes |
| A4 | Export and import boards as BBO LIN; hostile or non-variant input refused, as Python refuses it | P1 | Met | `lin.test.ts`, `lin_hostile.json` |
| A5 | The analysis never shows a wrong value: no fallback, a smaller table only costs time | P0 | Met | `dd.test.ts` runs with 7 entries |

## 7. Layout and look

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| U1 | Phone first: the bidding screen and your hand fit 390x844 without scrolling | P0 | Met (home-screen app); Partial in Safari with toolbars | ROADMAP 2.8 |
| U2 | Every card of your hand visible at once; a suit never splits or clips | P0 | Met | `Fan` |
| U3 | Play, Challenge and History one tap apart, in a compact row | P1 | Met (PR #25) | `TabStrip` |
| U4 | A desktop layout from 1200px, from the same table model | P2 | Met | `game.test.ts` renders both |
| U5 | Browser back and the phone's back swipe move between screens | P1 | Met | URL hash routing |
| U6 | History and Challenge in the Felt style, not the old busy layout | P1 | Open | ROADMAP 2.6 |
| U7 | How to play draws its examples like the table (`TrickFelt`) | P2 | Open | ROADMAP 2.7 |
| U8 | No stutter when the bid pad opens (bid meanings off the main thread if needed) | P2 | Open, unmeasured on a phone | ROADMAP 2.9 |
| U9 | Colours readable for colour-blind players: four-colour deck, WCAG AA inks, double dummy values signed as well as coloured | P1 | Met | `settings.svelte.ts` |
| U10 | UI changes are approved from a phone screenshot before they're built | P0 (process) | Met since 2026-10-22 | the user's rule |

## 8. Saved games and privacy

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| S1 | Saves never stop play: full or blocked storage is survived, an unreadable save is backed up, not overwritten | P0 | Met | `saves.test.ts` |
| S2 | Two open tabs don't overwrite each other's boards | P1 | Met | `mergeGames`, `saves.test.ts` |
| S3 | One malformed saved board can't break History | P1 | Met (2026-10-23): checked board by board on load, a bad one left out and the save backed up | `isRecord`, `saves.test.ts` |
| S4 | No accounts and no server: nothing leaves the browser except cookieless page counts | P0 | Met | CSP in `index.html` |

## 9. Engineering

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| E1 | A static site on GitHub Pages; no server | P0 | Met | `pages.yml` |
| E2 | Small: ~105 KB gzipped plus 21 KB of solver | P1 | Met | `npm run build` |
| E3 | The solver's memory capped for phones (102 MB) | P0 | Met | `TABLE_LIMIT` |
| E4 | Every string the app shows is escaped; no `{@html}` | P0 | Met | `lin.test.ts` |
| E5 | The Python and TS suites pass, CI under 30 minutes, no flaky tests | P1 | Partial: `test_the_evaluation_is_on_the_trick_scale` is unseeded and fails ~1 run in 60 | `tests/run_all.py`, `npm test` |
| E6 | A robot change is measured head to head and recorded in ROBOT_PROGRESS, kept or not | P0 (process) | Met | ROBOT_PROGRESS.md |

## Later

- **Online play with friends** (ONLINE_PLAN.md): designed, blocked on the
  accounts decision; waiting for the page counts to show use.
- **Undo a misclick** at the table: not asked for; would need a rule for
  challenge boards.

## Declined

The ones in ROADMAP's "Declined or settled", plus: an X-ray view of the
robots' hands at the table (removed 2026-10-21; History shows them).
