// The Cloudflare table server end to end, in workerd on a random local port:
// the Worker, a Durable Object per table on its own SQLite, robots on the
// object's alarm. The same flows as the Node server's tests (../../test):
// create, join, sit and play a whole board with three robots; reconnect;
// resume after a restart; the Origin and the limits. And what a board costs
// against the Free plan's daily limits.
import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync, copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import WebSocket from 'ws';
import { unstable_dev, type Unstable_DevWorker } from 'wrangler';
import { legalPlays } from '../../../frontend/src/lib/engine/auction';
import type { Seat } from '../../../frontend/src/lib/engine/card';
import type { ClientMessage, ServerMessage, TableView } from '../../../frontend/src/lib/table/protocol';

const ORIGIN = 'https://bridge.example';
const here = new URL('..', import.meta.url).pathname;
const dirs: string[] = [];
const workers: Unstable_DevWorker[] = [];

afterEach(async () => {
  while (workers.length) await workers.pop()!.stop();
  while (dirs.length) rmSync(dirs.pop()!, { recursive: true, force: true });
});

function tempDir(): string {
  const d = mkdtempSync(join(tmpdir(), 'bridge-cf-'));
  dirs.push(d);
  return d;
}

/** A small site in place of the beta build, with the real _headers. */
function assets(): string {
  const d = tempDir();
  writeFileSync(join(d, 'index.html'), '<!doctype html><title>beta</title>');
  copyFileSync(join(here, '_headers'), join(d, '_headers'));
  return d;
}

async function serve(vars: Record<string, string> = {}, persistTo?: string) {
  const w = await unstable_dev(join(here, 'src/worker.ts'), {
    config: join(here, 'wrangler.jsonc'),
    assets: assets(),
    vars: { ALLOWED_ORIGINS: ORIGIN, ROBOT_DELAY_MS: '50', BRIDGE_DEV: '1', ...vars },
    ip: '127.0.0.1',
    port: 0,
    inspect: false,
    logLevel: 'error',
    persist: !!persistTo,
    persistTo,
    experimental: { disableExperimentalWarning: true, disableDevRegistry: true },
  });
  workers.push(w);
  return { w, url: `http://127.0.0.1:${w.port}`, port: w.port };
}

async function createTable(url: string, headers: Record<string, string> = { origin: ORIGIN }) {
  const res = await fetch(`${url}/tables`, { method: 'POST', headers });
  return { status: res.status, body: await res.json() as { id?: string; error?: string } };
}

class Client {
  messages: ServerMessage[] = [];
  view: TableView | null = null;
  token?: string;
  closed: { code: number } | null = null;
  private waiters: (() => void)[] = [];

  private constructor(readonly ws: WebSocket) {
    ws.on('message', (data) => {
      const m = JSON.parse(data.toString()) as ServerMessage;
      this.messages.push(m);
      if (m.type === 'view') this.view = m.view;
      if (m.type === 'welcome' && m.token) this.token = m.token;
      this.wake();
    });
    ws.on('close', (code) => { this.closed = { code }; this.wake(); });
  }

  private wake() {
    for (const w of this.waiters.splice(0)) w();
  }

  static open(port: number, id: string, origin = ORIGIN): Promise<Client> {
    return new Promise((done, fail) => {
      const ws = new WebSocket(`ws://127.0.0.1:${port}/tables/${id}/ws`, { headers: { origin } });
      const c = new Client(ws);
      ws.once('open', () => done(c));
      ws.once('unexpected-response', (_req, res) => fail(new Error(`HTTP ${res.statusCode}`)));
      ws.once('error', fail);
    });
  }

  send(m: ClientMessage | Record<string, unknown>) {
    this.ws.send(JSON.stringify(m));
  }

  async until(pred: () => boolean, what: string, ms = 30000): Promise<void> {
    const end = Date.now() + ms;
    while (!pred()) {
      if (Date.now() > end) throw new Error(`timed out waiting for ${what}`);
      await new Promise<void>((r) => {
        this.waiters.push(r);
        setTimeout(r, 200);
      });
    }
  }

  async join(name: string, seat: Seat) {
    this.send({ type: 'hello', v: 1 });
    this.send({ type: 'join', name });
    await this.until(() => !!this.token, 'a token');
    this.send({ type: 'sit', seat });
    await this.until(() => this.view?.you.seat === seat, 'a seat');
  }

  lastError() {
    return [...this.messages].reverse().find((m) => m.type === 'error') as Extract<ServerMessage, { type: 'error' }> | undefined;
  }

  close() {
    this.ws.close();
  }
}

let n = 0;
async function playOut(c: Client) {
  for (let guard = 0; guard < 200; guard++) {
    await c.until(() => {
      const b = c.view?.board;
      return !!b && (b.phase === 'done' || b.actor === c.view!.you.seat);
    }, 'my turn or the end');
    const b = c.view!.board!;
    if (b.phase === 'done') return b;
    const at = b.at;
    if (b.phase === 'bidding') c.send({ type: 'call', id: `c${n++}`, at, call: 'Pass' });
    else {
      const seat = b.toAct!;
      const led = b.trick.length ? b.trick[0][1].suit : null;
      c.send({ type: 'card', id: `c${n++}`, at, seat, card: legalPlays(b.hands[seat], led)[0] });
    }
    await c.until(() => (c.view?.board?.at ?? 0) > at || c.view?.board?.phase === 'done', 'my action to land');
  }
  throw new Error('board did not finish');
}

async function stats(url: string, id: string) {
  return await (await fetch(`${url}/dev/tables/${id}/stats`)).json() as
    { rowsWritten: number; alarmsSet: number; databaseBytes: number };
}

