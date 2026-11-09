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
| 2026-11-03 | v0.1.0-alpha (PR #62): the Nov 3 bidding fixes, the 6-5 Michaels invite, the opening-suit cuebid fix | **233.1** | **5.0** |
| 2026-11-03 | main before PR #62 (PR #61's robots, every bidding change through 11-02) | 233.6 | 5.3 |
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
count. The card-play column is net, so it looks close to double dummy, but it
isn't: see "Card play, mistakes added up" below. The auction is where the
points are. The 2026-10-22 bidding changes moved the auction figure by
nothing (235.4 against 234.9) although each wins +4.66 a board head to head:
all four seats use them here, so what N/S gain E/W gain back; from the
declaring side the auction loss fell from 215.8 to 211.9. (An older figure, 143.7 / 31.8, was one auction per deal before any
card-play change below, so it isn't comparable.)

### Card play, mistakes added up

The figure to quote for card play. `research/robot_line_report.py` scores
every card the all-robot table plays against double dummy and adds each
side's costly cards: tricks given away a board, the share of real choices
(the legal cards don't all score the same) that cost a trick, and the share of
boards with at least one costly card. Lower is better. A fix is reported as
the change in these, before and after, on the same deals
(`robot_line_report.py --compare`), next to its head-to-head gain.

| measured | robots | deals | declaring side | opening lead | defence after the lead | boards with a costly card | net (cancels) |
|---|---|---|---|---|---|---|---|
| 2026-11-07 | **the Nov 6 fixes together (v0.1.3-alpha)**: the second-hand cover with dummy leading, the third-hand plan, `SURE_LEAD_UNRUFFED` and the bidding fixes (`/mnt/project-files/nov6-combined/line_report_vs_v012.txt`) | 199 | **2.59** (18%, 89%) | **0.40** (35%, 33%) | **2.12** (18%, 84%) | 95% | +0.08 |
| 2026-11-06 | main plus the third-hand plan (`THIRD_SEES_LAST`, `THIRD_HAND_PLAN`; `/mnt/project-files/third-sees-last/report_wide.txt`, against main measured the same day) | 199 | **2.68** (18%, 90%) | **0.40** (36%, 33%) | **2.25** (20%, 87%) | 97% | +0.03 |
| 2026-11-05 | v0.1.2-alpha with `SECOND_HAND_COVER_DUMMY_LED` (`/mnt/project-files/dummy-led-cover/gross_mistakes.txt`) | 199 | **2.66** (18%, 90%) | **0.40** (36%, 33%) | **2.29** (21%, 86%) | 95% | -0.03 |
| 2026-11-06 | main + `SURE_LEAD_UNRUFFED` alone (deal 157's K♥; `/mnt/project-files/sure-lead-unruffed/report.txt`) | 199 | **2.71** (18%, 90%) | **0.40** (36%, 33%) | **2.38** (21%, 88%) | 96% | -0.07 |
| 2026-11-05 | the Nov 4 evening fixes together (v0.1.2-alpha; `/mnt/project-files/nov4-evening-combined/line_report.txt`) | 199 | **2.74** (19%, 91%) | **0.40** (36%, 33%) | **2.41** (22%, 88%) | 97% | -0.07 |
| 2026-11-05 | main after PR #63 (v0.1.1-alpha) | 199 | **2.81** (19%, 91%) | **0.40** (36%, 34%) | **2.48** (22%, 89%) | 97% | -0.07 |
| 2026-11-05 | the same robots, first 100 deals | 100 | 2.69 (18%, 90%) | 0.39 (36%, 34%) | 2.40 (22%, 87%) | 97% | -0.11 |
| 2026-10-18 | before the trump-drawing fix and every play rule after it (`robot_lines_2026-10-18.jsonl`) | 100 | 3.94 (25%, 96%) | 0.41 (38%, 36%) | 3.85 (30%, 96%) | 97% | -0.32 |

Tricks given away a board (share of real choices that cost, share of boards
with one). Where it goes today: tricks 10-13, which the robots search over
every layout, 2% of cards cost a trick; tricks 5-9 about 15%, the largest
share for both sides; leads cost most (18% of declaring-side leads, 1.5 of
its 2.8 tricks). Double dummy sees all four hands, so part of each figure is a
guess no player could make, the opening lead most of all.

**Why not the net figure.** "Below double dummy" (the table next) is double
dummy minus declarer's tricks with robots defending: a trick the defence gives
away cancels one declarer gave away, so a board where each side drops two
tricks scores 0. In 2026-11-05's lines, 60% of the boards where declarer made
a costly card still finished at or above double dummy.

The robot declarer against double dummy, net, before the head-to-head metric
existed (397 library boards, GIB auctions, tricks below double dummy a board;
superseded by the table above):

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
| 10-30 | In notrump a defender on lead goes back to the opening-lead suit (championship records: experts 60%, robots 28%; `NT_DEFENCE_SUIT`). 400 fresh deals | **+0.046** | +2.64 | **+5.69** | 638 of 6,379 | on (your call; on the library: +0.052, t +2.70, +3.52 points) |
| 10-30 | ...partner's opening lead only (library) | +0.042 | +2.71 | +2.85 | 532 of 6,367 | off |
| 10-30 | With the defence out of trumps, a trump lead that partner must follow becomes a ruff in partner's hand (your 4♠ board, `IDLE_TRUMP_FOR_RUFF`). 400 fresh deals | +0.012 | +2.57 | +1.00 | 108 of 6,379 | on (your call; on the library: +0.009, t +2.14, +0.71 points) |
| 10-30 | ...never lead an idle trump at all | -0.001 | -0.22 | +0.58 | 419 of 6,379 | off (library +0.021, t +2.04: a trump lead is sometimes the entry) |
| 10-30 | ...and ruff at once | -0.004 | -0.38 | +1.01 | 582 of 6,379 | off (library +0.011, t +0.84) |
| 10-30 | Both shipped rules together. 400 fresh deals | **+0.058** | +3.24 | **+6.69** | 746 of 6,379 | on (library: +0.061, t +3.09, +4.23 points) |
| 10-30 | The opening lead in partner's suit is my top honour when partner showed 4+ judgement points there (board 26, `PARTNER_HONOUR_LEAD`). Library | +0.002 | +1.34 | +0.41 | 24 of 6,367 | on (your rule; 6 leads, net +1 double dummy; never fired on 400 fresh deals) |
| 10-30 | Second and fourth hand on the declaring side break a tie by playing the suit out with the count; second hand plays the lowest of equals and never spends the suit's top card (board 26, `COVER_SUIT_PLAN`, `COVER_PLAN_LOW`, `COVER_KEEP_MASTER`, `LAST_SUIT_PLAN`). 400 fresh deals, before `COVER_KEEP_MASTER` | +0.017 | +0.82 | +2.12 | 1,313 of 6,352 | on (library -0.001, t -0.07. Each changed card double dummy, with `COVER_KEEP_MASTER`: library 61 better / 21 worse, net +45; fresh 59 / 19, net +49) |
| 10-30 | ...second hand only; second hand keeping its old pick among equals; fourth hand only (library) | -0.007; -0.007; +0.007 | -0.45; -0.48; +0.69 | +0.71; +0.04; +0.80 | 1,052; 996; 480 | the package on |
| 10-30 | Second hand, dummy third and partner unseen, plays the suit out over partner's and declarer's layouts and plays the card that takes most: the A♠ over T♠ led with dummy 9-6 (your board, `SECOND_HAND_COVER`). Library | **+0.081** | +3.46 | **+8.72** | 1,967 of 6,367 | on (400 fresh deals: +0.059, t +2.79, +5.27 points. Each changed card double dummy: library 147 better / 27 worse, net +170; fresh 140 / 33, net +147) |
| 10-30 | ...judged on this trick alone: the chance partner holds a winning card after dummy's best reply (library; fresh) | +0.061; +0.041 | +3.30; +2.07 | +4.93; -0.88 | 1,220; 1,097 | off (the plan above gains more; it stays as the fallback when the plan can't run) |
| 10-31 | ...this trick's chance with the plan vetoing a worse card (library; fresh) | +0.054; +0.036 | +3.03; +2.11 | +3.72; +2.22 | 1,084; 1,007 | off |
| 11-04 | Fourth hand, out of the led suit with partner already winning, discards instead of ruffing: East ruffed dummy's winning 5♣ with the Q♥ (your board, `PARTNER_WINS_NO_RUFF`). Seated, 3 × 1,000 fresh deals (seeds 1104-1106) | **+0.015** | +3.45; +4.28; +2.63 | **+2.15** | 2,469 of 47,576 | on |
| 11-04 | Second to fourth hand play a trump or notrump suit out exactly once every card of it is located: T♥ from T5 with dummy 42 and South AQ6 (your 4♥, `LOCATED_SUIT_PLAN`). 3 × 1,000 fresh deals | **+0.016; +0.014; +0.010** | +3.74; +3.63; +3.53 | **+2.34; +1.72; +1.65** | 376; 322; 267 of ~15,800 | on (your call) |
| 11-04 | ...any suit, later ruffs ignored (seed 1104 only) | +0.019 | +3.93 | +2.55 | 521 of 15,816 | off (not finished on the other seeds) |
| 11-05 | `PARTNER_WINS_NO_RUFF` and `LOCATED_SUIT_PLAN` together on one side against neither (v0.1.2-alpha). Seated, 3 × 1,000 fresh deals (seeds 1104-1106, `/mnt/project-files/nov4-evening-combined/play_*.txt`) | **+0.034; +0.032; +0.021** | +5.08; +5.57; +4.18 | **+4.70; +5.30; +2.46** | 1,351; 1,073; 1,010 of ~15,850 | on |
| 11-05 | Second hand with dummy leading, declarer third and partner last plays the suit out over declarer's and partner's layouts: the T♣ from K T 7 4 3 over dummy's 9♣ (your board, `SECOND_HAND_COVER_DUMMY_LED`). Library | **+0.045** | +2.53 | **+5.33** | 1,367 of 6,367 | on (400 fresh deals, seed 1105: +0.051, t +2.81, +6.36 points; mistakes added up on 199 deals: declaring 2.74 -> 2.66, lead 0.40, defence 2.41 -> 2.29) |
| 11-06 | Third hand, dummy last, plays the cheapest card that wins whatever dummy does: Q♦ from AQ42 under dummy's lone K♦ (your board, deal 319, `THIRD_SEES_LAST`). Library | +0.012 | +2.77 | +1.40 | 108 of 6,367 | on (gross mistakes, 199 deals: defence 2.41 -> 2.39) |
| 11-06 | Third hand on defence plays the led suit out over partner's and declarer's layouts, ruffs counted, dummy or declarer last; also J♦ from AJ9732 under dummy's KQ (your board, deal 58, `THIRD_HAND_PLAN = 2`), with `THIRD_SEES_LAST`. Library | **+0.052** | +3.11 | **+4.01** | 992 of 6,367 | on (400 fresh deals, seed 1106: +0.053, t +3.06, +6.06 points; card by card on 199 solved deals +0.060 tricks a board: declarer last only +0.038, side suits off +0.049, ruffs ignored +0.057) |
| 11-07 | **The Nov 6 card-play fixes together (v0.1.3-alpha)**: `SECOND_HAND_COVER_DUMMY_LED`, `THIRD_SEES_LAST`, `THIRD_HAND_PLAN = 2` and `SURE_LEAD_UNRUFFED` on one side against none of them. Seated, 3 × 1,000 fresh deals (seeds 1104-1106, `/mnt/project-files/nov6-combined/play_*.txt`) | **+0.097; +0.104; +0.094** | +6.30; +6.77; +6.26 | **+12.84; +11.95; +10.59** | 6,156; 6,092; 5,923 of ~15,860 | on |

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
| 10-30 | Defence switches to a trump when dummy can ruff (championship records: experts 22%, robots 9%) | -0.008 (t = -0.86); narrowed +0.002 | a defender's trump lead gives away trump tricks here |
| 10-30 | Defence avoids leading into dummy's void (experts 6%, robots 12%) | -0.025 (t = -1.96) | worse |
| 10-30 | Declarer ruffs in the short hand before drawing, more often (one or two more rounds allowed) | +0.004; -0.004 | the robots already match experts when ruffs are there |

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
| 10-29 | A forced continuation reads partner's own call, not my notrump after it (1S-1NT no longer treats a natural 1S as forcing), and never bids a three-card suit (`FORCED_SUIT_MIN = 4`, the user's rule); seed 8M, 3,000 deals | +0.10 / +0.21 | +0.64 / +1.87 | 49 / 8 | on (bug fix) |
| 10-29 | Review fix: balancing lowers only the overcall floor, so 14-17 HCP with five cards still overcalls (`BALANCE`); seed 8M, 3,000 deals | +0.27 | +2.90 | 76 | on (bug fix) |
| 10-29 | `LOTT_TOTAL` only with 6+ HCP / only not vulnerable / both, each with the fix above, against the same base | +0.18 / +0.18 / +0.15 | +1.65 / +1.68 / +1.31 | 86 / 89 / 93 | 6+ HCP on (the user's call: no 4♥ on 3 HCP) |
| 10-30 | Partner's balancing overcall, 1x P P 2y, reads as an overcall (6+ HCP), not an opening (a balancing 2♣ was a strong 2♣: 3NT on a passed 10 HCP; `BALANCE_READ`); three sets of 3,000 fresh deals | +0.01, +0.22, +0.05 | +0.45, +2.89, +1.53 | 10, 12, 5 | on (bug fix) |
| 10-30 | ...a balancing two-level overcall needs 8+ (bid and read) / partner reads it as 8+ | -0.12, -0.27, -0.21 / 0 | -1.91, -2.71, -2.76 / | 29, 30, 40 / 0 | off (6+ kept) |
| 10-30 | A natural 2♣ overcall (direct or balancing, not over 1♣) is clubs in every reading: not forcing, counts for the fit, keycard asks and the LoTT (`NATURAL_2C`) | **+0.11, +0.26, +0.14** | +1.50, +2.03, +2.05 | 38, 73, 65 | on (bug fix) |
| 10-30 | ...and handed to `ai_bid` instead of GIB's `continuation` | -0.20, +0.06, +0.47 | -1.34, +0.25, +3.33 | 118, 194, 172 | off (competes much higher) |
| 10-30 | Review of PR #54: our 2♣ over their 1NT is Cappelletti (10+, not game forcing) / a natural 2♣ after their response, (1♦) P (1♥) 2♣, is an overcall / both (`OVER_1NT_2C`, `OVERCALL_AFTER_RESPONSE`) | +0.18, +0.16, +0.14 / +0.03, -0.06, +0.01 / **+0.18, +0.19, +0.14** | +1.39, +1.63, +1.27 / +0.48, -1.05, +0.95 / +1.37, +1.82, +1.27 | 85, 75, 97 / 12, 13, 3 / 90, 80, 99 | on (bug fixes) |
| 10-30 | Responder's cuebid raise of a minor needs 4+ ♦ / 5+ ♣ (`CUE_MINOR_SUPPORT`) / pre-emptive jump raise of a minor 5+ ♦ / 6+ ♣ over interference / and 1♣-3♣ on 6+ (10,000 fresh deals) | **+0.18** / -0.02 / -0.03 | +1.91 / -0.14 / -0.26 | 474 / 899 / 935 | on / off / off (your call: weak raises stay) |
| 10-31 | After the support double and RHO's bid, responder rebids the suit only with five (`SUPPORT_X_FREE`; the user's board) / with six; seed 12M, 10,000 deals | +0.05 / -0.02 | +1.93 / -0.56 | 82 / 186 | five on |
| 10-31 | After partner's two-suiter and RHO's bid, advancer competes only to the level of a fit (`TWO_SUITER_FREE`); seed 13M, 10,000 deals | +0.09 | +1.10 | 280 | on |
| 10-31 | After partner's cuebid raise and RHO's bid, a minimum passes unless the fit reaches the level | -0.04 | -0.36 | 414 | off (removed) |
| 10-31 | Slam on points needs 37 judgement points, not 33 (`SLAM = 37`: 6NT, quantitative 4NT, keycard; the championship study of uncontested auctions); three sets of fresh deals (4,000, 6,000, 6,000) | **+0.93, +1.07, +0.91** | +6.95, +8.99, +8.61 | 109, 165, 144 | on |
| 10-31 | ...the notrump slams alone (6NT, quantitative 4NT) / keycard alone | +0.78, +0.94, +0.53 / +0.05, +0.03, +0.15 | +6.40, +8.61, +6.98 / +2.27, +0.93, +3.63 | 102, 141, 126 / 7, 24, 18 | both on, as above |
| 10-31 | Opener passes when responder declines the game try (1M 2M try 3M), instead of bidding game anyway; two sets | -0.01, -0.08 | -0.11, -2.09 | 61, 49 | off |
| 11-02 | Smolen over 1NT and 2NT (`SMOLEN`; the user's request): library / seed 14M, 10,000 fresh deals | +0.02 / -0.01 | +0.82 / -1.55 | 6 / 22 | on (your request; rare, and the losses are Stayman auctions they overcall) |
| 11-02 | Stayman when they overcall it: opener shows a four-card major, responder raises it or bids a five-card major (`STAYMAN_CONTESTED`); with responder's 3NT and 2NT / without 3NT / without either; seeds 14M, 15M, 10,000 deals each | +0.00, +0.04 / +0.02, +0.05 / **+0.02, +0.07** | +0.10, +1.52 / +1.24, +2.07 / +1.58, +3.24 | 44, 58 / 34, 46 / 21, 31 | without either on |
| 11-02 | Partner's raise of my own suit is agreed, not partner's suit: only game once they pass (`OWN_SUIT_RAISED`); a weak jump overcaller passes after partner's raise (`JUMP_OVERCALL_PASSES`); their double of partner's asking call leaves it asking (`PREEMPT_ASK_DOUBLED`); a 10-card fit jams game over partner's weak jump overcall when we are not vulnerable (`JAM_WJO_VUL = 'white'`); three sets of 3,000 fresh deals | -0.00, +0.49, -0.04 | -0.01, +3.39, -0.26 | 267, 252, 239 | on (your choice) |
| 11-02 | ...the jump overcaller's pass alone / jam only white vs red / without the jump overcaller's pass | -0.26, -0.00, -0.26 / -0.09, +0.40, -0.16 / +0.25, +0.52, +0.14 | -2.95, -0.07, -2.85 / -0.56, +3.07, -0.94 / +1.60, +3.76, +0.94 | 34, 27, 34 / 242, 218, 217 / 241, 230, 212 | pass on (your rule), fav off |
| 11-02 | A free bid over partner's pre-empt counts partner as a raise, not an opening (`PROMISE_PREEMPT`; your training deal 315, 3♣ (3♠) 4♥ on six hearts); seed 7M, 10,000 deals; promise 2.06 / 1.0 / 0.0 | **+0.26** / +0.26 / +0.23 | +3.46 / +3.12 / +2.61 | 247 / 290 / 308 | 2.06 on |
| 11-02 | Advancer with 7+ cards in an unbid suit and 4-9 HCP jumps in it, pre-emptive; eight in a major bid game (`LONG_ADVANCE`; the user's item 6, experts name such a suit 51% of the time, robots 3%); seeds 7M (3,000 deals), 8M, 9M (10,000 each) | **+0.06, +0.08, +0.06** | +1.55, +2.34, +1.85 | 16, 69, 39 | on |
| 11-02 | ...from 0 HCP / the same jump by responder over their overcall (seed 7M only for the latter) | +0.09, +0.07 / -0.20 | +2.36, +1.96 / -2.20 | 99, 45 / 30 | off (4 HCP kept, conservative) / off |
| 11-02 | 1M (their overcall) 2NT is natural 11-12, not Jacoby, in every reading (`NATURAL_2NT`; the user's item 20, P 1♥ (1♠) 2NT P 4♥ on five hearts); opener accepts with 14+ HCP (4M with six, else 3NT), else passes or 3M with six; seeds 8M, 9M | +0.02, -0.02 | +1.08, -0.48 | 16, 16 | on (bug fix, neutral) |
| 11-02 | ...the reading alone, opener always passing / accepting at 13 / 15 / natural over Michaels too | -0.03, -0.08 / -0.03, -0.03 / -0.02, -0.06 / -0.02, -0.04 | -1.09, -2.40 / -1.40, -0.89 / -0.64, -1.95 / -0.64, -1.18 | 20, 31 / 19, 29 / 21, 31 / 21, 28 | off |
| 11-02 | After their bid over Stayman (review of the combined PR): a 2NT opener bids 3NT with a stopper; four of their suit and a stopper double for penalty; responder's game force doubles with four, else 3NT with a stopper, else passes (`STAYMAN_OPENER_3NT`, `STAYMAN_PENALTY_X`, `STAYMAN_RESPONDER_3NT`); seeds 14M, 15M, 10,000 deals each | **+0.04, +0.03** | +2.09, +1.80 | 12, 17 | on |
| 11-02 | ...also 3NT with no stopper (`STAYMAN_NO_STOP = '3NT'`) / a double on values instead / without the penalty doubles | +0.04, +0.03 / +0.02, +0.01 / -0.02, -0.01 | +1.74, +2.15 / +0.71, +0.33 / -2.40, -1.44 | 18, 22 / 18, 22 / 10, 14 | off (its 3NTs all went down) |
| 11-02 | Monday's combined bidding fixes, every switch above from 11-02 on against all of them off (which bids 4,000 of 4,000 auctions exactly as main), plus the pass-out-seat fix to `weak_jump_overcall`; seed 7M, 1,000 fresh deals (`/mnt/project-files/monday-combined/`) | +0.55 | +1.19 | 138 | on |
| 11-03 | A takeout double of 1♣/1♦ with 4-4 majors and three or fewer of their suit, a doubleton in the other minor allowed (`MAJORS_TAKEOUT`; the user's board, ♠AKQ7 ♥QJ92 ♦T98 ♣J4 over 1♦; experts double 12-14 HCP 24/29 over 1♦, 13/21 over 1♣) / direct and balancing seat (`MAJORS_TAKEOUT_BALANCE`); seeds 7M, 8M, 9M, 3,000 deals each | -0.06, -0.01, +0.01 / +0.09, -0.04, +0.01 | -1.19, -0.58, +0.75 / +0.98, -1.25, +0.37 | 25, 17, 11 / 42, 21, 14 | both seats on (your choice; neutral) |
| 11-03 | After our Michaels or Unusual 2NT, partner's choice of suit stands: pass unless 17+ HCP, compete reading partner as an advancer (`TWO_SUITER_CHOICE`); three sets of 3,000 fresh deals | -0.06, +0.10, +0.21 | -0.38, +0.51, +1.33 | 50, 59, 58 | on (your choice) |
| 11-03 | Balancing over a weak two, 2x P P: a six-card suit balances at the two level 3 HCP lighter (7+), and a three-level balance needs six cards (`BALANCE_WEAK_TWO`; the user's deals: 2♠ on QJT742 AT 92 T75 missed, 3♣ on 96432 went -300); three sets of 3,000 fresh deals. The gate alone: +0.03, -0.03, +0.00; the lighter 2-level balance alone: +0.00, +0.11, +0.07; a 4 HCP discount +0.07, +0.08, +0.08; five cards with two of A/K/Q at the three level -0.03, +0.09, +0.09 | +0.04, +0.08, +0.07 | +0.41, +1.12, +0.90 | 60, 55, 74 | on (your call) |
| 11-03 | An eight-card major with 9-15 HCP bids game at once over their one-level opening (`BLAST_GAME`); seeds 7M, 8M, 9M, 3,000 fresh deals each / 1,500 deals each filtered for such a hand (`/mnt/project-files/reverse-blast/`) | **+0.12, +0.07, -0.03** / **+11.9, +9.8, +14.2** | +2.33, +1.53, -1.69 / +9.65, +8.93, +10.59 | 6, 11, 10 / 1,107, 1,016, 1,211 | on |
| 11-03 | Opener reverses after 1x (y) 1NT or a one-level new suit, 16+ HCP, with the raise of a minor (`REVERSE_CONTESTED`, `REVERSE_MINOR_RAISE`); 4,000 deals each filtered for a reversing hand | -0.02, -0.09, -0.01 | -0.72, -4.26, -0.52 | 28, 48, 40 | on (your call, 11-03) |
| 11-03 | ...18+ HCP / five cards in the reverse suit (`REVERSE_HCP = 18` / `REVERSE_Z_LEN = 5`) | -0.04, -0.05, -0.01 / -0.00, +0.00, +0.00 | -2.43, -3.07, -1.41 / -1.00, 0, 0 | 12, 16, 2 / 1, 0, 2 | off |
| 11-03 | The overcaller answers partner's 2NT asking for the minor over their 1NT, (1NT) 2♥/2♠ (P) 2NT: 3♣/3♦, only when their 1NT is their only bid (`MINOR_ASK_ANSWER`; the user's deal, P P 1NT 2♥ P 2NT passed out two down). Before, nobody answered and the artificial 2NT played; seeds 7M, 8M, 9M, 10,000 deals each | -0.02, -0.01, -0.05 | -0.88, -0.88, -2.39 | 39, 19, 22 | on (your choice: a bug fix, since passing an artificial 2NT isn't bridge, and the robots never double a notrump partscore) |
| 11-03 | ...answering after their other bids too (a transfer, Stayman, a double) / the advancer asking only with 3+ / 4+ in each minor / never asking | -0.15, -0.05, -0.13 / -0.03, -0.03, -0.09 / -0.05, -0.03, -0.10 / -0.11, -0.06, -0.17 | -2.27, -1.43, -3.02 / -0.90, -0.94, -3.67 / -1.40, -0.85, -3.25 / -2.60, -1.52, -4.13 | 74, 56, 54 / 48, 24, 33 / 60, 39, 46 / 74, 61, 59 | off |
| 11-03 | Negative doubles with Lebensohl over 1NT (2♥/2♠): the double shows 8+ HCP, not four of their major; opener passes with four of theirs, else bids four of the other major, 2NT/3NT with a stopper, or a minor (`NEG_X_1NT`; the user's system); with the overcaller answering the 2NT ask over the double too (`MINOR_ASK_OVER_X`); seeds 7M, 8M, 9M, 10,000 deals each | -0.01, -0.00, +0.00 | -0.56, -0.01, +0.53 | 36, 11, 12 | on (your system) |
| 11-03 | ...the double at 10+ HCP / the answer over the double alone | -0.00, +0.01, +0.00 / +0.02, +0.00, -0.03 | -0.14, +0.46, +1.06 / +1.11, +0.80, -1.53 | 23, 11, 6 / 13, 9, 7 | off / on |
| 11-03 | The review of PR #62's three fixes: after the negative double over 1NT (2♥/2♠), 10+ HCP reaches game (a 4-3 major fit without a stopper, 4♣/♦ or 5♣/♦ on 12+, 3NT after opener's major) (`NEG_X_GAME`), and over their bid after the double opener bids four of the other major at the three level or doubles with four of theirs, responder doubles or bids 3NT on 10+ (`NEG_X_COMPETE`); the reverser bids 4♥/♠ over responder's 3♥/♠ on 6-5/5-5 or 18+ HCP (`REVERSE_MAJOR_RAISE`, fired on no deal); seed 7M, 10,000 fresh deals (`/mnt/project-files/pr62-review/measure/`) | -0.00 | -0.35 | 9 | on (your choice) |
| 11-03 | The Nov 3 combined bidding fixes, every switch above from 11-03 on against all of them off (which bids 4,000 of 4,000 auctions exactly as main); seed 7M, 1,000 fresh deals (`/mnt/project-files/nov3-combined/`). By fix: `TWO_SUITER_CHOICE` alone -0.56 (t -3.16, 13 auctions, 0 better: 6-5 two-suiters and a 16 HCP 5-5 no longer bid game over partner's choice), everything but it -0.07 (t -0.53); `BLAST_GAME` and `REVERSE_CONTESTED` moved no auction on these deals | -0.62 | -2.90 | 48 | on (each switch is the user's pick; `TWO_SUITER_CHOICE` measured +0.08 over 9,000 deals in its own thread, and these 1,000 are the start of its seed-7M set, -0.06 there) |
| 11-03 | A 6-5 Michaels / Unusual 2NT bidder raises partner's choice a level, inviting; advancer bids game with 8+ HCP, 6+ with four trumps (`TWO_SUITER_SHAPE = 'invite'`; the user's "6-5, come alive"); seeds 7, 8, 9 (billions), 1,500 deals each filtered for a 5-5 or better hand, against the bug fix below on both sides (`/mnt/project-files/shape-michaels/`) | **+0.60, +0.99, +0.49** | +2.43, +3.51, +1.59 | 47, 27, 75 | on (your pick) |
| 11-03 | ...but no invite over their double of partner's choice: pass and let them pay a level lower (`TWO_SUITER_SHAPE_DOUBLED = False`; the user's call); the same filtered deals | **+0.26, +0.00, +0.40** | +2.34, 0, +2.77 | 6, 0, 12 (15 better, none worse) | on |
| 11-03 | ...game at once with 6-5 / 5-5 inviting too (measured against the bug still in) | -0.05, +0.78, -1.69 / -0.84, -0.74, -2.53 | -0.16, +3.18, -3.56 / -1.53, -1.04, -3.73 | 39, 27, 71 / 141, 141, 166 | off |
| 11-03 | Partner rebidding the suit partner opened is not a cuebid raise (`CUE_REPLY_OWN_REBID`; 1♦ (2♦) P (2♠) P P 3♠ P 4♦ P: the 3♠ cuebidder read 4♦ as a cuebid and bid 4♠ on a doubleton, -1,800 to -2,100 doubled); the same filtered deals / seed 7M, 1,000 fresh deals with the invite | **+1.26, +2.02, +3.47** / +0.07 | +3.26, +2.89, +4.84 / +1.14 | 29, 25, 43 / 5 | on (bug fix) |
| 11-03 | Over their bid after partner's choice, 5+ cards compete one level higher (to 4M at most) when the choice was free or a jump: the level of the fit (`TWO_SUITER_FIT_COMPETE`; the user's call); filtered sets as above / seeds 7M, 8M, 9M, 1,000 fresh deals each | +0.23, -0.01, +0.09 / +0.21, -0.07, -0.26 | +2.12, -0.07, +0.60 / +1.69, -1.00, -1.37 | 5, 24, 14 / 3, 1, 4 | on (your call; neutral) |
| 11-03 | **The whole of PR #62 (v0.1.0-alpha)**: every switch above from 11-03 on, the review fixes and the 6-5 invite, against all of them off (which bids 4,000 of 4,000 auctions exactly as main); seeds 7M, 8M, 9M, 1,000 fresh deals each (`/mnt/project-files/nov3-combined/all_score*.txt`) | -0.55, -0.23, +0.35 (mean -0.14) | -2.67, -0.43, +0.97 | 51, 50, 55 | on (each switch your pick; the total is in the noise: these hands are rare on fresh deals, and the filtered sets above carry the signal) |
| 11-03 | **The whole of PR #62 (v0.1.0-alpha), final**: every switch above from 11-03 on, the fit compete included, against all of them off (main's bidding); seed 10M, 10,000 fresh deals (`/mnt/project-files/nov3-combined/big_score.txt`) | **+0.22** | +2.19 | 449 (224 better, 164 worse) | on |
| 11-04 | My suit doubled and passed round: pass, never the suit higher (`LEFT_IN`; the user's board 1♦ P P 1♠ X P P 2♠); seed 14M, 20,000 fresh deals (`/mnt/project-files/left-in/score.txt`) | **+0.14** | +5.63 | 85 (68 better, 13 worse) | on (your pick); running to a new 5+ suit +0.13, t +5.21, not kept |
| 11-04 | Every lone rebid of my own suit shows six (`REBID_ALONE_SIX_FROM = 2`, was 3; the user's rule), alone and with `LEFT_IN`; same deals (`score2.txt`) | +0.50 / **+0.62** | +5.10 / +6.17 | 3,436 / 3,495 | on, both (your pick) |
| 11-04 | No penalty double of a part score once an opponent's alert showed 20+ (2NT, strong 2♣) (`PENALTY_STRONG_STOP`; the user's board 2NT P 3♣ P 3♠ X); seeds 7M, 8M, 9M, 3,000 fresh deals each | -0.13, -0.39, -0.05 | -3.10, -3.37, -1.95 | 10, 24, 4 (0 better) | on (your call: no doubled part score stood; the loss is robots running into doubled games) |
| 11-04 | A five-card fit jams game over partner's simple major overcall, at any vulnerability (`JAM_OVERCALL_VUL = 'any'`; the user's training deal 30); 2,000 fresh deals x 3 | +0.14, +0.33, +0.58 | +1.09, +1.72, +2.96 | 54, 88, 89 | on (your pick) |
| 11-04 | ...not vulnerable only / only after they bid again | +0.06, +0.20, +0.23 / +0.05, +0.10 | +0.79, +1.87, +1.88 / +0.50, +0.59 | 24, 47, 41 / 39, 68 | off |
| 11-04 | No call over their bid past the six level (`COMPETE_MAX = 6`; deal 30 ran to 7♥ on two voids) | -0.08, +0.15, +0.03 | -1.00, +2.76, +1.00 | 2, 11, 1 | on (your pick; ends 7-level runaways) |
| 11-04 | ...past five / past game | -0.39, -0.41 / -1.06, -0.70 | -2.03, -2.16 / -3.94, -2.06 | 17, 22 / 86, 71 | off |
| 11-04 | A void worth 3 / 2 / 1 tricks once a fit is agreed, not 5 (`SHORT_VOID_TRICKS`); seed 7 | -0.93 / -1.46 / -1.71 | -3.71 / -3.73 / -4.34 | 69 / 104 / 130 | off |
| 11-04 | Advancer bids game in a five-card major over partner's takeout double when the cheapest answer is the three level (`ADVANCE_GAME_POINTS`; your deal, 3♥ P P X P 3♠ with 10 HCP; experts 4M 16 of 19); seeds 7M, 8M, 9M, 10,000 deals each; 9 / 10 / 11 points | **+0.06, +0.04, +0.06** / +0.04, +0.02, +0.05 / +0.05, +0.01, +0.05 | +2.56, +1.58, +2.46 / +2.40, +0.95, +2.53 / +3.15, +0.39, +2.58 | 36, 34, 46 / 23, 23, 28 / 11, 13, 18 | 9 on |
| 11-04 | A five-card suit for a direct two-level overcall needs quality: 4/5/6+ judgement points in it, two of AKQ or three of AKQJT, or six cards (the user's board: 1♦, East 2♣ on ♠A4 ♥8652 ♦A6 ♣Q6432); library / seeds 7M, 8M, 9M, 3,000 fresh deals each (`/mnt/project-files/overcall-suit/REPORT.md`) | 4 JP -0.59 / -0.34, -0.48, +0.11; 5 JP -2.89 / -0.68, -0.41, -0.18; 6 JP -3.57 / -0.52, -0.28, -0.09; AKQ -2.56 / -0.70, -0.46, -0.12; six cards -3.58 / -0.66, +0.00, +0.37 | 4 JP -1.15 / -1.48, -2.52, +0.50; AKQ -2.50 / -2.58, -1.75, -0.46; six cards -2.60 / -1.70, +0.01, +0.91 | 42-170 / 332-1,229 | off (your call: any five cards stays) |
| 11-04 | Answers to responder's cuebids over their Unusual 2NT: opener signs off or bids game, responder bids game on 13+ (`UNUSUAL_CUE_REPLY`; the user's board, 1♠ (2NT) 3♣ passed for -200); seed 41M, 20,000 fresh deals (`/mnt/project-files/unusual-cue/`) | **+0.15** | +5.02 | 85 (63 better, 16 worse) | on (bug fix, your pick) |
| 11-04 | Advancer picks a minor after our 4M / 4NT (both minors) over their weak two, which were passed (`WEAK_TWO_MINORS_ADVANCE`); the same deals | **+0.21** | +6.42 | 97 (73 better, 10 worse) | on (your pick) |
| 11-04 | ...both together / our calls over their 1NT read as the defence only when straight over it (`NT_ADVANCE_DIRECT_ONLY`) | **+0.36** / -0.09 | +8.12 / -3.29 | 182 / 89 | on / removed |
| 11-04 | The doubler answers partner's responsive double, (1x) X (2x) X (P): the better of the two unbid suits at its cheapest level, never a pass (`RESPONSIVE_ANSWER`; the gap analysis: the fallback read it as penalty); seeds 14M, 15M, 10,000 fresh deals each (`/mnt/project-files/responsive-answer/`) | **+0.07, +0.04** | +2.59, +0.84 | 24, 39 | on (your pick) |
| 11-04 | Their artificial bid shows the suit it shows, not its strain: over 1NT P 2♦ (a transfer) diamonds are ours, but only to 6+ cards and 12+ HCP (`THEIR_SHOWN_SUITS`, `SHOWN_SUIT_LEN`, `SHOWN_SUIT_HCP`; the gap analysis and the user's rule); seeds 14M, 15M, 10,000 fresh deals each (`/mnt/project-files/their-transfer/`) | +0.00, +0.01 | 0, +1.02 | 0, 3 | on (your rule) |
| 11-04 | ...for every hand / only in the pass-out seat / at 14+ HCP | -0.04 / -0.02 / 0.00 | -1.31 / -0.94 / 0 | 45 / 4 / 0 | off (a direct 3♦ over the transfer went for 1,470) |
| 11-04 | ...and partner reads it the same way: our side's first bid in their artificial suit is natural for both of us, never a cuebid (`SHOWN_SUIT_PARTNER`; the PR #63 review: partner bid 4♠ "again over the cuebid"); seeds 7M, 8M, 9M, 3,000 fresh deals each (`/mnt/project-files/pr63-review/measure/`) | +0.00, +0.00, +0.00 | 0 | 0 | on (bug fix, your pick) |
| 11-04 | **The Nov 4 fixes together (v0.1.1-alpha)**: every 11-04 row above that is on, the gap analysis's two included, against all of them off (which bids 2,000 of 2,000 auctions exactly as main); seeds 7M, 8M, 9M, 1,000 fresh deals each (`/mnt/project-files/nov4-combined/REPORT.md`, with each fix taken out on top of the rest: none turns negative except the penalty stop, which cost a little alone too) | +0.24, +2.15, +1.14 (mean **+1.18**) | +0.46, +3.64, +1.87 | 245, 220, 243 | on |
| 11-04 | A 2♣ rebid shows six clubs, five only with a singleton or void (`CLUB_REBID_LEN`; the user's board 53); seeds 7M, 8M, 9M, 1,000 fresh deals each (`/mnt/project-files/club-rebid/REPORT.md`) | -0.04, +0.02, -0.07 | -1.39, +1.94, -0.88 | 6, 14, 6 | on (your pick) |
| 11-04 | ...five only with 5-4 in the minors and shortness | -0.04, -0.24, -0.07 | -1.39, -2.55, -0.85 | 10, 22, 11 | off |
| 11-04 | Systems on over our penalty double of their 1NT: the doubler's partner pulls only with a Jacoby/Texas transfer, as over a 1NT opening; the doubler doubles a notrump runout or completes with 3+, a weak transferer then passes; and advancer no longer passes everything once the doubler bids again (`NT_X_SYSTEMS`, `NT_X_INTERFERED`, `NT_X_ADVANCE_FIX`; the user's system); seeds 17M, 18M, 19M, 5,000 fresh deals each (`/mnt/project-files/nt-x-systems/`). Pulling only with 7- HCP: 0.00; only with six: -0.03 | -0.06, +0.02, +0.04 | -1.26, +0.46, +0.64 | 34, 28, 26 | on (your system) |
| 11-04 | Systems on over their 2♣ overcall of our 1NT: X Stayman, 2♦/2♥ transfers, the uncontested continuations while they pass (2NT invites after the 2♦ denial); a long-diamond hand relays through 2NT (`NT_2C_SYSTEMS`; the user's system); same seeds and deals | +0.04, -0.01, -0.02 | +0.98, -0.55, -0.73 | 62, 45, 72 | on (your system) |
| 11-05 | A doubled or overcalled systems-on transfer is still a transfer: opener completes with three, and a transfer left doubled is run to the suit (`TRANSFER_INTERFERED`; the review of PR #65). 240,000 robot deals, seeds 11-14 (`/mnt/project-files/pr65-review/`): robots never doubled or bid over these transfers, so no robot auction changed; it fixes play against a person | 0.00 | 0.00 | 0 | on (your pick) |
| 11-04 | Responder's three-card raise of partner's 1♣/1♦ opening needs a side singleton or void; flat hands bid elsewhere (`MINOR_RAISE_SHORT`; the user's board, 1♦ P 1♠ X P 2♣ 2♦ on ♠QT853 ♥A863 ♦Q72 ♣T); seeds 7M, 8M, 9M, 1,000 fresh deals each (`/mnt/project-files/minor-raise-short/`) | +0.05, +0.58, +0.31 | +0.96, +1.95, +3.17 | 4, 6, 14 | on (your pick) |
| 11-04 | Support redouble: after 1x (P) 1y (X) opener redoubles with exactly three of y, so the raise shows four; over their bid after it, opener with three and a minimum passes (`SUPPORT_XX`, `SUPPORT_X_PASS='xx'`); seeds 7M-12M, 3,000 fresh deals each (`/mnt/project-files/support-xx/`) | +0.02, -0.02, -0.01, +0.20, -0.04, +0.10 | +1.82, -0.97, -0.52, +0.86, -1.40, +1.01 | 9, 9, 14, 6, 2, 5 | on (your pick; neutral) |
| 11-05 | **The Nov 4 evening bidding fixes together (v0.1.2-alpha)**: `CLUB_REBID_LEN`, the two systems-on fixes, `MINOR_RAISE_SHORT` and the support redouble, against all of them off (which bids 2,000 of 2,000 auctions exactly as main); seeds 7M, 8M, 9M, 1,000 fresh deals each (`/mnt/project-files/nov4-evening-combined/`; each fix taken out on top of the rest is in its `loo_score*.txt`: on the mean of the three seeds only the 2♣ rebid is negative, -0.04, +0.02, -0.07, as it was alone) | +0.72, +0.53, +0.44 (mean **+0.56**) | +2.32, +1.71, +2.36 | 33, 40, 43 | on |
| 11-05 | The doubler's answer to partner's responsive double is not the 18+ double-then-suit, so advancer no longer raises it to game on that reading (`DOUBLER_SUIT_NOT_ANSWER`; your deal, 1♦ P 1♥ X 2♥ X P 2♠ P 4♠ on an 8-count, doubled, down two); seeds 7M, 8M, 9M, 10,000 fresh deals each (`/mnt/project-files/responsive-raise-4s/`) | -0.01, +0.02, -0.02 | -0.45, +1.27, -1.53 | 20, 6, 11 | on (bug fix, your pick) |
| 11-05 | ...and the responsive doubler bids 4M on four of partner's answered major with 11 / 12 / 13+ HCP, even over their competition (`RESPONSIVE_GAME_HCP`); the same deals, the fix on in both | **+0.06, +0.00, +0.01** / +0.03, +0.00, +0.00 / +0.03, +0.01, +0.00 | +2.68, +0.41, +1.00 / +1.65, +0.41, 0 / +1.90, +1.00, 0 | 12, 2, 1 / 5, 2, 0 / 4, 1, 0 | 11 on (your pick) |
| 11-06 | The takeout doubler bids a 6+ card suit at the three level, alerted 6+ (`DOUBLER_SUIT_LEN3`; the user's board, 2♦ X P 2♠ passed out with ♠K64 ♥AKJT742 ♦KQ ♣A); 3 x 10,000 fresh deals, 120,000 boards (`/mnt/project-files/doubler-3level/`). 7+ cards: 0.00/0.00/+0.01, 27 changed; 5+: +0.03/+0.11/-0.15. On the user's own deal the pass was double dummy best (3♥ by North takes 7) | +0.01 (+0.01/+0.03/0.00) | +0.18/+1.41/-0.12 | 159 | on (your call: 6+) |
| 11-07 | **The Nov 6 bidding fixes together (v0.1.3-alpha)**: `DOUBLER_SUIT_NOT_ANSWER`, `RESPONSIVE_GAME_HCP = 11` and `DOUBLER_SUIT_LEN3 = 6` against all three off; seeds 7M, 8M, 9M, 1,000 fresh deals each (`/mnt/project-files/nov6-combined/all_score*.txt`). These auctions are rare on fresh deals; each fix's own 10,000-deal sets above carry the signal | +0.12, -0.23, +0.33 (mean +0.07) | +1.66, -2.30, +1.63 | 11, 7, 8 | on |
| 11-09 | After the support double (exactly three) and RHO's pass, the invitational jump to three of responder's suit needs five (`SUPPORT_X_INVITE`; the user's board P P 1♣ P 1♠ (2♥) X P 3♠ on ♠QJ95); four bid two; seed 23M, 10,000 fresh deals (`/mnt/project-files/support-x-invite/`) | **+0.08** | +2.52 | 44 (27 better, 5 worse) | on (your OK, 11-09) |
| 11-09 | Over their 1NT, the Cappelletti 2♣ one-suiter passes partner's 2♦ relay with diamonds and otherwise names its suit (`RELAY_ANSWER`; challenge board 79, (1NT) 2♣ (P) 2♦ (P) 3♦ on a diamond one-suiter); seeds 7M, 8M, 10,000 fresh deals each (`/mnt/project-files/cappelletti-relay/`) | +0.01, **+0.03** | +0.79, +3.29 | 29 (13 better, 6 worse), 23 (18 better, 0 worse) | on (your OK, 11-09) |
| 11-09 | After 1x (y) X (P) 2z (P), the negative doubler with as many x as z or more gives preference to 2x instead of passing; a six-card suit of its own is still rebid, and opener passes the preference (`NEG_PREFERENCE`; the user's board P 1♦ (1♠) X (P) 2♣ passed out on ♦AK4 ♣J); seeds 7M, 8M, 9M, 10,000 fresh deals each (`/mnt/project-files/neg-preference/REPORT.md`) | **+0.05**, +0.00, **+0.05** | +3.45, +0.20, +2.94 | 29 (21 better, 4 worse), 27 (15 better, 4 worse), 43 (31 better, 5 worse) | on (your OK, 11-09) |

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
