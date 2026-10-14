# Second-Highest Bridge

Contract bridge with one rule changed: **the second-highest card of the winning
suit takes the trick**, not the highest.

**Play it in your browser: https://hberk.github.io/second_highest_bridge/**

Nothing to install, no account. It runs entirely in the page, and your
finished boards are saved in your browser.

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
  this game.

## Running it yourself

There are two front ends over one rules engine:

```bash
# The web app (Svelte), as deployed
cd frontend
npm install
npm run dev

# The original Streamlit app (Python 3.12), the reference implementation
pip install -r requirements.txt
streamlit run app.py
```

Tests:

```bash
python tests/run_all.py     # the Python engine, solver and Streamlit app
cd frontend && npm test     # the web app, held to the Python engine call for call
```

The web app's engine is a line-for-line TypeScript port of the Python one. Its
tests check that it reproduces the Python engine exactly: every call, alert
and card over 1,200 full games, and all 400 library deals.

Design notes and measurements live in [`docs/`](docs/), with
[`CLAUDE.md`](CLAUDE.md) as the overview.

## Security

See [SECURITY.md](SECURITY.md) to report a problem privately.

## License

[MIT](LICENSE)
