# Challenge mode and robot card play

Head-to-head boards against an all-robot table, graded against double dummy, and the card-play improvements measured on that library.

Moved verbatim from `CLAUDE.md` on 2026-10-13, so it is read when the work needs it instead of loading into every session. [CLAUDE.md](../CLAUDE.md) keeps the guardrails and links here.

**`challenge.py`** — head-to-head mode: the same deal played by the human and by
an all-robot table, then graded. Pure domain logic, no Streamlit. It runs on
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
which a single score cannot answer. Measured 2026-10-19 by
`research/challenge_losses.py` over all 400 deals at all 16 board positions
(6,356 boards with a contract, 44 passed out), graded from N/S as the app
grades, so this is what the "Robots" column of the match table averages to.
The captions in both apps quote this table; rerun the script after a robot
change and update all three together:

| | mean per board | median |
|---|---|---|
| lost in the auction | **233.9** | 200.0 |
| lost in the card play | **12.5** | **0.0** |

Graded from the declaring side instead: 220.5 in the auction and **-26.0** in
the card play (median 0.0), so the declaring side's play beats double dummy on
average, on the defence's mistakes. The figures before this (143.7 / 31.8 over
372 boards) were one auction per deal and predate every card-play change
below, so they aren't comparable: the 16 board positions include vulnerable
boards, where par is worth far more (not measured separately).

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
over 15 minutes for the library -- too slow for the table -- and was dropped.
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
dummy on 3,668 of 6,356 boards (graded from N/S; 4,320 from the declaring
side); the auction is at or above par on 1,662. (One auction per deal, before
the card-play changes: 197 and 137 of 372, and the worst single auction gave
away 1,260, deal 346: E/W stopped in 2S with 7NT available.) Note the caveat baked into `par()`: it is
the best contract available to ONE side ignoring whether the opponents would
compete, so it is a ceiling and overstates the true bidding gap — but the ratio
between the two columns is what matters and is robust.

**Known limitation: one declarer per strain and side.** The library holds one
trick count per strain and side (`"C:N/S"`), solved with the declarer
`research/dd_dataset.declarer_for` picks (longer in the suit, or more HCP in
notrump; ties to North or East), and so with the opening lead from that seat's
left. `grade()` looks the count up by strain and side and never asks who
declared. When the auction puts the contract in the other hand, the double
dummy count can differ by a trick or more, and the difference lands in
`play_loss` and, through `dd_score`, in `bidding_loss`. It is common: measured
2026-10-18 over the robot table's auctions at all 16 board positions, **1,428 of
6,356 boards (22.5%)** are declared by the other partner, 612 of 1,972 in
notrump. The fix is to solve both declarers and key the library by
`strain:declarer`, or to record the solved declarer and flag mismatched boards.

`hands_for` deliberately rebuilds deals from stored text rather than calling
`research.dd_dataset.deal_for`, which seeds the global RNG (and puts it back
afterwards, since 2026-10-18); seeding inside the app would silently make every
later `deal()` reproducible. `ai.py` imports no
RNG at all, so the robot table is deterministic and the benchmark cannot drift —
also pinned by a test, because a benchmark that wandered would turn every margin
into noise.
