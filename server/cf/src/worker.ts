// The table server on Cloudflare (MULTIPLAYER_PLAN.md, M7): this Worker
// routes, and each table is a Durable Object (table-object.ts). The beta
// site is the Worker's static assets, served without running this code;
// only /tables, /healthz, /visit and /boards come here (wrangler.jsonc, `run_worker_first`).
//
// It checks what the Node server checks (server.ts): the Origin, the table id,
// and how many tables one address creates in an hour.
import { TABLE_ID_RE } from '../../../frontend/src/lib/table/protocol';
import { limitKey } from '../../src/limits';
import { newTableId } from '../../src/tables';
import type { Env } from './env';
import { isResting, logUnrecognised } from './resting';
import { restingSocket } from './table-object';
import { recordVisit, type VisitEvent } from './visits';
import { storeBoards } from './boards';

export { TableObject } from './table-object';
export { Limiter } from './limiter';

const WS_PATH = /^\/tables\/([A-Za-z0-9_-]+)\/ws$/;
const DEV_PATH = /^\/dev\/tables\/([A-Za-z0-9_-]+)\/(stats|rest|expire)$/;

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), {
  status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
});

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    try {
      return await route(req, env, ctx);
    } catch (e) {
      // A call into a Durable Object past the day's allowance throws.
      const path = new URL(req.url).pathname;
      if (isResting(e)) {
        if (WS_PATH.test(path) && req.headers.get('upgrade')?.toLowerCase() === 'websocket') return restingSocket();
        return json(503, { error: 'resting' });
      }
      logUnrecognised(`${req.method} ${path}`, e);
      return json(500, { error: 'server' });
    }
  },
} satisfies ExportedHandler<Env>;

async function route(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const count = (event: VisitEvent, referrer = '') => ctx.waitUntil(recordVisit(env.VISITS, event, req, referrer));
    const path = new URL(req.url).pathname;
    const origins = env.ALLOWED_ORIGINS.split(',').map((s) => s.trim()).filter(Boolean);
    const originOk = origins.includes(req.headers.get('origin') ?? '');
    const ip = limitKey(req.headers.get('cf-connecting-ip') ?? '');
    const table = (id: string) => env.TABLES.get(env.TABLES.idFromName(id));

    if (path === '/healthz' && req.method === 'GET') {
      // One call into a Durable Object: past the day's allowance it fails,
      // and the app, asking here after failed connects, shows "resting".
      // Any failure counts, so an error whose wording isResting doesn't know
      // still reads as resting here; it is logged for resting.ts.
      try {
        await env.LIMITER.get(env.LIMITER.idFromName('limiter')).ping();
      } catch (e) {
        if (!isResting(e)) logUnrecognised('healthz', e);
        return json(503, { error: 'resting' });
      }
      return json(200, { ok: true });
    }

    if (path === '/tables' && req.method === 'POST') {
      if (!originOk) return json(403, { error: 'origin' });
      const limiter = env.LIMITER.get(env.LIMITER.idFromName('limiter'));
      if (!await limiter.allow(ip, Number(env.CREATES_PER_HOUR ?? 10))) {
        return json(429, { error: 'Too many new tables; try again later.' });
      }
      const id = newTableId();
      if (!await table(id).create(id)) return json(500, { error: 'server' });
      count('create');
      return json(201, { id });
    }

    if (path === '/visit' && req.method === 'POST') {
      // The beta page's beacon on load (App.svelte): a page view by a browser
      // that ran the app, so link previews and crawlers aren't counted, and
      // the page itself stays a static asset (it loads even when the day's
      // Worker requests are spent, to say "resting").
      // Its body is document.referrer, read now: not after the response.
      const referrer = (await req.text()).slice(0, 500);
      if (originOk) count('view', referrer);
      return new Response(null, { status: 204, headers: { 'cache-control': 'no-store' } });
    }

    if (path === '/boards' && req.method === 'POST') {
      // A finished board or a few, from the app once each board is over
      // (frontend/src/lib/share.ts), anonymous: boards.ts stores what the
      // board itself says, never who sent it. A beacon reads no answer.
      const text = (await req.text()).slice(0, 64_000);
      if (!originOk || !env.BOARDS) return new Response(null, { status: 204 });
      const limiter = env.LIMITER.get(env.LIMITER.idFromName('limiter'));
      if (!await limiter.allow(`boards:${ip}`, Number(env.BOARDS_PER_HOUR ?? 60))) return json(429, { error: 'later' });
      try {
        return json(200, await storeBoards(env.BOARDS, text));
      } catch (e) {
        console.error('boards not stored:', e);
        return json(500, { error: 'server' });
      }
    }

    if (path === '/dev/boards' && req.method === 'GET' && env.BRIDGE_DEV === '1' && env.BOARDS) {
      return json(200, (await env.BOARDS.prepare('SELECT * FROM boards ORDER BY id').all()).results);
    }

    const ws = WS_PATH.exec(path);
    if (ws && req.method === 'GET') {
      if (!TABLE_ID_RE.test(ws[1])) return json(404, { error: 'not found' });
      if (!originOk) return json(403, { error: 'origin' });
      if (req.headers.get('upgrade')?.toLowerCase() !== 'websocket') return json(426, { error: 'websocket only' });
      const headers = new Headers(req.headers);
      headers.set('x-table-id', ws[1]);
      headers.set('x-ip', ip);
      count('join');
      return table(ws[1]).fetch('https://table/ws', { headers });
    }

    const dev = DEV_PATH.exec(path);
    if (dev && env.BRIDGE_DEV === '1') {
      if (dev[2] === 'stats') return json(200, await table(dev[1]).stats());
      if (dev[2] === 'expire') await table(dev[1]).expireNow();
      else await table(dev[1]).simulateLimit();
      return json(200, { ok: true });
    }

    if (path.startsWith('/tables') || path === '/healthz' || path === '/visit' || path === '/boards') return json(404, { error: 'not found' });
    return env.ASSETS.fetch(req);
}
