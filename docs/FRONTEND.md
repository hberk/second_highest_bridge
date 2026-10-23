# Svelte front end (`frontend/`)

The game: a static Svelte 5 + Vite app, how it is held to the Python engine, and its features.

Moved verbatim from `CLAUDE.md` on 2026-10-13, so it is read when the work needs it instead of loading into every session. [CLAUDE.md](../CLAUDE.md) keeps the guardrails and links here.

```bash
cd frontend
npm install
rustup target add wasm32-unknown-unknown   # once, for the double dummy solver
npm run fixtures   # export the Python engine's behaviour (needs Python 3.12+)
npm test           # TS engine parity with Python + headless table flow + WASM solver
npm run check      # svelte-check
npm run dev        # local dev server
npm run build      # static site in frontend/dist, deployed to GitHub Pages
```

The game, hosted on GitHub Pages: no server, everything runs in the browser,
~105 KB gzipped including the deal library, plus 21 KB for the double dummy
solver. It began as a port of a Streamlit app (`app.py`, `web/`), retired on
2026-10-21 once this one did everything it did; the Python engine stays and
remains the reference.
- `frontend/src/lib/engine/` is a **line-for-line TypeScript port** of
  `card.py`, `bridge/` (auction, trick, scoring; the trick rules `legalPlays` and
  `resolveTrick` live in `auction.ts`, there is no `trick.ts`) and
  `ai.py`/`gib.py`/`challenge.py`. It is
  held to the Python by `engine.test.ts` against fixtures from
  `tests/fixtures/export_ts_fixtures.py`: every legal-call list, call, alert and
  card over 1,200 games (half with a random human South, to reach states an
  all-robot table never does), every scoring case, 1,600 hand evaluations, and
  the robot table, grade and par of all 400 library deals. Exact equality,
  floats included. **Change `ai.py` and the port fails until it follows** --
  CI regenerates the fixtures on every run. Port details that matter: Python's
  `max`/`min` keep the first of tied items (`maxBy`/`minBy`), and 3.12's
  compensated `sum()` (`pythonSum`).
- `frontend/src/lib/game.svelte.ts` is the table's state machine. The auction is
  rebuilt from the call list rather than stored, so there is one source of truth.
  `game.test.ts` drives it through free and challenge boards, rendering every
  view at every step.
  `new Game(storage, random)` takes the random source that deals and picks
  challenge deals; every test passes a seeded one (`prng` from `meanings.ts`),
  since an unseeded "at least once in ten boards" check failed CI by chance.
