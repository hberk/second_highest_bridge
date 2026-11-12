# Changelog

Releases are tagged on main, and the tag matches the version in
`frontend/package.json` and `server/package.json` (`v0.1.0-alpha` is
0.1.0-alpha). Until 1.0 the robots' bidding and play change from release to release; every change and
what it was measured to be worth is in
[docs/ROBOT_PROGRESS.md](docs/ROBOT_PROGRESS.md).

## v0.1.5-alpha (unreleased)

Four fixes from the Nov 11 robot review.

- A robot about to bid 3NT "to play" on a known eight-card fit bids the fit
  instead, at the same level or one lower (+0.16 a board, three seeds).
- Five bidding logic bugs: Cappelletti only directly over 1NT; six of the
  major after a transfer no longer says "5"; opener passes 1NT 2♦ 2♥ (X) P P;
  the Lebensohl 2NT relay after a runout is answered; a transfer doubled after
  our 1NT overcall is completed or bid by responder.
- A defender doesn't lead for partner's ruff when declarer's bidding accounts
  for every trump left.
- Opener no longer doubles an opposing bid on 18+ HCP alone ("extra values"): partner
  left it in; opener passes (+1.0 a board over 10,000 fresh deals, three seeds).

Measured and left out: look-ahead play in tricks 6 to 8 (+0.13 tricks a
board, needs the web app's sampler and async robots first), the lone-trump
draw (flat), penalty doubles on four trumps only without a fit (a tie).

## v0.1.4-alpha (2026-11-10)

The Nov 10 fixes from played boards, and the table count: every card-play
rule now reads one count of what its seat has seen, and the fallback lead,
the declaring side's discards and fourth hand on defence are chosen from it.
Card play, tricks given away a board on the same 199 deals: declaring side
2.58 to 2.15, opening lead 0.39 to 0.40 (the bidding changes move some
contracts), defence 2.12 to 1.87. The count's three play rules measured +0.03 to +0.06 tricks a
board each to the side that uses them (seated, 3 x 1,000 fresh deals). The
bidding fixes +0.53 / +0.35 / +0.22 (long suits) and +0.02 / +0.21 / +0.22
(over 1x-P-1NT) points a board on 10,000-deal sets.

**The game**
- The challenge result is one scorecard: You, Robots and Par side by side,
  with par's contract named next to its score. The match totals come next,
  then the button for the next board, then the deal review.

**The robots**
- An eight-card major or a nine-card minor bids game at once: opening, over
  their opening, or as advancer's first call.
- Advancer with 10+ HCP and a seven-card suit names it, at the three level at
  most.
- Fourth seat over 1x-P-1NT bids a natural five-card suit at the two level
  (12-17 HCP) or doubles for takeout (12+ HCP with the shape, or 18+)
  instead of always passing, and the answer to a takeout double never names
  a suit they bid, game in a major included (2♥ P 3♦ X P is not 4♥).
- The fallback lead picks its suit by playing each suit out over the layouts
  the count allows.
- Declarer and dummy price each discard by what it costs in its suit.
- Fourth hand on defence plays the led suit out over the count.
- Declarer's side third hand plays the led suit out before following (the 8♠
  that keeps the 6♠ to trap West's 7♠).
- A discard keeps the low card that beats dummy in a located suit (South
  throws the A♠ and keeps the 2♠ over dummy's 4 3).
- Declarer doesn't draw trumps when every defence trump would take a round
  anyway (two or more out), and leads for a ruff instead of a trump that
  draws nothing (dummy's lone 6♥ ruffs the K♠).

## v0.1.3-alpha (2026-11-09)

The Nov 6 and Nov 9 fixes from played boards. The four Nov 6 card-play fixes
together measure +0.10 tricks and +11.8 points a board to the side that uses
them (seated, 3 x 1,000 fresh deals, t above 6 on each); the declarer's
crossing ruff adds +0.01. Card play, tricks given away a board on the same
199 deals: declaring side 2.74 to 2.58, opening lead 0.40 to 0.39, defence
2.41 to 2.12. The Nov 6 bidding fixes together +0.07 a board (3 x 1,000 fresh
deals, noise: the auctions are rare); the Nov 9 ones +0.01 to +0.08 each on
10,000-deal sets.

**The game**
- Par is now true duplicate par (both sides bid; sacrifices count), and its ⓘ opens on tap.
- Double dummy results are kept per board when you switch between the Your
  board and Robots' board tabs or pick another board in History.

**The robots**
- An answer to partner's responsive double is not read as the 18+
  double-then-suit, so advancer doesn't raise it.
- The responsive doubler bids game in a major partner answers with 11+ HCP
  and four cards in it (only after a real responsive double, and never in
  their suit).
- A takeout doubler's new suit at the three level shows six or more cards.
- Over their 1NT, a Cappelletti 2♣ one-suiter passes partner's 2♦ relay
  with diamonds instead of bidding 3♦.
- After a support double, responder's jump to three of their suit needs five
  cards.
- A negative doubler gives preference to opener's first suit instead of
  passing a worse fit; opener passes the preference.
- With 11+ HCP the negative doubler raises the longest fit to the three level
  instead (game in a major on 15+), and a strong opener invites over a
  preference to a major. Never five of a minor.
- Declarer leads the card that wins unless the suit is ruffed (the K♥ from
  dummy's K 4 2 over the bare ace).
- Declarer without trumps in hand crosses to the trump hand by a ruff to
  draw trumps, ruffing high enough to keep the low trumps that draw the rest.
- Second hand covers when dummy leads too (East's T♣ from K T 7 4 3 under
  dummy's 9♣).
- Third hand on defence plays the led suit out over partner's and declarer's
  possible holdings, and with dummy last plays the cheapest card that wins
  whatever dummy does.

## v0.1.2-alpha (2026-11-05)

The Nov 4 evening fixes from played boards. The bidding fixes together
measure +0.56 points a board against v0.1.1-alpha (3 x 1,000 fresh deals);
the two card-play fixes together +0.03 tricks and +4.15 points a board to the
side that uses them (seated, 3 x 1,000 fresh deals). Card play, tricks given away a
board on the same 199 deals: declaring side 2.81 to 2.74, opening lead 0.40
to 0.40, defence 2.48 to 2.41.

**The game**
- When you declare a suit contract, your own hand sorts like dummy's: trumps
  on the left.

**The robots**
- A 2♣ rebid shows six clubs, five only with a singleton or void.
- Systems on over our penalty double of their 1NT (transfers to run, the
  doubler completes or doubles their runout) and over their 2♣ overcall of
  our 1NT (X is Stayman, 2♦/2♥ transfer). If they double the transfer or
  bid over it, it is still completed (the review's fix).
- A three-card raise of partner's 1♣/1♦ opening needs a side singleton or
  void.
- Support redoubles: after 1x (P) 1y (X), opener redoubles with exactly three.
- Fourth hand doesn't ruff partner's winning trick.
- Second to fourth hand plays a trump or notrump suit out exactly once every
  card in it is located.
- Smolen is bid only over the Stayman denial (a human's 4♦ answer isn't one).

**Research**
- `robot_line_report.py` reports card play as mistakes added up per side,
  with `--compare` for a change's before and after.

## v0.1.1-alpha (2026-11-04)

The Nov 4 fixes from played boards and the gap analysis, measured together
at +1.18 points a board against v0.1.0-alpha (3 x 1,000 fresh deals).

**The robots**
- A suit doubled and passed round is passed, never rebid; every lone rebid of
  one's own suit shows six cards.
- No penalty double of a part score once an opponent has shown 20+.
- Opener's raise beside a support double is alerted as 4+ cards.
- A five-card fit bids game at once over partner's simple major overcall, at
  any vulnerability; nobody competes past the six level.
- Advancer bids game in a five-card major over a three-level takeout double
  with 9+ points.
- Our cuebids over their Unusual 2NT are answered; advancer picks a minor
  after our 4M/4NT minors over their weak two.
- The doubler answers partner's responsive double; the suit their transfer shows is
  ours to bid only with 6+ cards and 12+ HCP, and partner reads that bid as
  natural, not a cuebid.
- Measured and left as is: a five-card two-level overcall needs no particular
  suit quality.

## v0.1.0-alpha (2026-11-03)

The first tagged release: everything up to and including PR #62.

**The game**
- Second-highest bridge in the browser (https://hberk.github.io/second_highest_bridge/):
  play South against three robots, with alerts on every robot call and your own.
- Challenge mode on 400 double-dummy-solved deals, grading each board into
  what the auction and the card play cost.
- Bidding training on its own solved deals.
- Hand history with a card-by-card replayer, double dummy marks on every card
  (the Rust solver as WebAssembly), and LIN export and import.
- Multiplayer beta at bridge.ettamei.com: two to four people, robots in the
  other seats.

**The robots**
- GIB 2/1 bidding, with the competitive rules from the championship study
  (balancing, the Law of Total Tricks, penalty doubles, pre-empts, Stayman and
  negative doubles over interference).
- Card play: declarer 0.025 tricks a board below double dummy on the
  library. (Corrected 2026-11-05: that is a net figure, in which declarer's
  and the defence's mistakes cancel. Added up, each side gave away about 2.8
  tricks a board; see docs/ROBOT_PROGRESS.md.)

**In this release (PR #62)**
- A takeout double of 1♣/1♦ with both majors, direct and balancing seat.
- After our Michaels or Unusual 2NT, partner's choice of suit stands; a 6-5
  hand invites, but not over their double; over their bid, a five-card holding
  competes to the level of the fit.
- Balancing over a weak two: a good six-card suit at the two level; no
  three-level balance on a poor five-card suit.
- An eight-card major bids game at once over their one-level opening;
  reverses in a contested auction.
- The 2NT minor ask over their 1NT is answered; negative doubles with
  Lebensohl over (1NT) 2♥/2♠.
- Fixed: partner's rebid of the suit they opened was read as a cuebid.
