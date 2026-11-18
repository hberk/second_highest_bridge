// The table server on Cloudflare (MULTIPLAYER_PLAN.md, M7): this Worker
// routes, and each table is a Durable Object (table-object.ts). The beta
// site is the Worker's static assets, served without running this code;
// only /tables and /healthz come here (wrangler.jsonc, `run_worker_first`).
//
// It checks what the Node server checks (server.ts): the Origin, the table id,
// and how many tables one address creates in an hour.
import { TABLE_ID_RE } from '../../../frontend/src/lib/table/protocol';
import { limitKey } from '../../src/limits';
import { newTableId } from '../../src/tables';
import type { Env } from './env';
import { isResting, logUnrecognised } from './resting';
import { restingSocket } from './table-object';

export { TableObject } from './table-object';
export { Limiter } from './limiter';

const WS_PATH = /^\/tables\/([A-Za-z0-9_-]+)\/ws$/;
const DEV_PATH = /^\/dev\/tables\/([A-Za-z0-9_-]+)\/(stats|rest|expire)$/;

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), {
  status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
});

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    try {
      return await route(req, env);
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

async function route(req: Request, env: Env): Promise<Response> {
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
      return json(201, { id });
    }

    const ws = WS_PATH.exec(path);
    if (ws && req.method === 'GET') {
      if (!TABLE_ID_RE.test(ws[1])) return json(404, { error: 'not found' });
      if (!originOk) return json(403, { error: 'origin' });
      if (req.headers.get('upgrade')?.toLowerCase() !== 'websocket') return json(426, { error: 'websocket only' });
      const headers = new Headers(req.headers);
      headers.set('x-table-id', ws[1]);
      headers.set('x-ip', ip);
      return table(ws[1]).fetch('https://table/ws', { headers });
    }

    const dev = DEV_PATH.exec(path);
    if (dev && env.BRIDGE_DEV === '1') {
      if (dev[2] === 'stats') return json(200, await table(dev[1]).stats());
      if (dev[2] === 'expire') await table(dev[1]).expireNow();
      else await table(dev[1]).simulateLimit();
      return json(200, { ok: true });
    }

    if (path.startsWith('/tables') || path === '/healthz') return json(404, { error: 'not found' });
    return env.ASSETS.fetch(req);
}
