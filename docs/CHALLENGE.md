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

**Par is duplicate par (2026-11-06)**: both sides bid perfectly, each seeing
every card (`challenge.par_from_tricks`, searched over the whole auction, a
failing contract doubled). Before, par was the grading side's best contract on
its own; on board 76 (deal 169, N/S vulnerable) the app showed N/S par +90 for
2♦ while E/W make 4♠+1, so a user who scored exactly par (-450) was told the
auction cost 540. The two differ on 997 of the 1,600 deal and vulnerability
pairs. The one-sided figure stays as `challenge.ceiling`, used only by
`research/challenge_losses.py`, so the table below and ROBOT_PROGRESS stay
comparable; with robots in every seat, two-sided par is zero sum and averages out.

`bidding_loss` is par minus the double-dummy value of the contract reached;
`play_loss` is that value minus what was actually scored. The identity is exact
and `tests/test_challenge.py` asserts it on every deal in the library. It makes
"how good is the robot at **bidding**" and "at **declaring**" separable questions,
which a single score cannot answer. Measured 2026-10-19, with every card-play rule below on, by
`research/challenge_losses.py` over all 400 deals at all 16 board positions
(6,356 boards with a contract, 44 passed out), graded from N/S as the app
grades, so this is what the "Robots" column of the match table averages to.
The web app's Challenge caption quotes this table; rerun the script after a
robot change and update both together. Measured 2026-11-03 on PR #62
(v0.1.0-alpha: every bidding change through the Nov 3 fixes), graded with the
partner who actually declared (the library holds every declarer's count; par
takes the better partner); 6,367 boards with a contract, 33 passed out:

| | mean per board | median |
|---|---|---|
| lost in the auction | **233.1** | 200.0 |
| lost in the card play | **5.0** | **0.0** |

Graded from the declaring side: 211.4 in the auction and -4.7 in the card
play. Main before PR #62 (PR #61's robots): 233.6 and 5.3 from N/S, 212.2 and
-5.6 from the declaring side. All four seats bid the same way, so most of
what one side gains the other gains back.

Measured 2026-10-28, after fourth hand wins with a dead card first (below),
with the bidding before PR #40's jam rule: 240.8 in the auction and 20.7 in
the card play from N/S.

