# Challenge mode and robot card play

Head-to-head boards against an all-robot table, graded against double dummy, and the card-play improvements measured on that library.

Moved verbatim from `CLAUDE.md` on 2026-10-13, so it is read when the work needs it instead of loading into every session. [CLAUDE.md](../CLAUDE.md) keeps the guardrails and links here.

**`challenge.py`** — head-to-head mode: the same deal played by the human and by
an all-robot table, then graded. Pure domain logic, no UI. It runs on
`data/solved_deals.json` (written by `research/export_challenge_deals.py`): the
**400 deals, every one solved in all five strains for both declaring sides**. That
completeness is the whole point — whatever contract an auction reaches, its
double-dummy trick count is a lookup, so a board can be scored as if it had been
played perfectly without solving anything at run time. From that comes the split
the mode exists for:

    par - actual = bidding_loss + play_loss

`bidding_loss` is par minus the double-dummy value of the contract reached;
`play_loss` is that value minus what was actually scored. The identity is exact
and `tests/test_challenge.py` asserts it on every deal in the library. It makes
"how good is the robot at **bidding**" and "at **declaring**" separable questions,
which a single score cannot answer. Measured 2026-10-19, with every card-play rule below on, by
`research/challenge_losses.py` over all 400 deals at all 16 board positions
(6,356 boards with a contract, 44 passed out), graded from N/S as the app
grades, so this is what the "Robots" column of the match table averages to.
The web app's Challenge caption quotes this table; rerun the script after a
robot change and update both together. Measured 2026-10-24, after the
defender's suit plan (below), graded with the partner who actually declared
(the library holds every declarer's count; par takes the better partner):

| | mean per board | median |
|---|---|---|
| lost in the auction | **242.5** | 200.0 |
| lost in the card play | **5.2** | **0.0** |

Graded from the declaring side: 209.8 in the auction and -24.4 in the card
play. The same robots without the suit plan: 242.5 and 3.5 from N/S, 209.8
and -36.6 from the declaring side. Robots defend for N/S as often as they
declare, so a better defence moves the N/S figure little; it shows from the
declaring side, whose play now beats double dummy by 12 points a board less.
(The auction's 242.5 against 240.1 below is the jack's judgement point, PR
#28's last commit, measured after it.)

Measured 2026-10-23, after shortness (PR #26) and game by points (PR #28):
240.1 in the auction and 2.9 in the card play from N/S. All four seats bid
the new way, so what one side gains head to head (+6.78 and +2.62 a board)
the other gains back. Graded from the declaring side: 209.1 in the auction
and -35.8 in the card play.

Before those two, the robots of 2026-10-22 measured 244.0 and -5.0 from N/S.
Graded from the declaring side instead: 214.5 in the auction and **-39.6** in
the card play (median 0.0), so the declaring side's play beats double dummy on
average, on the defence's mistakes. The same robots graded with one declarer
per side (2026-10-22) gave 235.4 and 6.1 from N/S, 211.9 and -37.2 from the
declaring side: about 11 points a board of "card play loss" was the wrong
partner's count, and par rose by about 8 once a side could pick its better
declarer. (On 2026-10-21: 234.9 and 6.9 from N/S,
215.8 and -33.3 from the declaring side. On 2026-10-19, before the Oct 20-21
changes: 233.9 and 7.1 from N/S; 220.5 and -45.7, median -20.0, from the
declaring side.) The figures before this (143.7 / 31.8 over
372 boards) were one auction per deal and predate every card-play change
below, so they aren't comparable: the 16 board positions include vulnerable
boards, where par is worth far more (not measured separately).

**What the robots know when they play** (the user's call, 2026-10-20; three
switches, measured with `research/card_play_seated.py`: the switches on for
one side against robots without them, sides swapped, scored from the switched
side over all 400 deals x 16 boards. `card_play_h2h.py` switches all four
seats, which nets out a change both declarer and defenders use.)
- `NO_PEEK_OPENING_LEAD`: the opening leader no longer sees dummy before it
  goes down. `visible_hands` always included dummy, so the robot leader was
  handed it (7 library deals' leads changed, 164 and 212 among them). Seated:
  **+0.24 points per board, t = +1.39, 24 boards changed** -- the honest lead
  does no worse; the peek was unfair without being useful.
- `SHOWOUT_MIDDLE`: second and third hand drop the suits the next opponent
  has shown out of from the cards it might play (`_later_holdings`). The pool
  shrinks in ~7% of mid-hand decisions but the card changes rarely, because
  `_outlook` only counts the deciding suit. Seated: **-0.16, t = -0.79, 48
  boards changed**.
- `AUCTION_IN_PLAY`: `shown_lengths` reads each seat's suit floors off its
  alerts ("5+ ♠", "4+ ♥ ♠", "exactly 3 ♥" -- every number an alert quotes is
  true of the hand). The opening lead goes to partner's longest shown suit of
  5+ (`_partner_suit_lead`, `PARTNER_LEAD_MIN`), and `_splits` and the endgame
  search keep only layouts that fit the bidding. A human's call reads by what
  GIB would mean by it, never by the human's free-text self-alert: the apps
  ask the robots what they would bid there with sampled hands and keep that
  call's alert (`meanings.gib_alert`, the Python twin of
  `frontend/src/lib/meanings.ts`), once per call.
  Seated: **+0.43, t = +0.38, 492 boards changed**.
- All three: **+0.55 points per board, t = +0.48, 556 boards changed.** None
  is distinguishable from zero; they are kept as correctness (the user's
  call), not as a measured gain.

**Declarer sees its own two hands, defenders see dummy** (`ai.visible_hands`;
nobody sees a defender's cards). Before this, the robot played dummy blind to
declarer's own hand -- on a user's board dummy overtook declarer's winning J♥
with the K♥, fearing a queen declarer held -- and the robots' challenge table
passed no visible hands at all. Fixing both took the robot declarer from 0.471
to **0.310 tricks below double dummy per board** (47.2 to 27.8 points of play
loss, GIB auctions, 397 library boards). **The last three tricks are then
searched, single dummy** (`ai.ENDGAME_CARDS = 3`, `_endgame_totals`): every
layout of the unseen cards consistent with what the robot has seen -- its hand,
dummy, cards played, who has shown out -- is solved exactly (at most 20), and
the card with the most tricks summed over them is played. Never the real
layout: that would be double dummy. Enumerated, not sampled, so still
deterministic and still ported exactly. Down to **0.199 tricks below double
dummy per board (22.0 points)**, the whole library in ~15 s. Four cards measured
over 15 minutes for the library -- too slow for the table -- and was dropped,
until `_fast_search` (below) made it affordable.
**The search now starts at four cards** (`ai.DEEP_ENDGAME`,
`DEEP_ENDGAME_CARDS = 4`, the user's call, 2026-10-20), made affordable by
two rewrites that give `_search`'s exact answers
(`tests/test_play_information.py`): `_fast_search` (alpha-beta, bounds kept
per position, rank equivalence) and `_bit_search`, the same on 52-bit hands
as in bridge/solver, which the endgame uses (3-5x faster again). With
`_trump_losers` sharing one memory across calls -- its positions are keyed by
card order, so an answer holds in every game -- a robot board takes **~0.20 s,
against ~0.17 s before the deeper search** (240 boards replayed card for card
identical between the rewrites). Seated (`research/card_play_seated.py`):
**+0.190 tricks and +19.8 points per board for the side searching, t = +10.29
(tricks) over 398 deals, 2,092 of 6,356 boards changed** -- the largest
card-play gain measured here. Two things learned on the way:
- A position the memory already knew exactly was searched again with an
  empty window, and its entry overwritten with a wrong bound (deal 4: West's
  3♦ summed 43 over the layouts where it is worth 46). Now an exact entry is
  returned at once. The first measurement, with the bug, was +0.186 / +18.9.
- A sampled search from five or six cards (eight seeded layouts) was tried
  first and dropped: on deal 0 it put up the K♦ third in hand where the 6♦
  takes three more tricks, because whether the king wins turns on one of
  East's cards. Every layout from five cards took ~16 s a board -- until
  the shared memory below.
- **One memory for every search** (`ai.SHARED_POSITIONS`, `_position_memo`;
  the user's call, 2026-10-21): positions are kept in N/S tricks, one table
  per trump suit, across every layout, robot and board -- a position's value
  doesn't depend on who looks or which layout led there. Same play, half the
  time: **0.10 s a board at four cards** (from 0.20).
- **The search now starts at five cards** (`DEEP_ENDGAME_CARDS = 5`, the
  user's call, 2026-10-22). Against four, seated, **+0.204 tricks and +22.8
  points per board, t = +9.34 over 398 deals, 2,564 boards changed**
  (measured 2026-10-21; the play hasn't changed since) -- the fifth card pays
  as much as the fourth. It had waited on speed: the TS port searched on
  card lists, 1.6 s a board at five cards (10 s worst, desktop Node), on the
  phone's main thread. The port now searches on bit patterns like ai.py
  (`bitSearch`; four 13-bit suit masks a hand, since JS bit operators are
  32-bit): **0.18 s a board at five cards (0.9 s worst)**, against 0.14 s
  for the old port at four; 240 boards played card for card identical to
  the card-list search. The memory's key renumbers each suit's unplayed
  cards from the lowest (`_relative`, `relativeKey`): a position's value
  depends only on how the cards still out rank each other, so ♠QJ against
  ♠K, once the cards between are gone, is solved once with ♠98 against ♠10.
  Same play (160 boards replayed identical, fixtures byte for byte), and
  Python, the reference, goes from ~1.0 to ~0.67 s a board at five cards
  (0.11 s at four); the TS port to ~0.10 s. To keep CI near its old length,
  `tests/run_all.py` runs one test per process and the fixture export plays
  its boards on every core: here (4 cores) the Python suite takes ~5
  minutes, the export ~8, npm test ~4. Six cards took 22 s a board in
  Python (over 900 layouts).
- **Six cards is measured and left off** (the user's call, 2026-10-22): over
  five, seated in the TS engine on 100 deals, **+0.26 tricks and +26.8
  points a board, t = +4.35, 824 of 1,600 boards changed** -- but 4.6 s a
  board and up to 17.5 s for a single robot move on a desktop (86 of 3,952
  moves over a second), on the phone's main thread. It waits on a faster
  search or robot play off the main thread.
- Tried and dropped: trying the remembered best card first (0.87 s against
  0.77 s at five cards, no gain).
**Second hand covers to promote a visible partner** (`_cover_for_partner`):
when partner plays last and partner's hand is in view (declarer and dummy),
each card is scored by how many of the third player's possible cards -- drawn
only from cards the robot cannot see -- leave partner a winning reply. On a
user's 3NT East ducked the 8C holding K64 with dummy's 9C to come; covering
makes the nine win. Library: **0.199 -> 0.025 tricks below double dummy per
board (22.0 -> 6.2 points)**; "below double dummy" also credits weak robot
defence, so treat it as a ceiling on the gain. Until 2026-10-18 "cards the
robot cannot see" left out its own cards outside the led suit (it passed the
legal cards, not the hand), so its own trumps could be the third player's
ruff. Fixed; measured head to head it changed **0 of 6,356 boards** (the
candidate set differed on 2,564 of 3,932 calls over 60 deals, the card chosen
never), so it is a correctness fix with no effect on the library. The table below predates all
four changes.

**Fourth hand plays for the partnership** (`_play_last`): it used to take a
trick only if it could win it ITSELF, never by promoting partner's card. On a
user's 3H dummy played low under North's 7H where the king makes East's 8H
second-highest. Measured one side at a time over the library: declarer
**+0.43 tricks per board (t = +7.2)**, defence **+0.21 (t = +5.2)**.

**A void robot keeps its trumps** (`ai.KEEP_TRUMPS`, `_shed`; roadmap 3.11,
the user's rule, 2026-10-19). When `_play_last` and `_middle_play` find no
card that keeps the trick, they used to throw the lowest card by value in any
suit, so a robot void in the led suit could throw the 2 of trumps on a trick it
was losing anyway. Now a trump goes off-suit only to ruff for a win: a losing
card comes from a side suit while there is one. Head to head
(`card_play_h2h.py KEEP_TRUMPS`, both sides): **+0.003 declarer tricks per
board (t = +0.37), +0.7 points**; 88 of 6,356 boards changed. Kept as the
user's rule; it costs nothing measurable.

**Every robot card, scored double dummy** (`research/presolve_robot_lines.py`,
`research/robot_line_report.py`). The robot table is run on each deal at all 16
board positions (the robots bid differently by dealer and vulnerability);
identical lines are solved once, by the Rust `line_values` binary, which scores
every legal card at every decision against the contract: BBO's per-card
display. Records go to `research/data/robot_lines.jsonl`, stamped with a hash
of the robot code; a robot change makes them stale, so rerun after one. The
first 100 deals give 149 lines, about an hour on one worker. The report sorts
every costly card by side, seat in the trick, action and stage. Double dummy
sees all four hands, so a "mistake" may have been right on what the robot could
see: treat the report as where to look, and measure a fix head to head
(`research/card_play_h2h.py`). Before the trump fix below
(`robot_lines_before_draw_trumps.jsonl`), declarer-side leads were the largest
category: 29% cost a trick, 2.79 tricks a deal gross. After it, 24% and 2.41,
and robot declarers took 8.32 tricks a deal against 7.94 double dummy (8.08
before). "Gross" because costly cards offset: a trick one side gives away often
comes back from the other.

    python research/presolve_robot_lines.py --deals 100
    python research/robot_line_report.py

**Declarer draws trumps** (`ai.DRAW_TRUMPS`, `_draw_trump`). `_lead` is one rule
for every seat and ranks trumps last, so the declaring side kept leading side
suits into the defence's trumps: on deal 6, 4C by South with ten trumps
(Q1075 opposite AJ9643), South led the K♠ at trick 4 and went down; 9♣ or J♣
draws them and makes. Double dummy over the first 100 deals
(`research/robot_lines.jsonl`): with the defence still holding trumps, the
declaring side led one 38% of the time, and a costly side-suit lead where a
trump was best came up 66 times on 51 deals. Now, when the declaring side is
on lead and holds more trumps than the defence, it leads the trump that loses
the fewest trump tricks averaged over every split of the trumps it can't see
(weighted by how many ways each split can be dealt, ruling out a defender who
has shown out). A trump lead's outcome depends only on where the trumps are,
so the trump suit is searched on its own. Drawing at a cost still draws: the
user's point was that the trumps it loses can't ruff side-suit winners. The
one exception, also the user's: when the hand with fewer trumps is needed to
ruff the other hand's extra cards in a suit it holds at most one of, and
drawing would leave it too few, the long hand leads that suit for the ruff.
Head to head over the library (`research/card_play_h2h.py DRAW_TRUMPS`, all 16
board positions, 6,356 boards, t across deals): **+0.171 declarer tricks per
board (t = +3.19), +17.1 points (t = +2.43)**; 2,748 boards changed.

**Declarer runs a long suit** (`ai.RUN_LONG_SUIT`, `_run_long_suit`). On the
user's deal 96, 3NT by South, declarer won the opening heart and cashed the K♥
from AK9 opposite J74, setting up the defence's hearts (double dummy, six
tricks became two), with clubs AJ1084 opposite KQ63: five tricks off the top.
`_gap` judges a suit by declarer's own hand, so the K♣ and Q♣ in dummy counted
as holes. A suit led in notrump, or once the defence has no trumps, is a self-
contained puzzle like the trump suit, so the same search (`_splits`,
`_after_lead`) scores it: for each suit where the partnership holds seven or
more, the expected losers of its best lead over every split of the defence's
cards. The suit with the most expected tricks among those under half a loser
(`RUN_MAX_LOSERS`) is run, from the top on ties, since partner's follow comes
from the ordinary rules, not the search; a suit the defence is out of is run to
the end. Not "no loss on any split": under these rules a defender holding all
the outstanding cards behind dummy can nearly always slip one between
declarer's two, so even AKQJ10 8643 opposite 9752 loses to 4-0. The suit search
skips equivalent cards and stores positions by card order (answers checked
identical to the plain search on 2,578 random suits); a robot table costs about
twice what it did. Head to head with every other rule on: **+0.080 declarer
tricks per board (t = +1.99), +19.8 points (t = +2.91)**; 788 boards changed.

**Defenders lead their long suit in notrump** (`ai.NT_LONG_LEAD`,
`_nt_long_lead`). `_lead` ranks suits by `_gap` and length only breaks ties, so
a defender with five cards in a suit would lead a short, tidy one. The user's
point: set up the long suit, as in ordinary bridge, but lead the second-highest
card, since low gives the trick away here. A defender in notrump with a suit of
four or more leads second-highest from its longest. Every lead, not just the
opening one: the opening lead alone measured -0.019 tricks (t = -0.61), every
lead -0.073 (t = -1.75), -16.4 points (t = -2.39), both before
`RUN_LONG_SUIT`. Once declarer runs its long suits first the gain shrinks;
with every other rule on: **-0.086 declarer tricks per board (t = -1.85), -6.3
points (t = -0.97)**; 976 boards changed. Kept by the user's decision: never
harmful in three measurements, but not separately significant.

The three rules after draw-trumps, together, against the draw-trumps baseline
(`card_play_h2h.py RUN_LONG_SUIT NT_LONG_LEAD SURE_LEAD`): -0.127 declarer
tricks per board (t = -2.30), -11.1 points (t = -1.33), 2,044 boards changed.
Robots play both sides, so a declarer rule and two defence rules partly cancel;
each rule's own gain, measured with the others on, is the figure to judge it by.

**A defender on lead cashes a sure trick** (`ai.SURE_LEAD`, `_sure_lead`). A
defender's lead went straight to `_lead`, which never asks whether a card wins
and never looks at dummy. On the user's deal 92, 1NT by North, East won the J♦
at trick 2 with K765 of clubs, dummy's J1032 in view and the 8♣ 9♣ 4♣ gone: the
A♣ was the only club East couldn't see, so its holder had to play it under the
K♣. East led the 7♣ instead (`_gap` counted dummy's J♣ 10♣ as cards an
opponent might hold), dummy's J♣ won, and the king never scored: four tricks
given away double dummy. Now a defender on lead tries each card against every
split of the unseen cards of its suit between partner and declarer (none to a
seat that has shown out) and every legal play from there -- dummy's from its
known cards, a void hidden seat's as any unseen trump or a discard -- and leads
the lowest card that wins the trick every time. Partner's card counts against
us too, so "sure" never relies on partner finding a play. Head to head over the
library (`research/card_play_h2h.py SURE_LEAD`, 6,356 boards, baseline with
`RUN_LONG_SUIT` and `NT_LONG_LEAD` on): **-0.174 declarer tricks per board
(t = -4.53), -18.6 points (t = -3.40)**; 1,168 boards changed. No measurable
cost in speed. Choosing the lead suit with dummy in view when there is no sure
trick (`_gap` still ignores dummy) is the next step, not yet done.

**Four rules from the user's review of deals 92, 156 and 174** (2026-10-19;
the presolved robot lines in `research/data/robot_lines.jsonl`, viewed hand by
hand). Each is a switch, measured alone over the library (`card_play_h2h.py`,
6,356 boards, t across 398 deals), then all four together. A card is **dead**
when every higher card of its suit is played or in its own hand: it can never
be second-highest, so it wins only as the one card of its suit in a trick.

| switch | what it does | declarer tricks | points | boards changed | |
|---|---|---|---|---|---|
| `SURE_LEAD_DECLARER` | in the side suit the lead rules chose, lead the lowest card that wins for sure | **+0.165 (t = +3.81)** | +17.8 (t = +2.85) | 1,152 | **on** |
| `DEAD_CARD_LAST` | fourth hand that can't keep the trick follows with a dead card | +0.046 (t = +1.13) | +3.8 | 1,492 | **on** |
| `RUFF_LEAD` | defence out of trumps: lead a suit partner is void in, for a ruff | -0.020 (t = -0.98) | -2.8 | 596 | off |
| `FORCE_DUMMY` | a defender who'd lead a trump leads dummy's void suit instead | -0.001 (t = -0.05) | +0.3 | 156 | off |
| all four | | +0.158 (t = +2.73) | +15.8 (t = +1.69) | 2,540 | |

The two kept, together: **+0.183 declarer tricks per board (t = +3.37), +20.5
points (t = +2.35)**; 2,208 boards changed. Each with the other on:
`SURE_LEAD_DECLARER` +0.137 (t = +3.41), `DEAD_CARD_LAST` +0.018 (t = +0.41,
both sides netted; see below for one side at a time).

- **Sure lead for the declaring side** (deal 174, 4H by East): with dummy's
  10♣ and 9♣ 2♣ in hand, the 9♣ wins whatever the defence holds and the 2♣
  (what East led) lost to North's 8♣. `_sure_lead` is the defender's version;
  here partner's hand is in view, so partner's card is the one partner's own
  rules (`_middle_play`) would play. Its first form chose the suit as well,
  cashing any sure trick before the other lead rules ran, and cost the
  declaring side **0.85 tricks a board** on ten deals: a "sure" trump trick
  spent two trumps on one trick (deal 6, 4C by South, the J♣ to dummy's Q♣
  with the defence out of trumps, four tricks lost over the hand). Without
  trumps it still cost 0.18: cashing early lost timing (deal 0, 1NT) and
  ruffed in the long trump hand (deal 4). Card choice within the side suit
  the lead rules chose is the version measured above. The user's point, in the end:
  the 9♣ is plain good planning, not part of a ruffing plan.
- **Dead card in fourth seat** (deal 156, 1H by North): on 10♣ 3♣ 9♣ North
  dumped the 5♣, keeping A♣ K♣ that could never win a trick. Double dummy
  over 199 deals the lowest card lost 43.5 tricks where the lowest dead card
  lost 14.5; a dead card in ANY seat, following suit, is worse (-0.23 to -0.39
  a deal), since the card added decides which card is second-highest. It
  plays for both sides, so it was also measured one side at a time: declaring
  side **+0.077 (t = +3.33)**, defence -0.036 declarer tricks (t = -1.08, the
  defence's gain). On for both, as `NT_LONG_LEAD` was: the defence's half is
  never harmful but not separately significant.
- **Ruff lead** (deal 174: with the defence out of trumps East led trumps three
  times, each won with one of dummy's ruffing trumps) and **force dummy** (deal
  92, 3C by North: the A♥ or 10♥ makes trump-void-in-hearts dummy ruff, the 6♣
  let dummy underplay with the 3♣) are right on their deals but not on the
  library, so both stay off. Their code stays in both engines behind the
  switches.

**Two more from deal 43, both off** (2026-10-19; 3NT by West). Dummy led the
K♠ from AK9 at trick 2 where the Q♣ from Q65, opposite K10982, was double
dummy's best card; West then led the K♥ from AKQ3 and North's 9♥ won it.

- `LIVE_LEAD`: `_lead` passes over a suit whose lead card is dead. Measured
  one side at a time, it is worse for both: declaring side **-0.122 declarer
  tricks per board (t = -2.72)**, defence **+0.149 (t = +3.88)**, the
  defence's loss; the net +0.037 was the two cancelling. A dead card never
  takes a trick unless no one else can follow, so leading it spends a loser
  and keeps the live cards; deal 43 is the exception, not the rule. `_gap`'s
  liking for A-K holdings is, by accident, right.
- `NT_SET_UP_SUIT`: in notrump, when no long suit runs cheaply, the declaring
  side sets one up (`_run_long_suit` with no loser limit). It finds the Q♣ on
  deal 43. **+0.041 declarer tricks per board (t = +0.95), +4.2 points**;
  1,024 boards changed. Not proven, and left off until the boards where it
  loses show how to narrow it, as the first sure-lead rule was narrowed.
  Neither is ported to the Svelte engine: both are off, so its play is
  unchanged.

**A defender plans the suit it leads** (`ai.DEFENDER_SUIT_PLAN`,
`_defender_suit_plan`; the user's deal 356, 2026-10-24). 3S by East: North won
trick 2 and led the 9♥ from 10-9-6, with the A K Q J gone and dummy's 8♥ its
last heart. The nine could only be highest, so dummy's 8♥ won and dummy was
void to ruff (double dummy: 3S+1 after the nine, one down after the 6♥, which
lets South's 7♥ be second-highest). `_lead` picks a suit by `_gap` and leads
its second-highest card without asking whether that card can still be
second-highest. Two count-based fixes measured even: leading the highest live
card instead of a dead one (seated: defence -0.002 tricks, t = -0.16;
declaring side -0.019, t = -1.30; both together, head to head, -0.018, t =
-0.46), and the same only in a trump contract against dummy's last card in
the suit (12 boards changed, +0.001). The user's point is why: a dead card
isn't useless, since played under partner's lead it pushes partner's card into
second place, and in notrump that is how partner's suit runs. The card has to
be judged on the whole suit, not the one trick.

So a defender who sees dummy now plays its lead suit out (any defence lead
except a sure trick): for every way the unseen cards of the suit can lie
between partner and declarer, ruling out a seat that has shown out and keeping
the auction's floors, weighted as `_splits` weights, it leads the card that
takes the most tricks in the suit on average. The model: each layout is solved
with every card known, everyone follows while they can, a void dummy holding
trumps or a void declarer not known to be out of trumps may ruff (and wins), a
void defender discards. After the defence wins, its winner leads the suit again
(or partner, once the winner is out); after declarer's side wins, the defence
gets the lead back and leads it again, as if it had entries. At most 9 unseen
cards (`SUIT_PLAN_MAX_UNSEEN`). Head to head (`card_play_h2h.py
DEFENDER_SUIT_PLAN`, 6,356 boards): **-0.113 declarer tricks per board (t =
-2.50), -12.2 points (t = -2.39)**; 1,336 boards changed. Python spends about
0.13 s a board more (the slowest single lead 0.8 s, cold memory); the TS port
0.17 s a board against 0.12 s over the library (desktop Node), the slowest board
under a second either way. `tests/test_card_play_rules.py` holds deal 356.

**A cuebid raise that forces the three level needs four trumps or 12+
judgement points** (`gib.CUE_LIMIT_AT_3`), a small tightening of GIB's "limit
raise or better"; weaker hands with three trumps raise to the two level. The
same user board: 1H-(2C)-3C on three trumps and 10 HCP drove 28 HCP to 3H,
where seven tricks were the most available (and N/S could make ten in clubs).
Head to head **+0.1 per board, t = +2.24** -- rare, but positive.

**GIB judges level on this game's card values** (`gib.Hand.judge`): K=Q=3,
A=10=9=1, scaled to 40 a deck, from the fitted trick values. What a bid SHOWS
stays HCP (its alert quotes HCP); whether to stop, invite, bid game or try for
slam uses judgement points. Head to head against HCP judgement: **+2.7 per
board, t = +2.90**; self-play +32.7 -> +39.7, games 39% -> 36%, made 44% ->
46%. `gib.JUDGE_BY_VARIANT = False` (`settingsGib.judgeByVariant`) restores HCP.

**The robot declares well and bids badly.** Card play is at or above double
dummy on 3,944 of 6,356 boards (graded from N/S; 4,744 from the declaring
side); the auction is at or above par on 1,603 (measured 2026-10-23, every
declarer's count). (One auction per deal, before
the card-play changes: 197 and 137 of 372, and the worst single auction gave
away 1,260, deal 346: E/W stopped in 2S with 7NT available.) Note the caveat baked into `par()`: it is
the best contract available to ONE side ignoring whether the opponents would
compete, so it is a ceiling and overstates the true bidding gap — but the ratio
between the two columns is what matters and is robust.

**Every declarer is solved (2026-10-23).** The opening lead comes from
declarer's left, so the two partners of a side can take different numbers of
tricks in the same strain. The library first held one count per strain and
side, solved with the declarer `research/dd_dataset.declarer_for` picks, and
`grade()` never asked who declared; 22.5% of robot boards (1,428 of 6,356) are
declared by the other partner. `research/solve_declarers.py` solved every deal
from all four leads (22 CPU-hours: median 16 s per deal and strain, worst 49
minutes; 3 workers on a 4-core, 16 GB cloud machine; with 4 the machine restarted
twice, cause not confirmed), checked the two counts already known against it, and
`research/export_challenge_deals.py` keys `tricks` by `"<strain>:<declarer>"`.
Of the 4,000 strain-and-side pairs, the partners differ on 400: 374 by one
trick, 18 by two, 8 by three to five. `dd_tricks` takes a declarer; without
one (par, and `research/gib_h2h.py` before it passed one) it gives the better
partner's count, since a side can choose who declares.

`hands_for` deliberately rebuilds deals from stored text rather than calling
`research.dd_dataset.deal_for`, which seeds the global RNG (and puts it back
afterwards, since 2026-10-18); seeding inside the app would silently make every
later `deal()` reproducible. `ai.py` imports no
RNG at all, so the robot table is deterministic and the benchmark cannot drift —
also pinned by a test, because a benchmark that wandered would turn every margin
into noise.
