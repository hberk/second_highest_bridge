# Shared boards

Every finished board, from anyone who plays on the live site, so the robots can
be studied on more than our own play: where people beat the robots in
Challenge and Bidding training, and which robot contracts go down. Decided by
the user on 2026-11-28: on by default, anonymous, a one-line notice on the home
screen until closed, a switch in Settings, and solo, challenge and training
boards alike.

## What is sent, and when

Once a board is over, never during play: a solo or challenge board when its
last trick is done or it passes out, a training board when its recap appears.
`App.svelte` hands it to `share.ts`, which sends it with `navigator.sendBeacon`
to `POST /boards` on the site's own origin, together with any board an
earlier send couldn't deliver (kept in `localStorage` under `shb-share-queue`,
at most 40). Only the live site sends (`npm run site` sets `VITE_SHARE=1`;
local dev and the tests never do), and only while Settings > **Share finished
boards** is on. Boards loaded from LIN and boards played at a table with
friends are not sent.

A record (`shareRecord.ts`, `SharedBoard`) holds:

| mode | what |
|---|---|
| solo | the board as LIN: hands, calls, play, claim |
| challenge | the LIN, the deal's id in `data/solved_deals.json`, and the grade: your score and the robots', and each side's bidding and play loss against par |
| training | the deal's id in `data/training_deals.json`, the board number (dealer and vulnerability), the calls, and your score, the robots' and par |

and the app's version. **Never**: a name, a player or device id, a cookie, an
address, the alert text (a self-alert is typed text) or a board's label. The
LIN's player names are the seat names.

## What is stored

`server/cf/src/boards.ts` rebuilds each row from the board itself, so a forged
request can't add anything either: the LIN is replayed under this game's rules
(`fromLin`, which refuses an illegal call or card) and written again without
alerts, training calls are replayed, every number is range-checked, the day
comes from the server's clock, and the address is used only for the rate limit
(60 requests an hour) and never stored. A refused board is skipped, never the
batch. Rows go into the D1 database **`bridge_boards`**, table **`boards`**,
which `boards.ts` creates on first use:

| column | holds |
|---|---|
| `day` | the UTC day it arrived |
| `mode` | `solo`, `challenge` or `training` |
| `app` | the app version |
| `deal_id` | challenge and training: the deal's id |
| `board_num`, `dealer`, `vul` | the board |
| `auction` | the calls from the dealer, `P P 1S X ...` |
| `contract`, `declarer` | `4S`, `3NTX`, `2HXX` and `South`; empty when passed out |
| `tricks` | declarer's tricks (empty in training: no play) |
| `ns_score` | N/S's score as played (solo and challenge) |
| `you`, `robot`, `margin` | challenge and training: the player's score, the robots', and the difference (positive: the player did better) |
| `your_bidding_loss`, `your_play_loss`, `robot_bidding_loss`, `robot_play_loss` | challenge: each side's loss against par |
| `par` | training: par on the board |
| `lin` | solo and challenge: the whole board as LIN, to replay in History or research/ |

Free plan: D1 allows 5 GB, 100,000 rows written and 5 million read a day, apart
from the Durable Object allowance the tables use. A row is under 1 KB.

## Setting it up (once)

1. **The deploy token needs D1.** The first deploy creates `bridge_boards`
   itself (Wrangler provisions a D1 binding that has no id), which needs the
   `CLOUDFLARE_API_TOKEN` secret to hold **Account > D1 > Edit**. In the
   Cloudflare dashboard: your profile > **API Tokens** > the deploy token >
   **Edit** > add the permission > **Continue to summary** > **Update token**.
   The token's value doesn't change. Without it the deploy warns that it
   skipped provisioning and is likely to fail.
2. **For the report workflow** (optional): create a second token with only
   **Account > D1 > Read**, and add it as `CLOUDFLARE_D1_TOKEN` in GitHub:
   Settings > Environments > `cloudflare` > **Add environment secret**.

## Looking at the results in Cloudflare

