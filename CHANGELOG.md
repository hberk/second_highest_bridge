# Changelog

Releases are tagged on main, and the tag matches the version in
`frontend/package.json` and `server/package.json` (`v0.1.0-alpha` is
0.1.0-alpha). Until 1.0 the robots' bidding and play change from release to release; every change and
what it was measured to be worth is in
[docs/ROBOT_PROGRESS.md](docs/ROBOT_PROGRESS.md).

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
  ours to bid only with 6+ cards and 12+ HCP.
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
- Card play close to double dummy: declarer 0.025 tricks a board below it on
  the library.

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
