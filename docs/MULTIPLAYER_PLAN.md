# Multiplayer: the build plan

Status: **plan, 2026-10-26. Nothing built.** It turns the agreed design into
milestones the size of a PR, each with its files, tests and a "done when".

- [ONLINE_PLAN.md](ONLINE_PLAN.md) stays the reference for *what* online play
  means: the trust model, alerts, the event log, accounts and friends.
- [HOSTING_AND_LOCAL_SAVES.md](HOSTING_AND_LOCAL_SAVES.md) moved live tables
  to Cloudflare Durable Objects and asked whether guests could play by link.
- **This plan answers yes to that question:** live tables first, played by
  invite link with no accounts. Accounts, friends and server-saved history
  come after, as ONLINE_PLAN's Phase 1, and attach to tables without
  reworking them.

## Scope

**In (the first release):**
- Two to four humans at one table, in any seats; robots in the rest.
- A table plays a sequence of fresh boards; dealer and vulnerability rotate as
  in solo play.
- Every human sees their own hand, dummy once the opening lead is made, and
  the public auction and play. The server deals, holds the hands, validates
  every call and card, and runs the robots.
- Human alerts reach the opponents only; partner sees them after the board.
- After each board, everyone sees all four hands, all alerts, the score and the
  replay (the existing `HistoryView`, double dummy included), and the board is
  saved to each player's browser History like a solo board.
- Reconnecting (a phone locking, a train tunnel) resumes the board exactly.
- A seat whose player has gone can be handed to a robot, and taken back.

