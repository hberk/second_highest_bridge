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
| 2026-10-28 | fourth hand wins with a dead card first (`DEAD_WINNER_FIRST`; from the declaring side the play went from -11.8 to -21.0, see CHALLENGE.md; bidding before PR #40's jam rule) | **240.8** | **20.7** |
| 2026-10-28 | the same robots without it (PR #32's) | 240.8 | 12.1 |
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
| 10-28 | Of the cards that keep the trick, fourth hand plays a dead one first: the J♠, not the 6♠, ruffing from A♠ J♠ 6♠ (deal 10, `DEAD_WINNER_FIRST`). 800 fresh deals | **+0.029** | +2.83 | **+4.98** | 2,784 of 12,640 | on (your call; on the library: +0.062, t +3.33, +8.13 points) |
| 10-28 | ...for ruffs only | -0.001 | +0.65 | +0.87 | 1,528 of 12,640 | off |
| 10-28 | Third hand counts an overruff only as often as the next opponent can be out of the led suit, so it ruffs instead of discarding (deal 276, `RUFF_IF_FOLLOWS`). 800 fresh deals | +0.011 | +1.61 | +1.31 | 704 of 12,640 | on (your call; on the library: +0.018, t +2.57, +1.78 points) |
| 10-28 | ...in second hand as well | +0.007 | +1.10 | +0.51 | 744 of 12,640 | off |

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
| 10-28 | ...with five of a minor too (with the raise below) | +0.28 more | | 282 | on (your call) |
| 10-28 | A major raise counts trump length: HCP + 1 a trump past three (deal: 1♥ with ♠K5 ♥K9864 ♦K84 ♣832 raised to 2♥) | +0.13 | +2.94 | 215 | on (your call) |
| 10-28 | ...4M on any five trumps instead | 0.00 | +0.04 | 41 | off |
| 10-28 | ...jam (majors) and raise together, nobody bidding again after the jam | +1.11 | +8.98 | 880 | off |
| 10-28 | ...the same, letting both compete again after the jam | +1.22 | +10.40 | 874 | off |
| 10-28 | ...with minors, nobody bidding again | +1.38 | +9.54 | 1,162 | off |
| 10-28 | ...with minors, both competing again after the jam | **+1.50** | +10.64 | 1,156 | on (your call) |
| 10-28 | Partner's game stands: the fallback never raises partner's game while it is the highest bid (the user's training deal: 1♠ 3♦ P P 3♠ P 4♠ P 5♠). 10,000 fresh deals | **+0.36** | +5.99 | 184 | on |
| 10-28 | ...never bidding past game at all, over their bids too | -0.47 | -3.50 | 498 | off |
| 10-28 | A lone rebid at the three level or higher needs six cards (the user's rule: no 3♠ on five after a jump overcall). 10,000 fresh deals | **+0.27** | +3.82 | 237 | on (your rule) |
| 10-28 | ...and partner raises it on two cards | +0.28 | +3.63 | 300 | off (adds nothing) |
| 10-28 | Advancer's 2NT is the limit raise or better when the cuebid would pass three of partner's suit; the cuebid asks for a stopper (deal 276: 1♦ (2♣) 2♦ 3♦) | +0.07 | +1.72 | 173 | on (your call) |
| 10-28 | ...a game-forcing cuebid instead, limit hands raising to three | +0.12 | +2.81 | 159 | off (a tie with the above, -0.05, t = -1.3) |
| 10-28 | ...2NT a 10-12 limit raise, the cuebid game forcing | +0.02 | +0.38 | 172 | off |
| 10-28 | ...the game-forcing cuebid for responder too | +0.11 | +1.62 | 402 | off |
| 10-28 | A takeout doubler's new suit shows 18+ HCP and 5+ cards, bid through the two level; under 18 it passes; advancer raises it (training deal: 1♥ P P X 2♥ P P 2♠ read as an overcall). 20,000 fresh deals | +0.04 | +2.36 | 123 | on (your call) |
| 10-28 | ...bid through the three level | -0.01 | -0.18 | 388 | off |
| 10-28 | ...the 18+ meaning and the pass under 18 only, no new bids | +0.01 | +1.89 | 23 | off |
| 10-28 | ...2NT a 10-12 limit raise for responder too | -0.19 | -2.16 | 490 | off |
| 10-28 | Runouts after our 1NT is penalty-doubled (the user's DONT-like system), responder running with 4 HCP or less; the 1NT bidder never uses Stayman or transfers (training board 25). 20,000 fresh deals | **+0.09** | +2.17 | 374 | on (your call) |
| 10-28 | ...running with 7 HCP or less | +0.07 | +1.55 | 439 | off |
| 10-28 | ...with 7, opener never pulling a pass | +0.05 | +1.25 | 424 | off |
| 10-28 | ...running with 10 HCP or less | +0.03 | +0.58 | 460 | off |
| 10-28 | A double of their artificial bid is lead-directing: 5+ cards, 4+ judgement points in the suit, partner leads it (user's board: P P P 2♣ P 2♦ X with ♦KJT97, read as takeout); scored after the robot's real lead | +0.13 | +2.96 | 363 | on (your call) |
| 10-28 | ...5+ judgement points | +0.03 | +1.41 | 193 | off |
| 10-28 | ...6+ judgement points | -0.01 | -1.13 | 86 | off |
| 10-28 | ...any five cards | +0.13 | +2.19 | 712 | off |
| 10-28 | Respond 1-level on 5+ HCP with a singleton or void in opener's minor (fresh deals, as below) | **+0.19** | +3.41 | 241 | on (your call) |
| 10-28 | 3♣ checkback over opener's 2NT rebid (1♦ 1♥ 2NT 3♣) | **+0.08** | +3.28 | 126 | on (your call) |
| 10-28 | New minor forcing: opener answers at the two level, responder's next call judged on the fit (6-card major 2♠ over 2♥) | +0.03 | +1.63 | 88 | on (your call) |
| 10-28 | ...responder's next call alone, opener still jumping to 3M on 13-14 | +0.00 | +0.14 | 17 | off |
| 10-28 | A pre-emptor does not bid again unless partner's last call asks (training deal 270: P 2♦ (2♥) 2♠ (3♦) 3NT); the penalty double kept. 10,000 fresh deals | -0.08 | -1.45 | 131 | on (your call: the rule, a tie) |
| 10-28 | ...no penalty double from the pre-emptor either | -0.20 | -3.08 | 143 | off |
| 10-28 | ...only the branch that bid 3NT stops reading a pre-empt as forced | +0.01 | +1.34 | 4 | off |
| 10-28 | Over a minor opening, a five-card major is bid, not doubled (`NEG_BIDS_FIVE`; deal: 1♦ (1♥) X on six spades) | **+0.71** | +6.5 | 1,044 | on |
| 10-28 | Opener answers a negative double only once (`NEG_ANSWER_ONCE`; same deal, opener came back with 3♣) | -0.09 | -3.7 | 69 | off |
| 10-28 | Weak two suit by judgement points: none at favourable or equal, 2 unfavourable, +1 in second seat (training deal: ♥QT9865 passed) | **+1.31** | +7.46 | 2,081 | on (your call) |
| 10-28 | ...no suit test at all; 2+ points flat; one of A K Q; 3+, 4+, 5+ points | +1.41; +1.15; +0.93; +0.84, +0.49, +0.04 | +7.83; +6.69; +5.98; +5.85, +3.88, +0.39 | 2,186; 1,932; 1,618 | off (no test beat the chosen bar by +0.10, t = +2.45) |
| 10-28 | ...other spreads (fav/equal/unfav, +1 second seat): 0/1/3, 0/2/4, 0/3/5 | +1.18; +1.11; +0.94 | +6.87; +6.82; +6.48 | | off |
| 10-29 | The seven 10-28 fixes together (runouts, lead-directing double and the doubler never bidding again, NMF/checkback/light response, pre-emptor passes, double-then-suit 18+, five-card major over a negative double, weak two by judgement points) against main before PR #44; 1,000 fresh deals, scored after the robot's real opening lead (`/mnt/project-files/combined-bidding/combo.py`) | **+2.47** | +3.10 | 402 | on (PR #48); with the best lead instead +0.92, t = +1.24 |
| 10-29 | Reopening after 1x P P, every overcall and takeout floor 4 HCP lighter (`BALANCE`; championship study, see BIDDING.md); three sets of 3,000 fresh deals | +0.85, +0.19, +0.10 | +4.19, +0.86, +0.42 | 280, 279, 255 | on |
| 10-29 | One level past the LoTT over their raised three-level suit when our fit + 8 + my shortness reach 18 (`LOTT_TOTAL`) | +0.06, +0.17, +0.18 | +2.40, +2.73, +2.47 | 12, 26, 27 | on |
| 10-29 | Both together | **+0.91, +0.36, +0.27** | +4.46, +1.59, +1.12 | 292, 305, 282 | on |
| 10-29 | Balancing over their raise, 1x P 2x P P, 4-5 HCP lighter (suit bids, or takeout doubles only) | -0.14 to -0.26 | -1.6 to -2.1 | 76-92 | off (light balances get doubled); measured against pre-#48 robots |
| 10-29 | No weak jump overcall at unfavourable vulnerability / when vulnerable | -0.29 / -0.69 | -1.60 / -2.35 | 210 / 440 | off; measured against pre-#48 robots |
| 10-29 | Sounder two-level overcalls on a five-card suit, 12+ / 14+ HCP (experts 8-13% of such hands, robots 39-40%); seed 8M, 3,000 deals | -1.15 / -1.43 | -3.99 / -3.99 | 633 / 921 | off |
| 10-29 | Takeout double, not an overcall, with a five-card suit and 0-1 in theirs | -0.32 | -1.85 | 195 | off |
| 10-29 | A three-level pre-empt needs 3+ judgement points in the suit (all vulnerabilities / not favourable) | -0.27 / -0.23 | -2.70 / -2.59 | 41 / 45 | off |
| 10-29 | Weak jump overcalls only to the two level | -0.53 | -2.25 | 357 | off |
| 10-29 | A three-level overcall of a weak two on five cards needs 15+ | -0.04 | -0.27 | 154 | off |
| 10-29 | A pre-emptive jump raise of partner's minor over an overcall needs five trumps | -0.04 | -0.47 | 130 | off |

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
