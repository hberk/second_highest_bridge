# Requirements

What the web app must do, ranked, and whether it does it yet. Drafted
2026-10-23 from the code, the docs and the user's asks so far; re-ranked
2026-10-26 after PRs #26-#32. **The priorities are a proposal until the user
confirms them.**

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
the robots lose points (240.8 a board, against 6.0 in the play, ROBOT_PROGRESS),
and 60% of the auction's loss against two-sided par is in competitive
auctions, where the robots almost never double for penalty.

1. **E5** and housekeeping: the flaky test is seeded (2026-10-26); rerun
   `research/challenge_losses.py` after PR #32 and add its row.
2. **B7** Robots compete and double correctly: the trap pass, and converting
   partner's takeout double for penalty.
3. **B2** GIB's remaining handoff gaps: rerun the survey first (ROADMAP 1.6),
   since PRs #28-#32 changed contested bidding, then 1.3-1.5.
4. **A3** Tricks 1-2 of the analysis solved in the background and saved with
   the board (the user's choice, 2026-10-24; mockups waiting for approval).
5. **K5** (P2) The six-card endgame search, once a move can stay under 0.5 s.

Done 2026-10-23: **S3** (a malformed saved board can't break History),
**C5** (dealing a challenge board asks before throwing away the board in play)
**C4** (grading uses the partner who actually declared) and **U6** (History
and Challenge in the Felt style). Done 2026-10-23 to 25: **B3** for game
(shortness, game by points), **K6** (defenders' leads and returns), and the
first part of **B7** (the penalty double where X is free).

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
| B3 | Robots reach makeable games: bid game on a known fit, with shortness counted. Measured head to head, never from one side | P1 | Met (2026-10-24). LoTT and fit count (+4.66 a board, PR #22); shortness +2.62 (PR #26); game by points (3NT at 32, majors 26, 4M over 3NT) +6.78, the jack at 1 +1.17 (PR #28). Slam: settled as not paying here, see Declined | `research/gib_h2h.py`, BIDDING.md |
| B4 | Alerts state what a call shows, true of the hand, from the auction and call only, under 70 characters; pass reasons hidden while the board is live | P0 | Met | machine-checked, ARCHITECTURE.md |
| B5 | You can alert your own calls; the text is cleaned and escaped | P1 | Met | `cleanAlert`, `lin.test.ts` bans `{@html}` |
| B6 | GIB stays the system; the old one only as fallback (`ai.USE_GIB`) | P0 | Met | the GIB guardrail in CLAUDE.md |
| B7 | Robots compete and double correctly in contested auctions: of 6,356 library contracts 2,960 fail double dummy and 28 were doubled; a perfect-knowledge doubling ceiling is ~117 a board. Measured head to head on fresh deals | P1 | Partial: the penalty double where X is free and the cuebid raise as support, +4.34 a board (PR #30). Open: the trap pass, converting partner's takeout double | `research/gib_fresh_h2h.py`, ROBOT_PROGRESS |

## 4. Robot card play

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| K1 | Robots see only what a player at the table would: their hand, dummy once down, the auction, cards played | P0 | Met | CHALLENGE.md; the opening leader doesn't see dummy |
| K2 | Robot play is deterministic for a deal: no RNG in `ai.py` | P0 | Met | the determinism guardrail |
| K3 | Robots search the endgame single dummy from 5 cards | P1 | Met (PR #23, +22.8 a board) | `DEEP_ENDGAME_CARDS`, ROBOT_PROGRESS |
| K4 | No robot move takes long enough to notice on a phone (target: under 0.5 s a board's search) | P1 | Met at 5 cards (0.18 s a board) | the TS bit-pattern search |
| K5 | Search from 6 cards (+26.8 a board measured) | P2 | Open: 4.6 s a board, worst move 17.5 s on a desktop; a worker alone stops the stutter, not the wait, so it needs the WASM solver or a faster search | ROBOT_PROGRESS |
| K6 | Defenders lead and return on what they can know: partner's bid suit, a planned suit, a return for partner's ruff, partner's short lead read by counting | P1 | Met (PRs #31, #32: +12.2 and +1.52 a board) | ROBOT_PROGRESS, `card_play_seated.py` |

## 5. Challenge mode

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| C1 | Play a library deal and compare with an all-robot table on the same deal | P1 | Met | `challenge.py`, `test_challenge.py` |
| C2 | Grade both against par, split exactly into what the auction lost and what the play lost | P1 | Met | `test_challenge.py` asserts the identity on every deal |
| C3 | The review shows double dummy for every card, and lists where tricks were lost, for you and the robots | P1 | Met (PR #24) | `dd.test.ts` |
| C4 | Grading uses the declarer who actually played, not one per strain and side | P1 | Met (2026-10-23): every deal solved for all four declarers; par takes the better partner | `test_challenge.py`, `engine.test.ts` |
| C5 | Dealing a challenge board mid-board asks first | P2 | Met (2026-10-23) | `Game.inProgress`, `qol.test.ts` |

## 6. History and analysis

| id | requirement | pri | status | how we know |
|---|---|---|---|---|
| A1 | Every finished board is kept and can be replayed card by card, with all four hands | P1 | Met | `saves.ts`, HistoryView |
| A2 | Double dummy in the replayer: each legal card's outcome, signed and coloured; tricks 3-13 at once | P1 | Met | `dd.test.ts` against the Python solver |
| A3 | Tricks 1-2 of the analysis without waiting at the replayer: solved in a background worker when the board ends, saved with the board, resumed on reopen (the user's choice, 2026-10-24) | P1 | Partial: a tap solves them today (~38 s median natively on hard lines, phones slower); the background design is mocked, waiting for the user's approval | SOLVER.md |
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
| U6 | History and Challenge in the Felt style, not the old busy layout | P1 | Met (2026-10-23, approved from phone screenshots) | `HistoryView`, `ChallengeView`, `game.test.ts` |
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
| E5 | The Python and TS suites pass, CI under 30 minutes, no flaky tests | P1 | Met (2026-10-26: `test_the_evaluation_is_on_the_trick_scale` seeded; unseeded it failed ~1 run in 60) | `tests/run_all.py`, `npm test` |
| E6 | A robot change is measured head to head and recorded in ROBOT_PROGRESS, kept or not | P0 (process) | Met | ROBOT_PROGRESS.md |

## Later

- **Online play with friends** (ONLINE_PLAN.md): designed, not built. The user
  has a Cloudflare account; Cloudflare-only (Workers, D1, Durable Objects) is
  the recommended backend. Whether to promote it to P2 is the user's call;
  until then it waits for the page counts to show use.
- **Undo a misclick** at the table: not asked for; would need a rule for
  challenge boards.

## Declined

The ones in ROADMAP's "Declined or settled", plus: an X-ray view of the
robots' hands at the table (removed 2026-10-21; History shows them); a slam
bidding rule (2026-10-23: even seeing both hands, the best slam cells make
24-50%, under the ~50% a small slam needs; BIDDING.md); a singleton opening
lead (2026-10-25: +0.43 tricks double dummy, -0.42 points seated).