**The dashboard's D1 console** is the quickest way. Sign in at
dash.cloudflare.com, then **Storage & databases > D1 SQL database >
bridge_boards**. **Tables** shows the rows; **Console** runs any SQL, and
these are the useful ones (paste one, press **Execute**):

```sql
-- How many boards came in, per day and mode
SELECT day, mode, COUNT(*) AS boards FROM boards GROUP BY day, mode ORDER BY day DESC;

-- Challenge: do players beat the robot, and where does the robot lose?
SELECT COUNT(*) AS boards, SUM(margin > 0) AS players_won, SUM(margin < 0) AS robot_won,
       ROUND(AVG(margin)) AS avg_margin,
       ROUND(AVG(robot_bidding_loss)) AS robot_bidding_loss, ROUND(AVG(robot_play_loss)) AS robot_play_loss,
       ROUND(AVG(your_bidding_loss)) AS player_bidding_loss, ROUND(AVG(your_play_loss)) AS player_play_loss
FROM boards WHERE mode = 'challenge';

-- The challenge deals where players beat the robot by most
SELECT deal_id, COUNT(*) AS boards, ROUND(AVG(margin)) AS avg_margin,
       ROUND(AVG(robot_bidding_loss)) AS robot_bidding_loss, ROUND(AVG(robot_play_loss)) AS robot_play_loss
FROM boards WHERE mode = 'challenge' GROUP BY deal_id ORDER BY AVG(margin) DESC LIMIT 20;

-- Bidding training: the deals where players out-bid the robots by most
SELECT deal_id, COUNT(*) AS boards, ROUND(AVG(margin)) AS avg_margin, ROUND(AVG(par - robot)) AS robots_short_of_par
FROM boards WHERE mode = 'training' GROUP BY deal_id ORDER BY AVG(margin) DESC LIMIT 20;

-- Contracts the robots declared and went down in (North, East or West declaring)
SELECT contract, COUNT(*) AS played, SUM(tricks < CAST(substr(contract, 1, 1) AS INTEGER) + 6) AS down
FROM boards WHERE declarer IN ('North', 'East', 'West') AND tricks IS NOT NULL
GROUP BY contract ORDER BY down DESC LIMIT 20;

-- One deal's boards in full, to replay: copy a lin value into Hand history > Import
SELECT day, auction, contract, declarer, tricks, margin, lin FROM boards WHERE mode = 'challenge' AND deal_id = 17;
```

The console's queries count against the free reads (5 million a day), which
these come nowhere near.

**The report workflow** prints the same tables without opening the dashboard:
GitHub > Actions > **Shared boards** > **Run workflow** (days to show, 30 by
default). The tables appear on the run's page, and every row is attached as
`boards.jsonl` for research/. Locally: `CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_D1_TOKEN=... npm run boards [days] [--out boards.jsonl]` in
`server/cf`.

## Why this is allowed without a consent banner

The privacy rules (GDPR and the UK's version, the ePrivacy/PECR cookie rules)
cover data that identifies a person, which includes an address or a device id,
and the cookie rules need consent before an app stores an id on the device to
recognise someone. A record here has neither: the cards, calls and scores of a
board, with nothing that links it to a player, another board or a device. So
the notice says plainly what is sent and the switch turns it off; the queue in
`localStorage` holds unsent boards only, never an id. If accounts or per-player
statistics come later, that is the point where consent is needed. (The user's
reading as of 2026-11-28, not legal advice.)

## Tests

- `frontend/src/lib/offline.test.ts` (MP10): with every network API trapped,
  solo, challenge and training boards send nothing; with the app's hooks
  attached, each board is handed over exactly once and only after it is over;
  a record holds no alert, label or name; `share.ts` sends only to `/boards`
  and keeps a board when the send fails; `App.svelte` shares only under
  `VITE_SHARE` and with the setting on.
- `server/cf/test/boards.test.ts`: the row for each mode, the refusals, a
  self-alert's text not surviving, and a batch through the Worker into D1 in
  workerd, with the Origin check and the rate limit.
