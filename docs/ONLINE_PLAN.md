# Going online: accounts, saved hands, friends, live tables

Status: **agreed design, nothing built yet.** Backend: Supabase. Front end: the
existing Svelte app in `frontend/`, still deployed to Azure Static Web Apps.
The Streamlit app stays offline as the research/reference app and gets no
accounts.

See also [HOSTING_AND_LOCAL_SAVES.md](HOSTING_AND_LOCAL_SAVES.md): GitHub Pages
as the host, and browser-only saved games before Phase 1.

## What "play with friends" means

Friends sit at **the same table and play the same board live**: as partners,
as opponents, or two to four humans in any seats. **Robots fill the empty
seats.** Every human sees only their own hand (and dummy once it's down),
exactly as at a real table.

## Decisions

| question | decision | consequence |
|---|---|---|
| Sign-in | Email magic link only | No passwords, no OAuth apps to register |
| Trust between friends | **Not trusted** | At a shared table the server deals, holds the hands and validates every call and card |
| Human alerts | Humans alert their own calls | Alerts are a hidden-information channel, stored apart from the event log |
| History visibility | Private by default | `boards` readable by the owner only; sharing is explicit |
| Streamlit app | Stays offline | No changes to `app.py` |

## Principles

1. **Guests lose nothing.** Opening the site still deals a board against three
   robots, entirely in the browser, with no sign-in and no network calls.
2. **One engine.** `frontend/src/lib/engine/` (the TS port held to the Python
   by fixtures) is the rules, robots and scoring everywhere: in the browser
   for solo play, and on the server for shared tables.
3. **At a shared table the browser never holds the deal.** The server deals,
   validates, plays the robots and scores. A client receives only its own hand,
   dummy once it's down, and the public events. Opening dev tools reveals
   nothing, and X-ray is impossible by construction: the cards aren't there to
   show, so no setting needs locking.
4. **Store logs, not state.** `Game` already rebuilds the auction from the
   call list. A table is the deal plus an append-only list of events, and
   everything else is derived from it: the live view, the saved hand, the
   replay, and recovery after a reconnect.

## Two kinds of game

| | where it runs | saved as |
|---|---|---|
| **Solo** (free play and library challenge, as today) | browser | `trusted=false`. The client writes these rows, so they're only as honest as you are, and they're only ever shown to you. |
| **Shared table** | Edge Function | `trusted=true`. Only the server writes these rows; one per seated human. |

Anything another person sees (a friend's table result, any future
leaderboard) reads only `trusted=true` rows.

## Architecture

```
Browser (Svelte, Azure SWA)                       Supabase
┌──────────────────────────────┐                  ┌──────────────────────────────┐
│ Solo / library challenge:     │                  │ Auth (email magic link)      │
│ engine runs locally, as today │                  │                              │
│                               │──supabase-js────▶│ Postgres + Row Level Security│
│ Signed in: save solo boards,  │                  │  profiles, boards, friends,  │
│ history, friends, invites     │                  │  tables, seats, hands,       │
│                               │                  │  events, alerts              │
│ Shared table: send intents,   │──fetch──────────▶│ Edge Function `table-action` │
│ render events, own hand only  │                  │  (Deno, bundled TS engine):  │
│                               │◀──Realtime───────│  validate, apply, run robots │
└──────────────────────────────┘  events, presence└──────────────────────────────┘
```

## Data model (Postgres)

RLS is on for every table. "Owner" means `auth.uid()`. "Server" means the Edge
Function's service role: **no client policy grants these writes at all.**

| table | columns (abridged) | read | write |
|---|---|---|---|
| `profiles` | `id`, `username` unique, `display_name` | signed-in users | owner |
| `boards` | `id`, `user_id`, `kind` (`solo`/`challenge`/`table`), `table_id`, `record jsonb` (`HistoryRecord`), `schema_version`, `trusted bool`, `played_at` | owner | owner inserts `trusted=false`; server inserts `trusted=true` |
| `friendships` | `requester`, `addressee`, `status` (`pending`/`accepted`/`blocked`) | either party | requester inserts; addressee accepts; either removes |
| `tables` | `id`, `host`, `status` (`lobby`/`bidding`/`playing`/`done`/`closed`), `board_num`, `dealer`, `vulnerability` | members and invitees | server |
| `table_invites` | `table_id`, `user_id`, `seat` | host and invitee | server (host asks via the function) |
| `table_seats` | `table_id`, `seat`, `user_id` null (null = robot) | members | server |
| `table_hands` | `table_id`, `board_num`, `seat`, `cards` | **the seated user, own row only** | server |
| `table_events` | `table_id`, `board_num`, `seq`, `seat`, `kind` (`call`/`card`/`dummy`/`result`), `payload` | members | server |
| `table_alerts` | `table_id`, `board_num`, `seq` (of the call), `seat`, `text` | **opponents of the alerting seat**; everyone at the table once the board is done | server |

- **`unique (table_id, board_num, seq)`** makes a double click, or two players
  racing, harmless: the second insert fails.
- **`boards.record` is the `HistoryRecord` shape**, so a board from any source
  replays through the existing `HistoryView` unchanged. `schema_version` lets
  an old record be migrated on read. Storing **LIN** instead
  (`frontend/src/lib/lin.ts`, built and round-trip-tested since this plan was
  written) is the natural alternative: it *is* a deal plus an event log, and
  `fromLin` re-validates a board on every read. A table's `table_events` map
  one-to-one onto LIN's `mb` / `an` / `pc` entries.
- A table plays a **sequence of boards**: dealer and vulnerability rotate as
  in solo play, and after each board the host deals the next one.

### Alerts from humans

The call and its alert are sent together (`{call, alert?}`), as on BBO.
- Opponents see the alert; **partner doesn't**, since reading partner's alerts
  would be unauthorised information. Hence a separate table with its own policy,
  not a field on the public event.
- The text is plain, at most 70 characters (the robot alerts' limit), trimmed,
  and length-checked in a database `check` constraint as well as the form.
- After the board, all alerts (human and robot, including robot pass reasons)
  are visible to everyone at the table, as the result screen does today.
- Robot alerts follow the existing `liveAlerts` rule: no pass reasons while the
  board is live. A robot's alert is shown to everyone, its human partner
  included. A robot can't make use of unauthorised information, so that's
  harmless, and simpler.

## Phases

### Phase 1: accounts + saved hands

- Sign in by email magic link, then pick a username (unique, 3-20 of
  `[a-z0-9_]`, enforced by a `check` constraint).
- Finished solo and challenge boards (including the robots' comparison board)
  are inserted into `boards` with `trusted=false`. A challenge-results row lets
  `dealChallenge()` skip deals already played on any device.
- Boards played as a guest stay in memory. On sign-in, offer to save them.
- History tab: paged from `boards`, newest first, filter by kind; same
  `HistoryView`.
- Profile: username, board counts, challenge record against the robots.
- Front end: `supabase-js`, a `session.svelte.ts` store, a hash router (`#/`,
  `#/history`, `#/profile`, `#/friends`, later `#/table/<id>`).

### Phase 2: friends + live tables

**Friends.** Requests by username; accept, decline, remove, block. The friends
page shows who's online (Realtime **Presence**) and has an "Invite to my table"
button.

**Tables.**
- The host creates a table, picks their seat, and invites friends into seats.
  Uninvited seats are robots. The host can start as soon as at least one human
  is seated; seats whose invitee hasn't arrived yet are played by a robot.
- **Edge Function `table-action`** takes `{table_id, intent}`. Intents:
  `create`, `invite`, `join`, `leave`, `start`/`next_board`, `call {call,
  alert?}`, `card {card}`. For play intents it:
  1. checks the caller is seated and it's their turn (or they're declarer
     playing dummy, including a human declarer whose dummy is a robot's seat);
  2. rebuilds auction and trick state from `table_events` using the engine;
  3. validates with `legalCalls` / `legalPlays`;
  4. appends the event (and the alert row), then **runs robot seats**
     (`aiBidExplained`, `aiPlay` with `visibleHands`) until a human must act;
  5. after the opening lead, appends a `dummy` event carrying dummy's cards;
  6. after trick 13, scores with `scoreContract`, writes a `trusted=true`
     `boards` row for every seated human, and appends `result`.
- Dealing uses `deal(cryptoRandom)`; `deal()` already takes its RNG as a
  parameter. Fresh deals only. The challenge library is public, so it's never
  used at a shared table.
- **Realtime:** clients subscribe to Postgres Changes on `table_events` and
  `table_alerts`. Both respect RLS, so a client is only ever pushed what it may
  read. Presence on the table channel shows who's connected. On reconnect,
  reload the board's events; they're the only state there is.
- **Leaving and disconnects:** a seat whose player is gone for longer than a
  timeout (say 2 minutes) can be handed to a robot by the host; the player can
  retake it on return. If the host leaves, the host role passes to another
  human at the table.
- **The table view stops assuming South.** `Game.isHumanSeat`, `FeltTable`
  and `SeatPanel` take "my seat" and rotate so you're always at the bottom.
  Solo play passes `South` and is unchanged. Who plays which hand follows the
  real rules:

  | situation | who plays dummy |
  |---|---|
  | human declarer | that human plays both hands, even if dummy's seat was a friend's |
  | robot declarer, human partner as dummy | the robot plays both; the human watches |

- At the end of a board, everyone at the table sees all four hands, all
  alerts, the score and a replay (the existing `HistoryView` on the board
  record).

### Phase 3: polish (pick from)

Running score across a table's boards, rematch, kibitzers, claims, chat,
per-board share links (an explicit, revocable `share_token`; private stays the
default), per-user stats, and **asynchronous duplicate** (friends each play the
same fresh deals at their own tables and compare). Phase 2's engine already
supports that; it only needs one stored deal reused across tables.

## Running the engine in an Edge Function

Supabase Edge Functions run on Deno, which doesn't resolve the extensionless
imports (`from './card'`) the Vite code uses. Don't fork the engine:
- add `frontend/src/lib/engine/index.ts` exporting what the server needs;
- an npm script bundles it with esbuild into
  `supabase/functions/_shared/engine.js` (one file, no imports);
- CI rebuilds the bundle and runs fixture games through the *bundled* file, so
  the server can't drift from the port, the same way the port can't drift
  from the Python.

`ai.ts` uses no RNG, so a robot decision on the server is identical to the same
decision in the browser. A robot plays a whole board in ~40 ms on average
(whole library in ~15 s, endgame search included), and one request runs at
most three robot turns before a human must act again, which should sit well
inside Edge Function CPU limits. Measure it early in Phase 2 before relying on
that.

## Security notes

- **Free-text input arrives** (username, display name, alerts). CLAUDE.md
  records that the Streamlit app is XSS-safe *because* it has no text input.
  The Svelte app has no `{@html}`, so Svelte's escaping covers it. Keep it that
  way; add a test that fails if `{@html}` appears under `frontend/src`.
- **CSP** (`frontend/public/staticwebapp.config.json`): `connect-src` adds
  `https://<project>.supabase.co` and `wss://<project>.supabase.co`. Magic
  links are plain navigation, so nothing else changes.
- **The anon key is public by design.** Everything rests on RLS, so every table
  ships with policies *and* a test as a second user: can't read another
  seat's `table_hands`, can't read partner's `table_alerts` while the board is
  live, can't insert a `trusted=true` board, can't read another user's
  `boards`, can't join a table without an invite.
- The service-role key lives only in Edge Function secrets, never in the front
  end or the repo.

## Testing

- **RLS tests** against the local stack (`supabase start`), one per policy, in
  CI.
- **`table-action` tests:** drive tables with one, two and four humans to
  completion, and assert that:
  - no client query or Realtime message ever carries another seat's hand;
  - out-of-turn intents, illegal intents, and dummy played by the wrong player
    are refused;
  - partner never receives a live alert;
  - every human's saved `boards` record replays to the same score.
- Existing suites (`npm test`, the Python tests) are untouched by Phase 1.

## Cost and operations

Supabase's free tier (check current limits) covers a site for friends. But
**free projects pause after about a week of inactivity**; a site meant to stay
up needs the paid tier or a keep-alive ping.

Local development: `supabase start` (Docker) runs Postgres, Auth, Realtime and
Functions locally; `npm run dev` reads `VITE_SUPABASE_URL` /
`VITE_SUPABASE_ANON_KEY` from `frontend/.env.local` (gitignored).

## Before Phase 1

- Create a Supabase project and give me its URL and anon key, or set
  them in `frontend/.env.local` yourself. The service-role key never goes in
  the repo.
- Install Docker Desktop and the Supabase CLI for the local stack and the RLS
  tests.
