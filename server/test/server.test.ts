// The table server end to end, over real sockets on a random local port with
// a temporary SQLite file: create, join, sit, play a whole board with three
// robots; reconnect and restart mid-board; and every limit the server keeps.
import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import WebSocket from 'ws';
import { legalPlays } from '../../frontend/src/lib/engine/auction';
import type { Seat } from '../../frontend/src/lib/engine/card';
import type { ClientMessage, ServerMessage, TableView } from '../../frontend/src/lib/table/protocol';
import { startServer, type Options } from '../src/server';
import { EXPIRE_MS, realClock } from '../src/tables';

const ORIGIN = 'https://bridge.example';
const dirs: string[] = [];
const servers: { close(): Promise<void> }[] = [];

afterEach(async () => {
  while (servers.length) await servers.pop()!.close();
  while (dirs.length) rmSync(dirs.pop()!, { recursive: true, force: true });
});

function tempDir(): string {
  const d = mkdtempSync(join(tmpdir(), 'bridge-'));
  dirs.push(d);
  return d;
}

async function serve(over: Partial<Options> = {}, dir = tempDir()) {
  const s = await startServer({
    port: 0, host: '127.0.0.1', dbPath: join(dir, 'bridge.db'), allowedOrigins: [ORIGIN], robotDelayMs: 1, ...over,
  });
  servers.push(s);
  return { ...s, dir, url: `http://127.0.0.1:${s.port}` };
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
      ws.once('error', fail);
    });
  }

  send(m: ClientMessage | Record<string, unknown>) {
    this.ws.send(JSON.stringify(m));
  }

  /** Waits until `pred` holds of what this client has received. */
  async until(pred: () => boolean, what: string, ms = 20000): Promise<void> {
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
/** Play the board out from `c`'s seat: the first legal call is Pass, the
 *  card the first legal one. Returns when the board is over. */
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

describe('a table, end to end', () => {
  it('creates, joins, sits and plays a whole board with three robots', async () => {
    const s = await serve();
    const { status, body } = await createTable(s.url);
    expect(status).toBe(201);
    expect(body.id).toMatch(/^[A-Za-z0-9_-]{22}$/);
    const c = await Client.open(s.port, body.id!);
    await c.join('Alex', 'South');
    expect(c.view!.you.isHost).toBe(true);
    c.send({ type: 'deal' });
    const board = await playOut(c);
    expect(board.phase).toBe('done');
    expect(board.record?.table_id).toBe(body.id);
    if (!board.passedOut) expect(board.tricksTaken['N/S'] + board.tricksTaken['E/W']).toBe(13);
    // Once it's over, every hand is in the record.
    expect(Object.values(board.record!.initial_hands).every((h) => h.length === 13)).toBe(true);
  });

  it('reconnecting with the token gets the same seat and hand back', async () => {
    const s = await serve({ robotDelayMs: 50 });
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
    // A made-up token gets no seat.
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
    const first = await serve({ robotDelayMs: 1 }, dir);
    const { body } = await createTable(first.url);
    const a = await Client.open(first.port, body.id!);
    await a.join('Alex', 'South');
    a.send({ type: 'deal' });
    // Make a few of our own moves, then stop the server mid-board.
    await a.until(() => a.view?.board?.actor === 'South' || a.view?.board?.phase === 'done', 'my turn');
    const at = a.view!.board!.at;
    const token = a.token;
    await first.close();
    servers.splice(servers.indexOf(first), 1);

    const second = await serve({ robotDelayMs: 1 }, dir);
    const b = await Client.open(second.port, body.id!);
    b.send({ type: 'hello', v: 1, token });
    await b.until(() => b.view?.you.seat === 'South', 'my seat after the restart');
    expect(b.view!.board!.at).toBe(at);
    const board = await playOut(b);
    expect(board.phase).toBe('done');
  });

  it('answers a resent intent once', async () => {
    const s = await serve();
    const { body } = await createTable(s.url);
    const c = await Client.open(s.port, body.id!);
    await c.join('Alex', 'North');
    c.send({ type: 'deal' });
    await c.until(() => c.view?.board?.actor === 'North' || c.view?.board?.phase === 'done', 'my turn');
    if (c.view!.board!.phase !== 'bidding') return;
    const at = c.view!.board!.at;
    const m = { type: 'call', id: 'same', at, call: 'Pass' } as const;
    c.send(m);
    c.send(m);
    await c.until(() => (c.view?.board?.at ?? 0) > at, 'the call');
    const calls = c.view!.board!.calls.filter((_, i) => i >= at && c.view!.board!.calls[i][0] === 'North');
    expect(calls.length).toBe(1);
  });
});

describe('the limits the server keeps', () => {
  it('refuses another origin, for tables and sockets', async () => {
    const s = await serve();
    expect((await createTable(s.url, {})).status).toBe(403);
    expect((await createTable(s.url, { origin: 'https://evil.example' })).status).toBe(403);
    const { body } = await createTable(s.url);
    await expect(Client.open(s.port, body.id!, 'https://evil.example')).rejects.toThrow(/403/);
  });

  it('refuses a socket to a table that does not exist', async () => {
    const s = await serve();
    await expect(Client.open(s.port, 'B'.repeat(22))).rejects.toThrow(/404/);
    await expect(Client.open(s.port, 'short')).rejects.toThrow(/404/);
  });

  it('closes a socket that sends too much, or too fast', async () => {
    const s = await serve();
    const { body } = await createTable(s.url);
    const big = await Client.open(s.port, body.id!);
    big.ws.send('x'.repeat(5000));
    await big.until(() => !!big.closed, 'the close');
    expect(big.closed!.code).toBe(1009);

    const fast = await Client.open(s.port, body.id!);
    for (let i = 0; i < 40; i++) fast.send({ type: 'ping' });
    await fast.until(() => !!fast.closed, 'the close');
    expect(fast.closed!.code).toBe(1008);
  });

  it('caps sockets and new tables per address', async () => {
    const s = await serve({ socketsPerAddress: 2, createsPerHour: 2 });
    const { body } = await createTable(s.url);
    await Client.open(s.port, body.id!);
    await Client.open(s.port, body.id!);
    await expect(Client.open(s.port, body.id!)).rejects.toThrow(/429/);
    expect((await createTable(s.url)).status).toBe(201);
    expect((await createTable(s.url)).status).toBe(429);
  });

  it('believes X-Real-IP only from the trusted proxy', async () => {
    const trusted = await serve({ createsPerHour: 1, trustedProxy: '127.0.0.1' });
    expect((await createTable(trusted.url, { origin: ORIGIN, 'x-real-ip': '10.0.0.1' })).status).toBe(201);
    expect((await createTable(trusted.url, { origin: ORIGIN, 'x-real-ip': '10.0.0.2' })).status).toBe(201);
    expect((await createTable(trusted.url, { origin: ORIGIN, 'x-real-ip': '10.0.0.1' })).status).toBe(429);

    const untrusted = await serve({ createsPerHour: 1 });
    expect((await createTable(untrusted.url, { origin: ORIGIN, 'x-real-ip': '10.0.0.1' })).status).toBe(201);
    expect((await createTable(untrusted.url, { origin: ORIGIN, 'x-real-ip': '10.0.0.2' })).status).toBe(429);
  });

  it('refuses an old app with a clean "please reload"', async () => {
    const s = await serve();
    const { body } = await createTable(s.url);
    const c = await Client.open(s.port, body.id!);
    c.send({ type: 'hello', v: 0 });
    await c.until(() => !!c.closed, 'the close');
    expect(c.lastError()!.code).toBe('version');
  });

  it('deletes tables nobody has opened for a week', async () => {
    let offset = 0;
    const s = await serve({ clock: { ...realClock, now: () => Date.now() + offset } });
    const { body } = await createTable(s.url);
    expect(s.tables.exists(body.id!)).toBe(true);
    offset = EXPIRE_MS + 1000;
    expect(s.tables.sweep()).toEqual([body.id]);
    expect(s.tables.exists(body.id!)).toBe(false);
  });
});

describe('static files and health', () => {
  it('serves the build with the right types, caching and headers', async () => {
    const pub = join(tempDir(), 'public');
    mkdirSync(join(pub, 'assets'), { recursive: true });
    writeFileSync(join(pub, 'index.html'), '<!doctype html><title>t</title>');
    writeFileSync(join(pub, 'assets', 'solver-abc.wasm'), Buffer.from([0, 97, 115, 109]));
    writeFileSync(join(tempDir(), 'secret.txt'), 'secret');
    const s = await serve({ publicDir: pub });

    const index = await fetch(`${s.url}/`);
    expect(index.status).toBe(200);
    expect(index.headers.get('cache-control')).toBe('no-cache');
    expect(index.headers.get('content-security-policy')).toContain("frame-ancestors 'none'");
    expect(index.headers.get('content-security-policy')).toContain('wss://bridge.example');

    const wasm = await fetch(`${s.url}/assets/solver-abc.wasm`);
    expect(wasm.headers.get('content-type')).toBe('application/wasm');
    expect(wasm.headers.get('cache-control')).toContain('immutable');

    expect((await fetch(`${s.url}/../secret.txt`)).status).toBe(404);
    expect((await fetch(`${s.url}/%2e%2e/secret.txt`)).status).toBe(404);
    expect((await fetch(`${s.url}/nope.js`)).status).toBe(404);

    const health = await (await fetch(`${s.url}/healthz`)).json() as { ok: boolean };
    expect(health.ok).toBe(true);
  });
});
