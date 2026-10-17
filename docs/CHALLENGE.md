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
which a single score cannot answer. Measured over the 372 library boards the
robots reach a contract on:

| | mean per board | median |
|---|---|---|
| lost in the auction | **143.7** | 130.0 |
| lost in the card play | **31.8** | **0.0** |

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
defence, so treat it as a ceiling on the gain. The table below predates all
four changes.

**Fourth hand plays for the partnership** (`_play_last`): it used to take a
trick only if it could win it ITSELF, never by promoting partner's card. On a
user's 3H dummy played low under North's 7H where the king makes East's 8H
second-highest. Measured one side at a time over the library: declarer
**+0.43 tricks per board (t = +7.2)**, defence **+0.21 (t = +5.2)**.

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

**The robot declares well and bids badly.** Card play is perfect (at or above
double dummy) on 197 of 372 boards; the auction on 137. The worst single auction
gave away 1,260 (deal 346: E/W stopped in 2S with 7NT available). At 289 deals
the same table read 149.1 / 28.1 over 267 boards — the extra 100 deals moved
neither column materially. Note the caveat baked into `par()`: it is
the best contract available to ONE side ignoring whether the opponents would
compete, so it is a ceiling and overstates the true bidding gap — but the ratio
between the two columns is what matters and is robust.
`hands_for` deliberately rebuilds deals from stored text rather than calling
`research.dd_dataset.deal_for`, which reseeds the global RNG; doing that inside
the app would silently make every later `deal()` reproducible. `ai.py` imports no
RNG at all, so the robot table is deterministic and the benchmark cannot drift —
also pinned by a test, because a benchmark that wandered would turn every margin
into noise.
