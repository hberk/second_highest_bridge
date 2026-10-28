# Bidding and hand evaluation

The robots' bidding: GIB (the default), the previous fitted system that still answers contested auctions, and the research behind every constant. **Read the two-metrics warning and the noise floor before tuning anything.**

Moved verbatim from `CLAUDE.md` on 2026-10-13, so it is read when the work needs it instead of loading into every session. [CLAUDE.md](../CLAUDE.md) keeps the guardrails and links here.

## GIB 2/1 (`gib.py`), the default

**`gib.py`** — **the robots' bidding system: GIB 2/1 game force**, from BBO's
[GIB system notes](https://www.bridgebase.com/doc/gib_system_notes.php), adopted
in full at the user's request because it is the system players know. 5-card
majors, 15-17 1NT, 20-21 2NT, strong 2♣, weak twos, 2/1 game forcing, 1NT
forcing, Jacoby 2NT, splinters, inverted minors, Soloway jump shifts, two-way
game tries, Reverse Drury, new minor and fourth suit forcing; Stayman, Jacoby and
Texas transfers, minor-suit Stayman, minor transfers, shortness bids, Gerber and
quantitative 4NT over notrump; RKCB 0314 with queen and king asks, DOPI;
negative (through 3♠), support (through 2♥), responsive and takeout (through
4♥) doubles, weak jump overcalls, 1NT overcall, Michaels, Unusual 2NT,
unusual-vs-unusual, leaping minors over weak twos, Cappelletti, Lebensohl,
Jordan 2NT. `ai.ai_bid_explained` asks `gib.gib_bid` first; it returns None only
for contested auctions the notes leave to judgment, where `ai.py`'s previous
logic answers. `frontend/src/lib/engine/gib.ts` is its line-for-line port.
- **Measured against the previous system and adopted anyway, by choice.** Over
  400 deals x 4 dealers, head to head: **-6.6 per board, t = -2.99**. Self-play
  declaring-side +33.3 against +65.5; contracts made 45% against 67%; 32%
  notrump, 38% game or higher and 8 slams, against 0%, 5% and 0; passed out 11
  boards in 1,600 against 126; auction loss against par 174.6 against 145.6.
  It loses for the reasons recorded below -- game and notrump are rarely right
  in this variant -- and the user chose familiarity over score. **Do not "fix"
  GIB toward the measured system.** The previous system is intact behind
  `ai.USE_GIB = False` (`settingsAi.useGib` in the port) for comparisons.
- `gib.ILLEGAL` records any call a branch produced that was not legal; the
  guard in `gib_bid` substitutes a legal one, and `tests/test_gib.py` asserts
  the list stays empty over 600 auctions.
- Alerts quote **HCP** ("15-17 HCP") where GIB does, and "points" (the guide
  count) only where the branch enforces it. An artificial call's alert says
  "Artificial" and is exempt from naming its own suit; `_name_the_suit`
  appends the suit to any other suit bid's alert, so the text still depends on
  the call alone.
- **Where GIB hands off** (surveyed 2026-10-14, 4,000 random boards, all four
  seats robots): **14.9% of calls, on 48% of boards**, are made by `ai.py`'s
  fallback. 97% of those are second-round-or-later calls in contested
  auctions -- opener's 2nd (22%), responder's 2nd (22%), opener's 3rd+ (17%),
  overcaller's 2nd (14%) -- where the fallback passes 63-96% of the time and
  **never doubles**. First calls are covered; the one deliberate exception is
  advancing a takeout double. Each fix below came from this survey; the
  open candidates are listed in [ROADMAP.md](ROADMAP.md). Tools:
  `research/gib_handoffs.py` (the survey) and `research/gib_h2h.py` (head to
  head for a new branch).
- **Systems on over our 1NT overcall** (`Ctx.nt_overcall`): after (1x)-1NT,
  both partners play the 1NT opening's whole structure, every round, at the
  overcall's 15-18, while the opponents pass. Before, only advancer's first
  call was systems on: the overcaller then read a transfer as natural and
  passed it, in (1D)-1NT-(P)-2D in their own suit.
- **Reopening double** (`_reopening`, `_answer_reopening`): after
  1x (y) P (P), with y a natural one- or two-level overcall, opener doubles on
  0-1 cards in their suit, or 2 with 15+ HCP (`REOPEN_DOUBLETON_HCP`); a
  six-card suit on less rebids instead, and 18+ doubles on any length. Before,
  opener with a singleton or void never doubled (36 of 116 reopening seats in
  the survey: 11 passes, 25 rebids). Responder passes for penalty with 4+ in
  their suit, two of the top five honours and 6+ HCP, else bids: a 4-card
  major, notrump with a stopper and 6+, partner's suit, the longest unbid suit.
  Head to head over the library: **+1.64 per board, t = +2.06, 28 of 1,600
  auctions changed** -- most of it responder answering at all, where the old
  18+ double was left in by accident (deal 7: 2S doubled made, now 3H scores).
  The penalty pass is kept **by choice**: without it measured +1.74
  (t = +2.36), a difference of one deal. That deal, 303, is worth knowing:
  South's QJ1065 of hearts behind declarer's suit is a textbook trap pass,
  yet E/W take 9 tricks in hearts -- under second-highest rules a trump stack
  of honours is not the penalty it is in ordinary bridge.
- **Opener after they bid over partner's negative double**
  (`_negative_double_competed`, `_answer_extras_double`): `1x (1y) X (2y) ?`.
  The fallback read partner as having **passed** ("Partner has passed; not
  enough to bid again alone") and bid the promised fit **0 times in 27**
  survey hands that held it. Now: four in a suit the double promised bids
  it, cheapest with a minimum, a jump with 15+ (`NEG_COMPETED_JUMP_HCP`),
  game in a major with 18+; else a six-card suit rebids; else 17+ doubles
  for extra values, **only over a two-level bid**; else pass. Responder
  passes opener's double for penalty with four of their suit and two of the
  top five honours, else bids. Head to head: **+0.40 per board, t = +1.58,
  18 of 1,600 auctions changed** -- positive, below detection, because the
  auction is rare. The first version doubled at any level and measured
  +0.09: on deal 334 opener doubled 3S, responder had no answer below the
  four level, and 3S doubled made.
- **Opener after they overcall the response** (`_rebid_over_their_overcall`):
  `1x (P) 1y (2z) ?`. The fallback raised every four-card fit to the two
  level, 12 HCP or 18, and passed 18-19 balanced. Now: four-card support
  raises cheapest with 12-14, jumps with 15+, bids game in a major with 18+;
  else 2NT on 18-19 balanced with their suit stopped (`REBID_2NT`); else a
  six-card suit rebids, jumping with 15+; else a new four-card suit at the
  two level with 16+ (`REBID_NEW_SUIT_HCP`); else pass. Exactly three is
  still the support double. Head to head: **-0.07 per board, t = -1.22, 4 of
  1,600 auctions changed** -- the library barely reaches this auction. The
  changed boards show the variant's usual cost of showing strength (deal
  234: 4S with 18 failed where 2S made; deal 228: 2NT went down where 2S
  made). **Kept by the user's choice**, as GIB-standard bidding.
  - **The splinter in their suit** (`COMPETED_SPLINTER`,
    `COMPETED_SPLINTER_MIN = 19`, `_answer_competed_splinter`; the user's call,
    2026-10-20): with four of partner's major and 0-1 of their suit, and HCP
    plus dummy points for the shortness (void 5, singleton 3) of 19+, opener
    jumps to 4z, game forcing; responder bids 4M. Only below game in the
    major (no 4♠ over 1♥ (2♠)). Deal 329, 1♣ (P) 1♥ (2♦) with ♠K752 ♥Q753
    ♦— ♣AKQ63, used to raise to 2♥ and defend 3♦ where 7♥ makes; now 4♦-4♥,
    13 tricks. Head to head (`research/gib_h2h.py COMPETED_SPLINTER`): **+0.19
    per board, t = +1.00, 2 of 1,600 auctions changed** (329 +610; 234 the
    same 4♠ via 4♥). No slam follow-up yet: responder always signs off.
- **Game over a three-level jump overcall** (`JUMP_OVERCALL_GAME`, in
  `_respond_over_interference`; the user's call, 2026-10-20): 1M (3x) with
  3+ support and 11+ HCP bids 4M. Before, the cuebid (4x) was above the
  three-level limit, 3M needed 6-9, and these hands passed or made a
  negative double. Deal 346: ♠AK96 ♥K ♦QJ10432 ♣J6 passed 1♠ (3♥); 4♠
  makes 13. Head to head: **+0.76 per board, t = +1.93, 9 of 1,600 auctions
  changed** (wins 346, 88, 386; loss 202). At 10+ it measured +0.53
  (t = +1.29, 14 changed): deals 1 and 381 went down in game with exactly
  10. 11 was chosen by the user knowing it drops those two -- a threshold
  read off a handful of deals, so treat it as below the noise floor.
- **After our two-suited overcall** (Unusual 2NT, Michaels; the user's call,
  2026-10-20). Two faults, two switches:
  - `TWO_SUITER_GAME` (`_advance`): advancer with 3+ in one of partner's
    suits and game values (`judge` + `TWO_SUITED_MIN` >= `GAME`) bids game
    in it. Before, advancer always took the cheapest preference: deal 163,
    (1♦) 2NT (P) with five clubs and a 10-card fit bid 3♣, and N/S defended
    4♦ where 7♣ makes; now 5♣, 13 tricks.
  - `TWO_SUITER_READ` (`continuation`, `_our_two_suiter`,
    `_two_suiter_lengths`): the later rounds read the overcall as 8+ HCP and
    5-5 in its suits, and advancer's suit bids as a preference (3) or a suit
    of their own (5). Before, they read our 2NT as a 20-21 opening and the
    next bids as Stayman and transfers, so neither hand saw the fit.
  - Head to head: **+0.23 per board, t = +1.43, 3 of 1,600 auctions changed**
    (all deal 163). `TWO_SUITER_READ` alone scores +0.00: on 163 the minor-fit
    branch still prefers 3NT below 29 combined. 36 library auctions have a
    two-suited overcall at all.
- **Their contract is not our game reached** (`THEIR_CONTRACT_DOUBLE`,
  `_over_their_contract`, in `continuation`; the user's call, 2026-10-20).
  `continuation` passed "Game reached" whenever the bidding stood at 3NT or
  the four level, without asking whose bid it was: when they outbid our game
  or bid 3NT themselves, the robots passed it as if it were ours, and nobody
  ever doubled (24 library auctions, 8 deals). Now, when they hold the
  contract, double for penalty if our side has shown game values (bid game,
  a game-forcing auction, or `judge` + partner's minimum >= `GAME`); else
  pass, "Their contract; nothing more to show." Head to head: **+2.99 per
  board, t = +3.48, 20 of 1,600 auctions changed**, 18 better: deal 118 4♠
  doubled four down (+1100), 109, 125, 224, 110, 235. The loss is deal 328
  (-170 twice), where their 4♥ makes. Deal 67 still passes 3NT that goes
  down five: opener's 2NT rebid is not credited as 18-19, so E/W never see
  game values.
- **Our natural overcall is not an opening** (`OVERCALL_READ`,
  `_their_opening_suit`, `_our_two_level_overcall`; with `VALUES_AT_FOUR`;
  the user's call, 2026-10-20). `continuation` read our first call with an
  opening's meaning: (1♦) 2♣ as a strong 2♣ and game forcing, 2♦/2♥/2♠ as a
  weak two, and a one-level overcall's later bids with 2/1 game-force rules.
  Deal 67 (corrected: E/W's 2NT there answers the negative double, it is not
  18-19): South, 10 HCP, overcalled 2♣ and then bid 3NT over their 2NT, six
  down; now it passes. Now, after their one-level suit opening, the
  opening's forcing rules don't apply to us, and a natural non-jump
  two-level overcall reads as 5+ cards and 10+ HCP (`OVERCALL_2`), with
  advancer's suit bids as support (3) or a suit of their own (5) -- the
  two-suiter's reading with one suit. Over 1NT nothing changes (2♣ there is
  artificial).
  - The old misreading had been feeding `THEIR_CONTRACT_DOUBLE`: the
    overcalling side "saw" game values and doubled. `VALUES_AT_FOUR` counts
    our side bidding to the four level as values instead (deal 118: we
    competed to 4♣, their 4♠ doubled is four down). It changes nothing on
    its own.
  - Head to head, both together: **+3.42 per board, t = +3.58, 81 of 1,600
    auctions changed** (62 better, 17 worse). `OVERCALL_READ` alone +2.05
    (t = +1.73). The worst losses -- 109, 125, 235 -- are boards where the
    misread side bid 3NT on values it didn't have and the opponents then ran
    into a doubled contract.
- **After a single raise, 1M-2M** (`_game_try`, `responder_rebid`; roadmap
  3.7 and 3.8, both the user's call, 2026-10-19).
  - **Opener's splinter** (`SELF_SPLINTER`, `SELF_SPLINTER_MIN = 18`):
    1♥-2♥-3♠/4♣/4♦ and 1♠-2♠-4♣/4♦/4♥ show a singleton or void there and
    18+ HCP, game forcing; responder bids 4M. Before, a human's 1♥-2♥-3♠ read
    as a help-suit game try, the decline (3♥) was illegal, and the guard bid
    4♥ for it. Head to head (`research/gib_h2h.py SELF_SPLINTER`): **1 of
    1,600 auctions changed** (deal 116, 1♥-2♥-3♠-4♥ where opener used to bid
    4♥ directly), the same contract, so +0.00.
  - **1M-2M-3NT is a choice of games**: responder passes with three trumps and
    no singleton or void, and bids 4M with a fourth trump or a short suit.
    Robots never bid 3NT here; it answers a human opener, who used to be
    passed out in 3NT every time.
- **Why the robots miss game and slam** (2026-10-22, all 400 library deals at
  all 16 board positions, auctions only). Boards where one side can make game
  are about 191 of the ~235 points a board lost in the auction. The largest
  share, 99, is the opponents buying the hand, mostly on deals where both
  sides have a fit; stopping in a partscore is 61. Tricks follow the combined
  fit, not high cards: a fit of 7, 8, 9 and 10+ cards takes 7.0, 8.3, 9.0 and
  9.9 tricks, almost whatever the HCP, and makes game 10%, 18%, 28% and 51% of
  the time. GIB judges game on judgement points alone, so it bid game on 92%
  of 7-card fits with 26+ HCP (15% make) and 14% of 10-card fits. A void
  multiplies the slam rate by nine (15.6% against 1.7%); the slam hands average
  22 HCP. Robot 3NT makes 23%. Two switches followed, both the user's call.
- **The Law of Total Tricks in competition** (`LOTT`, `_total_tricks`,
  `_partner_length`; the user's call, 2026-10-22). When they hold the
  contract and GIB would pass (or hand off), bid our fit to the level of the
  trumps we know we hold together: 8 the two level, 9 the three, 10 the four
  (`LOTT_MAX`). Partner's length is read from their natural bids: a raise 3,
  a one-level major opening or an overcall 5, a minor opening 3, a weak two
  or a jump overcall 6, a higher pre-empt 7, a new suit 4, a rebid one more.
  Not over a doubled contract. A raise of partner's suit needs 6-9 HCP
  (`LOTT_RAISE`), GIB's free raise, so it never shares a call with GIB's
  "3+, 6+ HCP" raise on a hand that branch would not make; that also keeps
  the alert test. Deal 354: 3♥ (X) P (4♣) P (P), North with ♠A985 ♥1073 ♦962
  ♣KQ4 now bids 4♥ on ten trumps, which makes. Head to head
  (`research/gib_h2h.py LOTT`): **+3.56 per board, t = +4.49, 71 of 1,600
  auctions changed**. `LOTT_MAX` 3 measured +3.50 (t = +5.60, 50 changed);
  5 the same as 4.
  - **A weak raise with distribution** (`LOTT_SHORT`, the user's call: weaker
    raises are fine with shape). Under 6 HCP, a raise needs 3+ trumps and a
    side singleton or void. GIB's free raises in the same auctions
    (`_respond_over_interference`'s 6+, advancer's 6-9) and every LoTT raise
    with 3+ trumps now alert "3+ ♥, competitive." (`_raise_alert`), so the one
    alert is true of both. Deal 333: (1♣) 1♠ (3♣) with ♠109875 ♥J74 ♦Q1093 ♣7
    raises to 3♠ on 3 HCP, and partner competes to 4♠ over 4♣. Head to head
    against LoTT without it: **+0.27 per board, t = +1.89, 7 auctions changed**.
    LoTT with it, against neither: +3.82 (t = +4.76, 78 changed).
- **Count the fit** (`FIT_COUNT`, `_fit_bonus`; the user's call, 2026-10-22).
  Where GIB judges game once a fit is known -- opener after 1M-2M and 1M-3M,
  responder after a game try and after opener's raise, and `continuation`'s
  fit branch -- judgement points gain `FIT_POINTS` (3) for each trump the two
  hands are known to hold past `FIT_BASE` (10), lose as many for each short of
  it, and gain `VOID_POINTS` (3) for a side void with three or more trumps.
  Never in a range a call shows, so no alert changes. Head to head: **+0.83
  per board, t = +2.93, 35 of 1,600 auctions changed**. It pays by stopping
  short on known 8- and 9-card fits (deal 248: 1♣-1♠-2♠ with ♠Q985 ♥KQ9
  ♦J10965 ♣10 passes instead of bidding a 4♠ that fails). The sweep, read as
  a direction, not a fit: a base of 8, which only adds, lost **-1.5 to -2.0
  (t = -3.4 to -4.3)** at 3-6 points a trump; a base of 9 scored -0.35 to
  +0.29; 10 scored +0.23 at 6 points and +0.83 at 2-3. Promoting game on a
  *known* 9-card fit loses here, as the table above predicts (9-card fits make
  game 28%). Known lengths are minimums, which is why the base sits above the
  trick fit's ~9.7.
  - All three switches together: **+4.66 per board, t = +5.48, 113 auctions
    changed** (`FIT_COUNT` and `LOTT` alone: +4.39, t = +5.23, 106).
- **Slam bidding doesn't pay here** (2026-10-23, the 101 slam deals of
  `research/data/dd_slam.jsonl`; [SOLVER.md](SOLVER.md) for how they were
  found). The robots bid slam on 0 of their 404 auctions: the opponents buy
  the hand 40% of the time, the slam side stops in a partscore 27% and in game
  33%. Every slam convention GIB has (keycard, Gerber, splinters, quantitative
  4NT) waits for `SLAM` (33) HCP, and these hands hold 23 on a typical deal.
  But no slam rule can pay: on the 1,481 screened sides with a 9+ card fit,
  even the evaluator given BOTH hands finds no group that makes slam above
  24-38%, and a ridge model on the exact trump and side honours, the trump
  split and the shortness (fitted on half, tested on the other) has its top
  40 making 40% and its top 10 making 50%, under 1% of the sides. A small
  slam needs about 50% over game. Tricks here turn on where single cards sit
  (the trick estimate is off by 1.5-1.6 tricks), which no auction carries.
  Control cuebids would not help either: they count aces, and an ace here is
  worth about a ten. Don't reopen slam bidding without a new idea.
- **Shortness once a fit is agreed** (`SHORT_VOID_TRICKS`,
  `SHORT_SINGLETON_TRICKS`, `_with_shortness` in ai.py; the user's call,
  2026-10-23). The auctions that stop low on those deals end in the previous
  system's fallback ("No extra values."), whose count adds up cards and so
  cannot see a short suit. On the 1,481 screened sides, the best fit takes ten
  tricks this often:

  | major fit | no singleton or void | singleton | void |
  |---|---|---|---|
  | 9 cards | 21% | 46% | 73% |
  | 10 cards | 22% | 58% | 87% |

  Shortness, not fit length, makes game, which is why promoting game on a
  known 9-card fit lost (above). So where the fallback raises or rebids an
  agreed suit with three or more trumps (`_response`, `_rebid`), a void adds
  five tricks (always game) and a singleton one; only the hand's shortest side
  suit counts. Being added to the count, the void also lifts `_place`'s
  ceiling, so in competition the void hand bids on past game (deal 116: 5♥
  over their 4♠, +650 to +850). A raise of ours while they hold the
  undoubled contract now carries the LoTT alert (`_contest_alert`), since GIB's
  LoTT makes the same call in the same auctions. Deal 52: 2♥ X P 2♠ P P 3♥ P
  now 4♥, +450.
  - **Measured on 13x the library.** The 400 library deals were too few (t =
    1.7 at first). An auction can only score differently where the rule
    changes it, so 5,000 more random deals (seeds from 3,000,000) were bid
    without solving, which takes a minute, and only the 493 that any candidate
    changed were solved in full; every other board scores 0 by construction.
    One deal still solving was left out: 5,399 deals, 21,596 boards. **+2.62
    per board, t = +9.24, 1,404 auctions changed**; +22.4 on the slam deals.
  - Its bidding wars can reach slam on few high cards (seed 5, deal 33: West's
    diamond void competes to 5♥, North's singleton outbids to 6♦ on 22 HCP), so
    `test_slams_are_bid_only_on_slam_values` now allows a slam under 27 HCP
    only after an opponents' bid at the five level (the user's call).
  - Measured and left off: the void at exactly game, which leaves the ceiling
    alone, +1.72 (t = +7.15, 1,315 changed); the singleton alone +0.86
    (t = +5.05); singleton values 0.5-1.5 all
    positive on the library, 1.0 best; a singleton in GIB's own `_fit_bonus`
    changed 7-12 auctions and lost 0.2 (t = -2).
- **Game by points** (`GAME`, `GAME_MAJOR`, `NT_GAME`, `MAJOR_OVER_3NT`,
  `RESPONSE_MIN`, `LOTT_MAX`; the user's calls, 2026-10-23). Measured with
  `research/gib_fresh_h2h.py` on 3,000 fresh random deals (12,000 boards),
  solving only the contracts a change moves. The library was too small and
  pointed the wrong way: a one-level overcall on 5-6 HCP scored +1.5 to +1.8
  there (t = +2.3) and -0.8 to -1.0 on fresh deals (t = -3.2 to -3.9), and
  responding on 5 HCP +1.2 there and -0.78 (t = -4.9) fresh.
  - **3NT here makes about 13% of the time at almost any HCP** (the library's
    800 sides with 20+ HCP, best declarer), against 26% for a major game on
    an 8-card fit. GIB bids game at 25 judgement points, and every step up
    paid: 26 +1.21, 28 +3.00, 30 +3.99, 32 +4.62, 35 +5.10 a board. The
    gain is in notrump and the "values" line, not the majors: a major-game
    line of its own at 26 changed 46 auctions, +0.10. So `GAME` (3NT, a
    minor, `continuation`'s values) is 32 and `GAME_MAJOR` 26.
  - Opposite our 1NT/2NT, 32 sits one point under `SLAM` (33), and since
    judgement points skip 15 the responder would never invite or use
    Stayman: pass on 14, quantitative 4NT on 16. `NT_GAME` keeps that
    structure at 28 and scores the same (+6.78 against +6.81).
  - **A major game, not 3NT** (`_major_over_notrump`): instead of bidding
    3NT, or passing partner's 3NT, bid 4M when this hand's length and what
    partner's bids have shown (`_partner_length`; a natural notrump bid two;
    a completed transfer nothing) make eight. A fit both have bid is left
    alone (1M-2M-3NT, roadmap 3.7). Mostly 1M-2x-2M-3NT, where the rebid
    shows six: fresh deal 1237, ♠AJ86543 ♥AQ98 ♦A ♣2 opposite ♠K7 ♥KJ74 ♦J8
    ♣AK763, 3NT took 2 tricks and 4♠ takes 10. **+1.72 a board, t = +11.6,
    410 of 23,828 boards** (5,957 deals); a 9-card line +0.46, not counting
    notrump +0.77. The library alone: 17 auctions, -0.05.
  - Responding at 7 HCP, not 6: +0.52 (t = +2.7). Law of Total Tricks to the
    five level with 11 trumps: +0.19 (t = +2.4).
  - Measured and left off: never bidding 3NT at all, +0.7 to +1.4 on the
    library (t < 1; the 3NTs that make pay too much); an overcall at 10+ HCP
    +0.12 (t = +0.5); a takeout double at 14+ +0.03.
  - All of it together, against the robots before: **+6.78 a board,
    t = +14.6, 2,220 of 12,000 boards changed**. Game-or-higher contracts
    fall from 36% of boards to 28% (500 fresh deals).
  - **The jack counts 1 judgement point** (`Hand.judge`, the user's call): it
    counted 0, rounded from a 100-deal fit that lumped it with the 8 down to
    the 5; the 400-deal fit below has J +0.23 tricks, level with the 10
    (+0.20) and 9 (+0.20) and above the ace (+0.08). With it K=Q=3,
    A=J=10=9=1 is 40 a deck, so no rescaling. Against the robots above:
    **+1.17 a board, t = +4.5, 516 auctions changed** (3,000 fresh deals).
    With it, 3NT at 34 +1.27 (inside the noise of the same line), at 30
    +0.45, majors at 27 +0.89; a jack worth 2 +0.79.
- **Penalty doubles** (`ai.PENALTY_DOUBLE`, `PENALTY_JUDGE`; the user's rule,
  2026-10-24). Against **two-sided par** (both sides bid perfectly, a failing
  contract is doubled, either side may sacrifice) the robots are 233 points a
  board off over the library's 6,400 boards, about the one-sided 242, and 60%
  of it is in auctions both sides bid. The robots almost never doubled for
  penalty: 2,960 of 6,356 contracts fail double dummy and 28 were doubled;
  1,600 went two or more down undoubled. Doubling every failing contract
  with perfect knowledge would be worth ~117 a board, so head to head had
  been paying for overbidding nobody punished.
  - The rule: where the robot would pass an opponents' natural suit bid
    (not one alerted "Artificial") and the system gives X no other meaning
    there, double with 5+ trumps, or 4+ at the three level or higher, when
    my judgement points plus the middle of the range partner's alerts show
    reach 20. An open range ("8+ HCP") counts
    as seven wide; no range as a third of the points I don't hold. The
    alert, "Penalty: 5+ ♥." (4+ at the three level), depends only on the
    auction. Partner passes it ("Partner's penalty double stands").
  - The bidder reads partner's alerts, so `ai_bid_explained` takes the
    robots' alerts by call index (`alerts`); left out, it uses what it said
    on the same auction object (`_robot_alerts`). A person's self-alert is
    not read.
  - A side doubled for penalty never bids its own strain higher: the
    branches that raise a fit ran 4♦X up to 7♦X (`_penalty_or_base`).
  - **Only where X is free** (`_double_is_free`). Where X is takeout,
    negative, responsive or another penalty, a penalty double for some hands
    gives one call two meanings, which breaks the alert rule (REQUIREMENTS
    B4; `test_a_bid_alert_depends_only_on_the_auction_and_the_call` caught
    1D-X "Penalty: 5+ ♦" against "Takeout: 12+ HCP"). Whether X is free is
    asked the bidding box's way: up to `meanings.SAMPLE_HANDS` hands sampled
    from a generator seeded by the auction, with the penalty double off; one
    X is enough. No global RNG, so the guardrail on determinism holds; the
    answer is cached per auction. Of the +7.30 measured without it, +3.83
    came where X was free, +3.04 where it was takeout (mostly a one-level
    opening with five trumps behind it) and +0.29 negative. The trap pass
    and partner's reopening double passed for penalty would be the standard
    way to get some of the rest.
  - On the library's final contracts with exact points, first: 4+ trumps
    and 20+ +8.2 a board, 5+ +5.3 (112 failed, 4 made); trumps alone +0.4,
    points alone -40. Then in the auction, 3,000 fresh deals: **+4.09 a
    board, t = +7.4, 750 auctions changed** (504 better, 192 worse). Where X
    is also takeout or negative, +7.30 (off, above); before the doubled side
    stopped raising, +10.95: the incumbent's runouts were part of that. The
    robots don't run from a penalty double; a person might.
- **A cuebid raise shows support to the LoTT** (`CUE_RAISE_FIT`, the user's
  deal 338): 1♦ 1♠ X 2♦ (3+ ♠, 10+) - 2♠ 3♥ was passed out with ten spades,
  because `_partner_length` and `_total_tricks` read only natural bids and
  South, at 10 HCP, was over the competitive raise's 6-9. Now a bid in their
  suit after partner's suit counts 3+ in it, both ways. 3,000 fresh deals:
  **+0.24, t = +2.9, 61 auctions changed** (47 better, 14 worse).
- **Ten trumps jam to game at once** (`JAM_GAME`, `_jam_spot`, `_jam_game`,
  `_after_jam`; the user's Challenge deal, 2026-10-28: 2♠ (X) with ♠A10652
  ♥853 ♦J8 ♣Q96 passed, bid 4♠ and 5♠ a round late, and E/W made 6♥).
  When partner's opening is our side's only bid, my first call is game in it
  if my length and partner's shown length make ten (`JAM_FIT`): over any
  call of theirs after a one-, two- or three-level opening, and over a pass
  too after a pre-empt (`JAM_OPENINGS`, `JAM_OVER_BIDS`, `JAM_UNCONTESTED`).
  Five of a minor too (`JAM_MINORS`); the no-runaway test lets a jammed
  five-level contract through. The pre-empter passes over their next bid
  (else 3♦ X 5♦ went on to 6♦ and 7♦); after that both partners compete as
  usual (the user's choice; `JAM_NEVER_AGAIN` makes both pass for good). A
  penalty double outranks the jam. Every game bid in the jam seat, whichever
  branch bids it, alerts "Game in ♥: to make or to jam the auction." 10,000
  fresh deals (`research/gib_fresh_h2h.py`), with the raise below: **+1.50 a
  board, t = +10.6, 1,156 auctions changed** (515 better, 345 worse). The
  user's exact case alone (weak two doubled) +0.04, t = +1.9, 26 auctions;
  over overcalls and three-level pre-empts too +0.26; with one-level majors
  +0.74; majors only +1.22; with `JAM_NEVER_AGAIN` +1.38 (majors only +1.11).
- **A major raise counts trump length** (`RAISE_TRUMP_POINTS`, the user's
  deal: 1♥ with ♠K5 ♥K9864 ♦K84 ♣832 raised to 2♥). With four or more
  trumps and under 13 HCP, 2M, 3M or 4M is chosen on HCP plus one point a
  trump past three; that hand is now a 3♥ limit raise, declined. The raise
  alerts drop their HCP ranges ("3+ ♥. Single raise.", "4+ ♥. Limit
  raise."), which a hand counting length would not keep. Alone: **+0.13,
  t = +2.9, 215 auctions changed**. 4M on any five trumps instead: 0.00.

## The previous system (`ai.USE_GIB = False`)

- **Everything in this section about `ai_bid` describes the
  PREVIOUS system** (`ai.USE_GIB = False`), which still answers the contested
  situations GIB's notes do not cover. Its rules -- never bid notrump, never
  cuebid, 2/1 forcing one round, game only in a major -- are NOT the robots'
  default any more; GIB's are (see `gib.py` above). The measurements below
  remain true, and are why GIB scores worse here.
- `ai.py`'s hand evaluation and bidding thresholds are **fitted, not hand-written**.
  `eval_hand_sh` returns EXPECTED TRICKS (trump card +1.025, K or Q +0.281, A/10/9
  +0.117, J/8/7/6/5 -0.094, 4/3/2 -0.199, plus `LENGTH_BONUS` 0.25 for each trump
  past the fourth in one hand) and every threshold in `ai_bid` is in
  that same unit, so each can be compared directly against solved results. See
  "Hand evaluation and bidding" below for the fits. `OPEN_TRICKS` is the one
  constant not fitted from double dummy results -- the dataset holds no auctions --
  so it was calibrated by simulation instead: auctions over the 100 solved deals,
  contracts scored, thresholds swept. 4.5 won at **+88.9 per board against the old
  `ai_bid`'s -1.5**. `tests/test_bidding_calibration.py` guards the findings the
  calibration rests on, not exact frequencies a bigger dataset will move.
- `ai_bid` runs a **2/1-shaped auction**: a new suit at the two level shows real
  values and asks partner to describe again, a jump raise shows support with extra,
  a simple raise is limited. Two things are deliberately NOT borrowed from real 2/1,
  both measured:
  - **It is forcing for one round, not to game.** Standard 2/1 is game-forcing
    because in real bridge game is usually right. Here 4M is makeable 21% and twelve
    tricks 1.3%, so committing to game loses: driving to game measured **-14 to -20
    points per board**.
  - **Promises are differentiated but CONSERVATIVE.** What each action really holds
    was measured (opened 4.66, 2/1 5.66, simple raise 3.56, jump raise 4.67 at the
    10th percentile), and feeding those true values in scored **-16.0, t = -2.55**
    against a flat promise. Accurate promises bid *worse*, because the loss function
    is asymmetric: with +/-1.14 tricks of estimate error, bidding at true capability
    overshoots half the time, and overtricks score the same as contracted tricks so
    undershooting is nearly free. Every promise is therefore shifted down by
    `PROMISE_SHIFT = 1.5`, which keeps the ordering (partner's bid still means
    something) while restoring the conservatism. Net cost of the whole structure:
    **-0.5 points per board, t = -0.09, not distinguishable.** Do not "correct" the
    promises upward to their measured values.
  - A first attempt that let the contract floor follow partner's level upward
    escalated badly — 2-level contracts collapsed from 211 to 125 and the score fell
    14 points. `_place` therefore always floors at `PARTSCORE_LEVEL`, never at
    partner's level, and every describing call goes through it.
  - **A SIMPLE RAISE at the partscore level is never vetoed by the level cap**
    (`max(ceiling, PARTSCORE_LEVEL)` in `_place`). Because the ceiling is
    computed from a deliberately conservative partner promise, it was
    suppressing the most routine bid in bridge: on board 146 South held
    four-card support and 10 points opposite an opening, scored the partnership
    at 7.63 against a true 10.57, and **passed**. Head to head this is
    **+4.0 per board, t = +2.19, 42 of 300 deals moved** — the largest single
    gain in the file. It does not reopen the escalation above: only level 2 is
    admitted, so a 3-level call still has to clear the ceiling on its own. This
    also flipped the whole card incorporation from -3.3 to **+1.7** head to head
    against the pre-card AI.
- **TWO METRICS, AND THE DIFFERENCE MATTERS. Read this before quoting any
  competitive number.** `research/hand_value.py` scores a board
  from the **declaring side**: "given that somebody bought this contract, how did
  they do". That is the right question for *is this contract any good* and it is
  the metric every figure elsewhere in this section uses. It is the **wrong**
  question for any decision made while competing or defending, for two reasons:
  - a board where the opponents blunder into a doubled contract and make it
    counts as a large *positive*, because the metric grades whoever declared;
  - a passed-out board scores 0, so a tighter opening floor looks like a loss
    simply for passing more boards out.

  The fair test seats the variant against the incumbent — variant at N/S,
  incumbent at E/W, then the seats swapped — and scores from the **variant's own
  side**, so the baseline is 0 by construction and the number is a head-to-head
  margin. Four claims were re-measured this way and every magnitude shrank by
  roughly 4x, with two changing **sign**:

  | change | declaring-side | head-to-head |
  |---|---|---|
  | takeout double, alone | +9.8 (t = +2.13) | **+2.2 (t = +1.75)** |
  | cuebid turned on | -16.4 (t = -3.34) | **-4.1 (t = -2.66)** |
  | opening at the card's 12+ | -11.6 (t = -3.34) | **-0.2 (t = -0.14)** |
  | always answer a takeout double | -3.3 (t = -1.68) | **+2.1 (t = +1.65)** |

  Do not quote a declaring-side figure for a competitive decision.

- **The UMD Duplicate Bridge Club system card is the reference for structure and
  vocabulary**, and after the re-measurement above it is followed *exactly* on
  every point this variant can use — there is no longer a house deviation on the
  opening. Net effect of the whole incorporation, head to head against the
  pre-card AI: **+13.3, t = +3.92, 153 of 300 deals moved** — significant, so
  the card is not merely free here, it is better. THREE competitive fixes
  carried it there, all three found by a user reading auctions rather than by
  any sweep: the simple raise no longer vetoed by the level cap (+4.0), the
  free bid in competition (+3.6), and the lone rebid no longer clamped to the
  partscore (+3.6). Before them the same comparison read -3.3. The lesson is
  worth keeping: every one of those was a hand that **could not make a bid at
  all**, and none showed up as a tuning problem — constant sweeps had been
  exhausted while three whole branches were missing. A fourth change,
  `LENGTH_BONUS`, added +3.7 on top; it is the only one of the four that is a
  constant rather than a branch, and the only one that does NOT improve the
  evaluation (see below).

- **`LENGTH_BONUS = 0.25` per trump past the fourth, and what it is honestly
  worth.** A user proposed that 7- and 8-card suits were under-valued. Tested
  directly over 2378 solved cases, that claim is **false**: per-hand residuals
  are +0.06 tricks at six cards (t = +0.59) and -0.04 at seven (t = -0.23),
  i.e. flat. The real prediction bias is on **combined partnership** length —
  7 trumps too low by 0.33 (t = +5.56), 8 by 0.45 (t = +6.33), 11 too HIGH by
  1.06 (t = -2.69) — which a bidder cannot observe at the table. Board 106
  settles it: both sides hold an eleven-card fit there and the model is 1.60
  too LOW for N/S in clubs and 2.53 too HIGH for E/W in diamonds, same deal,
  same length, opposite errors.
  A per-card length bonus nevertheless scores well, and the direction survives
  a split-half check (positive on both halves at every floor of 3, 4 or 5).
  **But it does not work by predicting better — it works by outbidding**, and
  the self-play column falls the whole way up the plateau:

  | bonus | head-to-head | 3-level+ | 5-level+ | made | self-play |
  |---|---|---|---|---|---|
  | 0.00 | — | 63 | 1 | 67% | +57.1 |
  | **0.25 (shipped)** | **+5.8 (t = +2.40)** | 91 | 4 | 65% | +56.3 |
  | 0.25 + `GAME_TRICKS` 10.0 | (same, -0.0) | — | — | 66% | **+57.2** |
  | 0.50 | +12.9 (t = +4.01) | 117 | 10 | 63% | +55.9 |
  | 0.75 | +14.3 (t = +3.75) | — | — | — | — |

  Shipped at the conservative end **deliberately**: it is an edge against a
  timid opponent bought with accuracy, not a better evaluation, and the larger
  settings break the level discipline that the rest of this section rests on.
  Raising it needs new evidence, not a bigger sweep.
  It also forced `GAME_TRICKS` up from 9.5 to 10.0 (see above). That is the
  general hazard with this constant: it shifts the whole trick scale, so every
  threshold expressed in tricks has to be re-checked against it, not just the
  score.
  - **Points are counted the card's way: high cards + length points (one per card
    past the fourth in a suit), minus one for a flat 4-3-3-3.** `_points` returns
    this, not raw HCP, and every threshold and alert is denominated in it. This
    was mostly a language fix: the system looked far lighter than it was, because
    its median opening is 11 raw HCP but **exactly 12 guide points**. Shortness
    points (void 5, singleton 3, doubleton 1) are in `_dist_points`, valid only
    opposite a known fit as the card requires.
  - **Opening is the card's 12+.** This was briefly shipped at 10+ on a
    declaring-side reading of -11.6 (t = -3.34); head to head the card's own
    floor costs **-0.2 (t = -0.14)**, i.e. nothing. The earlier figure was almost
    entirely the pass-out artifact described above (35 boards passed out against
    10, each scoring 0 for that metric). The gate is enforced, so the alert
    quotes 12+ truthfully.
  - **Adopted and free** (each measured, none detectable): the card's better-minor
    rule (longer minor; 1♣ when both are three, 1♦ when both are four); pre-empts
    at its lengths (six cards at the two level, seven at the three, 6-10 points);
    level-differentiated overcalls (8+ at the one level, 10+ at the two); a 6+
    floor for a one-level response and for a simple raise (both **0 of 299 deals
    changed** — no-ops that make the alerts true); and a 10+ floor on the jump
    raise (also **0 of 299**, because the trick threshold beside it already
    implied 10+).
  - **No pre-empt in fourth seat** (a user caught a weak 2♠ after three
    passes). There a two-level opening shows 11-15 points and six cards, as in
    standard bridge. Head to head over 289 deals x 4 dealers: +0.22 per board,
    t = +1.07, 13 contracts moved — rare, so not detectable, but never worse.
  - **The takeout double is the biggest single win in the file: +2.2 per board
    head to head, t = +1.75** (+9.8 on the inflated declaring-side metric).
    The card's conditions exactly — 12+ points (14+ over a two-level
    opening), two or fewer cards in their suit, three or more in every other. It
    pays for every other change here. Before it, a 15-point hand with no
    five-card suit simply passed: there was no call for "values but no suit", so
    the whole class went unbid. Advancing it is compulsory — leaving a takeout
    double in converts it to a *penalty* double, a different call — so
    `_advance_double` answers **at any level**, including above the usual
    ceiling when partner's double of a weak two leaves only a three-level reply.
    An earlier version passed when too weak to reply cheaply; on deal 212 that
    left a takeout double in as penalty and handed the opponents 2S doubled and
    making, worth 570. Always answering is **+2.1 head to head (t = +1.65)**,
    where the declaring-side metric scored it -3.3 — precisely because that
    metric counts the opponents' 570 as a success.
  - **`ai_bid` does NOT cuebid, and this was measured, not assumed:
    -4.1 per board head to head, t = -2.66** (-16.4 on the declaring-side
    metric), pushing contracts at the 3-level or higher from 17 to 25. Advancer bidding the opponents' suit on 11+ with support loses for
    the same reason game-forcing 2/1 loses here — showing extra values buys
    height, and an undoubled overtrick scores what a contracted trick scores. The
    **reading** is kept (`_is_cuebid`, and both rebid branches), so a human South
    who cuebids is understood by robot North rather than being raised in the
    opponents' suit. Do not re-enable the call without new evidence.
  - **Declined as inapplicable, not as unfinished work:** every notrump
    convention on the card (1NT and 2NT openings, Stayman, Jacoby transfers, 1NT
    forcing, Gerber) is moot because notrump is never bid, and the slam machinery
    (1430 RKCB, strong 2♣) is moot because twelve tricks occur on 1.3% of deals —
    the card itself marks most of those rows "Ask for help!".
  - **A two-over-one is ONLY a suit ranking below opener's** (`_is_two_over_one`).
    That is what forces it to the two level; a higher-ranking suit is available
    at the one level, so bidding it at the two is a **jump shift** — a different
    call, and a level of room thrown away. The AI bid `1D - 2S` alerted as
    "Forcing" until a user caught it, because the old code tried the two level
    first and never compared ranks. So `1S-2H`, `1S-2D`, `1S-2C`, `1H-2D`,
    `1H-2C` and `1D-2C` are two-over-ones; `1D-2S`, `1D-2H` and `1C-2D` are not,
    and **over 1C there is no two-over-one at all**, since every other suit can
    be bid at the one level. `tests/test_bidding_rebids.py` pins both the rank
    table and a whole-auction guard that nothing alerted "Forcing" is a jump
    shift.
  - **A FREE BID of a long suit in competition** (`FREE_BID_LENGTH = 6`,
    `FREE_BID_POINTS = 8`). Partner opens, an opponent overcalls, and the
    one-level response is gone; the only two-level route was the two-over-one,
    which wants 12 points and — over 1C, by the rank rule — does not exist at
    all. So the hand **passed**, and the pass alerted "no five-card suit". A
    user found it on two boards: board 2's North passed holding **eight**
    diamonds, board 109's East holding six; across 300 deals that alert was
    false **141 times**, the worst being a nine-card suit with 16 points.
    A two-level call here is NOT a two-over-one — the overcall removed the cheap
    response, so it shows a suit, not game values; the card's 2/1 rows are for
    uncontested auctions. Head to head **+3.6 per board, t = +2.36** at 6+/8+.
    Swept: 5+/6+ gave +3.5 (t = +1.94), 6+/6+ +3.4 (t = +2.23), 7+/6+ only +0.3.
    Board 109 now reaches 4S for +420, the best contract on the deal, where it
    used to creep to 2S for +170 — but board 106 shows the cost, where East's
    2D steals the board from a North hand that takes all thirteen tricks.
  - **No alert may deny a suit the hand is holding.** The two bugs above were
    both *reported as alert bugs* and turned out to be missing branches. The
    overcall pass now says "no five-card suit **outside theirs**", which is a
    different and true claim (`best_suit` there excludes suits the opponents
    bid, so a hand whose only long suit is theirs reaches it).
    `test_no_alert_denies_a_suit_the_hand_is_holding` checks both forms against
    the hand, and is the prose counterpart to the numeric alert test.
  - **Two more bugs the card's own structure exposed, both fixed.** A hand that had
    opened and whose partner then passed fell through every branch into the
    *overcall* code: it re-bid its own suit alerted as "Overcall", and where the
    opponents had only doubled (a double is not a bid, so `opponents_bid` was
    False) it reached the *opening* branch and passed with "No suit worth opening"
    having opened that suit two calls earlier. `_rebid_alone` now handles it, on
    the card's minimum-rebid tier (12-15 points with five cards, or six cards on
    any strength) — which measured best of five bars tried, at +1.2 against
    never rebidding alone's -3.3. **Its level is decided by the ceiling, not by
    a clamp to the partscore.** The original clamp (`min(ceiling,
    PARTSCORE_LEVEL)`) meant a lone rebid could never go above the two level,
    so once the opponents competed to 2-something the hand was silenced no
    matter what it held: on board 106 North sat on eight clubs to the KQJ and a
    void — N/S take all thirteen tricks in clubs and E/W none — with its own
    estimate reading 11.37 tricks, and passed. Removing the clamp is
    **+3.6 per board, t = +2.92, 26 of 300 deals**; capping at 3 instead
    measured identically, because the ceiling never exceeds 3 in practice.
    Separately, the overcall branch could name a
    suit **the opponents had bid** (over 1♥, a hand with five hearts and 18 points
    "overcalled" 2♥); excluding their suits gained ~3 points and removed a call
    partner could not distinguish from a cuebid.
- `ai_bid` **never bids notrump**, and caps every raise at `int(combined estimate)
  - 6`, the highest level the fit is expected to make. Without that cap `_cheapest`
  climbs to whatever is legal: in a contested auction "raise to the 2-level" finds
  no legal 2-bid and walks up to the SEVEN level, which put 14 of 40 smoke-test
  contracts there before it was caught. Game is four of a major and nothing else --
  `_game_call` returns None for a minor, because 5m needs eleven tricks (makeable
  11%) and 3NT nine (10%), both worse than simply playing the partscore. The
  resulting contracts: 0% notrump, 0% above the 5-level, 67% at the 1- or 2-level
  (was 76% before `LENGTH_BONUS`; see below for the discipline that bought).
  `tests/test_bidding_rebids.py` pins the level discipline and the 7-level
  regression; the older re-raise cascade it was written for is pinned there too.

## Hand evaluation and bidding research

Fitted from `research/data/dd_pilot.jsonl`, now **complete at 400 deals / 2000 solve
pairs / 4000 declarer-solves**, every deal carrying all five strains (deals 301-400
were added with `--extra-fits 3 --engine rust` in 46 minutes, which also filled the
11 older deals that had been missing strains). Regenerate with
`python research/hand_value.py`. Figures were first taken at 100 deals x 3 strains;
where the larger sample moved them, both are given, because the movement is the lesson.

**Read this before tuning any constant.** Paired across identical deals, the per-deal
score difference has SD 45, so the smallest detectable effect is about 5.2 points per
board at 300 deals, 4.5 at 400, 4.1 at 500, 2.9 at 1000. A power calculation made at 153 deals
predicted `GAME_TRICKS` would need ~306 deals to resolve and the coefficient choice
~492; at 300 deals both predictions held exactly. Current state:

- **`GAME_TRICKS = 10.0`, raised from 9.5 when `LENGTH_BONUS` was added.** The
  older sweep (+77.4 at 9.5 against +75.4 at 9.0, +73.0 at 10.0, +72.2 at 10.5)
  was run when a trump card was worth a flat 1.025. The length bonus adds up to
  ~1.5 tricks to a long-suit partnership's combined count, so 9.5 began firing on
  hands with no game values at all — a seven-card suit with **six points** bid 4S
  and went three down. At 10.0 the head-to-head difference against 9.5 is
  **-0.0 (t = -0.04)**, while game contracts fall 27 → 20, the make rate rises
  65% → 66%, and the declaring-side score recovers +56.3 → +57.2, just above the
  +57.1 it had before the bonus. Turning game off entirely cost **-5.3,
  t = -1.98** in the original sweep. **Do not restore 9.5 without also removing
  the length bonus** — the two constants are on the same scale and move together.
- **The coefficient choice is genuinely immaterial, not merely unresolved.** A refit on
  the full 300 deals scores -0.6 against the shipped set (t = -0.25) while changing the
  contract on 24 deals; the gap *shrank* from -2.1 at 153 deals. Leave them alone.

Do not "improve" these constants against an unpaired mean; that is fitting noise.

- **`eval_hand_sh` has no predictive power.** Against real double dummy tricks it
  scores r = -0.035 (R^2 = 0.001), and r = -0.138 in notrump — slightly *negative*.
  Standard HCP is barely better (R^2 = 0.020). It ranks A+K (+4.0) and A-K-Q (+5.5)
  highest, which are close to the worst holdings in this variant. This needs
  replacing outright, not retuning.
- **Trump length is the dominant term**: +1.029 tricks per combined trump card
  (t = 33) in the full rank model, +1.025 in the reduced point count below. Fit
  length alone gives R^2 = 0.700 — worth about 3x a queen, per card.
- **The honour hierarchy is inverted at the top** (suit contracts, n=400): Q +0.352,
  K +0.343, A +0.186 — the ace is not significant (se 0.111, t = 1.69) and sits
  *below* the ten's +0.194. The ace belongs with the tens: it can never win a
  contested trick, so it only scores as the sole card of the winning suit.
- **The fitted point count** (per card, summed over the partnership's 26 cards;
  additive per hand, so each player counts their own and partner adds):
  trump card +1.025, K or Q +0.281, A/10/9 +0.117, J/8/7/6/5 -0.094, 4/3/2 -0.199,
  intercept ~0. In-sample R^2 0.746, out-of-sample 0.740 at 100 deals. **That R^2 is
  population-dependent and was flattering.** It was measured over a set mixing each
  side's best fit with contracts the AI never bids, and the extra spread in trump
  length inflates it. Refit on the population the AI actually bids — its own best fit,
  declaring — the same model explains only **R^2 0.362 (out-of-sample 0.348)**. The
  count is well calibrated there (bias -0.06 tricks, r = +0.704, MAE 1.07 with both
  hands known); it just explains less of a narrower range. Quote R^2 with its
  population attached.
- **Notrump is almost never right — but "never" was a small-sample artifact.** At 100
  deals the suit won 91%, tied 9% and lost **0 of 172**. At 300 deals it wins 89%, ties
  10% and **loses 7 of 600 (1%)**, and at 400 deals 9 of 800 (1%) — so 1% is the stable rate, and the original zero was
  an artifact. The conclusion (do not bid it) is untouched; the
  absolute claim was wrong, and is just the kind of zero a larger sample kills. Mean gap -2.65
  tricks, widening to -3.62 on 9+ card fits. NT tricks are also near-unpredictable
  (R^2 = 0.169 with all 13 rank counts; best single correlate is queens, r = +0.243).
  Don't "improve" the notrump evaluation — the fix is to stop bidding notrump.
  A viable niche was searched for and does not exist. Tried: balanced hands, 24+ and
  26+ HCP, 7-card (the worst possible) fits, minor-only fits, and notrump at the 1-
  and 2-levels as a cheap partscore. Compared at the SAME level the suit wins every
  subset; on 7-card fits the suit beat notrump in tricks 4/9, tied 5/9, lost 0/9.
  Beware the trap that caught a first pass here: 1NT appeared to beat "2 of our fit"
  on 7-card fits, but that compares different levels — the real finding was "don't bid
  2 on a 4-3 fit". Notrump's scoring premium (40 for the first trick against 30/20)
  is worth 10-20 points; its trick deficit averages 2.65, worth far more.
  Prediction fails too: notrump tricks reach only R^2 = 0.229 using all 13 rank
  counts plus shape and mechanism features. A "bid 3NT when the model predicts it"
  policy loses at every threshold, and where the model is most confident 0% of those
  contracts made — worse than the 10% base rate. Mechanism features (cards an
  opponent holds a higher card in; cards that top their suit outright) explained
  R^2 = 0.003. That hypothesis is dead; don't revive it without new evidence.
- **Undoubled overtricks score the same as contracted tricks**, so underbidding is
  nearly free and the only prize for a higher contract is the game bonus. Game is
  rare: 4M makeable 28%, 5m 11%, 3NT 10%. Mean score per board: always-2-of-our-fit
  +81.6 (made 75%), the recommended policy (2 of our fit, 4M when the count reaches
  9.5) +86.0 (made 71%), fit-6 capped at 3 +65.8, always 3NT -114.8, oracle +175.1.
- **Scores, old against new `ai_bid`.** The pre-rewrite version scored **-1.5 per
  board**: 40% notrump contracts, 74% at the 3-level or higher, 48% in the side's own
  longest fit. The rewrite scores **+79.6 per board over the full 300 deals**, with 291
  of 292 contracts scorable: 0% notrump, 8% at the 3-level or higher, 80% in the side's
  own longest fit, 74% made. Two earlier figures are superseded: **+88.9** (100 deals,
  only 80 of 96 scorable) and **+66.3** (153 deals). Coverage is what moved them — the
  extra strains exposed contracts that could not previously be scored.
- **Fit-finding is not the hard part.** If each partner shows only their longest
  suit, a natural auction reaches the true best combined fit 94% of the time (mean
  loss 0.08 cards); showing every 4+ suit reaches it 100%.
- **Bid game only in a major**, when the count predicts >= 9.5 tricks: 4M scores
  +202 there against +157 for 2M. Never 5-of-a-minor.
- Deals are genuinely competitive: both sides' tricks in their own best fits sum to
  17.23 on average (not 13), and both sides can take 7+ tricks in 81% of deals. A
  flat 1-level policy scores best in isolation (+105) but is not actually available.

- **Where the remaining points are, and why most are out of reach.** The gap to an
  oracle bidding exactly what makes is 121 points per board: 68% level error, 32%
  strain error. The level error is dominated by missed slams — 26 contracts wanted a
  level 2+ higher, the worst being 2D taking 11 tricks where 6H scores +980 against
  +150. **This is not a fixable bidding-logic gap.** On every deal where 12 tricks were
  available, even the TRUE combined count with both hands known justified only level
  3-5, because the count's MAE is 1.07 tricks and slams need precision at the very top
  of the range. Bidding at the ceiling instead of the cheapest raise was tried and
  measured: 5 deals changed, 4 got worse (paired t = -1.41).
- **The level policy is already near its ceiling given this evaluation.** The AI bids a
  mean level of 1.90; the true combined count justifies 1.87. What it cannot see is the
  2.49 that actual tricks justify — that needs a better evaluation, not better rules.
- **The evaluator is at the information ceiling of card counting. This avenue is
  closed — do not reopen it without a new idea, not just new features.** Searched with
  `research/evaluator_search.py` and follow-ups over 2378 suit solves, 5-fold
  cross-validated and grouped by deal:
  - shipped 5-term model: **OOS MAE 1.144**
  - splitting honours by trump/side, adding voids, singletons, doubletons, longest
    side suit — every combination: **1.138 to 1.154**, i.e. nothing
  - all 13 ranks x trump/side (26 terms): **1.146**, no better than five
  - squares and all pairwise interactions: **1.145**, no better
  - non-additive joint partnership structure (top-k trumps held, trump split between
    the hands, combined side shape): **1.219, worse alone**, and 39 terms combining
    everything reach only **1.143**. So the per-hand additivity constraint that makes
    the count usable in an auction costs essentially nothing.
  - The one real gain is that **trump length is not linear**: free dummies per length
    give MAE **1.110**. The linear term over-credits long fits badly — at 11 trumps it
    predicts 11.49 tricks against an actual 9.94, because with 11 of 13 trumps the
    opponents hold two and extra trumps stop converting under the second-highest rule.
    Implemented as a correction inside the auction it changed 7 deals of 299, was worse
    on 4, **t = -0.83**. Real in MAE, invisible in score. Not shipped.
  - **Why it cannot go further:** feature vectors that occur more than once differ by
    **0.754 tricks** on average, because the other 26 cards decide the rest and a
    bidder never sees them. Double dummy tricks come from a search over play, not a
    formula, and no count of one partnership's cards can cross that floor.
- **What the remaining ~80 points/board would actually need.** Simulating an evaluator
  with error sigma and bidding `level = round(estimate) - 6` scores +158 per board at
  sigma 0 against ~+68 at today's accuracy — so accuracy is worth 10-20x any rule
  change (all of which measured within +/-5 and none significant). But a perfect
  evaluator with that trivial policy reaches +157.6 against the oracle's +159.3, which
  says the *policy* is finished and only the *evaluation* is short. Since the
  evaluation is at its informational ceiling, the only avenue left is **search at bid
  time** (single-dummy sampling through `bridge/solver`), which is not bound by the
  0.754 floor. Cost is the obstacle: a full-deal solve is 9s even in Rust, so ~100
  samples is ~15 minutes per bid. Viable only for a few mid-play decisions, not an
  auction.
- **A partner who has PASSED is still modelled as one who bid.** `_rebid_alone`
  values a silent partner at `PROMISE_RESPONDED_1` (2.89), which is what a partner
  who actually responded promises; a pass denies values, so the true figure is
  lower. The effect is masked rather than harmful — the level cap fires first, so
  the AI passes anyway where it matters (deal 4: 15 points and five spades,
  combined 7.97, ceiling 1) — and correcting it downward would only make the AI
  more conservative. Worth a measurement if the partner model is revisited.
- The AI's combined estimate (own hand + the `PROMISE_*` constants (`PROMISE_SHIFT`, `PROMISE_OPENED`, ...)) runs **+1.8 tricks high**
  and correlates only r = +0.20 with actual tricks, against r = +0.70 for the true
  count. A better partner model is the most promising open lead, but nothing at n=153
  can be validated against the noise floor.

Known-thin evidence, worst first — treat these as provisional:
- Most tuning is now **below the noise floor** (see the warning at the top of this
  section). Further constant-fiddling needs a much larger dataset, not more cleverness.
- The **game trigger still fires rarely in live auctions** (it changes only 7 deals in
  300 against never bidding game), which is why proving it needs so many boards. The
  policy analysis, which sees the true combined count rather than the auction's
  estimate, puts game clearly ahead at count >= 9.5 (n=55, +182.5 against +157.8) and
  clearly behind at >= 9.0 (+142.4 against +150.4). 9.5 is the right edge.
  **At 400 deals the 9.0 row flipped**: +154.1 against +150.8 (n=131), a 3.3-point
  game lead, while 9.5 kept its lead but narrowed to +170.4 against +154.7 (n=81).
  A 3-point swing on ~130 boards is well inside the noise floor, so this is "the
  edge sits somewhere in 9.0-9.5", not evidence to move it — and `GAME_TRICKS`
  is 10.0 in the live auction anyway because of `LENGTH_BONUS`.
- The **ace's estimate has wandered with sample size** — +0.186 (t=1.69, not
  significant) at 100 deals, +0.221 (t=3.51) at 153, +0.097 (t=2.47) at 300, **+0.080 (t=2.32) at 400**.
  At 300 deals it is significantly positive but the *smallest* of the top six ranks,
  sitting below the ten (+0.210), the jack (+0.184) and the nine (+0.172) — a stronger
  form of the original finding, not a weaker one. K (+0.418) and Q (+0.398) carry the
  hand. At 400 the ordering holds: K +0.438, Q +0.365, J +0.225, 10 +0.203,
  9 +0.202, and the 8 (+0.123, t=3.37) has now also overtaken the ace. This wandering is why `hand_value.py` prints live t-statistics rather than a
  hard-coded verdict.
- Deals with 12+ tricks remain rare (4 of 153).
