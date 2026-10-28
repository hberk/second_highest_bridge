# Robot progress

Every measured improvement to the robots, oldest first, with what it was worth.
Each figure is copied from the measurement recorded in
[CHALLENGE.md](CHALLENGE.md) (card play) or [BIDDING.md](BIDDING.md)
(bidding), where the method and the deals behind it are written up.

**Read every number so that positive means the robots got better.** A defence
rule is measured as fewer declarer tricks, so its sign is flipped here. The
gains are not additive: each was measured against the robots of its day, and
rules overlap (a trick one rule saves, another may have saved already).

## Where the robots stand

What the robots give away on the challenge library, measured by
`research/challenge_losses.py` (all 400 deals at all 16 board positions,
graded from N/S as the app grades):

| measured | robots | lost in the auction | lost in the card play |
|---|---|---|---|
| 2026-10-24 | the penalty double where X is free, a cuebid raise read as support (PR #30), with the defender's suit plan | **240.8** | **6.0** |
| 2026-10-24 | the defender plans the suit it leads (without it: 242.5 / 3.5; from the declaring side the play went from -36.6 to -24.4) | 242.5 | 5.2 |
| 2026-10-23 | shortness once a fit is agreed (PR #26) and game by points (PR #28) | 240.1 | 2.9 |
| 2026-10-23 | the same robots as 10-22, graded with the partner who declared (every declarer solved) | 244.0 | -5.0 |
| 2026-10-22 | the Law of Total Tricks and the fit count (bidding) | 235.4 | 6.1 |
| 2026-10-21 | every rule below, through the four-card endgame search | 234.9 | 6.9 |
| 2026-10-19 | every rule up to then | 233.9 | 7.1 |
| 2026-10-19 | before `SURE_LEAD_DECLARER`, `DEAD_CARD_LAST` | 233.9 | 12.5 |

Points a board against par, split by the identity par - actual = bidding loss +
play loss. From 2026-10-23 the grade uses the partner who actually declared
and par the better partner, so the rows above it measured something slightly
different: about 11 points of their card-play loss was the wrong declarer's
count. The card play is close to double dummy now; the auction is where the
points are. The 2026-10-22 bidding changes moved the auction figure by
nothing (235.4 against 234.9) although each wins +4.66 a board head to head:
all four seats use them here, so what N/S gain E/W gain back; from the
declaring side the auction loss fell from 215.8 to 211.9. (An older figure, 143.7 / 31.8, was one auction per deal before any
card-play change below, so it isn't comparable.)

The robot declarer against double dummy, before the head-to-head metric
existed (397 library boards, GIB auctions, tricks below double dummy a board):

| change | below double dummy |
|---|---|
| the robot table passes no visible hands | 0.471 |
| declarer sees its own two hands, defenders see dummy | 0.310 |
| the last three tricks searched single dummy | 0.199 |
| second hand covers to promote a visible partner | **0.025** |

## Card play

Head to head (`research/card_play_h2h.py`): the robot table on all 400 deals
at all 16 board positions with the switch off, then on, the boards paired.
**Tricks** a board for the side the rule plays for; **t** across deals (about 2
or more is a real effect); **points** a board.

| date | change | for | tricks | t | points | status |
|---|---|---|---|---|---|---|
| by 10-12 | Fourth hand plays for the partnership, not just itself | declarer | **+0.43** | +7.2 | | on |
| | | defence | **+0.21** | +5.2 | | |
| 10-17 | Declarer draws trumps (unless dummy must ruff first) | declarer | **+0.171** | +3.19 | +17.1 | on |
| 10-17 | Declarer runs a long suit | declarer | **+0.080** | +1.99 | +19.8 | on |
| 10-17 | Defenders lead their long suit in notrump | defence | +0.086 | +1.85 | +6.3 | on (your call) |
| 10-17 | A defender cashes a sure trick, seen through dummy | defence | **+0.174** | +4.53 | +18.6 | on |
| 10-18 | Covering robot counts its own cards correctly | | 0 boards changed | | | on (bug fix) |
| 10-19 | Sure lead for the declaring side: the 9♣ to dummy's 10♣ (deal 174) | declarer | **+0.165** | +3.81 | +17.8 | on |
| 10-19 | Dead card when fourth hand can't win: A♣/K♣, not 5♣ (deal 156) | declarer | **+0.077** | +3.33 | +9.5 | on |
| | | defence | +0.036 | +1.08 | +5.4 | |
| 10-19 | A void robot keeps its trumps unless ruffing wins | both | +0.003 | +0.37 | +0.7 | on (your rule) |
| 10-24 | A defender plans the suit it leads: the 6♥, not the dead 9♥ (deal 356) | defence | **+0.113** | +2.50 | +12.2 | on |

The two 2026-10-19 rules together: **+0.183 tricks, +20.5 points a board**
(t = +3.37).

From 2026-10-20, seated (`research/card_play_seated.py`): the switch on for
one side only, against robots without it, sides swapped, scored from the
switched side over all 400 deals x 16 boards. `card_play_h2h.py` switches all
four seats, which nets out a change both declarer and defenders use.

| date | change | tricks | t | points | boards changed | status |
|---|---|---|---|---|---|---|
| 10-20 | The opening leader no longer sees dummy before it goes down | | +1.39 | +0.24 | 24 | on (your call: correctness) |
| 10-20 | Second and third hand drop suits the next opponent has shown out of | | -0.79 | -0.16 | 48 | on (your call: correctness) |
| 10-20 | Play reads the bidding: lead partner's suit, layouts that fit the auction | | +0.38 | +0.43 | 492 | on (your call: correctness) |
| 10-20 | The endgame search starts at four cards, not three | **+0.190** | +10.29 | **+19.8** | 2,092 | on |
| 10-21 | One position memory for every search | | | | 0 (same play, half the time) | on |
| 10-22 | The endgame search starts at five cards, not four (measured 10-21) | **+0.204** | +9.34 | **+22.8** | 2,564 | on (your call) |
| 10-24 | A defender on lead leads a suit partner bid naturally when holding 3+ (opening lead and later; board 17). 600 fresh deals | +0.011 | +0.48 | +0.62 | 860 of 9,504 | on, awaiting your review |
| 10-24 | ...the same with 4+ | +0.000 | -0.21 | -0.22 | 500 of 9,504 | off |
| 10-25 | Opening lead of a side singleton in a suit contract, holding a trump (`SINGLETON_LEAD`; +0.43 tricks double dummy in the lead study). 600 fresh deals | +0.006 | -0.49 | -0.42 | 540 of 9,504 | off |
| 10-25 | A defender leads back a suit partner showed out of while partner may hold a trump (`RUFF_RETURN`) | +0.007 | +1.67 | +1.33 | 296 of 9,504 | (part of the row below) |
| 10-25 | ...and returns partner's opening-lead suit when it reads as a singleton at 20%+ (`SHORT_LEAD_RETURN`: the unseen cards, the second-highest lead convention, declarer's bid length) | +0.003 | +1.30 | +1.53 | 380 of 9,504 | (part of the row below) |
| 10-25 | ...an honour lead (J+) read by counting alone, not the lead convention (`SHORT_LEAD_HONOUR`, your call: people lead honours from other holdings, deal 356) | +0.002 | +1.28 | +1.52 | 364 of 9,504 | on (your call) |
| 10-25 | ...with the singleton opening lead as well | +0.004 | -0.35 | -0.58 | 888 of 9,504 | off |
| 10-25 | ...both together; with low singletons only (ten or below) | +0.011; +0.003 | +0.67; +0.35 | +0.77; +0.39 | 756; 632 | off |

The three information rules together: +0.55 points a board, t = +0.48, 556
boards changed. None is distinguishable from zero; they are kept because a
robot should play only on what it could know.

Tried and left off:

| date | change | tricks | why |
|---|---|---|---|
| by 10-12 | Searching the last four tricks, not three | | 15 minutes for the library: too slow for the table (done on 10-20, above, once the search was rewritten) |
| 10-17 | Notrump long-suit lead on the opening lead only | -0.019 | every lead did better |
| 10-19 | Ruff lead for the declaring side (deal 174) | -0.020 | right on its deal, not on the library |
| 10-19 | Defender forces dummy instead of leading a trump (deal 92) | -0.001 | no effect |
| 10-19 | Never lead a dead card while a live one will do (deal 43) | declarer -0.122, defence -0.149 | worse for both sides: a dead card is a loser worth spending |
| 10-19 | Declarer sets up its long suit in notrump (deal 43) | +0.041 (t = +0.95) | right direction, not proven; left off, to narrow first |
| 10-20 | A sampled search from five or six cards (eight layouts) | | deal 0: the K♦ third in hand where the 6♦ takes three more; eight layouts misjudge one card |
| 10-22 | The endgame search from six cards, over five (TS engine, 100 deals) | **+0.260** (t = +4.35), +26.8 points, seated | **waiting** (your call): 4.6 s a board, up to 17.5 s a move on a desktop, on the main thread |
| 10-21 | Trying the remembered best card first | | slower (0.87 s against 0.77 s a board at five cards), no gain |
| 10-24 | Lead the highest live card instead of a dead second-highest (deal 356) | defence -0.002, declarer -0.019 (seated) | no effect: a dead card still promotes partner's |
| 10-24 | The same, only in a trump contract against dummy's last card in the suit | +0.001 (12 boards) | almost never fires |

## Bidding

Head to head: the variant at N/S against the robots without it at E/W, then
swapped, each contract scored at its double dummy result (`research/gib_h2h.py`
since 2026-10-14: 400 deals x 4 dealers, 1,600 auctions). **Points** a board
from the variant's side; t as above.

| date | change | points | t | auctions changed | status |
|---|---|---|---|---|---|
| by 10-12 | GIB 2/1 adopted in place of the fitted system | -6.6 | -2.99 | | on (your choice: the system players know) |
| by 10-12 | GIB judges level on this game's card values (K=Q=3, A=10=9=1) | **+2.7** | +2.90 | | on |
| by 10-12 | A cuebid raise that forces the three level needs four trumps or 12+ | +0.1 | +2.24 | | on |
| 10-14 | Reopening double after 1x (y) P (P), and responder's answer | **+1.64** | +2.06 | 28 | on |
| 10-14 | Opener bids the fit after they bid over a negative double | +0.40 | +1.58 | 18 | on |
| 10-14 | Opener shows strength after they overcall the response | -0.07 | -1.22 | 4 | on (your choice: GIB-standard) |
| 10-19 | Opener's splinter after a single raise (1♥-2♥-3♠) | +0.00 | | 1 | on (your call) |
| 10-19 | 1M-2M-3NT is a choice of games | | | | on (answers a human opener; robots never bid it) |
| 10-20 | Opener splinters in their suit after they overcall the response (deal 329) | +0.19 | +1.00 | 2 | on (your call) |
| 10-20 | Responder bids game over a three-level jump overcall with 3+ support, 11+ HCP (deal 346) | **+0.76** | +1.93 | 9 | on (your call: 11, not 10) |
| 10-20 | After our two-suited overcall: advancer bids game with a fit, and the later rounds read it (deal 163) | +0.23 | +1.43 | 3 | on (your call) |
| 10-20 | Their contract is not our game reached: double for penalty with game values (deal 118) | **+2.99** | +3.48 | 20 | on (your call) |
| 10-20 | Our natural overcall is read as an overcall, not an opening (deal 67), with values counted at the four level | **+3.42** | +3.58 | 81 | on (your call) |
| 10-22 | Law of Total Tricks: compete to the level of our fit (deal 354) | **+3.56** | +4.49 | 71 | on (your call) |
| 10-22 | ...and a weak raise with a singleton or void (deal 333) | +0.27 | +1.89 | 7 | on (your call) |
| 10-22 | Game judged on the known fit: 3 points a trump past ten, fewer costs the same (deal 248) | **+0.83** | +2.93 | 35 | on (your call) |
| 10-23 | Shortness once a fit is agreed: a void adds 5 tricks (game, and a higher ceiling in competition), a singleton 1 (the old-system fallback, deal 52); measured over 5,400 deals, 21,596 boards | **+2.62** | +9.24 | 1,404 | on (your call) |
| 10-23 | ...the void valued at exactly game instead | +1.72 | +7.15 | 1,315 | off (your call: the higher ceiling pays) |
| 10-23 | ...the singleton alone | +0.86 | +5.05 | 806 | (part of the row above) |
| 10-23 | A singleton in GIB's own fit count (`_fit_bonus`), 1-3 points | -0.21 to -0.26 | -1.7 to -2.0 | 7-12 | off |
| 10-23 | Game by points: 3NT and minors at 32 judgement points (was 25), majors 26, opposite our 1NT/2NT 28; 4M over 3NT on a known 8-card major fit; respond on 7 HCP; LoTT to five. 3,000 fresh deals, 12,000 boards (`gib_fresh_h2h.py`) | **+6.78** | +14.61 | 2,220 | on (your call) |
| 10-23 | The jack counts 1 judgement point, not 0 (on top of the row above; 3,000 fresh deals) | **+1.17** | +4.46 | 516 | on (your call) |
| 10-23 | ...and 3NT at 34; at 30; majors at 27; a jack worth 2 | +1.27; +0.45; +0.89; +0.79 | +4.73; +1.62; +3.29; +2.25 | 553; 637; 559; 933 | off |
| 10-23 | ...4M over 3NT alone (5,957 fresh deals) | **+1.72** | +11.56 | 410 | (part of the row above) |
| 10-23 | ...game at 32 alone; at 28 | **+4.62**; +3.00 | +10.27; +8.64 | 2,097; 1,366 | (part of the row above) |
| 10-23 | ...a major game at 26 alone | +0.10 | +1.70 | 46 | (part of the row above) |
| 10-23 | A one-level overcall on 5 or 6 HCP (was 8): +1.5 to +1.8 on the library, then on fresh deals | -0.76 to -1.00 | -3.2 to -3.9 | 487-627 | off |
| 10-23 | Responding on 5 HCP (was 6): +1.2 on the library, then on fresh deals | -0.78 | -4.94 | 260 | off |
| 10-23 | Never bidding 3NT (library) | +0.67 to +1.37 | +0.45 to +0.98 | 289 | off |
| 10-23 | Overcall at 10+ HCP; takeout double at 14+ (fresh) | +0.12; +0.03 | +0.50; +0.35 | 497; 132 | off |
| 10-24 | Penalty double: where the robot would pass their natural suit bid and the system's X has no other meaning here, double with 5+ trumps, or 4+ at the three level, when our judgement points (mine plus the middle of partner's alerted range) reach 20; a side doubled for penalty never bids its strain higher. 3,000 fresh deals | **+4.09** | +7.40 | 750 | on (your call) |
| 10-24 | ...also where X is takeout or negative (one call, two meanings: breaks B4) | +7.30 | +9.67 | 1,402 | off |
| 10-24 | ...and before the doubled side stopped raising its own suit (the incumbent ran 4♦X to 7♦X) | +10.95 | +13.37 | 1,402 | (a bug's gain) |
| 10-24 | A cuebid raise shows 3+ of partner's suit to the LoTT (deal 338: 1♦ 1♠ X 2♦ - 2♠ 3♥ passed out on ten spades) | +0.24 | +2.88 | 61 | on (your call) |
| 10-24 | ...both together | **+4.34** | +7.77 | 809 | on |
| 10-28 | Ten trumps jam to game at once: partner's opening, my first call, any interference (or a pass after a pre-empt), majors (the user's Challenge deal: 2♠ X with ♠A10652). 10,000 fresh deals, measured before the rule below that nobody bids again after it | **+1.09** | +10.05 | 659 | on (your call) |
| 10-28 | ...the user's exact case only (weak two doubled) | +0.04 | +1.89 | 26 | (folded into the above) |
| 10-28 | ...with five of a minor too (with the raise below) | +0.27 more | | 282 | off (trips the no-runaway test) |
| 10-28 | A major raise counts trump length: HCP + 1 a trump past three (deal: 1♥ with ♠K5 ♥K9864 ♦K84 ♣832 raised to 2♥) | +0.13 | +2.94 | 215 | on (your call) |
| 10-28 | ...4M on any five trumps instead | 0.00 | +0.04 | 41 | off |
| 10-28 | ...jam and raise together, nobody bidding again after the jam | **+1.11** | +8.98 | 880 | on |
| 10-28 | ...the same, letting both compete again after the jam | +1.22 | +10.40 | 874 | off (the user's rule: never later) |

### The previous system (`ai_bid`)

Still answers the contested auctions GIB's notes leave to judgement, and is the
whole system behind `ai.USE_GIB = False`. Measured head to head against the
version before each change, on 300 deals, points a board; all made before the
first commit (2026-10-03):

| change | points | t | deals moved |
|---|---|---|---|
| A simple raise is never vetoed by the level cap | **+4.0** | +2.19 | 42 of 300 |
| A free bid of a long suit in competition | **+3.6** | +2.36 | |
| A lone rebid is no longer clamped to the partscore | **+3.6** | +2.92 | 26 of 300 |
| A length bonus of 0.25 a trump past the fourth | **+5.8** | +2.40 | |
| The UMD system card, all of it, against the pre-card AI | **+13.3** | +3.92 | 153 of 300 |

## Adding a row

1. Put the change behind a switch in `ai.py` or `gib.py`.
2. Measure it head to head: `python research/card_play_h2h.py SWITCH` for card
   play, `python research/gib_h2h.py SWITCH` for bidding (a defence rule, or
   one that plays for both sides, one side at a time if the net is unclear).
3. Write it up where it belongs (CHALLENGE.md or BIDDING.md), then add the row
   here with its date and status. A change that was measured and left off gets
   a row too.
4. After a change that's kept, rerun `python research/challenge_losses.py` and
   add a line to "Where the robots stand".
