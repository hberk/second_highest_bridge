# Hosting, saved games, and the road to multiplayer

Status: **proposed 2026-10-13. Pages hosting and browser saves are built.**
Pages deploys once the repo is public.

| stage | what | where | state |
|---|---|---|---|
| Now | Host the Svelte app | **GitHub Pages** (replaces Azure Static Web Apps, which was never deployed) | built: `.github/workflows/pages.yml` |
| Now | Saved games, no accounts | **The browser** (`localStorage`) | built: `frontend/src/lib/saves.ts` |
| Later | Live tables with friends | **Cloudflare** Workers + Durable Objects | proposed; see below |
| Open | Accounts, history across devices | Supabase Auth + Postgres (as in [ONLINE_PLAN.md](ONLINE_PLAN.md)), or Cloudflare-native | undecided |

[ONLINE_PLAN.md](ONLINE_PLAN.md) stays the reference for *what* online play
means: the rules, trust, alerts, the data model and the phases. This doc changes
*where* it runs.

## GitHub Pages

The Svelte app is fully static. `npm run build` writes HTML, CSS and JS to
`frontend/dist`, and rules, robots, scoring and the challenge library all run in
the browser.

- **Workflow** (`.github/workflows/pages.yml`):
  - **while the repository is private, nothing runs.** Actions minutes on
    private repos are metered, so every job is skipped (a skipped job starts no
    runner). A manual "Run workflow" still runs the checks on demand;
  - once public, every push and pull request runs the gate: fixtures from
    Python 3.12, `npm ci`, `npm run check`, `npm test`, `npm run build`. Public
    repos' Actions are free;
  - only a push to `main` uploads and deploys.
- **To turn it on:**
  1. make the repo public. Pages from a private personal repo needs GitHub Pro,
     and the site is public either way;
  2. go to Settings → Pages → Source: **GitHub Actions**;
  3. push, or start a new run with **Run workflow**. Not "Re-run jobs": a
     re-run replays the original event, including the visibility it saw, so
     a run from while the repo was private skips again.

  The site is then at `https://hberk.github.io/second_highest_bridge/`.
- **Base path:** `vite.config.ts` sets `base: './'`, so the same build works
  from Pages' sub-path or any other address. Tested on 2026-10-13: the built
  site served from `/second_highest_bridge/` played a board, reloaded with the
  board still in its history, and logged no CSP violations.
- **No routes:** the tabs are component state, not URLs, so Pages' lack of a
  single-page-app fallback doesn't matter. A hash router (`#/history`) keeps
  that true.
- **Headers:** Pages can't send custom headers.
  - The CSP is a `<meta>` in `frontend/index.html`, and the referrer policy is
    `<meta name="referrer">`.
  - `frame-ancestors`, `X-Content-Type-Options` and `Permissions-Policy` can't
    be set this way. That's acceptable for a game with no sign-in; revisit when
    accounts arrive.
  - Any new `connect-src` (an accounts API, a Cloudflare WebSocket) goes in that
    meta tag.

## Saved games in the browser

**What is saved:** finished boards (`HistoryRecord`), challenge results, the
passed-out count and the board number.
- **Key:** `localStorage` key `shb-games-v1`, holding
  `{version, boardNum, history, challengeLog, passedOut}`.
- **When:** written after every finished board, every passed-out board and
  every LIN import.
- **Loaded:** by `new Game()`.
- **Not saved:** a board still in progress.
- **Settings:** stay under `shb-settings`, as before.

**How it behaves:**
- **Never in the way:** a full or blocked storage is ignored, and play carries
  on with the session in memory.
- **Never destructive:** an unreadable or unknown-version save is copied to
  `shb-games-backup` before the game starts empty.
- **Bounded:** only the newest 500 boards are kept. **Download all boards
  (.lin)** in Hand History is the archive.
- **Eviction:** after the first save, `navigator.storage.persist()` asks the
  browser not to evict the site under disk pressure.
- **Player control:** Display → **Saved on this device** shows the counts and a
  **Clear saved games** button.

**How long it lasts:** `localStorage` survives closing the browser, restarts
and reboots. It's lost or separate when:
- **the player clears site data** or cookies;
- **a private or incognito window** closes;
- **Safari on iPhone/iPad goes 7 days without a visit.** Script-written storage
  is deleted then. A site added to the Home Screen is exempt. This is the one
  that matters for a phone game;
- **the device or browser differs.** Nothing syncs; that's what accounts are
  for;
- **the origin differs.** Moving the site to a new address starts everyone
  empty.

**Ready for accounts:** the records are the `HistoryRecord` shape ONLINE_PLAN
stores in `boards.record`. Phase 1's "boards played as a guest stay in memory;
on sign-in, offer to save them" becomes **"on sign-in, offer to upload the boards
saved on this device"**. Uploaded boards are client-written, so they get
`trusted=false`.

## Multiplayer on Cloudflare (proposed, longer term)

**Why Cloudflare:** a live table is a small, stateful, real-time thing, and that
is exactly what a Durable Object is: **one object per table**, with
- WebSockets to the seated players;
- the deal and the event log in the object's own SQLite storage;
- the engine running beside them.

ONLINE_PLAN's principles carry over unchanged:
- the server deals and validates;
- a client only ever receives its own hand, dummy once it's down, and the
  public events;
- state is the deal plus an append-only event log.

| ONLINE_PLAN (Supabase) | Cloudflare equivalent |
|---|---|
| Edge Function `table-action` | The table's Durable Object, which receives intents over its WebSocket |
| Realtime (Postgres Changes) | The same WebSockets, pushing each seat only what it may see |
| `table_events`, `table_hands`, `table_alerts` | The object's SQLite tables; per-seat visibility is enforced in code, not RLS |
| Presence | The object knows who is connected |
| Engine bundled for Deno | Engine bundled for Workers (plain ES modules; the same esbuild step) |

**Hosting:** Workers can also serve the static site, so the game and its tables
could live on one platform. Pages can stay as the host until then.

**Cost:** the Workers Free plan includes SQLite-backed Durable Objects:
- 100,000 requests a day;
- 13,000 GB-seconds of compute a day;
- 5 GB of storage.

Going over a limit fails the request; there are no charges. That was checked on
2026-10-13; confirm on Cloudflare's pricing page before relying on it. A
friends' table is far inside it.

**Open questions before building:**
- **Accounts.** Cloudflare has no hosted login or row-level security.
  - **Option 1:** keep Supabase for Auth and the `boards`/friends tables, with
    Durable Objects only for live tables. The object verifies the Supabase JWT on
    connect.
  - **Option 2:** build accounts on Workers + D1 (email magic links through a
    mail API).

  Option 1 reuses most of ONLINE_PLAN Phase 1.
- **Guest tables.** Could friends play by sharing a table link with no accounts
  at all? A Durable Object makes that cheap: a seat token per invite. It would
  let multiplayer ship before accounts.
- **Trusted results.** A table's object writes results server-side, so they are
  `trusted=true`. Wherever accounts live has to accept those writes from the
  object alone.
