# Second-Highest Bridge

Contract bridge with one rule changed: **the second-highest card of the winning
suit takes the trick**, not the highest.

**Play it in your browser: https://hberk.github.io/second_highest_bridge/**

Nothing to install, no account. It runs entirely in the page, and your
finished boards are saved in your browser. Visits are counted with Cloudflare
Web Analytics, which uses no cookies and doesn't track you between sites.

## The rules

Everything is ordinary contract bridge (auction, contracts, duplicate scoring)
except who wins a trick:

- The winning suit is trumps if any trump was played, otherwise the suit led.
  That holds in notrump too.
- Of the cards played in the winning suit, the **second-highest** wins.
- If only one card of the winning suit was played, it wins.

So the ace is often a liability, length in trumps is worth more than honours,
and many of bridge's instincts point the wrong way.

## What's here

- **Play South against three robots.** They bid **GIB 2/1**, the system BBO's
  robots play, with alerts on every robot call: hover a call to see what it
  shows. Alert your own calls too.
- **Challenge the robots.** Deals come from a library of 400 deals solved
  exactly (double dummy) in every strain. You play a board, an all-robot table
  plays the same cards, and the difference is split into what the **auction**
  cost and what the **card play** cost.
- **Hand history.** Replay any board card by card, and export or import it as
  LIN, BBO's hand-record format. LINs are replayed under second-highest rules,
  so a board played under ordinary rules will usually be refused.
- **A double dummy solver** for the variant, which is how the library was
  solved. How many tricks a deal is worth with perfect play wasn't known for
  this game. The hand history runs it in your browser: step through a board
  and every card shows how the contract would end if it were played.

## How good the robots are

On the 400 library deals at all 16 board positions (v0.1.0-alpha, measured
2026-11-03 by `research/challenge_losses.py`):

- **Card play still gives away tricks on both sides.** Scored card by card
  against double dummy (v0.1.3-alpha, 2026-11-07, 199 library deals), the declaring
  side gives away 2.6 tricks a board and the defence 2.5 (0.4 of it on the opening lead); 95%
  of boards have at least one costly card. The endings are close to perfect
  (2% of cards in the last four tricks cost one), the middle of the hand is
  not. Because robots sit on both sides, those mistakes mostly cancel in the
  final score, which is why the older net figures (5 points a board, 0.025
  tricks) looked close to perfect.
- **The auction is where the points go:** 233 points a board below par, the
  double dummy best result for both sides. Par assumes perfect bidding by
  everyone, so no table reaches it, but it is the figure each bidding change
  is measured against.

Every rule the robots use, and what it was worth, is in
[`docs/ROBOT_PROGRESS.md`](docs/ROBOT_PROGRESS.md); changes by release are in
[`CHANGELOG.md`](CHANGELOG.md).

## Running it yourself

The web app is in `frontend/` (Svelte). It needs Node and, for the double
dummy solver, Rust with the WebAssembly target:

```bash
rustup target add wasm32-unknown-unknown
cd frontend
npm install
npm run dev
```

The Python code at the top level is the reference engine the web app is ported
from: rules, scoring, robot bidding and play, the solver and the research
tooling. It needs Python 3.12 and nothing else to install.

Tests:

```bash
python tests/run_all.py     # the Python engine and solver
cd frontend && npm test     # the web app, held to the Python engine call for call
```

The web app's engine is a line-for-line TypeScript port of the Python one. Its
tests check that it reproduces the Python engine exactly: every call, alert
and card over 1,200 full games, and all 400 library deals.

Design notes and measurements live in [`docs/`](docs/), with
[`CLAUDE.md`](CLAUDE.md) as the overview. Every improvement to the robots and
what it was worth is in [`docs/ROBOT_PROGRESS.md`](docs/ROBOT_PROGRESS.md).

## Credits

The championship auctions behind the robots' competitive bidding study, and
the card play behind their notrump defence and trump play (see
[`docs/CHALLENGE.md`](docs/CHALLENGE.md)), come from
[ContractBridge/pbn-files](https://github.com/ContractBridge/pbn-files),
a collection of PBN hand records from world and national championships.

## Security

See [SECURITY.md](SECURITY.md) to report a problem privately.

## License

[MIT](LICENSE)
