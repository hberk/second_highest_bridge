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
no server, everything runs in the browser, ~105 KB gzipped including the deal
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
- **Screens (the Felt design, 2026-10-16).** Phone first, portrait, dark
  green. `App.svelte` switches between a home page (`HomeView`) and the
  table, Challenge, History and How to play, each with a back button
  (`TopBar`); the screen follows the URL hash (`#table`, `#history`), so the
  browser's back button and the phone's back swipe work. Settings live in a
  bottom sheet (`Sheet` + `SettingsPanel`), opened from the gear on home and
  at the table. `TableView` is one 520px column: the auction on an oval of
  felt (`AuctionFelt`, each seat's latest call where it sits and the newest
  alert spelled out), the trick on the felt (`TrickFelt`) with a line under it
  saying who is winning and why (`trickText.ts`), your hand as an overlapping
  fan at the bottom (`Fan`; legal cards rise, the rest grey out), the dummy
  above the felt once it's down, and X-ray hands as suit lines (`MiniHand`).
  The full auction is a sheet. **Wide screens (1200px and up,
  `viewport.svelte.ts`) get a desktop layout instead**: a header with the
  sections as tabs and the Display menu (`DeskHeader`), and
  `DesktopTableView`, with everything on screen at once: a strip of board
  facts (board, dealer, vulnerability, high bid or contract, trick, tricks
  won, session), West and East as seat panels beside a larger felt
  (`SeatCard`), the dummy above, your hand in large cards with the full
  strength line (HCP, 2nd-highest value, shape), and down the right the
  auction, your call (`BidPad` docked: its meaning box opens to the left),
  the last trick and the session table. Both layouts read the table from one
  `TableModel` (`tableModel.svelte.ts`: whose turn, which hands are face up,
  seat labels, the last-trick peek, fast play), so they can't disagree, and
  `game.test.ts` renders and checks both at every step of every board. Home
  is the same on both. `index.html` and `public/manifest.webmanifest`
  make it a full-screen app when added to an iPhone's home screen. The icon
  ("the second spade": an ivory spade with a gold 2, on the felt) is
  `public/favicon.svg`; `scripts/make_icons.py` draws the home-screen,
  manifest and `.ico` sizes from it with Pillow, so edit the SVG and rerun it;
  `felt.css` keeps content clear of the notch and home bar with the
  safe-area insets.
- **Two-tap bidding with meanings** (`BidPad.svelte`, `meanings.ts`). Every
  call is a button. The first tap opens a box saying what the call would mean
  here; tapping the same button again makes it; the box also takes a
  self-alert. The meaning comes from the robots themselves: an alert depends
  only on the auction and the call (machine-checked, see
  [ARCHITECTURE.md](ARCHITECTURE.md)), so `callMeanings` asks `aiBidExplained`
  what it would bid with 4,000 sampled hands in this seat and keeps each
  call's alert. The sample is seeded from the auction (the same auction always
  reads the same) and skewed towards strong and long hands, which uniform
  deals rarely reach. It's what partner, a robot, will take the call to mean.
  `describeCall` turns an alert into a title ("Negative double", "Transfer",
  "Natural"), tags ("4+ ♠", "6+ HCP") and a plain sentence from a glossary of
  the conventions GIB uses. A call no sampled hand makes says so: "No agreed
  meaning". Pass gets a general explanation, since robot pass reasons read
  the hand. `meanings.test.ts` checks the sampled meaning against the robots'
  real alert at every bid of real auctions. Nothing here touches the engine,
  so the fixtures don't cover it, and `ai.py` stays free of any RNG: the
  sampler's is its own.
- Styles: `felt.css` holds the Felt design and its colour tokens, loaded
  last, so the older sheets (`table.css`, ported from `styles.css` with
  Streamlit selectors dropped, and `app-shell.css`) take on its colours where
  History and Challenge still use them. `mobile.css` now only tightens How to
  play's felt diagrams on phones. Svelte escapes all text,
  so the `unsafe_allow_html` audit ([ARCHITECTURE.md](ARCHITECTURE.md)) has no equivalent here: no `{@html}`
  is used anywhere.
- **Self-alerts** (both apps): the bidding box has an alert field (in the
  Svelte app, "Add an alert" in the box a first tap opens); the
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
  off by default, and `Game.autoPlayForced` defaults to false so the
  state machine and its tests behave as before unless asked) and **fast
  play** (`settings.fastPlay`, next trick after 1.2 s); a **session
  scoreboard** (`SessionScore.svelte`) on the home page: N/S total, made and
  set counts, a board-by-board running total, and the margin against the
  robots on challenge boards. Passed-out boards count (`Game.passedOutCount`,
  `passed_out_count`); boards imported from LIN don't (`imported`). Auto-play
  is off by default in both apps (since 2026-10-15), and `test_app_flow`'s
  `_start_play_as` switches it on only when a test asks: the others click
  every card themselves. Last trick and the auction are buttons beside your
  hand in the Svelte app. Fast play in Streamlit
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
  - **At most 500 boards, imported ones dropped first** (`trimHistory`): a
    big LIN import used to push out every board the player had played.
  - **Tabs don't overwrite each other.** Each save re-reads storage and
    merges (`mergeGames`; a board's identity is `boardKey`: number, dealer,
    hands and calls, since two tabs can each deal "board 11"), and each tab
    takes on another tab's save or clear through the `storage` event.
    Before, a tab wrote its own copy over whatever another tab had saved.
- Deployment: `.github/workflows/pages.yml` exports fixtures, type-checks,
  tests and builds, and deploys `frontend/dist` to GitHub Pages from `main`.
  **Nothing runs while the repo is private** (metered Actions minutes; every
  job is skipped, except a manual "Run workflow"). Once public, every push and
  pull request is checked (Pages on a private personal repo would need GitHub
  Pro anyway). `vite.config.ts` sets `base: './'`
  because Pages serves the site from `/second_highest_bridge/`. Pages can't send
  headers, so the CSP is a `<meta>` in `frontend/index.html`: scripts from
  `'self'` only, plus exactly two outside origins for Cloudflare Web Analytics
  (cookieless page views, added 2026-10-14): the beacon script and its
  endpoint. Styles need `'unsafe-inline'` for inline style attributes,
  measured; `frame-ancestors` can't be set this way. See
  `docs/HOSTING_AND_LOCAL_SAVES.md`. TypeScript is pinned to 6 because
  svelte-check does not yet support 7 on its own.