describe('the Cloudflare table server', () => {
  it('creates, joins, sits and plays whole boards with three robots on alarms', async () => {
    const s = await serve();
    const { status, body } = await createTable(s.url);
    expect(status).toBe(201);
    expect(body.id).toMatch(/^[A-Za-z0-9_-]{22}$/);
    const c = await Client.open(s.port, body.id!);
    await c.join('Alex', 'South');
    expect(c.view!.you.isHost).toBe(true);

    const before = await stats(s.url, body.id!);
    const boards = 3;
    const costs: { rows: number; alarms: number }[] = [];
    let last = before;
    for (let i = 0; i < boards; i++) {
      c.send({ type: 'deal' });
      await c.until(() => c.view?.board?.num === i + 1, `board ${i + 1}`);
      const board = await playOut(c);
      expect(board.phase).toBe('done');
      expect(board.record?.table_id).toBe(body.id);
      if (!board.passedOut) expect(board.tricksTaken['N/S'] + board.tricksTaken['E/W']).toBe(13);
      expect(Object.values(board.record!.initial_hands).every((h) => h.length === 13)).toBe(true);
      const now = await stats(s.url, body.id!);
      costs.push({ rows: now.rowsWritten - last.rowsWritten, alarms: now.alarmsSet - last.alarmsSet });
      last = now;
    }
    // What a board costs against the Free plan's daily limits: rows written
    // (100,000 a day) and requests, which alarms count toward (100,000 a day).
    console.log(`per board: ${JSON.stringify(costs)}; database ${last.databaseBytes} bytes`);
    for (const k of costs) {
      expect(k.rows).toBeLessThan(250);
      expect(k.alarms).toBeLessThan(120);
    }
  });

  it('reconnecting with the token gets the same seat and hand back', async () => {
    const s = await serve();
    const { body } = await createTable(s.url);
    const a = await Client.open(s.port, body.id!);
    await a.join('Alex', 'East');
    a.send({ type: 'deal' });
    await a.until(() => !!a.view?.board, 'a board');
    const hand = a.view!.board!.hands.East;
    expect(hand.length).toBe(13);
    a.close();

    const b = await Client.open(s.port, body.id!);
    b.send({ type: 'hello', v: 1, token: a.token });
    await b.until(() => b.view?.you.seat === 'East', 'my seat back');
    expect(b.view!.board!.hands.East.length).toBeGreaterThan(0);
    const c = await Client.open(s.port, body.id!);
    c.send({ type: 'hello', v: 1, token: 'A'.repeat(22) });
    await c.until(() => !!c.lastError(), 'an error');
    expect(c.lastError()!.code).toBe('bad_token');
    await c.until(() => !!c.view, 'a view');
    expect(c.view!.you.seat).toBeNull();
    expect(JSON.stringify(c.view)).not.toContain(JSON.stringify(hand[0]));
  });

  it('resumes a board after a restart, robots and all', async () => {
    const dir = tempDir();
    const first = await serve({}, dir);
    const { body } = await createTable(first.url);
    const a = await Client.open(first.port, body.id!);
    await a.join('Alex', 'South');
    a.send({ type: 'deal' });
    await a.until(() => a.view?.board?.actor === 'South' || a.view?.board?.phase === 'done', 'my turn');
    const at = a.view!.board!.at;
    const token = a.token;
    await first.w.stop();
    workers.splice(workers.indexOf(first.w), 1);

    const second = await serve({}, dir);
    const b = await Client.open(second.port, body.id!);
    b.send({ type: 'hello', v: 1, token });
    await b.until(() => b.view?.you.seat === 'South', 'my seat after the restart');
    expect(b.view!.board!.at).toBe(at);
    const board = await playOut(b);
    expect(board.phase).toBe('done');
  });

  it('refuses another Origin, an unknown table, and a malformed id', async () => {
    const s = await serve();
    expect((await createTable(s.url, { origin: 'https://evil.example' })).status).toBe(403);
    expect((await createTable(s.url, {})).status).toBe(403);
    const { body } = await createTable(s.url);
    await expect(Client.open(s.port, body.id!, 'https://evil.example')).rejects.toThrow('HTTP 403');
    await expect(Client.open(s.port, 'B'.repeat(22))).rejects.toThrow('HTTP 404');
    await expect(Client.open(s.port, 'short')).rejects.toThrow('HTTP 404');
    expect((await fetch(`${s.url}/tables/${body.id}/ws`, { headers: { origin: ORIGIN } })).status).toBe(426);
  });

  it('limits the tables one address creates in an hour', async () => {
    const s = await serve({ CREATES_PER_HOUR: '3' });
    const got = [];
    for (let i = 0; i < 4; i++) got.push((await createTable(s.url)).status);
    expect(got).toEqual([201, 201, 201, 429]);
  });

  it('serves the site with its security headers, and /healthz', async () => {
    const s = await serve();
    const res = await fetch(`${s.url}/`);
    expect(res.status).toBe(200);
    expect(await res.text()).toContain('<title>beta</title>');
    expect(res.headers.get('content-security-policy')).toContain("frame-ancestors 'none'");
    expect(res.headers.get('content-security-policy')).toContain('wss://bridge.second-highest.workers.dev');
    expect(res.headers.get('x-content-type-options')).toBe('nosniff');
    expect((await fetch(`${s.url}/healthz`)).status).toBe(200);
    expect((await fetch(`${s.url}/tables`)).status).toBe(404);
  });

  it('keeps the measurements endpoint off outside development', async () => {
    const s = await serve({ BRIDGE_DEV: '0' });
    const { body } = await createTable(s.url);
    expect((await fetch(`${s.url}/dev/tables/${body.id}/stats`)).status).not.toBe(200);
  });
});
