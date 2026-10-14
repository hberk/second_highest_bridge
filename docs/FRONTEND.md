# Svelte front end (`frontend/`)

The static Svelte 5 + Vite port of the Streamlit app: how it is held to the Python engine, and the features both apps share.

Moved verbatim from `CLAUDE.md` on 2026-10-13, so it is read when the work needs it instead of loading into every session. [CLAUDE.md](../CLAUDE.md) keeps the guardrails and links here.

```bash
cd frontend
npm install
npm run fixtures   # export the Python engine's behaviour (needs Python 3.12+)
npm test           # TS engine parity with Python + headless table flow
npm run check      # svelte-check
npm run dev        # local dev server
npm run build      # static site in frontend/dist, deployed to GitHub Pages
```

A static Svelte 5 + Vite port of the Streamlit app, hosted on GitHub Pages:
no server, everything runs in the browser, ~62 KB gzipped including the deal
library. `app.py` and the Python engine stay as they are and remain the
reference.
- `frontend/src/lib/engine/` is a **line-for-line TypeScript port** of
  `card.py`, `bridge/` (auction, trick, scoring) and `ai.py`/`challenge.py`. It is
  held to the Python by `engine.test.ts` against fixtures from
  `tests/fixtures/export_ts_fixtures.py`: every legal-call list, call, alert and
  card over 1,200 games (half with a random human South, to reach states an
  all-robot table never does), every scoring case, 1,600 hand evaluations, and
  the robot table, grade and par of all 400 library deals. Exact equality,
  floats included. **Change `ai.py` and the port fails until it follows** --
  CI regenerates the fixtures on every run. Port details that matter: Python's
  `max`/`min` keep the first of tied items (`maxBy`/`minBy`), and 3.12's
  compensated `sum()` (`pythonSum`).
- `frontend/src/lib/game.svelte.ts` is `app.py`'s state machine. The auction is
  rebuilt from the call list rather than stored, so there is one source of truth.
  `game.test.ts` drives it through free and challenge boards, rendering every
  view at every step -- the counterpart of `tests/test_app_flow.py`.
- Styles come from `styles.css` (`frontend/src/styles/table.css`, Streamlit
  selectors dropped; `app-shell.css` replaces them). Svelte escapes all text,
  so the `unsafe_allow_html` audit ([ARCHITECTURE.md](ARCHITECTURE.md)) has no equivalent here: no `{@html}`
  is used anywhere.
- **Self-alerts** (both apps): the bidding box has an alert field; the
  text goes with the next call (`Game.humanBids(call, alert)`, `human_bids` in
  `app.py`), is cleaned by `cleanAlert` / `clean_alert` (one line, at most 70
  characters), and is shown live even on a pass, while robot pass reasons stay
  hidden. The robots don't read it. Streamlit can't clear a text box from the
  run that read it, so its key includes the auction's length
  (`self_alert_<board>_<calls>`): each call gets a fresh box. Because the
  Svelte app takes free text, `lin.test.ts` fails if `{@html}` appears in any
  component; for Streamlit see the `unsafe_allow_html` review in [ARCHITECTURE.md](ARCHITECTURE.md).
- **LIN** (`bridge/lin.py` and `frontend/src/lib/lin.ts`, both apps): BBO's
  hand-record format, exported and imported in the History tab. **The two
  write byte-identical LIN**: `export_ts_fixtures.py` writes Python's LIN for
  300 boards to `lin.json`, and `lin.test.ts` must parse each to Python's
  score and write it back unchanged. Exported
  and imported in the History tab. `toLin` writes only what LIN holds (deal,
  dealer, vulnerability, calls, alerts as `mb|1S!|an|...|`, cards); `fromLin`
  rebuilds contract, trick winners and score by **replaying under
  second-highest rules**, which doubles as validation: out-of-turn cards,
  revokes, illegal calls and duplicate cards are refused, so most LINs from
  ordinary bridge are rejected, and so is a board that stops early (an
  unfinished auction, or play that ends without an `mc` claim): there is
  nothing to score. It reads BBO's variants (a missing fourth hand,
  `mc` claims, lower case, `!S` suit symbols). `|` in an alert becomes `/`,
  the one lossy step. BBO's own viewer applies ordinary rules, so it shows our
  tricks going to the wrong hands. In Streamlit, a board that ended in a claim
  skips the double dummy panel, which needs all 13 tricks.
- **Table conveniences** (both apps; `qol.test.ts`, `tests/test_app_flow.py`;
  Streamlit: sidebar checkboxes and `web/session_view.py`): **Last trick** on the
  felt from trick 2 on (the peek is keyed to the moment it was asked for, so
  any card played drops it); **auto-play forced cards** (`settings.autoPlay`,
  on by default in the app, but `Game.autoPlayForced` defaults to false so the
  state machine and its tests behave as before unless asked) and **fast
  play** (`settings.fastPlay`, next trick after 1.2 s); a **session
  scoreboard** (`SessionScore.svelte`) on the Table tab: N/S total, made and
  set counts, a board-by-board running total, and the margin against the
  robots on challenge boards. Passed-out boards count (`Game.passedOutCount`,
  `passed_out_count`); boards imported from LIN don't (`imported`). Auto-play
  is on by default in both apps, so `test_app_flow`'s `_start_play_as` switches
  it off: those tests click every card themselves. Fast play in Streamlit
  sleeps 1.2 s after the trick is drawn, then reruns.
- **The challenge review renders the history view a second time in the same
  run**, so `render_history_tab(..., key=)` prefixes every widget key (`hist`
  for the History tab, `chal` for the review), including the double dummy
  panel's (`hist_dd_on_<board>`). Before this, both used `hist_board_sel`.
- **Not ported: the double dummy analysis panel** (`web/analysis_view.py`). The
  route for it is `research/solver-rs` compiled to WebAssembly, not a port of
  `bridge/solver`.
- **Saved games** (`frontend/src/lib/saves.ts`, `saves.test.ts`): finished
  boards, challenge results and the passed-out count are kept in `localStorage`
  under `shb-games-v1` (newest 500 boards) and restored by `new Game()`, which
  also carries the board number on. Every access is guarded: a full or blocked
  storage never stops play, and an unreadable save is copied to
  `shb-games-backup` rather than overwritten. Records are `HistoryRecord`, the
  shape `docs/ONLINE_PLAN.md` stores server-side. `new Game(null)` keeps
  nothing (the default in Node, so tests start clean).
- Deployment: `.github/workflows/pages.yml` exports fixtures, type-checks,
  tests and builds, and deploys `frontend/dist` to GitHub Pages from `main`.
  **Nothing runs while the repo is private** (metered Actions minutes; every
  job is skipped, except a manual "Run workflow"). Once public, every push and
  pull request is checked (Pages on a private personal repo would need GitHub
  Pro anyway). `vite.config.ts` sets `base: './'`
  because Pages serves the site from `/second_highest_bridge/`. Pages can't send
  headers, so the CSP is a `<meta>` in `frontend/index.html` (`script-src
  'self'`; styles need `'unsafe-inline'` for inline style attributes,
  measured; `frame-ancestors` can't be set this way). See
  `docs/HOSTING_AND_LOCAL_SAVES.md`. TypeScript is pinned to 6 because
  svelte-check does not yet support 7 on its own.
