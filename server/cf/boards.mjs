// The shared finished boards (src/boards.ts), read back from D1 over
// Cloudflare's API and printed as Markdown tables; `--out file.jsonl` also
// writes every row in the window, one JSON object a line, for research/.
//
//   CLOUDFLARE_ACCOUNT_ID=... CLOUDFLARE_D1_TOKEN=... npm run boards [days] [--out boards.jsonl]
//
// The token needs only Account > D1 > Read. The "Shared boards" workflow
// (.github/workflows/boards.yml) runs this with the `cloudflare` environment's
// secrets, shows the tables on its run page and attaches the rows. The same
// queries can be pasted into the dashboard's D1 console (docs/SHARED_BOARDS.md).
import { writeFileSync } from 'node:fs';

const account = process.env.CLOUDFLARE_ACCOUNT_ID;
const token = process.env.CLOUDFLARE_D1_TOKEN;
const args = process.argv.slice(2);
const outAt = args.indexOf('--out');
const out = outAt >= 0 ? args.splice(outAt, 2)[1] : null;
const days = Math.max(1, Math.min(3650, Number(args[0] ?? 30) || 30));
if (!account || !token) {
  console.error('Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_D1_TOKEN (Account > D1 > Read).');
  process.exit(1);
}

const api = `https://api.cloudflare.com/client/v4/accounts/${account}/d1/database`;
async function call(url, init) {
  const res = await fetch(url, { ...init, headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' } });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.success === false) throw new Error(`D1 answered ${res.status}: ${JSON.stringify(body.errors ?? body).slice(0, 300)}`);
  return body.result;
}
const dbs = await call(`${api}?name=bridge_boards`);
const db = dbs.find((d) => d.name === 'bridge_boards');
if (!db) {
  console.log('No `bridge_boards` database yet: the deploy makes it, and the first shared board makes its table.');
  process.exit(0);
}
async function sql(query, params = []) {
  const [r] = await call(`${api}/${db.uuid}/query`, { method: 'POST', body: JSON.stringify({ sql: query, params }) });
  return r.results;
}

const since = `day >= date('now', '-${days} days')`;
const n = (v, d = 0) => (v === null || v === undefined ? '' : Number(v).toFixed(d));
const table = (head, rows) => [`| ${head.join(' | ')} |`, `|${head.map((_, i) => (i ? '--:' : '---')).join('|')}|`,
  ...(rows.length ? rows.map((r) => `| ${r.join(' | ')} |`) : [`| (none yet) |${head.slice(1).map(() => ' |').join('')}`])];

let perDay;
try {
  perDay = await sql(`SELECT day, mode, COUNT(*) AS n FROM boards WHERE ${since} GROUP BY day, mode ORDER BY day DESC`);
} catch (e) {
  if (/no such table/.test(String(e))) {
    console.log('No boards shared yet: the table is made when the first one arrives.');
    process.exit(0);
  }
  throw e;
}
const [challenge, deals, training, trainingDeals, downs] = await Promise.all([
  sql(`SELECT COUNT(*) AS n, AVG(margin) AS margin, SUM(margin > 0) AS won, SUM(margin < 0) AS lost,
       AVG(your_bidding_loss) AS ybl, AVG(your_play_loss) AS ypl, AVG(robot_bidding_loss) AS rbl, AVG(robot_play_loss) AS rpl
       FROM boards WHERE mode = 'challenge' AND ${since}`),
  sql(`SELECT deal_id, COUNT(*) AS n, AVG(margin) AS margin, AVG(robot_bidding_loss) AS rbl, AVG(robot_play_loss) AS rpl
       FROM boards WHERE mode = 'challenge' AND ${since} GROUP BY deal_id ORDER BY AVG(margin) DESC LIMIT 15`),
  sql(`SELECT COUNT(*) AS n, AVG(you) AS you, AVG(robot) AS robot, AVG(par) AS par, SUM(margin > 0) AS won, SUM(margin < 0) AS lost
       FROM boards WHERE mode = 'training' AND ${since}`),
  sql(`SELECT deal_id, COUNT(*) AS n, AVG(margin) AS margin, AVG(par - robot) AS robot_short
       FROM boards WHERE mode = 'training' AND ${since} GROUP BY deal_id ORDER BY AVG(margin) DESC LIMIT 15`),
  sql(`SELECT contract, COUNT(*) AS played, SUM(tricks < CAST(substr(contract, 1, 1) AS INTEGER) + 6) AS down
       FROM boards WHERE mode IN ('solo', 'challenge') AND declarer IN ('North', 'East', 'West') AND ${since}
       GROUP BY contract HAVING played >= 3 ORDER BY 1.0 * down / played DESC, played DESC LIMIT 15`),
]);

const byDay = new Map();
for (const r of perDay) {
  const d = byDay.get(r.day) ?? byDay.set(r.day, { solo: 0, challenge: 0, training: 0 }).get(r.day);
  d[r.mode] = r.n;
}
const c = challenge[0], t = training[0];
const lines = [`## Shared boards, last ${days} days (UTC)`, ''];
lines.push(...table(['day', 'solo', 'challenge', 'training'], [...byDay].map(([day, d]) => [day, d.solo, d.challenge, d.training])), '');
lines.push('### Challenge: players against the robot', '',
  `${c.n} boards: players beat the robot on ${c.won ?? 0}, lost on ${c.lost ?? 0}; average margin ${n(c.margin, 1)} (positive: the player did better).`, '',
  ...table(['loss against par (average)', 'bidding', 'play'], c.n ? [['players', n(c.ybl, 1), n(c.ypl, 1)], ['robot', n(c.rbl, 1), n(c.rpl, 1)]] : []), '');
lines.push('Deals where players beat the robot most (data/solved_deals.json ids):', '',
  ...table(['deal', 'boards', 'avg margin', 'robot bidding loss', 'robot play loss'],
    deals.map((r) => [r.deal_id, r.n, n(r.margin), n(r.rbl), n(r.rpl)])), '');
lines.push('### Bidding training', '',
  `${t.n} boards: players' average ${n(t.you)}, the robots' ${n(t.robot)}, par ${n(t.par)}; players beat the robots on ${t.won ?? 0}, lost on ${t.lost ?? 0}.`, '',
  'Deals where players out-bid the robots most (data/training_deals.json ids):', '',
  ...table(['deal', 'boards', 'avg margin', 'robots short of par'], trainingDeals.map((r) => [r.deal_id, r.n, n(r.margin), n(r.robot_short)])), '');
lines.push('### Robot declarers: contracts that go down most (3 or more boards)', '',
  ...table(['contract', 'played', 'down', 'share'], downs.map((r) => [r.contract, r.played, r.down, `${n(100 * r.down / r.played)}%`])), '');
console.log(lines.join('\n'));

if (out) {
  const rows = await sql(`SELECT * FROM boards WHERE ${since} ORDER BY id`);
  writeFileSync(out, rows.map((r) => JSON.stringify(r)).join('\n') + (rows.length ? '\n' : ''));
  console.error(`${rows.length} rows written to ${out}`);
}
