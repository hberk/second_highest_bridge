// One table, as a Durable Object: the same `Tables` and `Store` as the Node
// server (../../src), holding just this table. Its database is the object's
// own SQLite; its timers are the object's alarm (alarm-clock.ts); its sockets
// are the runtime's WebSockets.
//
// The sockets are accepted the ordinary way, not with the Hibernation API:
// `Tables` keeps each socket's state (greeted, which player) in memory, so the
// object stays awake while anyone is connected. On the Free plan that is
// billed duration: 13,000 GB-s a day, about 28 hours of open tables a day at
// 128 MB. A table with nobody connected sleeps and costs nothing.
import { DurableObject } from 'cloudflare:workers';
import { ROBOT_DELAY_MS } from '../../../frontend/src/lib/table/core';
import { MAX_MESSAGE_BYTES, RESTING_CLOSE } from '../../../frontend/src/lib/table/protocol';
import { Store } from '../../src/store';
import { EXPIRE_MS, Tables } from '../../src/tables';
import { AlarmClock } from './alarm-clock';
import { DoSql } from './do-sql';
import type { Env } from './env';
import { SIMULATED_LIMIT, isResting } from './resting';

/** Sockets one address may hold open at this table. */
export const SOCKETS_PER_ADDRESS = 8;

export class TableObject extends DurableObject<Env> {
  private sql: DoSql;
  private store: Store;
  private clock: AlarmClock;
  private tables: Tables;
  private socketsByIp = new Map<string, number>();

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.sql = new DoSql(ctx.storage);
    this.store = new Store(this.sql, { indexes: false });
    this.clock = new AlarmClock(ctx.storage, () => this.expiresAt());
    const delay = Number(env.ROBOT_DELAY_MS ?? ROBOT_DELAY_MS);
    this.tables = new Tables(this.store, this.clock, undefined, delay, isResting);
  }

  /** This table's id, from its own row; null before it is created and once it has closed. */
  private tableId(): string | null {
    const row = this.ctx.storage.sql.exec('select id from tables limit 1').toArray()[0];
    return row ? String(row.id) : null;
  }

  private expiresAt(): number | null {
    const id = this.tableId();
    const last = id ? this.store.lastActive(id) : null;
    return last === null ? null : last + EXPIRE_MS;
  }

  /** Called by the Worker for POST /tables. False if the id is taken. */
  create(id: string): boolean {
    if (this.tables.exists(id)) return false;
    this.tables.create(id);
    this.clock.arm();
    return true;
  }

  /** What a board costs here, for the measurements (BRIDGE_DEV only). */
  stats(): { rowsWritten: number; alarmsSet: number; databaseBytes: number } {
    return { rowsWritten: this.sql.rowsWritten, alarmsSet: this.clock.alarmsSet, databaseBytes: this.ctx.storage.sql.databaseSize };
  }

  /** Development only: act as if the day's rows written were spent. */
  simulateLimit(): void {
    this.sql.failWrites = SIMULATED_LIMIT;
  }

  /** A table socket, forwarded by the Worker once it has checked the path and Origin. */
  async fetch(req: Request): Promise<Response> {
    const id = req.headers.get('x-table-id') ?? '';
    const ip = req.headers.get('x-ip') ?? '';
    if (req.headers.get('upgrade')?.toLowerCase() !== 'websocket') return new Response(null, { status: 426 });
    if (!id || !this.tables.exists(id)) return new Response(null, { status: 404 });
    if (this.sql.failWrites) return restingSocket();
    if ((this.socketsByIp.get(ip) ?? 0) >= SOCKETS_PER_ADDRESS) return new Response(null, { status: 429 });

    const pair = new WebSocketPair();
    const [client, server] = [pair[0], pair[1]];
    server.accept();
    const handlers = this.tables.open(id, {
      send: (text) => { if (server.readyState === WebSocket.OPEN) server.send(text); },
      close: (code, reason) => { try { server.close(code, reason); } catch { /* already closing */ } },
    });
    if (!handlers) {
      server.close(4004, 'No such table');
      return new Response(null, { status: 101, webSocket: client });
    }
    this.socketsByIp.set(ip, (this.socketsByIp.get(ip) ?? 0) + 1);
    let open = true;
    const closed = () => {
      if (!open) return;
      open = false;
      const n = (this.socketsByIp.get(ip) ?? 1) - 1;
      if (n > 0) this.socketsByIp.set(ip, n);
      else this.socketsByIp.delete(ip);
      try {
        handlers.close();
      } catch (e) {
        console.error(`${new Date().toISOString()} table ${id} close:`, e);
      }
    };
    server.addEventListener('message', (ev) => {
      if (typeof ev.data !== 'string') return server.close(1003, 'Text only');
      if (ev.data.length > MAX_MESSAGE_BYTES) return server.close(1009, 'Too big');
      try {
        handlers.message(ev.data);
      } catch (e) {
        if (isResting(e)) return this.tables.restAll();
        console.error(`${new Date().toISOString()} table ${id}:`, e);
        server.close(1011, 'Server error');
      }
    });
    server.addEventListener('close', (ev) => {
      // Answer the client's close, then tidy up.
      try { server.close(ev.code === 1005 ? 1000 : ev.code, 'Bye'); } catch { /* already closed */ }
      closed();
    });
    server.addEventListener('error', closed);
    return new Response(null, { status: 101, webSocket: client });
  }

  /** The robots' moves and the other timers, and a week-old table's close. */
  async alarm(): Promise<void> {
    this.clock.ring();
    const expires = this.expiresAt();
    if (expires !== null && expires <= Date.now()) {
      try {
        this.tables.sweep();
      } catch (e) {
        console.error(`${new Date().toISOString()} sweep:`, e);
      }
      this.clock.arm();
    }
  }
}

/** A socket opened only to say the server is resting: the app can't read a
 *  refused upgrade's status, but it reads this close code. */
export function restingSocket(): Response {
  const pair = new WebSocketPair();
  pair[1].accept();
  pair[1].send(JSON.stringify({ type: 'error', code: 'resting', message: 'The table server is resting until its daily allowance resets.' }));
  pair[1].close(RESTING_CLOSE, 'Resting');
  return new Response(null, { status: 101, webSocket: pair[0] });
}
