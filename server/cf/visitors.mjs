// The Cloudflare site's visitor counts (src/visits.ts), read back from
// Analytics Engine's SQL API and printed as Markdown tables:
//
//   CLOUDFLARE_ACCOUNT_ID=... CLOUDFLARE_ANALYTICS_TOKEN=... npm run visitors [days]
//
// The token needs only Account > Account Analytics > Read. The "Visitor
// counts" workflow (.github/workflows/visitors.yml) runs this with the
// `cloudflare` environment's secrets and shows the tables on its run page.
// Analytics Engine keeps three months; `days` is 30 by default.
const account = process.env.CLOUDFLARE_ACCOUNT_ID;
const token = process.env.CLOUDFLARE_ANALYTICS_TOKEN;
const days = Math.max(1, Math.min(90, Number(process.argv[2] ?? 30) || 30));
if (!account || !token) {
  console.error('Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_ANALYTICS_TOKEN (Account Analytics: Read).');
  process.exit(1);
}

async function sql(query) {
  const res = await fetch(`https://api.cloudflare.com/client/v4/accounts/${account}/analytics_engine/sql`, {
    method: 'POST', headers: { authorization: `Bearer ${token}` }, body: `${query} FORMAT JSON`,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`Analytics Engine answered ${res.status}: ${text.slice(0, 300)}`);
  return JSON.parse(text).data;
}

const since = `timestamp > NOW() - INTERVAL '${days}' DAY`;
// blob1 event, blob2 country, blob3 the day's visitor mark, blob4 referrer
// (visits.ts, BLOBS). _sample_interval undoes sampling, which only starts
// far above this site's traffic.
const [byVisitor, countries, referrers] = await Promise.all([
  sql(`SELECT toStartOfInterval(timestamp, INTERVAL '1' DAY) AS day, blob1 AS event, blob3 AS visitor,
       SUM(_sample_interval) AS n FROM bridge_visits WHERE ${since} GROUP BY day, event, visitor`),
  sql(`SELECT blob2 AS country, SUM(_sample_interval) AS n FROM bridge_visits
       WHERE ${since} AND blob1 = 'view' GROUP BY country ORDER BY n DESC LIMIT 15`),
  sql(`SELECT blob4 AS referrer, SUM(_sample_interval) AS n FROM bridge_visits
       WHERE ${since} AND blob1 = 'view' AND blob4 != '' GROUP BY referrer ORDER BY n DESC LIMIT 15`),
]);

const perDay = new Map();
const row = (day) => perDay.get(day) ?? perDay.set(day, { view: 0, visitors: new Set(), create: 0, join: 0, players: new Set() }).get(day);
for (const r of byVisitor) {
  const d = row(String(r.day).slice(0, 10));
  const n = Number(r.n);
  if (r.event === 'view') { d.view += n; d.visitors.add(r.visitor); }
  if (r.event === 'create') d.create += n;
  if (r.event === 'join') { d.join += n; d.players.add(r.visitor); }
}

const lines = [`## Visitors, last ${days} days (UTC)`, ''];
lines.push('| day | page views | visitors | tables created | players at a table |', '|---|--:|--:|--:|--:|');
const total = { view: 0, create: 0 };
for (const [day, d] of [...perDay].sort(([a], [b]) => b.localeCompare(a))) {
  lines.push(`| ${day} | ${d.view} | ${d.visitors.size} | ${d.create} | ${d.players.size} |`);
  total.view += d.view; total.create += d.create;
}
if (!perDay.size) lines.push('| (nothing yet) | | | | |');
lines.push("", `In all: ${total.view} page views, ${total.create} tables created. Visitors are counted per day, so a`,
  'person who comes back tomorrow counts again.', '');
lines.push('### Countries (page views)', '', '| country | views |', '|---|--:|',
  ...countries.map((r) => `| ${r.country || '?'} | ${r.n} |`), '');
lines.push('### Came from', '', '| site | views |', '|---|--:|',
  ...(referrers.length ? referrers.map((r) => `| ${r.referrer} | ${r.n} |`) : ['| (no outside links yet) | |']), '');
console.log(lines.join('\n'));
