// The table server's HTTP and WebSocket front end, for Node: static files
// for the beta build, POST /tables, the table sockets, and /healthz. Caddy
// sits in front (TLS, a path allow-list); this checks again what matters:
// the Origin, message sizes and rates, sockets and tables per address.
//
// No request may end the process: every handler is caught and logged, the
// static files are a fixed map read at start, and a target that isn't a
// path (`//`) is a 400, not a throw.
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { extname, join, relative, resolve, sep } from 'node:path';
import type { Duplex } from 'node:stream';
import { WebSocketServer, type WebSocket } from 'ws';
import { MAX_MESSAGE_BYTES, TABLE_ID_RE } from '../../frontend/src/lib/table/protocol';
import { Store } from './store';
import { Tables, realClock, type Clock } from './tables';

export interface Options {
  port: number;
  host?: string;
  dbPath: string;
  /** The beta build's files; none served when unset. */
  publicDir?: string;
  /** Origins allowed to open a table: `https://bridge.ettamei.com`. */
  allowedOrigins: string[];
  /** The reverse proxy's address: only from it is X-Real-IP believed. */
  trustedProxy?: string;
  clock?: Clock;
  /** Tables one address may create in an hour. */
  createsPerHour?: number;
  /** Sockets one address may hold open. */
  socketsPerAddress?: number;
  /** The robots' pace (600 ms); the tests shorten it. */
  robotDelayMs?: number;
}

/** Both sides ping this often, so a dead phone socket is noticed. */
export const PING_MS = 25_000;

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.wasm': 'application/wasm', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon',
  '.webmanifest': 'application/manifest+json', '.json': 'application/json', '.txt': 'text/plain; charset=utf-8',
};

const WS_PATH = /^\/tables\/([A-Za-z0-9_-]+)\/ws$/;

/** `::ffff:192.168.1.2` and `192.168.1.2` are the same peer. */
const bare = (ip: string | undefined) => (ip ?? '').replace(/^::ffff:/, '');

/** What the per-address limits count: an IPv4 address, or an IPv6 /64
 *  (one home or phone holds a whole /64 and can rotate within it). */
export function limitKey(ip: string): string {
  if (!ip.includes(':')) return ip;
  const [head, tail = ''] = ip.toLowerCase().split('::');
  const left = head ? head.split(':') : [];
  const right = tail ? tail.split(':') : [];
  const groups = [...left, ...Array<string>(Math.max(0, 8 - left.length - right.length)).fill('0'), ...right];
  return `${groups.slice(0, 4).map((g) => g.replace(/^0+(?=.)/, '')).join(':')}::/64`;
}

/** The request's path, or null for a target that isn't one (`//x`,
 *  `http://...`, `*`): never a throw. */
export function pathOf(target: string | undefined): string | null {
  if (!target || !target.startsWith('/') || target.startsWith('//')) return null;
  try {
    return new URL(target, 'http://x').pathname;
  } catch {
    return null;
  }
}

/** Every file of the build, read once at start. Requests are served from
 *  this fixed map: no request touches the disk, and none can grow it. */
function loadFiles(dir: string | null): Map<string, Buffer> {
  const files = new Map<string, Buffer>();
  if (!dir) return files;
  const walk = (d: string) => {
    for (const name of readdirSync(d)) {
      const full = join(d, name);
      if (statSync(full).isDirectory()) walk(full);
      else files.set(`/${relative(dir, full).split(sep).join('/')}`, readFileSync(full));
    }
  };
  walk(dir);
  return files;
}

export const log = (what: string, e: unknown) => console.error(`${new Date().toISOString()} ${what}:`, e);