**Out (later, see [After the first release](#after-the-first-release)):**
accounts, friends lists, server-side history, running score across boards,
claims, chat, kibitzers, async duplicate. Solo play and Challenge don't
change at all, and still make no network calls.

## The decisions this plan makes

| question | decision | why |
|---|---|---|
| Backend | **Cloudflare Worker + one Durable Object per table** | The user has a Cloudflare account; ROADMAP recommends Cloudflare-only. A table is small, stateful and real-time, which is what a Durable Object is. |
| Accounts first or tables first | **Tables first, by invite link** | Accounts are a separate project (auth, mail, RLS or D1). Friends can play without them, and nothing in the table design depends on them. |
| Static site | **Stays on GitHub Pages** | Only the table server is new. Moving the site to Workers is optional and unrelated. |
| Where the rules run on the server | **The same `frontend/src/lib/engine/` source**, imported by the Worker | Wrangler bundles TypeScript itself (extensionless imports included), so ONLINE_PLAN's separate esbuild step for Deno isn't needed. |
| Table logic | **A pure TypeScript module, `frontend/src/lib/table/`**, shared by server and tests | Everything that matters (legality, visibility, robots, scoring) is testable in plain Vitest, without Cloudflare. The Durable Object is a thin shell. |
| State | **The deal plus an append-only event log** (ONLINE_PLAN principle 4) | Reconnect, replay and the saved record all derive from it. |
| What a client is sent | **Only what its seat may see, filtered on the server** | Opening dev tools reveals nothing; there's no X-ray to lock. |
| How a client receives it | **A full snapshot on (re)connect, then events** | A board is a few KB, so resending it is cheaper than delta bookkeeping and can't drift. |
| Seat-relative UI | **Every view takes "my seat"** and rotates so you sit at the bottom | Solo passes `South` and is unchanged. Rotating the *deal* instead (everyone thinks they're South) was considered and rejected: compass names would disagree between friends talking about the same board. |

## How a table works

```
Browser (GitHub Pages)                         Cloudflare
┌───────────────────────────────┐   HTTPS POST ┌─────────────────────────────────┐
│ Solo / Challenge: unchanged,   │─────────────▶│ Worker  /tables  (create)       │
│ engine runs locally            │              │         /tables/<id>/ws (join)  │
│                                │              │   checks Origin, routes by id   │
│ Table: RemoteTable             │   WebSocket  │              │                  │
│   sends intents                │◀────────────▶│ TableObject (Durable Object)    │
│   renders its seat's view      │              │   SQLite: seats, deals, events, │
│   saves finished boards        │              │           alerts, players       │
│   to localStorage History      │              │   table/core.ts: validate,      │
└───────────────────────────────┘              │   apply, robots, views, score   │
                                                └─────────────────────────────────┘
```

### Joining

1. The host taps **Play with friends**. The app POSTs to `/tables`, which
   creates a Durable Object under a random id and returns the id plus the
   host's **player token**.
2. The app shows a share link: `…/second_highest_bridge/#/t/<tableId>`. The id
   is 128 random bits, so the link is the invitation. It's sent with the
   phone's share sheet (`navigator.share`, with copy-to-clipboard as fallback).
3. A friend opens it, types a display name (1-20 characters, cleaned like an
   alert), picks a free seat, and receives their own player token.
4. Player tokens live in `localStorage` under `shb-tables`, keyed by table id,
   and are sent as the first WebSocket message (never in a URL, so they never
   reach a log or a `Referer`). Reopening the link on the same device takes the
   seat back.
5. The host can **lock** the table (no new players), **move** players between
   seats and **remove** a player. A leaked link can at worst fill an empty
   seat, until the host locks or removes.

### Playing a board

- The host taps **Deal** once at least one human is seated. Empty seats, and
  seats whose player isn't connected, are robots.
- The server deals with `deal(cryptoRandom)` (`deal()` already takes its RNG),
  writes `table_hands`, and runs robot turns until a human must act.
- A human's intent is checked, in this order: the sender holds a token for the
  table; it's their turn, or they're declarer playing dummy; the intent was
  made against the current state (`at` = the last event seq the client had);
  the call or card is legal (`legalCalls`, `legalPlays`). Refused intents get
  an `error` naming why, and change nothing.
- **Who plays which hand**, as at a real table:

  | situation | who plays dummy |
  |---|---|
  | human declarer | that human plays both hands, even if dummy's seat is a friend's |
  | robot declarer, human partner is dummy | the robot plays both; the human watches |
  | human dummy, human declarer | declarer plays; dummy watches |

- **Robot pacing:** each robot action is a separate Durable Object *alarm*,
  about 600 ms after the last event. That paces the table like a real one
  instead of robot calls arriving in a burst, and it keeps each invocation to
  one robot decision, which matters for the CPU limit (see M0).
- **Pauses are the client's business.** The server doesn't wait at the end
  of a trick or the auction. Each client keeps showing the completed trick (1.2
  s, or until tapped, per the player's own fast-play setting), queueing events
  that arrive meanwhile. One slow reader never holds up the table.
- After trick 13 the server scores (`scoreContract`) and sends every client the
  full board as a `HistoryRecord`. Each client saves it to its History, marked
  with the table id, and it replays and exports to LIN like any other board.
- **Next board:** each human taps **Ready**; the next board deals when every
  connected human is ready, or when the host taps **Deal now**.

### What each seat can see

| | before the opening lead | after the opening lead | after the board |
|---|---|---|---|
| own hand | yes | yes | yes |
| dummy | dummy's own player only | everyone | everyone |
| the other hands | no | no | everyone |
| calls and cards played | everyone | everyone | everyone |
| a human's alert | the two opponents | the two opponents | everyone |
| a robot's alert | everyone, pass reasons hidden (`liveAlerts`) | same | everyone, pass reasons too |

A robot's alert shown to its human partner is harmless (ONLINE_PLAN): a robot
can't use unauthorised information. The bidding box's call meanings
(`callMeanings`) need no hidden information and keep running in the browser.

### Leaving and reconnecting

- On reconnect the client sends `hello {token, lastSeq}` and gets a fresh
  snapshot; there is no other recovery path, so there's nothing to get out of
  sync.
- A seat disconnected for **60 seconds** while it's that seat's turn shows the
  others a **Let a robot play** button. A robot then plays the seat, mid-auction
  or mid-play (`aiBidExplained` and `aiPlay` work from any state; the robot
  reads the human's earlier calls as GIB would). The player can **Take my seat
  back** on return, at their next turn.
- If the host leaves, the host role passes to the longest-seated connected
  human.
- A table with no connection for **7 days** deletes itself (an alarm calls
  `deleteAll()`). Finished boards are already in each player's browser.

## Wire protocol

One file, `frontend/src/lib/table/protocol.ts`, imported by both sides.
JSON over the WebSocket; every message has a `type`. Version it from day one
(`v: 1` in `hello`), so a stale cached app gets a clean "please reload".

**Client to server:**

| type | fields | notes |
|---|---|---|
| `hello` | `v`, `token?`, `name?`, `lastSeq?` | first message; no token = spectator of the lobby until `sit` |
| `sit` | `seat` | free seats only; returns a token |
| `stand` | | |
| `deal` | | host, or everyone `ready` |
| `ready` | | after a board |
| `call` | `id`, `at`, `call`, `alert?` | `alert` cleaned with `cleanAlert` on the server too |
| `card` | `id`, `at`, `seat`, `card` | `seat` is own seat or, for declarer, dummy |
| `robot` | `seat` | hand a disconnected seat to a robot |
| `host` | `lock?`, `move?`, `remove?` | host only |

`id` is a client-chosen intent id: a repeated id (a double tap, a resend after
reconnect) is answered with the original outcome and applied once.

**Server to client:**

| type | fields |
|---|---|
| `welcome` | `you: {seat, isHost}`, `snapshot` |
| `snapshot` | table, seats and presence, board, dealer, vulnerability, `events` up to now, your hand, dummy if visible, alerts you may see, `seq` |
| `event` | `seq`, `kind` (`call`/`card`/`dummy`/`result`/`seat`/`presence`), payload filtered for you |
| `error` | `id?`, `code` (`not_your_turn`, `illegal`, `stale`, `locked`, …), `message` |

A client that sees a gap in `seq` asks for a snapshot. Inbound messages are
capped at 2 KB and 20 a second per socket; past either, the socket is closed.

## Storage in the Durable Object (SQLite)

| table | columns |
|---|---|
| `meta` | `id`, `created_at`, `host_player`, `locked`, `board_num`, `status` (`lobby`/`bidding`/`playing`/`done`) |
| `players` | `player_id`, `token_hash` (SHA-256; the token itself is never stored), `name`, `seat` null, `last_seen` |
| `boards` | `board_num`, `dealer`, `vulnerability`, `hands` (JSON, server only), `record` (JSON `HistoryRecord`, once done) |
| `events` | `board_num`, `seq`, `seat`, `kind`, `payload`, `intent_id`; **`unique(board_num, seq)`** and **`unique(intent_id)`** |
| `alerts` | `board_num`, `seq` (of the call), `seat`, `text` |

Visibility is enforced in one function, `viewFor(state, seat)`, not in the
schema, so that one function is what the leak tests hammer.

## Code changes, by area

**Frontend, new:**
- `src/lib/table/core.ts`: the pure table. `TableState` (deal + events),
  `applyIntent(state, seat, intent) → {events} | {error}`, `nextRobotAction`,
  `viewFor(state, seat)`, `finishedRecord(state) → HistoryRecord`. Imports the
  engine; knows nothing of WebSockets or Svelte.
- `src/lib/table/protocol.ts`: the message types above.
- `src/lib/table/remote.svelte.ts`: `RemoteTable`, the client. Holds the
  latest view, the socket, the reconnect loop (backoff 1, 2, 4, 8 s, then
  every 15 s), the trick-display queue and the outbox of unacknowledged
  intents.
- Views: `LobbyView.svelte` (name, seats, share link, lock), a table-only
  strip of who's connected, and **Ready / Let a robot play / Take my seat
  back** buttons.

**Frontend, changed:**
- `game.svelte.ts`: the `HUMAN = 'South'` constant (line 63) and
  `isHumanSeat` (line 336) become a `mySeat` field, `South` by default.
- `tableModel.svelte.ts`: read from a small `TableSource` interface that both
  `Game` and `RemoteTable` implement (phase, hands visible to me, calls,
  alerts, tricks, whose turn, contract, my seat), instead of from `Game`
  directly. The labels "You", "Partner", "LHO", "RHO" come from `mySeat`.
- `FeltTable`, `AuctionFelt`, `TrickFelt`, `SeatBox`/`SeatCard`, `TableView`,
  `DesktopTableView`: replace the literal `'South'` (about 40 places; `grep
  -n "'South'" src/lib/views src/lib/components`) with `mySeat`, and place
  seats with `rotate(seat, mySeat)` → bottom/left/top/right. Result text
  ("to your side, North-South") is phrased from `mySeat`'s side.
- `App.svelte`: a `#/t/<id>` route.
- `saves.ts`: `HistoryRecord` gains optional `table_id` and `my_seat`;
  History shows "your side" from `my_seat` when present.
- `index.html`: the CSP's `connect-src` adds the Worker's `https://` and
  `wss://` origins, nothing else.
- `HowToPlayView` and `AuctionGrid` keep fixed compass order: they describe
  rules and a written record, not your seat.

**Server, new top-level `server/`:**
- `wrangler.toml`: one Worker, one Durable Object class with SQLite storage
  (`new_sqlite_classes` migration), the allowed origins as a variable.
- `src/worker.ts`: routes `POST /tables` and `GET /tables/<id>/ws`; refuses an
  `Origin` other than the Pages site (and `localhost` in dev); per-IP rate
  limit on table creation.
- `src/tableObject.ts`: the WebSocket **Hibernation API** (`acceptWebSocket`,
  tags per player), so idle tables between turns cost no duration;
  persistence of events; `alarm()` for robot turns, the 60 s disconnect
  check and 7-day expiry. All game logic is a call into `table/core.ts`.
- `package.json` with `wrangler` and `@cloudflare/vitest-pool-workers`.

**Not changed:** `frontend/src/lib/engine/` (the server imports it as is, so
the fixture parity with Python covers the server too), the Python code, the
fixtures, solo play, Challenge, LIN.

## Milestones

Each is one PR, merged green, and each leaves the app shippable.

### M0: spike and measure (1-2 days)

- `wrangler` hello-world Durable Object with SQLite and a WebSocket, deployed
  to the user's account at a `*.workers.dev` address.
- Import the engine into it and time, **inside workerd**, the CPU of: one
  `aiBidExplained`, one `aiPlay` at each trick (the five-card endgame search is
  the expensive one), `scoreContract`, and `viewFor`.
- **The risk this retires:** the Workers Free plan caps CPU per invocation
  (10 ms when last documented; check the current pricing page). An average
  robot board is ~40 ms, so most single decisions should fit, but the endgame
  search may not. If the worst decision is over the limit: Workers Paid ($5 a
  month) raises it to seconds, and that's the recommendation, since there is no
  fallback that keeps the hands off the clients.
- **Done when:** a numbers table is added to this doc, and the plan is
  confirmed or amended.

### M1: the table view takes "my seat" (2-3 days, no network)

- `mySeat` through `Game`, `TableSource`, `TableModel` and the views, as above.
- A hidden debug setting (or test-only) seats the solo player anywhere; solo
  stays South.
- **Tests:** `game.test.ts` already renders both layouts at every step; run it
  with `mySeat` in each of the four seats and check the bottom hand is always
  `mySeat`'s, the turn indicator and "You" labels follow it, and South's
  output is byte-identical to today's.
- **Done when:** `npm test` and `npm run check` pass, and solo play looks
  unchanged on a 390x844 phone and at 1200px.

### M2: the pure table core (3-4 days, no network)

- `table/core.ts` and `table/protocol.ts`.
- **Tests (`table/core.test.ts`), the heart of the whole plan:**
  - **Parity with solo:** for 200 seeded deals, a table with one human at South
    making the same calls and cards as a `Game` produces identical robot calls,
    alerts, cards and score. The robots are the same robots.
  - **No leaks:** drive 500 seeded tables with 1-4 humans making random legal
    intents; at *every* step, for every seat, `viewFor` contains no card of
    another hand except dummy after the lead, and no live alert from partner.
    Checked by scanning the serialised view, so a leak through any field fails.
  - **Refusals:** out-of-turn, illegal, stale `at`, dummy played by dummy's
    owner when partner declares, a defender playing dummy: each refused, state
    unchanged.
  - **Idempotency:** replaying any intent id is a no-op.
  - **Records:** every finished table's `HistoryRecord` round-trips through
    `toLin`/`fromLin` to the same score.
  - **Robot takeover** mid-auction and mid-play, and handing the seat back.
- **Done when:** all of the above pass in plain Vitest.

### M3: the server (3-4 days)

- `server/` as above; deploy to `workers.dev`.
- **Tests** with `@cloudflare/vitest-pool-workers` (runs in workerd, real
  SQLite): create, join, sit, a full board with one human and three robots
  over a real socket; reconnect with `lastSeq` gets the same view; a second
  socket with another seat's token is refused; Origin refused; oversized and
  flooding sockets closed; hibernation then wake keeps the board; robot alarms
  fire in order; the expiry alarm deletes.
- CI: a `server` job beside the frontend job in `pages.yml` runs
  `npm ci && npm test` in `server/`. Deploying the Worker stays manual
  (`npx wrangler deploy`) until the release, so no Cloudflare secret goes into
  GitHub before it's needed.
- **Done when:** the tests pass and a board can be played end to end with
  `wscat`.

### M4: the client (4-5 days)

- `RemoteTable`, `LobbyView`, the route, the share link, the CSP change.
- **Play with friends** on the home page, below Play and Challenge.
- The connected-players strip; the reconnect banner ("Reconnecting…", never a
  blank table); Ready; the end-of-board screen reusing the solo one, with
  `HistoryView` and its double dummy analysis.
- **Tests:** a fake socket in Vitest replaying server messages through
  `RemoteTable` (trick queue, gap → snapshot, outbox resend after reconnect);
  `game.test.ts`-style rendering of every step of a remote board in both
  layouts.
- **Done when:** two browser windows on one laptop play a board against
  `wrangler dev`.

### M5: hardening (3-4 days)

- **End-to-end:** Playwright (preinstalled in the cloud sessions) with four
  browser contexts against `wrangler dev` + `vite`: four humans play two full
  boards; one context goes offline mid-trick and comes back; one closes and a
  robot takes the seat; the host leaves and the role passes. Assert in the
  browser that no page ever holds another seat's cards (scan the DOM *and* the
  received messages).
- Phone checks on a real iPhone: Safari suspends sockets when the screen locks,
  so resume on `visibilitychange` as well as on socket close.
- Error copy for every `error.code`; a "table no longer exists" screen.
- **Done when:** the Playwright suite is green in CI three runs in a row.

### M6: release (1 day)

- `wrangler deploy`; the production Worker origin in the CSP; the Pages
  site rebuilt.
- Docs: REQUIREMENTS gains a Multiplayer section (below), and **S4** ("No
  accounts and no server") is restated as: *solo play and Challenge send
  nothing; a table connects to the table server only when you open one.*
  FRONTEND.md gets a Multiplayer entry; HOSTING_AND_LOCAL_SAVES moves live
  tables from "proposed" to "built"; ROADMAP moves the item.
- **Done when:** the user has played a board with a friend on two phones.

**Total: roughly 3-4 weeks of sessions**, most of it M1, M2 and M4. M0 can
stop the plan early, cheaply, if the CPU numbers are bad.

## Requirements to add (REQUIREMENTS.md)

| id | requirement | pri | how we'll know |
|---|---|---|---|
| MP1 | Two to four humans play one board live, robots in the other seats | P0 | Playwright four-context test |
| MP2 | A client never receives a card it couldn't see at a real table | P0 | `core.test.ts` leak scan; Playwright DOM and message scan |
| MP3 | Partner never sees a human's alert while the board is live | P0 | `core.test.ts` |
| MP4 | Every call and card is validated on the server | P0 | `core.test.ts` refusals; server tests |
| MP5 | Robots at a table bid and play exactly as in solo | P1 | `core.test.ts` parity |
| MP6 | A dropped connection resumes the board exactly | P0 | server and Playwright reconnect tests |
| MP7 | A departed player's seat can go to a robot and come back | P1 | `core.test.ts`, Playwright |
| MP8 | Finished table boards appear in each player's History and LIN export | P1 | `core.test.ts` LIN round trip |
| MP9 | Joining needs only a link and a name | P1 | Playwright |
| MP10 | Solo and Challenge make no network calls | P0 | CSP; a test that a solo board opens no socket |

## Security checklist

- Hands exist only in the Durable Object and in `viewFor`'s filtered output.
- Player tokens: 128 random bits, sent in the first message only, stored
  hashed on the server, revocable by the host (remove).
- Every string from a client (names, alerts) is length-limited and cleaned on
  the server, and rendered with Svelte's escaping; `lin.test.ts`'s ban on
  `{@html}` still covers every component.
- `Origin` checked on the WebSocket upgrade and on `POST /tables`.
- Message size and rate limits per socket; table creation rate-limited per IP.
- No Cloudflare secrets in the repo; `wrangler` authenticates on the user's
  machine.
- Pages still can't send `frame-ancestors`; a table page in a hostile frame
  could be clickjacked into a misplay at worst. Acceptable for friends;
  revisit if the site moves to Workers, which can send headers.

## After the first release

In rough order, each its own plan when it's next:
1. **Running score across a table's boards** and **rematch** (cheap: the
   object already has every board).
2. **Accounts** (ONLINE_PLAN Phase 1): Supabase Auth or Workers + D1, still
   undecided. A table then accepts an account token in place of a player token,
   and writes `trusted=true` boards for its players from the object.
3. **Friends** and **invite to my table** (ONLINE_PLAN Phase 2), on accounts.
4. **Claims.** Under second-highest rules a claim is harder to judge by eye
   than in bridge; the double dummy solver could verify one, or opponents
   accept or reject it.
5. **Async duplicate:** friends play the same fresh deals at their own tables
   and compare; one stored deal reused across tables.
6. Chat (short presets first; free text is another escaping surface),
   kibitzers.

## Open questions for the user

1. **Promote to P2 now, or wait for the page counts** (ROADMAP's open
   question)? This plan doesn't change that call; it makes the work ready.
2. **Tables before accounts?** Recommended, and assumed above.
3. **Workers Paid ($5/month)** if M0 shows the endgame search over the Free
   plan's CPU limit?
4. **A custom domain** for the Worker, or `*.workers.dev`? Either works; a
   domain is needed only if the site itself later moves to Workers.
5. The repo must be **public** for Pages to deploy at all (HOSTING); a table
   server pointing at an undeployed site can only be tested locally.