- **Screens (the Felt design, 2026-10-16).** Phone first, portrait, dark
  green. `App.svelte` switches between a home page (`HomeView`) and the
  table, Challenge, History and How to play. Play, Challenge and History are
  tabs in one slim row (`TabStrip`, 2026-10-23, the user's call: tabs again,
  but compact): the spade goes home, `?` opens How to play (which keeps a
  back button, `TopBar`), and Challenge and History use the row as their whole
  top bar, so only the table pays for it (about 40px; the bidding box and
  your hand still fit a 390x844 screen). The screen follows the URL hash
  (`#table`, `#history`), so the browser's back button and the phone's back
  swipe work. Settings live in a
  bottom sheet (`Sheet` + `SettingsPanel`), opened from the gear on home and
  at the table. `TableView` is one 520px column: the auction on an oval of
  felt (`AuctionFelt`, each seat's latest call where it sits and the newest
  alert spelled out), the trick on the felt (`TrickFelt`) with a line under it
  saying who is winning and why (`trickText.ts`), your hand as an overlapping
  fan at the bottom (`Fan`; legal cards rise, the rest grey out), the dummy
  above the felt once it's down. There is no X-ray view of the robots' hands
  (removed 2026-10-21, the user's call): the hand record in History shows them.
  The full auction is a sheet. **History and Challenge (2026-10-23)** share `HistoryView` in the same
  look: a result card, a ‹ › board picker (a Your board / Robots' board switch
  when the review shows two boards of one deal), the auction, the trick on the
  felt (`TrickFelt`) with the line saying who wins it, the four hands around
  it, and the step buttons in a bar kept at the bottom of the screen
  (`.hv-controls`, sticky). The trick log, LIN record and import sit in
  collapsed sections at the end. **Wide screens (1200px and up,
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
  last, so the older sheets (`table.css`, ported from the Streamlit app's
  stylesheet, and `app-shell.css`) take on its colours where
  History and Challenge still use them. `mobile.css` now only tightens How to
  play's felt diagrams on phones. Svelte escapes all text, and no `{@html}`
  is used anywhere.
- **Self-alerts**: "Add an alert" in the box a first tap opens; the text goes
  with the next call (`Game.humanBids(call, alert)`), is cleaned by
  `cleanAlert` (one line, at most 70 characters; `clean_alert` in
  `bridge/auction.py` is its Python twin), and is shown live even on a pass,
  while robot pass reasons stay hidden. The robots don't read it. Because the
  app takes free text, `lin.test.ts` fails if `{@html}` appears in any
  component.
- **LIN** (`frontend/src/lib/lin.ts`, and `bridge/lin.py` in Python): BBO's
  hand-record format, exported and imported in the History tab. **The two
  write byte-identical LIN**: `export_ts_fixtures.py` writes Python's LIN for
  300 boards to `lin.json`, and `lin.test.ts` must parse each to Python's
  score and write it back unchanged. **They also refuse the same input**:
  `lin_hostile.json` holds odd and hostile texts with Python's verdict
  (prototype keys as a vulnerability, `mc` values `Number()` would read, other
  scripts' digits, a byte-order mark, an over-long alert), and `lin.test.ts`
  must agree on each. Imported alerts get the typed-alert clean-up (one line,
  70 characters); an import reads at most 500 boards and 1 MB, and boards
  already imported are skipped. Exported
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
  tricks going to the wrong hands. A board that ended in a claim gets double
  dummy values for the tricks that were played.
- **Table conveniences** (`qol.test.ts`): **Last trick** on the
  felt from trick 2 on (the peek is keyed to the moment it was asked for, so
  any card played drops it); **auto-play forced cards** (`settings.autoPlay`,
  off by default, and `Game.autoPlayForced` defaults to false so the
  state machine and its tests behave as before unless asked) and **fast
  play** (`settings.fastPlay`, next trick after 1.2 s); a **session
  scoreboard** (`SessionScore.svelte`) on the home page: N/S total, made and
  set counts, a board-by-board running total, and the margin against the
  robots on challenge boards. Passed-out boards count (`Game.passedOutCount`);
  boards imported from LIN don't (`imported`). Auto-play is off by default
  (since 2026-10-15). Last trick and the auction are buttons beside your
  hand.
- **Double dummy in the replayer** (2026-10-21; `src/lib/dd/`,
  `dd.test.ts`). `research/solver-rs` compiled to WebAssembly
  (`research/solver-rs/wasm`, 50 KB), not a port of `bridge/solver`. At each
  step, every legal card of the seat to play carries how the contract ends if
  it's played and both sides play perfectly after: **−n** (red) down n, **=**
  (grey) exactly, **+n** (green) n overtricks; the card played is underlined.
  Signed as well as coloured, for colour-blind players, and measured against
  the contract on a defender's turn too (the user's choices, from a mock).
  On in History and in the challenge review (`analysis` prop; the challenge
  review had it off until 2026-10-22), so the robots' line can be checked
  card by card. Under the replayer, **Where tricks were lost** lists every
  analysed card that was worse for its side than the best card held
  (`tricksLost`): trick, seat, how the contract moved (e.g. −1 → =) and the
  card(s) that kept it; a tap jumps the replayer there. It grows as earlier
  tricks are analysed. `dd.test.ts` checks the list accounts for every trick:
  from the first decision analysed, N/S's tricks are the best they could force,
  less what N/S gave away, plus what E/W gave away.
  - **It runs in a worker**, one per board shown (`worker.ts`, terminated on
    leaving the board, which frees the table), and fills in from the last
    trick back with one `Search` kept through the board: the endgame is
    instant and fills the table the earlier tricks reuse.
  - **Depth.** Tricks 3-13 at once (`AUTO_CARDS = 11`); tricks 1-2 on a tap.
    Measured on 38 library boards, WebAssembly in Node on the laptop, table
    capped at 1M entries: the last 10 tricks 0.28 s median, 2.0 s worst; the
    last 11, 0.87 s and 4.9 s. The whole hand, tricks 1-2 included: 31 s
    median, over a minute on 13 of the 38 boards and up to 7 minutes (the
    1M cap evicts on hard deals; uncapped natively, 11 s median and 47 s at
    worst). Phones will be slower. WebAssembly ran at native speed at every
    depth measured, with every value identical to the native solver.
  - **Memory.** `TABLE_LIMIT = 4_194_304` slots of 24 bytes, allocated
    when a board loads: 102 MB of WebAssembly memory, measured, and it never
    grows (until 2026-10-22, a hash map of 1M entries, ~130 MB at the peak).
    The fixed table made tricks 1-2 about 3x faster natively on 10 robot
    lines (139 s median to 38 s; SOLVER.md), so the timings under Depth,
    taken before it, are now pessimistic. The native limit (50M, gigabytes) would kill a phone
    tab. A smaller table costs time, never a different value (`dd.test.ts`
    also runs with 7 entries).
  - **Checked against the Python solver** (`export_ts_fixtures.py` writes
    `dd.json`: every decision of the last five tricks of 16 boards, 320 in
    all), value for value, and against the native build on 38 stored robot
    lines in the spike (every card of every decision, identical).
  - **No fallback.** `npm run wasm` (run before dev, test and build) needs
    Rust with the `wasm32-unknown-unknown` target and fails without it; CI
    adds the target. The page's CSP allows `'wasm-unsafe-eval'` for it.
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