export async function startServer(o: Options): Promise<{ port: number; close(): Promise<void>; tables: Tables }> {
  const clock = o.clock ?? realClock;
  const store = new Store(o.dbPath);
  const tables = new Tables(store, clock, undefined, o.robotDelayMs);
  const createsPerHour = o.createsPerHour ?? 10;
  const socketsPerAddress = o.socketsPerAddress ?? 8;
  const creates = new Map<string, number[]>();
  const socketsByIp = new Map<string, number>();
  const started = clock.now();
  const files = loadFiles(o.publicDir ? resolve(o.publicDir) : null);

  const wss = new WebSocketServer({ noServer: true, maxPayload: MAX_MESSAGE_BYTES });

  /** The client's address for the limits: the peer, or what Caddy says when
   *  Caddy is the peer. */
  function clientIp(req: IncomingMessage): string {
    const peer = bare(req.socket.remoteAddress);
    const real = req.headers['x-real-ip'];
    if (o.trustedProxy && peer === o.trustedProxy && typeof real === 'string' && real) return limitKey(bare(real.trim()));
    return limitKey(peer);
  }

  const originOk = (req: IncomingMessage) => o.allowedOrigins.includes(String(req.headers.origin ?? ''));

  const connectSrc = o.allowedOrigins.map((x) => x.replace(/^http/, 'ws')).join(' ');
  const CSP = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
    + `img-src 'self' data:; connect-src 'self' ${connectSrc}; object-src 'none'; base-uri 'self'; `
    + "form-action 'none'; frame-ancestors 'none'";

  function json(res: ServerResponse, status: number, body: unknown): void {
    res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(JSON.stringify(body));
  }

  function serveStatic(req: IncomingMessage, res: ServerResponse, path: string): void {
    const name = path === '/' ? '/index.html' : path;
    const body = files.get(name);
    if (!body) return json(res, 404, { error: 'not found' });
    const headers: Record<string, string> = {
      'content-type': TYPES[extname(name)] ?? 'application/octet-stream',
      'x-content-type-options': 'nosniff',
      'referrer-policy': 'no-referrer',
      'cache-control': name.startsWith('/assets/') ? 'public, max-age=31536000, immutable' : 'no-cache',
    };
    if (name.endsWith('.html')) {
      headers['content-security-policy'] = CSP;
      headers['x-frame-options'] = 'DENY';
    }
    res.writeHead(200, headers);
    res.end(req.method === 'HEAD' ? undefined : body);
  }

  function handle(req: IncomingMessage, res: ServerResponse): void {
    const path = pathOf(req.url);
    if (path === null) return json(res, 400, { error: 'bad request' });
    if (path === '/healthz' && req.method === 'GET') {
      return json(res, 200, {
        ok: true, uptime_s: Math.round((clock.now() - started) / 1000),
        open_tables: tables.openTables, sockets: tables.sockets,
      });
    }
    if (path === '/tables' && req.method === 'POST') {
      req.resume();
      if (!originOk(req)) return json(res, 403, { error: 'origin' });
      const ip = clientIp(req);
      const now = clock.now();
      const recent = (creates.get(ip) ?? []).filter((t) => now - t < 3600_000);
      if (recent.length >= createsPerHour) return json(res, 429, { error: 'Too many new tables; try again later.' });
      recent.push(now);
      creates.set(ip, recent);
      return json(res, 201, { id: tables.create() });
    }
    if (req.method === 'GET' || req.method === 'HEAD') return serveStatic(req, res, path);
    json(res, 404, { error: 'not found' });
  }

  const http = createServer((req, res) => {
    try {
      handle(req, res);
    } catch (e) {
      log('request', e);
      if (!res.headersSent) json(res, 500, { error: 'server' });
      else res.destroy();
    }
  });

  function refuse(socket: Duplex, status: number, text: string): void {
    socket.end(`HTTP/1.1 ${status} ${text}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n`);
  }

  function upgrade(req: IncomingMessage, socket: Duplex, head: Buffer): void {
    const match = WS_PATH.exec(pathOf(req.url) ?? '');
    if (!match || !TABLE_ID_RE.test(match[1])) return refuse(socket, 404, 'Not Found');
    if (!originOk(req)) return refuse(socket, 403, 'Forbidden');
    const ip = clientIp(req);
    if ((socketsByIp.get(ip) ?? 0) >= socketsPerAddress) return refuse(socket, 429, 'Too Many Requests');
    const id = match[1];
    if (!tables.exists(id)) return refuse(socket, 404, 'Not Found');
    wss.handleUpgrade(req, socket, head, (ws: WebSocket) => {
      const handlers = tables.open(id, {
        send: (text) => { if (ws.readyState === ws.OPEN) ws.send(text); },
        close: (code, reason) => ws.close(code, reason),
      });
      if (!handlers) return ws.close(4004, 'No such table');
      socketsByIp.set(ip, (socketsByIp.get(ip) ?? 0) + 1);
      let alive = true;
      ws.on('pong', () => { alive = true; });
      const pinger = setInterval(() => {
        if (!alive) return ws.terminate();
        alive = false;
        ws.ping();
      }, PING_MS);
      ws.on('message', (data, isBinary) => {
        if (isBinary) return ws.close(1003, 'Text only');
        try {
          handlers.message(data.toString());
        } catch (e) {
          log(`table ${id}`, e);
          ws.close(1011, 'Server error');
        }
      });
      ws.on('close', () => {
        clearInterval(pinger);
        const n = (socketsByIp.get(ip) ?? 1) - 1;
        if (n > 0) socketsByIp.set(ip, n);
        else socketsByIp.delete(ip);
        try {
          handlers.close();
        } catch (e) {
          log(`table ${id} close`, e);
        }
      });
      ws.on('error', () => ws.terminate());
    });
  }

  http.on('upgrade', (req, socket, head) => {
    try {
      upgrade(req, socket, head);
    } catch (e) {
      log('upgrade', e);
      socket.destroy();
    }
  });

  // A daily sweep for week-old tables, and the rate-limit memory with them.
  const sweeper = setInterval(() => {
    try {
      tables.sweep();
    } catch (e) {
      log('sweep', e);
    }
    const now = clock.now();
    for (const [ip, ts] of creates) if (!ts.some((t) => now - t < 3600_000)) creates.delete(ip);
  }, 3600_000);
  sweeper.unref();

  await new Promise<void>((done) => http.listen(o.port, o.host ?? '0.0.0.0', done));
  const address = http.address();
  const port = typeof address === 'object' && address ? address.port : o.port;

  return {
    port,
    tables,
    close: () => new Promise<void>((done) => {
      clearInterval(sweeper);
      tables.shutdown();
      for (const ws of wss.clients) ws.terminate();
      wss.close();
      http.close(() => {
        store.close();
        done();
      });
      http.closeAllConnections();
    }),
  };
}
