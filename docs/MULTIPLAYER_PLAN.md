# Multiplayer: the build plan

Status, 2026-10-27: **M1-M4 built and tested on the `multiplayer` branch**
(the my-seat views, the table core, the Node server, the client). A board
has been played in a browser by two people and two robots against a local
server. **M5 and M6 wait on the homelab container (LXC 213)**: the first
deploy, phones, Playwright. Where the build differs from the plan below, the
section says so.

The plan turns the agreed design into
milestones the size of a PR, each with its files, tests and a "done when".
Revised the same day with the engine measured in Node
([What a robot costs](#what-a-robot-costs-measured-2026-10-26)), and on
2026-10-27 by the user's call: **the beta runs on the user's homelab**, a
Node server in an LXC behind Caddy at **`bridge.ettamei.com`** (public, the
user's OK, 2026-10-27). Cloudflare is the optional last milestone, taken only
once the beta shows the mode is played
([M7](#m7-optional-move-to-cloudflare)).

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
| Backend (beta) | **One Node 24 process in a homelab LXC, behind Caddy at `bridge.ettamei.com`** (the user's call, 2026-10-27) | Build, test and play the whole mode before committing to a platform. No quotas, no memory cap, and the homelab already serves public apps this way. |
| Backend (later) | **Cloudflare Worker + one Durable Object per table, if the beta earns it** ([M7](#m7-optional-move-to-cloudflare)) | A table is small, stateful and real-time, which is what a Durable Object is. Workers **Free**, no paid fallback, `*.workers.dev` (the user's calls, 2026-10-26): see [The Free plan's budget](#the-free-plans-budget). |
| Keeping the move cheap | **The server is a thin host around `table/core.ts`**, behind one `TableHost` interface (storage, timers, sockets) | The Node host is built now; a Durable Object host is a second implementation, not a rewrite. Same protocol, same SQLite schema. |
| Where the beta frontend lives | **Served by the same Node process**, a build with the server's address in it | Same origin, so no CORS and a one-line CSP. The GitHub Pages site is untouched and still makes no network calls. |
| Accounts first or tables first | **Tables first, by invite link** | Accounts are a separate project (auth, mail, RLS or D1). Friends can play without them, and nothing in the table design depends on them. |
| Solo site | **Stays on GitHub Pages** | Only the table server is new. |
| Where the rules run on the server | **The same `frontend/src/lib/engine/` source**, bundled into the server | esbuild bundles the TypeScript (extensionless imports included) into one `server.js`; wrangler would do the same for M7. |
| Table logic | **A pure TypeScript module, `frontend/src/lib/table/`**, shared by server and tests | Everything that matters (legality, visibility, robots, scoring) is testable in plain Vitest, with no server at all. The host is a thin shell. |
| State | **The deal plus an append-only event log** (ONLINE_PLAN principle 4) | Reconnect, replay and the saved record all derive from it. |
| What a client is sent | **Only what its seat may see, filtered on the server** | Opening dev tools reveals nothing; there's no X-ray to lock. |
| How a client receives it | **A full snapshot on (re)connect, then events** | A board is a few KB, so resending it is cheaper than delta bookkeeping and can't drift. |
| Seat-relative UI | **Every view takes "my seat"** and rotates so you sit at the bottom | Solo passes `South` and is unchanged. Rotating the *deal* instead (everyone thinks they're South) was considered and rejected: compass names would disagree between friends talking about the same board. |

## How a table works

```
Browser at https://bridge.ettamei.com      caddy-pi (.211)     LXC 213 "bridge" (Node 24, :8787)
┌──────────────────────────────┐  HTTPS  ┌──────────────┐    ┌──────────────────────────────────┐
│ the beta build of the app     │────────▶│ path allow-  │───▶│ server.js                        │
│ Solo / Challenge: unchanged,  │  WSS    │ list, TLS,   │    │   static files (/opt/bridge/     │
│ engine runs locally           │◀───────▶│ X-Real-IP    │◀──▶│     public)                      │
│ Table: RemoteTable            │         └──────────────┘    │   POST /tables, /tables/<id>/ws  │
│   sends intents               │                             │   Origin check, rate limits      │
│   renders its seat's view     │                             │   one Table per open table:      │
│   saves finished boards       │                             │     table/core.ts: validate,     │
│   to localStorage History     │                             │     apply, robots, views, score  │
└──────────────────────────────┘                             │   SQLite /var/lib/bridge/        │
                                                              │     bridge.db (WAL)              │
                                                              └──────────────────────────────────┘
```

The server is `core.ts` inside a `TableHost`: storage (append an event, load a
table), a timer (`schedule(table, ms)`, for robot turns and the disconnect and
expiry checks) and sockets (send to a seat, close). The Node host implements
it with `node:sqlite`, `setTimeout` and the `ws` package. A Durable Object host
([M7](#m7-optional-move-to-cloudflare)) would implement the same interface
with the object's SQLite, alarms and the Hibernation API.

### Joining

1. The host taps **Play with friends**. The app POSTs to `/tables`, which
   creates a table under a random id and returns the id plus the host's
   **player token**.
2. The app shows a share link: `https://bridge.ettamei.com/#/t/<tableId>`. The
   id is 128 random bits as unpadded base64url, **exactly 22 characters**
   (Caddy's WebSocket route matches `^/tables/[A-Za-z0-9_-]{22}/ws$`), so the
   link is the invitation. It's sent with the phone's share sheet
   (`navigator.share`, with copy-to-clipboard as fallback).
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

- **Robot pacing:** each robot action is its own `schedule()` tick, about
  600 ms after the last event. That paces the table like a real one instead
  of robot calls arriving in a burst, and keeps each tick to one robot
  decision. On Node a tick runs on the one event loop, so the worst decision
  (235 ms, measured) briefly delays every other table; fine for a few tables,
  and `worker_threads` is the fix if it ever isn't. (On Cloudflare the tick is
  an alarm, never `setTimeout`; see M7.)
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
- A seat whose player has been disconnected for **60 seconds** shows the
  others a **Let a robot play** button (built: at any point in the board, not
  only on that seat's turn). A robot then plays the seat, mid-auction
  or mid-play (`aiBidExplained` and `aiPlay` work from any state; the robot
  reads the human's earlier calls as GIB would). The player can **Take my seat
  back** on return, at their next turn.
- If the host leaves, the host role passes to the longest-seated connected
  human: **seated players only**, never a watcher holding the link.
- **Seats are fixed while a board is played** (`sit` and `stand` are refused
  mid-board): a seat's view includes its hand, so sitting in an empty seat
  would read it. Absence mid-board is `robot` and `reclaim`.
- **Robots play only while someone seated is connected**: a table left to
  robots (or a script's empty table) costs no CPU.
- A table with no connection for **7 days** is deleted (a daily sweep on
  Node; an alarm calling `deleteAll()` on a Durable Object). Finished boards
  are already in each player's browser.
- **Sockets drop routinely**, not only on bad networks: a deploy
  (`systemctl restart`), a container reboot, a phone sleeping, Wi-Fi handing
  over to 5G. Resuming from the token and the event log is the normal path,
  tested as such. Both sides ping every **25 s**, so a dead phone socket is
  noticed and a quiet table isn't cut by a NAT idle timeout. Caddy keeps open
  WebSockets for 10 minutes across its own config reloads
  (`stream_close_delay`).

## Wire protocol

One file, `frontend/src/lib/table/protocol.ts`, imported by both sides.
JSON over the WebSocket; every message has a `type`. Versioned from day one
(`v: 1` in `hello`): a stale cached app gets a clean "please reload" (close
code 4000). `parseClientMessage` accepts only these shapes, with no extra
keys.

**Client to server:**

| type | fields | notes |
|---|---|---|
| `hello` | `v`, `token?` | first message; without a token you see the table as a watcher |
| `join` | `name` | 1-20 characters, cleaned (`cleanName`); the answer is a `welcome` with your token |
| `sit` | `seat` | an empty seat; also how you move between boards |
| `stand` | | your seat goes to a robot |
| `deal` | | after a board: you're ready; the host's deals at once |
| `call` | `id`, `at`, `call`, `alert?` | `alert` cleaned with `cleanAlert` on the server too |
| `card` | `id`, `at`, `seat`, `card` | `seat` is your own or, as declarer, dummy |
| `robot` | `seat` | a seat whose player has been gone 60 s goes to a robot |
| `reclaim` | | take your seat back from the robot |
| `lock` | `locked` | host only |
| `remove` | `player` | host only |
| `ping` | | answered with `pong` |

`id` is a client-chosen intent id: a repeated id (a double tap, a resend after
reconnect) is answered with the original outcome and applied once. `at` is
the number of actions on the board the client saw; anything else is `stale`.

**Server to client:**

| type | fields |
|---|---|
| `welcome` | `playerId` (null for a watcher), `token` (on `join` only) |
| `view` | the seat's whole `TableView`: seats and presence, the board as this seat may see it (`viewFor`), and once it's over its `HistoryRecord` |
| `error` | `id?`, `code` (`not_your_turn`, `illegal`, `stale`, `locked`, `full`, `not_host`, `bad_token`, `version`, …), `message` |
| `pong` | |

**Built differently from the first draft (2026-10-27): a whole view after
every change, not a snapshot plus events.** A view is a few KB and a board
about 60 changes, so a table sends well under a megabyte a board, and there
is no event bookkeeping, no gap detection and no resync path: a reconnect is
the same message as any update. M7 could still move to events if Cloudflare's
costs ever made it worth it.

Inbound messages are capped at 2 KB and 20 a second per socket; past either, the socket is closed.
Open sockets are capped per client address (8), and table creation is
rate-limited per address (10 an hour). The address is the TCP peer, except
that `X-Real-IP` is believed when, and only when, the peer is Caddy
(192.168.169.211).

## Storage (SQLite)

One file, `/var/lib/bridge/bridge.db` on the homelab (path from `BRIDGE_DB`),
in WAL mode; the same tables would sit in each Durable Object under M7. A
`table_id` column leads every key on Node, where one file holds every table.

| table | columns |
|---|---|
| `meta` | `id`, `created_at`, `host_player`, `locked`, `board_num`, `status` (`lobby`/`bidding`/`playing`/`done`) |
| `players` | `player_id`, `token_hash` (SHA-256; the token itself is never stored), `name`, `seat` null, `last_seen` (written on disconnect, not per message) |
| `boards` | `board_num`, `dealer`, `vulnerability`, `hands` (JSON, server only), `record` (JSON `HistoryRecord`, once done) |
| `events` | `board_num`, `seq`, `seat`, `kind`, `payload`, `intent_id`, `alert`; **`primary key (board_num, seq)` `without rowid`** |

Visibility is enforced in one function, `viewFor(state, seat)`, not in the
schema, so that one function is what the leak tests hammer.

The schema is kept lean even on Node, so M7 costs nothing: the events key is
the table itself (`without rowid`), an alert is a column of its call's event
rather than a table of its own, and intent ids are checked against the
current board's events held in memory (a board has ~62) instead of a
`unique(intent_id)` index. A repeated id from an earlier board is answered
`stale`, which is the right answer anyway. (Why it matters on Cloudflare:
[The Free plan's budget](#the-free-plans-budget).)

A table's in-memory state (`TableState`) is lost on a restart (Node: a deploy
or reboot; a Durable Object: hibernation or eviction). The host rebuilds it
from `boards` and `events` before handling anything for that table;
`core.ts` has one `replay(deal, events)` for this, the same function the
tests use. Pending robot ticks are re-derived from the replayed state, never
stored.

Backups: the homelab's nightly 03:30 fleet backup takes a `sqlite3 .backup`
of the file (safe against a live WAL database). Losing it would lose only
unfinished boards; finished ones are in each player's browser.

## What a robot costs (measured 2026-10-26)

200 seeded fresh deals, four robots, the current engine
(`frontend/src/lib/engine/`), each `aiBidExplained` and `aiPlay` timed alone,
in Node 24 on the development desktop: the beta's own runtime. The homelab's
i7-6700 is older, so M3 re-measures on the container; workerd runs the same
V8, so M7 would re-measure there to check, not to discover.

| | median | p95 | p99 | worst | over 10 ms |
|---|---|---|---|---|---|
| a call | 0.02 ms | 0.10 | 0.90 | **189 ms** | 13 of 1,936 |
| a card | 0.03 ms | 9.6 | 58 | **235 ms** | 507 of 10,400 |
| a card at five cards (endgame search) | 2.4 ms | 48 | 90 | 137 ms | 212 of 800 |
| a card at 12 cards (trick 2) | 0.03 ms | 37 | 101 | 214 ms | 83 of 800 |
| `scoreContract` | 0.01 ms | | | 0.17 ms | 0 |
| a whole robot board | 97 ms | 328 | 433 | 470 ms | |

- **188 of 200 boards have at least one decision over 10 ms**, and those
  decisions are 88% of all robot time. The plan's earlier "~40 ms a board"
  was too low.
- Not yet profiled. The slow calls are most likely `doubleIsFree` sampling
  an auction it hasn't seen (cached per auction afterwards). The slow early
  cards can't be the endgame search, which starts at five cards, so they're
  in the declarer and defender planning (`drawTrump`, `defenderSuitPlan`,
  `runLongSuit` and the like). M3 profiles both, for latency only.
- **CPU is not a limit on either host.** The 600 ms robot pacing hides the
  worst decision from the players, and against a Durable Object's 30 s an
  invocation it is under 1%.
- **Memory is the limit that matters, on either host.** The shared position memory
  (`SHARED_POSITIONS`, `POSITION_MEMO_MAX = 600_000` per trump suit) holds on
  to about 1 MB a board. The heap after a forced GC, by boards played:

  | boards | 1 | 10 | 25 | 50 | 100 | 150 | 200 |
  |---|---|---|---|---|---|---|---|
  | retained heap | 16 MB | 26 | 44 | 68 | **122** | 152 | **169** |

  The memo's cap is 600,000 positions per trump suit, five suits, so it keeps
  growing well past 200 boards. The homelab service runs with
  `MemoryMax=512M` and would be killed some hundreds of boards after a
  restart; a Cloudflare isolate has 128 MB, shared by several objects, and
  would go around the hundredth board.
  **The fix: clear the position memory when a board ends.** A position's
  value doesn't depend on who looks or which layout led there (CHALLENGE.md),
  so clearing it changes no card, only the next board's first searches. It
  needs one exported `clearPositionMemo()` in `ai.ts`, mirrored in `ai.py` as
  `clear_position_memo()` so the port stays line for line. The `doubleIsFree`
  cache (`FREE`) is small and keyed by auction; leave it.
- The same growth happens in solo play on a phone. Out of scope here; noted
  for ROADMAP.

**At the table, with the memory cleared (2026-10-27).** `npm run bench` in
`server/` (`src/bench.ts`): 200 seeded robot boards through the table core,
`clearPositionMemo()` as each ends, Node 24 on the development desktop.

| | median | p95 | p99 | worst |
|---|---|---|---|---|
| a call | 0.03 ms | 0.1 | 79 | 150 ms |
| a card | 0.06 ms | 9.9 | 59 | **905 ms** |
| a whole robot board | 108 ms | 331 | 615 | 953 ms |

Retained heap after a forced GC: 5 MB after 1 board, 16 MB after 100,
**25 MB after 200** (169 MB without the clearing). The price is a colder
search at the start of each board: the worst card goes from 235 ms to
905 ms, so a robot very occasionally takes about a second instead of the
600 ms pace.

**On the container (2026-10-28).** The same bench on LXC 213 (1 core, Node
24.22.1), 200 boards in 36 s:

| | median | p95 | p99 | worst |
|---|---|---|---|---|
| a call | 0.04 ms | 0.7 | 141 | 298 ms |
| a card | 0.08 ms | 12.2 | 72 | **1,006 ms** |
| a whole robot board | 133 ms | 425 | 823 | 1,072 ms |

Retained heap 24 MB after 200 boards; peak RSS 146 MB, well under the unit's
`MemoryMax=512M`. One core does a whole robot board in about a tenth of a
second at the median, so a handful of tables never queue behind each other.
To rerun: `node build.mjs bench` in `server/`, copy `dist/bench.js` over,
`node --expose-gc bench.js` there.

## The Free plan's budget

For [M7](#m7-optional-move-to-cloudflare) only; the homelab has no quotas.
Rows written is the one that shapes the schema now: an insert costs a row for
the table plus one per index, so a board is about **115 rows written** (62
events, ~47 `setAlarm`, a few for the board and players).

Daily limits reset at 00:00 UTC. Past one, that kind of operation fails until
the reset, so the table must show a clear "the table server is resting until
<time>" rather than a broken board.

| Free limit | a board costs | so Free carries |
|---|---|---|
| Worker CPU, 10 ms a request | routing only (`POST /tables`, the WebSocket upgrade) | not a constraint |
| Durable Object CPU, 30 s an invocation | worst robot decision 235 ms | not a constraint |
| Memory, 128 MB an isolate | ~1 MB a board until cleared | fine, **with `clearPositionMemo()`** |
| Requests, 100,000 a day (alarms count; incoming WebSocket messages count 1 in 20) | ~47 robot alarms + ~1 for human messages + connects ≈ 50 | ~2,000 boards a day |
| Rows written, 100,000 a day | ~115 (above) | **~850 boards a day: the binding limit** |
| Rows read, 5 million a day | a wake replays one board's events, ~62 | not a constraint |
| Duration, 13,000 GB-s a day | billed only while awake; hibernation-eligible objects aren't billed | ~29 hours of awake objects a day |
| Storage, 5 GB | a board record is a few KB; tables delete themselves after 7 days | not a constraint |

The 7-day expiry already keeps storage bounded. The table creation rate limit
is what keeps a leaked link or a script from spending the day's rows.

## Hosting the beta (homelab)

Built and run by the homelab session; its record is `configs/bridge/` and
`docs/services.md` in the homelab repo (`e:\Claude\Personal\homelab`). Agreed
2026-10-27; the user approved the public name and going public directly.

| | |
|---|---|
| Container | **LXC 213 `bridge`** on the Proxmox node (192.168.169.24): Debian 13, unprivileged, `nesting=1`, 1 core, 1 GB RAM + 512 MB swap, 8 GB rootfs on local-lvm, `onboot=1`, DHCP pinned by a Firewalla reservation. Node 24 from NodeSource; no Docker. |
| Edge | **Caddy on caddy-pi (192.168.169.211)**, vhost `bridge.ettamei.com`, Let's Encrypt TLS. A path allow-list, 404 for everything else: GET/HEAD `/`, `/index.html`, `/assets/*`, `/favicon.ico`, `/favicon.svg`, `/icon-*.png`, `/manifest.webmanifest` (compressed); POST `/tables` (16 KB body cap); GET `^/tables/[A-Za-z0-9_-]{22}/ws$` with `Upgrade: websocket`. `X-Real-IP` set from the peer, no `trusted_proxies`, `stream_close_delay 10m`, upstream keep-alive 4 s. HTTP/3 off. |
| DNS | A Squarespace CNAME to the Firewalla DDNS name, plus a Firewalla rule pointing LAN clients straight at .211. |
| Service | `bridge.service`: `User=bridge` (no login), `ExecStart=/usr/bin/node /opt/bridge/server.js`, `PORT=8787`, `BRIDGE_DB=/var/lib/bridge/bridge.db` (`StateDirectory=bridge`), `Restart=on-failure`, `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `ReadWritePaths=/var/lib/bridge`, `MemoryMax=512M`. |
| Firewall (nftables, in the CT) | 8787 from .211 (Caddy) and .212 (Uptime Kuma) only; SSH from the home LAN and VPN ranges only. |
| Monitoring | Uptime Kuma probes `http://<ct>:8787/healthz` directly (never public) and `https://bridge.ettamei.com/`; alerts to ntfy. Logs in journald. |
| Backup | The .db in the nightly fleet backup, by `sqlite3 .backup`. |

**Deploy** (`server/deploy.sh`, run from the development machine):
`npm run build:beta` in `frontend/` and the esbuild bundle in `server/`, then
a tarball of `server.js` and `public/` over ssh into `/opt/bridge` as
`builder` (the last release kept in `.previous/`), then `sudo systemctl
restart bridge.service` (the only sudo `builder` has), then a check that
`/healthz` answers, run inside the container. The SSH key is a
dedicated one, `~/.ssh/bridge_deploy`, used for nothing else. The database
lives outside `/opt/bridge`, so a deploy can't touch it. A deploy drops
every socket; clients resume (above). First deploy 2026-10-28 (53c4235).
A manual deploy now writes `/opt/bridge/.hold`, which pauses the deploys
from main below; `rm /opt/bridge/.hold` resumes them.

### Deploying from main

Chosen 2026-10-28. The homelab **pulls**; GitHub gets no key and no route in.
A self-hosted runner was ruled out (on a public repo it runs workflow code
inside the house), and so was pushing over SSH (a homelab key in someone
else's repo, and an open SSH port or a VPN for the runner).

1. On a push to main, once `build`, `python-tests` and `server` pass, the
   `release-server` job in `pages.yml` builds the beta site and the server
   bundle as one `bridge.tar.gz` (`server.js`, `public/`, and `VERSION`, the
   full commit). It attests it with `actions/attest-build-provenance`, which
   signs a statement through Sigstore that this workflow built this file from
   this commit. It publishes both files as a prerelease named
   `bridge-<12 hex>`. The last five are kept.
2. In LXC 213, `bridge-pull.timer` runs `server/pull/bridge-pull.mjs` as
   `builder` every five minutes. It installs the newest `bridge-*` release
   only if all of these hold:
   - the download matches the digest GitHub reports for it;
   - `gh attestation verify` passes with the attached bundle, offline, with no
     GitHub login. The certificate identity must be exactly
     `.github/workflows/pages.yml@refs/heads/main` of the repo, the source
     digest the release's commit, and the runner GitHub-hosted;
   - the `VERSION` inside is that commit.

   Then it swaps the files in as `deploy.sh` does, restarts, and checks
   `/healthz`. A release that doesn't come up is rolled back and recorded in
   `/opt/bridge/.failed`, and is never retried.
3. The script and its units live root-owned in `/opt/bridge-pull` and
   `/etc/systemd/system`, so the account that deploys can't loosen its own
   checks.

Tested 2026-10-28 against a fake GitHub API: no release, a correctly signed
file from another repo (gh's own release), and a tampered download are all
refused, and nothing is installed. The first real install waits on this
landing on main.

**What this means:** whoever can merge to `main` decides what runs in LXC 213.
That is why the container is walled off from the LAN on the Proxmox host
(in: Caddy and Uptime Kuma to 8787, SSH from admin hosts; out: DNS and HTTPS
to the internet only), and why `bridge.service` runs under the full systemd
sandbox. Branch protection with required review on `main` is the other half.

**The beta build** (`vite build --mode beta`) differs from the Pages build in
two ways only: "Play with friends" is shown, and the CSP's `connect-src`
adds `wss://bridge.ettamei.com`. The Pages build has neither, so the public
solo site still makes no network calls. Solo History saved on the Pages
origin doesn't appear on `bridge.ettamei.com` (browser storage is per
origin); LIN export and import moves boards between them.

Static files: `/assets/*` are hashed and sent `Cache-Control: immutable`;
`index.html` is `no-cache`, so a deploy reaches phones on their next load.
The `.wasm` solver must be sent as `application/wasm`.

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
- **Alert filtering moves out of Svelte.** `liveAlerts` (line 125, a
  `$derived` keyed on `HUMAN`) and `robotAlerts` (line 293, the alerts robots
  may read: robots' own, never a person's free text) become pure functions in
  a new `src/lib/alerts.ts`, taking the calls, the alerts and the set of human
  seats. `Game` and `table/core.ts` both call them, so the server can't hide
  or show a different set than solo does. The server never imports a
  `.svelte.ts` file.
- `HistoryRecord` moves from `game.svelte.ts` to `saves.ts` (which already
  owns the saved shape), re-exported from `game.svelte.ts` so no import
  breaks.
- `engine/ai.ts` and `ai.py`: `clearPositionMemo()` /
  `clear_position_memo()`, exported, not called by solo play (see
  [What a robot costs](#what-a-robot-costs-measured-2026-10-26)).
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
- `index.html` and `vite.config.ts`: a `beta` mode. Only its build adds
  `wss://bridge.ettamei.com` to the CSP's `connect-src` and shows Play with
  friends ([The beta build](#hosting-the-beta-homelab)).
  `package.json` gains `build:beta`.
- `HowToPlayView` and `AuctionGrid` keep fixed compass order: they describe
  rules and a written record, not your seat.

**Server, new top-level `server/` (as built):**
- `src/tables.ts`: `Tables`, the host around the core. It owns the open
  tables (loaded from the store on first use), each one's connections and
  presence, intent ids answered once, robot ticks (`setTimeout`, one decision
  each), the host hand-off and away checks, persistence after every change,
  and `clearPositionMemo()` as each board ends. A connection is anything
  with `send` and `close`, so it knows neither HTTP nor `ws`. (The plan's
  `TableHost` interface for M7 is this file's storage, timer and socket
  seams; it gets a name when a second host exists.)
- `src/store.ts`: `node:sqlite` in WAL mode: `tables` (meta JSON), `boards`
  (deal, record), `events` (one action a row, `without rowid`).
- `src/server.ts`: `node:http` for the static beta build, `POST /tables`
  and `GET /healthz` (uptime, open tables, sockets; never on Caddy's list),
  `ws` for the table sockets. The Origin check and the per-address limits.
  The page's CSP sent as a header, with `frame-ancestors 'none'`.
- `src/main.ts`: starts it from the environment: `PORT`, `HOST`,
  `BRIDGE_DB`, `PUBLIC_DIR`, `ALLOWED_ORIGINS`, `TRUSTED_PROXY`. SIGTERM closes
  sockets with 1012 so clients reconnect.
- `src/bench.ts`: the robot measurement, `npm run bench`.
- `build.mjs`: esbuild bundles `main.ts` with the engine into one
  `dist/server.js` (only `ws` from npm; bundled too, so the container needs no
  `npm install`), and fails if the challenge deal library rides along.
- `deploy.sh`: as in [Hosting the beta](#hosting-the-beta-homelab); a tarball
  over ssh (no rsync on Windows), health checked from inside the container.
- `package.json` with `ws`, `esbuild`, `vitest`; `npm run dev` runs it here.

**Not changed:** `frontend/src/lib/engine/` apart from `clearPositionMemo()`
(the server imports it as is, so the fixture parity with Python covers the
server too), the fixtures, solo play, Challenge, LIN. The server imports
`card`, `auction`, `ai`, `gib`, `scoring` and `../meanings` (which `ai.ts`
needs for sampling), all plain TypeScript. It must **not** import
`engine/challenge.ts`, whose `$root/data/solved_deals.json` import is a Vite
alias that esbuild (and wrangler) doesn't know and would bundle 400 deals for
nothing; a test in `server/` fails if the bundle contains `solved_deals`.

## Milestones

Each is one PR, merged green, and each leaves the app shippable.

The Cloudflare spike that was M0 is now part of the optional
[M7](#m7-optional-move-to-cloudflare): the homelab has no CPU, memory or
daily limits to retire first, and the Node measurement above already covers
the engine.

### M1: the table view takes "my seat" (2-3 days, no network)

- `mySeat` through `Game`, `TableSource`, `TableModel` and the views, as above.
- A hidden debug setting (or test-only) seats the solo player anywhere; solo
  stays South.
- `src/lib/alerts.ts` (`liveAlerts`, `robotAlerts`) and the `HistoryRecord`
  move, as above.
- `clearPositionMemo()` in `ai.ts` and `ai.py`, with a test that clearing it
  between boards changes no card over 40 seeded boards.
- **Tests:** `game.test.ts` already renders both layouts at every step; run it
  with `mySeat` in each of the four seats and check the bottom hand is always
  `mySeat`'s, the turn indicator and "You" labels follow it, and South's
  output is byte-identical to today's. `alerts.test.ts`: with South the only
  human, both functions give exactly what `Game` gives today, on every step
  of 40 seeded boards.
- **Done when:** `npm test` and `npm run check` pass, and solo play looks
  unchanged on a 390x844 phone and at 1200px.
- **Built 2026-10-27.** Solo play renders exactly as before: 1,420 frames of
  25 seeded boards in both layouts, before and after, differ only in Svelte's
  hydration comments and one space. `game.test.ts` plays from North, East and
  West too. `alerts.test.ts` wasn't written: `Game` now calls `alerts.ts`
  itself, so the render comparison and M2's parity test cover it. Also moved
  out of Svelte, for the server: `ChallengeLogEntry` (to `saves.ts`); the
  trick line (`trickText.ts`) speaks from your seat.

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
- **Built 2026-10-27**, at smaller counts than drafted to keep the suite
  quick: parity over 60 boards, the leak scan over 120 random tables (1-4
  people and a watcher; 2,000+ views checked at every step). Idempotency lives
  in the server (a repeated `at` is `stale` in the core).

### M3: the server, on the homelab (3-4 days)

- `server/` as above, and the first deploy to LXC 213 (`deploy.sh`).
- **Tests** in Vitest against a real server on a random local port, with a
  temporary SQLite file: create, join, sit, a full board with one human and
  three robots over a real socket; reconnect with `lastSeq` gets the same
  view; a second socket with another seat's token is refused; Origin refused;
  oversized, flooding and too-many sockets closed; `X-Real-IP` ignored unless
  the peer is the trusted proxy; **a restart mid-board** (close the server,
  open a new one on the same file) resumes the board with pending robot turns
  re-derived; robot ticks fire in order; the expiry sweep deletes; the bundle
  contains no `solved_deals`.
- **Measure on the container:** `server/bench.ts`, the measurement above
  kept as a script (200 seeded robot boards, a `robotTable`-style loop timing
  each decision), with `clearPositionMemo()` at each board's end: per-decision times
  on the i7-6700, and retained memory flat across boards. Profile the slowest
  calls and cards, for latency only. If memory isn't flat, add a
  `setPositionMemoMax()` and lower the cap for the server; the play doesn't
  change.
- CI: a `server` job beside the frontend job in `pages.yml` runs
  `npm ci && npm test` in `server/`. No homelab key goes into GitHub: since
  2026-10-28 main publishes an attested release and the homelab pulls it
  ([Deploying from main](#deploying-from-main)); `deploy.sh` stays for manual
  deploys.
- **Done when:** the tests pass; `http://<ct>:8787/healthz` answers from the
  LAN while `https://bridge.ettamei.com/healthz` is a 404; and a board can be
  played end to end over `wss://bridge.ettamei.com` with `wscat`.
- **Built 2026-10-27** (`server/`, 12 tests, `npm run bench`). Not yet: the
  first deploy and the measurement on the container, which wait on LXC 213.

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
- **Done when:** two browser windows on one laptop play a board against the
  local server (`vite` + `server` in dev), and two phones play one on
  `bridge.ettamei.com`.
- **Built 2026-10-27**: `remote.svelte.ts`, `RemoteView.svelte` (join,
  seats, share, lock, the strip), the `#/t/<id>` route, the beta build.
  `remote.test.ts` drives it against an in-process server on the real core.
  Two browser tabs (two origins, so two people) played a board against the
  local server, through a server restart in the lobby and a reload in the
  auction. Two phones on `bridge.ettamei.com` wait on the deploy.

### M5: hardening (3-4 days)

- **End-to-end:** Playwright (preinstalled in the cloud sessions) with four
  browser contexts against the local server + `vite`: four humans play two full
  boards; one context goes offline mid-trick and comes back; one closes and a
  robot takes the seat; the host leaves and the role passes. Assert in the
  browser that no page ever holds another seat's cards (scan the DOM *and* the
  received messages).
- Phone checks on a real iPhone: Safari suspends sockets when the screen locks,
  so resume on `visibilitychange` as well as on socket close. And a deploy
  during a live board: every client resumes without a reload.
- Error copy for every `error.code`; a "table no longer exists" screen.
- **Done when:** the Playwright suite is green in CI three runs in a row.

### M6: the friends beta (1 day)

- Friends get links to `bridge.ettamei.com`. The Pages site doesn't change
  and doesn't link to it (the user's call, 2026-10-27).
- Docs: REQUIREMENTS gains a Multiplayer section (below), and **S4** ("No
  accounts and no server") is restated as: *solo play and Challenge send
  nothing; a table connects to the table server only when you open one.*
  FRONTEND.md gets a Multiplayer entry; HOSTING_AND_LOCAL_SAVES records the
  homelab table server as built; ROADMAP moves the item.
- **Done when:** the user has played a board with a friend on two phones.

**Total: roughly 3-4 weeks of sessions**, most of it M1, M2 and M4.

### M7 (optional): move to Cloudflare

Only if the beta shows the mode is played, and the homelab isn't the place
for it. Workers **Free**, no paid fallback, `*.workers.dev` (the user's
calls, 2026-10-26).

- `server/src/cf/`: a second `TableHost`. `wrangler.toml` with one Worker and
  one Durable Object class on SQLite (`new_sqlite_classes`); `worker.ts`
  routes and checks `Origin`; `tableObject.ts` uses the WebSocket
  **Hibernation API** (`acceptWebSocket`, tags per player) so idle tables
  cost no duration, and an **alarm** per robot tick, never `setTimeout` (a
  pending timer keeps the object awake, and on Free every awake second is
  billed). Tests with `@cloudflare/vitest-pool-workers`, the M3 list plus
  hibernation then wake.
- Measure inside workerd: the 200 robot boards, one decision per alarm;
  retained memory per board (128 MB an isolate); rows written per board from
  the SQLite cursor's `rowsWritten`, against the ~115 budgeted. If rows
  written is far over: batch a robot's alarm and its event into one
  transaction, and chain robot turns inside one alarm when no human is
  connected.
- The `resting` error and its screen, for a spent daily limit.
- Moving tables: none. Live tables are short-lived; the switch happens
  between boards, and finished boards are in players' browsers.
- **Done when:** the M3 and M5 suites pass against `wrangler dev`, and the
  beta's address points at the Worker.

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

- Hands exist only in the server's memory and database, and in `viewFor`'s
  filtered output.
- **The server faces the internet from the home network.** It runs
  unprivileged, as a no-login user, under systemd's sandboxing, reachable only
  from Caddy and Uptime Kuma; Caddy passes nothing outside the allow-list.
  It makes no outbound connections and holds no secrets. A compromise of the
  process reaches the container, not the LAN.
- `X-Real-IP` is believed only from Caddy's address; Caddy overwrites any
  client-sent forwarding headers (no `trusted_proxies`).
- **No request ends the process** (from the pre-release review, 2026-10-27):
  every HTTP, upgrade, socket and timer handler is caught and logged; a
  target that isn't a path (`//`) is a 400; the static files are a fixed map
  read at start, so no URL grows the memory; a stored table that doesn't
  load is one lost table, and a robot that throws stops its table only.
- The server refuses to start without `TRUSTED_PROXY` and `PUBLIC_DIR`
  (`BRIDGE_DEV=1` allows it on a development machine), and the per-address
  limits count an IPv6 /64 as one address.
- The deploy key is dedicated and can do one privileged thing: restart
  `bridge.service`.
- Player tokens: 128 random bits, sent in the first message only, stored
  hashed on the server, revocable by the host (remove).
- Every string from a client (names, alerts) is length-limited and cleaned on
  the server, and rendered with Svelte's escaping; `lin.test.ts`'s ban on
  `{@html}` still covers every component.
- `Origin` checked on the WebSocket upgrade and on `POST /tables`.
- Message size and rate limits per socket; table creation rate-limited per IP.
- No secrets in the repo: the deploy key stays on the development machine;
  under M7, `wrangler` authenticates there too.
- The beta server sends its own headers, so it sends the CSP as a header and
  `frame-ancestors 'none'`, which Pages can't: no clickjacking a table.

## After the first release

In rough order, each its own plan when it's next:
1. **Running score across a table's boards** and **rematch** (cheap: the
   server already has every board).
2. **Accounts** (ONLINE_PLAN Phase 1): Supabase Auth or Workers + D1, still
   undecided. A table then accepts an account token in place of a player token,
   and writes `trusted=true` boards for its players from the server.
3. **Friends** and **invite to my table** (ONLINE_PLAN Phase 2), on accounts.
4. **Claims.** Under second-highest rules a claim is harder to judge by eye
   than in bridge; the double dummy solver could verify one, or opponents
   accept or reject it.
5. **Async duplicate:** friends play the same fresh deals at their own tables
   and compare; one stored deal reused across tables.
6. Chat (short presets first; free text is another escaping surface),
   kibitzers.

## Open questions for the user

Answered:
- **If it moves to Cloudflare:** Workers **Free**, no paid fallback;
  `*.workers.dev` (2026-10-26).
- **The beta:** on the homelab, at `bridge.ettamei.com`, public from the
  start (2026-10-27).
- **The Pages site doesn't link to the beta** (2026-10-27): only people given
  the address find it, for now.

Still open:
1. **Promote to P2 now, or wait for the page counts** (ROADMAP's open
   question)? Work started on the `multiplayer` branch on 2026-10-26; ROADMAP
   should say so when M1 merges.
2. **Tables before accounts?** Recommended, and assumed above.