Graded from the declaring side: 214.8 in the auction and -21.0 in the card
play. The same robots without the dead winner (the robots of PR #32): 240.8
and 12.1 from N/S, 214.8 and -11.8 from the declaring side. All four seats use
the rule, and the N/S figure nets declarer against defence, so it moves with
whichever side gains more; from the declaring side the play beats double
dummy by 9.2 points a board more. Seated on the library (one side with the
rule, sides swapped): +0.062 tricks, +8.13 points a board (t = +2.87).

Measured 2026-10-24, after the penalty double where X is free, the cuebid
raise read as support (PR #30) and the defender's suit plan: 240.8 in the
auction and 6.0 in the card play from N/S; 214.8 and -24.3 from the declaring
side. All four seats bid the new way, so what one side gains head to head
(+4.34 a board) the other gains back.

Before PR #30, after the defender's suit plan (2026-10-24): 242.5 in the
auction and 5.2 in the card play from N/S; 209.8 and -24.4 from the declaring
side. The same robots without the suit plan: 242.5 and 3.5 from N/S, 209.8
and -36.6 from the declaring side. Robots defend for N/S as often as they
declare, so a better defence moves the N/S figure little; it shows from the
declaring side, whose play now beats double dummy by 12 points a board less.
(The auction's 242.5 against 240.1 below is the jack's judgement point, PR
#28's last commit, measured after it. PR #30 brings it back to 240.8.)

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
  5+ (`_partner_suit_lead`, `PARTNER_LEAD_MIN`); failing that, and on every
  later defensive lead, to a suit partner bid naturally where I hold 3+
  (`_fit_lead`, `FIT_LEAD_MIN`, the user's rule from board 17: lead the
  partnership's fit), unless trumps, or an opponent or dummy is out of it.
  A natural suit bid whose alert names no length counts as a floor of one.
  Seated on 600 fresh deals: **+0.62 points, t = +0.48, 860 of 9,504 boards
  changed** (4+: -0.22, t = -0.21).
  A defender on lead returns a suit partner has shown out of while partner
  may still hold a trump (`_ruff_return`, `RUFF_RETURN`), and partner's
  opening-lead suit when it reads as a singleton (`_short_lead`,
  `SHORT_LEAD_RETURN`, `SHORT_LEAD_PCT` = 20): the robots lead the
  second-highest from two or more, so from length partner holds exactly one
  of the unseen higher cards; every split of the unseen cards with declarer
  (who holds its bid length) is counted. An honour lead (J or higher,
  `SHORT_LEAD_HONOUR`) is read by counting alone, since people lead honours
  from other holdings (deal 356: K♥ from K-7-3-2). Seated on 600 fresh deals:
  **+1.52 points, t = +1.28, 364 boards changed** (+1.53 reading honours too). A side-singleton opening lead
  (`SINGLETON_LEAD`, off) was +0.43 tricks double dummy in the lead study
  but -0.42 points in play, and -0.58 with the return.
  `_splits` and the endgame search keep only layouts that fit the bidding. A human's call reads by what
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
defence, so treat it as a ceiling on the gain. It is a net figure: declarer's
and the defence's mistakes cancel, and added up card by card each side still
gave away about 2.8 tricks a board on 2026-11-05 (ROBOT_PROGRESS.md, "Card
play, mistakes added up"). Until 2026-10-18 "cards the
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

Its summary adds each side's costly cards up (tricks given away a board by
the declaring side, on the opening lead and by the defence); that, not the
net figure, is what to quote for card play, and `--compare before.jsonl`
gives a fix's before and after on the same deals. Planning runs on every
worker too; 200 deals take about 45 minutes on four, solved from scratch.

**The value cache** (2026-11-12). A line's values depend only on the deal and
its cards, never on the robot code that chose them, so every solved line also
goes into `research/data/robot_line_values.jsonl` (committed), and a line found
there, from any robot version, is copied instead of solved: a fix that changes
a few dozen lines solves only those. Of the 63 main lines solved on 2026-11-12,
60 were already in the combined branch's run, and 182 lines repeated across the
older saved runs, every one with identical values. The cache is tied to a hash
of the Rust solver's source (`solver_version`): change the solver and nothing
in it is reused. A copied line passes the same value-chain check as a solved
one. Lines still to solve start slowest first, by the stored times for the same
deal and contract (a deal never solved counts as slowest): on 2026-11-12 deal
197 started last and ran 29 minutes alone after the rest had finished.
`--no-cache` solves everything afresh; `--adopt FILE...` adds the lines of a
presolve output to the cache. For a combined PR, run main's lines first and the
branch's second (not side by side), so the branch copies every line it shares
with main; then commit the cache with the PR, so the next PR finds main's
lines already solved.

    python research/presolve_robot_lines.py --deals 100
    python research/robot_line_report.py
    python research/robot_line_report.py --compare research/data/robot_lines_2026-10-18.jsonl

`research/data/robot_lines.jsonl` holds main's lines after PR #63 (the first
200 deals, 2026-11-05): the "before" for the next change.

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
- **Unless it's ruffed** (`SURE_LEAD_UNRUFFED`, on; deal 157, spades by
  North, user's review 2026-11-06): dummy's K♥ 4♥ 2♥ to North's bare A♥, East
  out of hearts. No heart was sure, since East might ruff, so the fallback 4♥
  went and lost to West's 9♥; under the ace the K♥ is second-highest and wins.
  A ruff beats every card of the suit alike, so with no sure card a second
  pass leaves the ruffs out and leads the lowest card that wins whenever
  nobody ruffs. Gross double dummy losses on 199 deals: declaring side 2.74 to
  2.71, defence 2.41 to 2.38, opening lead 0.40 unchanged; the robot table's
  tricks on the 405 boards whose play changed: -1 in all (flat).
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

**Fourth hand wins with a dead card first** (`ai.DEAD_WINNER_FIRST`; the
user's deal 10, 2026-10-28). Spades by East, trick 5: South led the 8♣, dummy
played the 10♣ and North the 4♣; East, void in clubs, ruffed with the 6♠ from
A♠ J♠ 6♠ (the K♠ and Q♠ gone) and went one down, where the J♠ or A♠ makes
(double dummy). `_play_last` played the cheapest card that keeps the trick, and
a lone trump always wins, so it picked the six. In this game that spends the
wrong card: a dead card wins later only alone in its suit, while a low card can
still be second-highest. So of the cards that keep the trick, fourth hand now
plays the lowest dead one, if any. Seated (`card_play_seated.py`, 800 fresh
deals x 16 boards): **+0.029 tricks, +4.98 points a board (t = +2.83)**; 2,784
of 12,640 boards changed. The same for ruffs only measured even (-0.001
tricks, +0.87 points, t = +0.65, 1,528 boards): a dead trump still pushes
partner's trump into second place later, and the gain is in following suit.
Seated on the challenge library itself: +0.062 tricks, +8.13 points a board
(t = +2.87), 1,448 of 6,356 boards changed.
`tests/test_card_play_rules.py` holds deal 10.

**Third hand ruffs when the next opponent can't overruff** (`ai.RUFF_IF_FOLLOWS`;
the user's deal 276, 2026-10-28). Clubs by West, trick 4: dummy led the J♠,
South played the K♠, and West, void in spades, threw the 3♥ (double dummy two
tricks worse than a ruff). `_middle_play` takes the cheapest card that keeps
the trick and that at most one of the next opponent's possible cards takes
back. The discard left dummy's jack second-highest unless North had the Q♠,
one threat; on a ruff both unseen clubs counted as overruffs, two. But North
can only overruff when out of spades, with eight unseen. So for third hand an
overruff threat now counts the chance the next opponent is void in the led
suit (`_void_chance`: every split of the unseen cards between the unseen hands
equally likely; 9 in 75,582 on deal 276). Seated (800 fresh deals x 16 boards):
**+0.011 tricks a board (t = +1.61), +1.31 points**, 704 of 12,640 boards
changed; on the challenge library **+0.018 tricks (t = +2.57), +1.78 points (t = +1.94)**,
328 of 6,356. Double dummy on each changed card (fresh deals, both sides on):
third hand's ruffs gained 87 tricks over 145 cards (78 better, 18 worse).
Second hand doing the same was even (both together +0.007 tricks, t = +1.10;
its 20 changed cards -3 tricks double dummy), so it is third hand only.
`tests/test_card_play_rules.py` holds deal 276.

**Two rules from championship play records** (2026-10-30; the user's call).
The [ContractBridge/pbn-files](https://github.com/ContractBridge/pbn-files)
PBN records (1996-2002 championships, regular bridge) carry the card play of
36,756 boards up to the claim. The robots replayed 3,063 of those deals in the
experts' contracts, and every lead was compared by its structure: trumps left,
ruffs available, which suit the defence led before, dummy's holding. Card ranks
were ignored, since they mean something else here. Data, scripts and the full
comparison: `/mnt/project-files/championship-play/` (`REPORT.md`). Each rule was
measured seated (`card_play_seated.py`) on the library and on 400 fresh seeded
deals.

- **Notrump defence goes back to the opening-lead suit** (`ai.NT_DEFENCE_SUIT`,
  `_nt_defence_suit`). In notrump a defender on lead leads a suit partner led
  before 60% of the time; the robots, leading their own longest suit
  (`_nt_long_lead`) on every lead, 28%. Now a defender on lead leads the
  opening-lead suit (whoever led it) while it holds one and the opening leader
  hasn't shown out. Library **+0.052 tricks (t = +2.70), +3.5 points**, 774
  boards changed; fresh deals **+0.046 (t = +2.64), +5.7 points**. Partner's
  lead only, not my own: +0.042 (t = +2.71) on the library.
- **An idle trump becomes a ruff** (`ai.IDLE_TRUMP_FOR_RUFF`,
  `_ruff_for_idle_trump`; the user's board, 4S by North, 2026-10-29). Two
  rounds drew the defence's trumps. At trick 6 South led the 9S from J9, North
  had to follow with the K, and two trumps took one trick where a heart, ruffed
  in North, takes it with one. No lead rule fired, and `_lead` liked J9 of
  trumps. So when the defence is out of trumps and `_lead` picks a trump that
  partner must follow, the declaring side leads a suit partner is void in
  instead, while partner holds a trump. The user's point: declarer needn't
  ruff at once, and a trump lead can be the entry that keeps the lead in the
  right hand. Banning idle trump leads outright measured +0.021 (t = +2.04) on
  the library and -0.001 on fresh deals; ruffing at once as well, +0.011 and
  -0.004. The narrow rule: library **+0.009 (t = +2.14), +0.7 points**; fresh
  **+0.012 (t = +2.57), +1.0 points**; 108 boards changed on each. The board
  makes 12 tricks instead of 11. `tests/test_card_play_rules.py` holds it.
- Both together: library **+0.061 tricks, +4.23 points a board (t = +3.09)**,
  882 boards changed; fresh deals **+0.058, +6.69 points (t = +3.24)**, 746.
- Measured and left out, with no code kept: a defence trump switch when dummy
  holds a short side suit and trumps (experts 22%, robots 9%): -0.008
  (t = -0.86), and +0.002 narrowed to dummy with two trumps or fewer.
  Not leading into dummy's void while dummy holds trumps (experts 6%, robots
  12%): -0.025 (t = -1.96). `_ruff_first` allowing one or two more rounds of
  trumps before it calls the short hand's ruffs safe: +0.004, -0.004. With
  ruffs to take, the robots already delay drawing trumps as often as experts
  (40-45% against 41-47% lead one first). With none, experts lead something
  else first 36% of the time and the robots 13%. No rule for that yet.


**Board 26: partner's honour, and the suit played out with the count**
(2026-10-30, the user's board: challenge deal 114, 2S by East after 1NT P
2H(transfer) X P..., North's lead-directing double showing ♥A K J 8 3).

- **The opening lead in partner's suit is my top honour when partner's
  bidding showed judgement points there** (`ai.PARTNER_HONOUR_LEAD`,
  `PARTNER_HONOUR_JUDGE = 4`). South led the 2 from Q-2; the queen under
  North's jack makes a trick and leaves partner well placed. `shown_lengths`
  now also reads "N+ judgement points" off an alert, under `shown['judge']`.
  Rare (lead-directing doubles only): 6 leads changed on the library, net +1
  trick double dummy; none on 400 fresh deals.
- **Second hand, with partner last and in view, breaks a tie by playing the
  suit out** (`ai.COVER_SUIT_PLAN`, `_cover_suit_plan`). At trick 2 North led
  the K♥ with A-8-3 left, East held T-6 and dummy 9-7; South was out by the
  count (the double showed five). The T and the 6 both win the trick, so
  `_cover_for_partner` kept the T; but the 6 and dummy's 7 win it, and then
  the T and 9 win another heart. When cards tie on the trick, the suit is now
  played out over every layout of its unseen cards that fits who has shown out
  and the auction's floors (the defence plan's model with the sides swapped
  and no ruffs), and the card that takes the most tricks in the suit is played,
  the lowest of equals (`COVER_PLAN_LOW`). The suit's top unplayed card is
  never spent on a tie (`COVER_KEEP_MASTER`): of 26 such cards, 1 was better
  double dummy and 6 worse.
- **Fourth hand on the declaring side breaks a tie the same way**
  (`ai.LAST_SUIT_PLAN`): of the cards that keep the trick, the one the plan
  rates best. After K-T-2, dummy's 9 and 7 both win; the 9 leaves the 7 beside
  East's 6 to win a later heart.
- Seated head to head the package is within noise (library -0.001 tricks,
  fresh deals +0.017, t = +0.82, +2.1 points; about 1,300 boards changed on
  each): the gain is about a tenth of a trick a deal. So every changed card was
  scored double dummy against the old one from the same position
  (`/mnt/project-files/board26-play/`, `REPORT.md`). Library: 355 positions,
  **61 better, 21 worse, net +45 tricks**. Out of sample, 400 fresh deals
  (seed 1030): 321 positions, **59 better, 19 worse, net +49**, ahead in every
  part (dummy second +25, declarer second +7, declarer fourth +8, dummy fourth
  +9; suit contracts +40, notrump +9). Letting the defenders choose the next
  lead after they win a trick changed no card and was dropped.
  `tests/test_card_play_rules.py` holds the board.

**Second hand covers when dummy plays third** (2026-10-30, the user's board:
West declaring led the T♠ at trick 7, North held ♠A J 8 3, dummy ♠9 6).

- North played the 8: `_middle_play` scores a card by what dummy can do to it
  and stops there, and the 8 holds unless dummy plays the 9, which it does.
  Partner, fourth and unseen, can't get the trick back. The user's point: dummy
  holds nothing above the nine, so an honour makes the ten second-highest for
  now and partner's king or queen then pushes North's card into second place.
- `ai.SECOND_HAND_COVER` (`_cover_unseen_partner`): second hand, dummy third
  and partner's hand unseen, plays the suit out over every layout of its unseen
  cards between partner and declarer (`_unseen_partner_plan`: who has shown
  out, the auction's floors, no ruffs, as `_cover_suit_plan` with partner the
  hidden hand) and plays the card that takes the most tricks in the suit; the
  old card when it ties, else the lowest of the best. Where the plan doesn't
  apply (a discard, history unknown) a card is scored by the chance, after
  dummy's best reply, that partner holds a card winning the trick for us
  (`_partner_chances`, even odds a card). On the board the plan plays the
  ace, the only card that saves two tricks double dummy; the trick's chance
  alone plays the jack, which wins the trick but strands the ace.
- Seated head to head: library **+0.081 tricks, t = +3.46, +8.7 points**;
  400 fresh deals (seed 1031) **+0.059, t = +2.79, +5.3 points**; about 1,900
  boards changed of 6,350. Each changed card double dummy against the old one:
  library 440 positions, 147 better, 27 worse, net +170; fresh 418, 140 / 33,
  net +147. Judging this trick alone gained about half (seated +0.061 and
  +0.041; double dummy +84 and +79). Measured and dropped: the trick's chance
  with the plan breaking ties or vetoing a worse card (veto +0.054 / +0.036
  seated), odds from hand sizes and the auction, skipping dummy-void tricks,
  and a margin before changing the card (`/mnt/project-files/second-hand-cover/`,
  `REPORT.md`). `tests/test_card_play_rules.py` holds the board.

**...and when dummy led** (2026-11-05, the user's board: trick 3, dummy led
the 9♣, East held ♣K T 7 4 3 over declarer's unseen ♣A Q 8 5 2, partner ♣J 6).

- East played the 3, which gives away two tricks double dummy; the T was best.
  The cover above only ran with dummy third, so with dummy leading,
  `_middle_play` judged the card against declarer alone and ducked.
- `ai.SECOND_HAND_COVER_DUMMY_LED`: the same suit plan (`_unseen_partner_plan`)
  with dummy the leader, declarer third and partner last, the suit's unseen
  cards laid out between declarer and partner. No `_partner_chances` fallback:
  where the plan doesn't apply, the old card stands. On the board it plays the T.
- Seated head to head: library **+0.045 tricks, t = +2.53, +5.3 points**;
  400 fresh deals (seed 1105) **+0.051, t = +2.81, +6.4 points**; about 1,370
  boards changed of 6,350. Mistakes added up, 199 deals: declaring side 2.74 ->
  2.66, opening lead 0.40 -> 0.40, defence after the lead 2.41 -> 2.29
  (`/mnt/project-files/dummy-led-cover/`). `tests/test_card_play_rules.py`
  holds the board.

**Every card of the suit located** (2026-11-04, the user's 4♥: trick 5, South
led the 8♥, West showed out, dummy's 9♥ won whatever East played; East ♥T5,
dummy ♥42, South ♥AQ6).

- East played the 5: `_play_last` dumps the lowest card when nothing keeps the
  trick. The 5, between South's honour and dummy's small heart, is always
  second-highest later; the ten can be beaten by South's six. Once the other
  hidden hand has shown out, every card of the suit is placed.
- `ai.LOCATED_SUIT_PLAN` (`_located_suit_plan`): second, third and fourth hand,
  following suit, with every card of the led suit located (the hand, the
  visible hands, and one hidden hand that hasn't shown out holding the rest),
  play the suit out exactly (`_plan_trick`, this trick included) and play the
  card that takes the most tricks in it; the old card when it ties, else the
  lowest of the best. 1 = the trump suit or notrump only (nobody can ruff), 2 =
  any suit with later ruffs ignored, 0 off. Shipped at 1.
- Seated head to head, 3 × 1,000 fresh deals (seeds 1104-1106): **+0.016,
  +0.014, +0.010 tricks a board, t = +3.74, +3.63, +3.53; +2.3, +1.7, +1.6
  points**; about 300 of 15,800 boards changed. Any suit (2) on seed 1104:
  +0.019, t = +3.93, +2.6 points, 521 boards; not finished on the other seeds
  (`/mnt/project-files/located-suit/`). `tests/test_card_play_rules.py` holds
  the board.

**A discard keeps the card that wins in a located suit** (2026-11-10, user's
board). Deal 206, 3♥ by East, trick 5: East led the K♥ and South, out of trumps,
threw the 2♠ from A J 7 5 2. Every other spade had been seen and dummy held 4 3.
- South threw the 2: `_middle_play` found nothing that keeps the trick and
  `_shed` dumps the lowest side card, as in ordinary bridge. Here a trick only
  two hands follow to goes to the LOWER card: the 2 was the one spade under
  dummy's, and without it both of dummy's spades won.
- `ai.DISCARD_SUIT_PLAN` (`_discard_suit_plan`): after any rule picks a discard,
  if every card of its suit is located (as `LOCATED_SUIT_PLAN` locates them),
  the suit is played out (`_plan_suit`, ruffs ignored, since a ruff takes the
  trick whichever card was thrown) with each of the hand's cards of it gone. A
  discard that loses a trick there gives way to the highest card that loses
  none; the suit stays the one chosen. Shipped on.
- Robot lines on 199 library deals: 56 discards changed on 349 lines, each
  scored double dummy: +17 tricks for the side that threw, none lost. Gross
  mistakes 2.58 -> 2.57 declaring side, 2.12 -> 2.11 defence
  (`/mnt/project-files/keep-low-spade/`). `tests/test_card_play_rules.py`
  holds the board.

**Third hand on defence plays the suit out** (2026-11-06, two user boards).
Deal 319, 4♥ by South, trick 7: East led the 5♦, South played the 9♦, West held
♦A Q 4 2 with dummy's lone K♦ to come, and played the 2. Deal 58, 2♠ by South,
trick 2: East led the 6♦, South played the 10♦, West held ♦A J 9 7 3 2 with
dummy's K Q to come, and played the 2.

- `_middle_play` asks who holds the trick now and which later cards could take
  it away, never which later card hands it back. The 2 "keeps" partner's card
  winning until dummy's honour makes declarer's card second-highest; the queen
  (the jack) loses for now, but dummy's honour pushes it into second place.
- `ai.THIRD_SEES_LAST` (`_third_sees_last`): third hand with the last hand in
  view plays the cheapest card that wins whatever that hand plays, unless the
  old card already does.
- `ai.THIRD_HAND_PLAN` (`_third_hand_plan`): third hand on defence, following
  suit, plays the led suit out over every layout of its unseen cards between
  partner and declarer (as `_unseen_partner_plan`; who has shown out, the
  auction's floors, declarer's and dummy's ruffs in a side suit of a trump
  contract) and plays the card that takes the most tricks in it; the old card
  when it ties, else the lowest of the best. 1 = declarer last, 2 = dummy last
  too, 0 off. Shipped at 2. Both boards: the queen, the jack (double dummy 8
  tricks for declarer against 9).
- Seated head to head: the sure-winner rule alone **+0.012 tricks, t = +2.77,
  +1.4 points**, 108 boards. With the plan: library **+0.052, t = +3.11, +4.0
  points**; 400 fresh deals (seed 1106) **+0.053, t = +3.06, +6.1 points**;
  about 1,000 of 6,370 boards changed. Gross mistakes, 199 deals: the defence
  2.41 -> 2.25 tricks a board (third hand 0.43 -> 0.31), the declaring side
  2.74 -> 2.68 (it meets different positions). Card by card against the old
  card on the same 199 deals: +0.060 a board; declarer last only +0.038, side
  suits left out +0.049, ruffs ignored +0.057 (`/mnt/project-files/third-sees-last/`,
  `variants.py`). `tests/test_card_play_rules.py` holds both boards.

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
away 1,260, deal 346: E/W stopped in 2S with 7NT available.) Note the caveat baked into this par (now
`challenge.ceiling`): it is the best contract available to ONE side ignoring
whether the opponents would compete, so it is a ceiling and overstates the true bidding gap — but the ratio
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

## Crossing to the trump hand to draw trumps (deal 80)

A user's 2♥ by East, trick 8: dummy (West) on lead with ♠2 ♦J9 ♣K86 and no
trumps, East holding ♥AJ42 ♦8 ♣9, South still with ♥75 and both defenders out
of clubs. Dummy led a club, which South could ruff.

- Why: `_draw_trump` returns None when the hand on lead holds no trumps; it
  never asks whether the lead can cross to the hand that has them.
  `_run_long_suit` rightly refuses while the defence holds trumps, and the
  fallback `_lead` reads only dummy's own cards (gap analysis tied ♦ and ♣,
  clubs were longer), so it led the 8♣ (the 6♣ with `SURE_LEAD_UNRUFFED`).
- `ai.ENTRY_TO_DRAW` (`_entry_to_draw`): a declaring-side hand on lead with no
  trumps, whose partner's `_draw_trump` would draw, leads its lowest card of a
  side suit partner is void in, when both defenders follow on at least
  `ENTRY_FOLLOW` (85%) of the layouts and neither has shown out.
- `ai.RUFF_KEEPS_DRAW` (`_ruff_for_draw`): the declaring side, ruffing third or
  fourth with the first trump in the trick, ruffs with the trump that leaves
  the fewest `_trump_losers`; third hand only when the fourth hand is void in
  the led suit at most 15% of the time (a lower ruff would win). East ruffs
  with the J♥, keeping the 2 and 4 that draw the 7 5.
- The board makes 10 tricks, the user's line. Seated head to head, 3 × 1,000
  fresh deals: **+0.013, +0.013, +0.006 tricks** (t 2.81, 2.35, 1.42); gross
  mistakes on 199 deals 2.56 / 0.40 / 2.10 (from 2.59 / 0.40 / 2.12).
  `tests/test_card_play_rules.py` holds the deal.

**Deal 13, 4♠ by South (user's board, 2026-11-10).** Trick 2: dummy led the
9♠, East covered with the 10♠, and South held A K Q J 8 6 with dummy's 5♠ left
and West's 7 3 2 unseen. South played the 6♠: declarer's side in third seat
had only `_middle_play` (the cheapest card that keeps this trick), and both the
8 and the 6 leave the nine second-highest. The 8 keeps the 6 to sandwich West's
7 between dummy's 5 and South's 6 next round; double dummy 10 tricks against 9.
- `ai.DECLARER_THIRD_PLAN` (`_declarer_third_plan`): third hand on the
  declaring side, in the trump suit or notrump (1; 2 adds side suits, not
  measured), plays the led suit out over the layouts of its unseen cards
  between the defenders (`_cover_suit_plan`, this trick included) and plays
  the card that takes the most tricks in it. Fourth hand already did this
  (`LAST_SUIT_PLAN`), defence third hand too (`THIRD_HAND_PLAN`).
- Seated head to head, 3 × 1,000 fresh deals: **+0.017, +0.036, +0.027
  tricks** (t 1.71, 4.00, 2.87), +3.47 / +4.22 / +2.23 points; gross mistakes
  on 199 deals 2.57 / 0.39 / 2.11 (main 2.58 / 0.39 / 2.12).
  `tests/test_card_play_rules.py` holds the deal.
## The table count (2026-11-10)

An audit of every robot card on 199 library deals, each traced to the rule
that chose it (`research/play_rule_trace.py`), found 2.82 of the 5.09 tricks a
board given away (gross, both sides) on cards chosen by rules that read only
their own hand and the cards played: the fallback lead `_lead` (1.21, mostly
the wrong suit, not the wrong card), the discards in `_shed` (0.84), fourth
hand's `_play_last` (0.32) and the notrump leads (0.27). The rules that do
count each rebuilt their own picture of the table — "seen", "unseen",
show-outs, hand sizes, the auction's floors — about fifteen times, each a
little differently.

- **Phase 1 (this change, no card changes).** `ai.TableCount` is that picture,
  built once per card by `ai_play` from what the seat may legally know, and
  passed to every rule as `count`: `seen`, `unseen`, `gone`, `out` (who has
  shown out), `size`, `floor`, `played_in`, `master`, `dead`, `splits`
  (`_splits`), `fits_auction`. A rule called on its own builds one from the same
  arguments. `tests/test_table_count.py` keeps the derivations in the count (no
  rule reads `_FULL_DECK`, `_shown_out` or `_played_in`, or builds
  `set(played)`) and checks the count against the real deal at every card of
  12 robot games. The robots' 6,400 lines on the library (400 deals × 16 boards)
  are identical before and after, and the web engine's `TableCount` follows
  line for line (fixtures).
- **Still blind, by design of phase 1:** `_lead`, `_gap` and `_nt_long_lead`
  still read only the cards played, and `_shed` reads neither. Phase 2 rebuilds
  them on the count, one measured switch each: the lead's suit choice by the
  suit plans over `count.splits`, discards that keep the guard against dummy's
  visible length, fourth hand on defence.
- **Phase 2.1, the lead's suit (`COUNT_LEAD`).** When no lead rule fires, `_lead`
  still names a suit by `_gap`, and `_count_lead` then asks the count instead,
  for a seat that sees a second hand: each suit it holds is played out over
  every layout of its unseen cards between the two hidden hands (shown-outs and
  the auction's floors respected, weighted as `splits` weights), with
  `_defender_suit_plan`'s suit model. U is the tricks this side takes in the
  suit leading it now; V the tricks it takes if the other side opens it. The
  suit with the most U + (U − V) is led, with the card that takes the most;
  `_lead`'s suit wins a tie. Declarer never picks trumps this way (drawing
  them is `_draw_trump`'s call), the defence in a suit contract keeps `_lead`
  (every version measured worse there: the model's ruffs are too rough), and a
  suit with more than `SUIT_PLAN_MAX_UNSEEN` unseen cards leaves `_lead` alone.
  Scored one decision at a time against the solver on the 2,448 fallback leads
  of 199 deals: 1.63 → 1.27 tricks a board (declarer in notrump 0.47 → 0.23,
  declarer in a suit 0.50 → 0.41, defence in notrump 0.16 → 0.12; U alone,
  U − V alone and U + (U − V)/2 all did worse). Whole games on the same deals,
  gross: declaring side 2.58 → 2.31, defence 2.12 → 1.99 tricks given a board,
  the opening lead unchanged; seated on 3 × 1,000 fresh deals +0.051, +0.058,
  +0.028 tricks a board (t 2.95, 3.33, 1.54). It costs about 0.08 s a fallback
  lead in Python. Deal 114's robot table now wins three hearts for E/W, not two.
- **Phase 2.2, the declaring side's discards (`COUNT_DISCARD`).** Void and not
  ruffing, a robot threw `_shed`'s card, the lowest side card wherever it
  was. Of the 0.98 tricks a board lost on cards played while void (199 deals,
  after phase 2.1), about half was a discard from the wrong suit. Now the
  declaring side prices each card it could throw: its suit is played out over
  the count's layouts with and without the card, a suit's tricks the average
  of us opening it and them opening it, and the cheapest card replaces
  `_shed`'s when that one costs half a trick more (`COUNT_DISCARD_MARGIN`).
  Not inside the endgame search, which already sees every card. The defence
  keeps `_shed`: the model lets either defender lead the suit whenever it
  likes, blind to partner's entries, and every margin tried measured worse
  there. Nor does declarer stop ruffing second hand when partner wins anyway
  (0.14 tricks a board lost that way): keeping the trump measured worse too.
  Offline, the declaring side's void cards 0.55 → 0.47 tricks a board; whole
  games, declaring side 2.31 → 2.24, defence 1.99 → 2.01 (its play is
  unchanged; the boards it meets are not); seated on fresh deals, see
  ROBOT_PROGRESS.
- **Phase 2.3, the defence's fourth hand (`FOURTH_HAND_PLAN`).** `_play_last`
  played the cheapest card that kept the trick, or the lowest: one trick's
  worth of thought, where fourth hand's card also decides what is left of the
  suit. The third-hand plan (`_third_hand_plan`) already plays the led suit out
  over the count's layouts with the trick so far on the table, so fourth hand
  on defence now follows suit with it too (the declaring side has
  `LAST_SUIT_PLAN`). Card by card, the defence's fourth-hand cards in the led
  suit lost 0.215 → 0.122 tricks a board; whole games, defence 2.01 → 1.97,
  declaring side 2.24 → 2.23; seated +0.026, +0.026, +0.027 tricks a board on
  fresh deals (t 3.46, 3.86, 3.69). Fourth-hand discards keep `_shed`.
## Playing for ruffs when drawing trumps gains nothing (deals 215, 102)

Two user boards where declarer led trumps that did no good.

- Deal 215, 2♥ by West, trick 5: South had shown out of hearts, North held the
  ♥10 5, dummy the A K over West's 8 4. Whichever hand leads, North's 10 and 5
  each take a round, so drawing gains nothing: the defence makes both trumps
  anyway and the declaring side throws two trumps a round that could each
  have ruffed. `_draw_trump` only asked whether the defence still held trumps
  and whether we held more, and dummy cashed the K♥ (three tricks double
  dummy).
- `ai.NO_FUTILE_DRAW` (`_draw_plan`): when the best trump lead loses a trick to
  every outstanding trump on every layout, and two or more are out, no trump
  is led; the fallback `_lead` picks a side suit. Dummy now leads the 10♣. With
  one defence trump out the test fires constantly and drawing is usually
  right (left in, the lone trump overruffs a higher ruff, since of two trumps
  the lower wins): those cases went 3 better, 8 worse card by card on 199
  solved deals, so they're excluded.
- Deal 102, hearts by East, trick 5: four trumps each way, so `_draw_trump`
  declined; the fallback `_lead` reads only declarer's cards and picked the
  10♥, never asking whether dummy (void in spades, the 6♥ left) could ruff the
  K♠ (one trick double dummy).
- `ai.RUFF_NOT_DRAW`: when the fallback picks a trump that `_draw_trump` didn't
  choose, the declaring side leads a suit its visible partner is void in while
  partner holds a trump (`_ruff_for_idle_trump` with `defence_trumps=True`).
  Card by card on 199 solved deals: 4 better, 0 worse.
- Seated head to head, 3 × 1,000 fresh deals: **+0.005, −0.001, +0.003 tricks**
  (t 1.53, −0.35, 1.20); gross mistakes on 199 deals 2.57 / 0.39 / 2.11 (from
  2.58 / 0.39 / 2.12). `tests/test_card_play_rules.py` holds both deals.
- With `COUNT_LEAD` (v0.1.4-alpha): the count's lead never picks a trump for
  the declaring side, so it would hide the trump `RUFF_NOT_DRAW` looks for (on
  deal 102 it chose the Q♣, a trick worse than the K♠). `RUFF_NOT_DRAW` also
  fires when `_lead`'s own pick is that trump, and its ruff suit's card, like
  `NO_FUTILE_DRAW`'s side suit, comes from `_fallback_lead`. Order of the
  discard rules: `COUNT_DISCARD` picks the suit, then `DISCARD_SUIT_PLAN` picks
  the card in it. `test_shipped_rules_together_on_the_users_deals` holds deals
  13, 102, 206 and 215 with every rule as shipped.
