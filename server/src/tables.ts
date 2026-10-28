// The tables this server holds open: each one's state, its sockets, who is
// connected, and the robot's next move. All game logic is a call into the
// core (frontend/src/lib/table/core.ts); this file is the shell around it.
//
// Nothing here knows HTTP or `ws`: a connection is anything with `send` and
// `close`, so the tests drive it directly and the Node front end (main.ts)
// only adapts sockets to it.
import { createHash, randomBytes } from 'node:crypto';
import {
  ROBOT_DELAY_MS, TAKEOVER_MS, addPlayer, applyIntent, applyRobot, derive, finishedRecord, maintain, newTable,
  playerById, robotAction, robotTurn, viewFor, type Context, type Outcome, type TableState,
} from '../../frontend/src/lib/table/core';
import {
  PROTOCOL_VERSION, parseClientMessage, type ClientMessage, type ErrorCode, type ServerMessage,
} from '../../frontend/src/lib/table/protocol';
import { clearPositionMemo } from '../../frontend/src/lib/engine/ai';
import type { Readings } from '../../frontend/src/lib/alerts';
import type { Store } from './store';

export interface Conn {
  send(text: string): void;
  close(code: number, reason: string): void;
}

export interface Clock {
  now(): number;
  setTimeout(fn: () => void, ms: number): unknown;
  clearTimeout(handle: unknown): void;
}

export const realClock: Clock = {
  now: () => Date.now(),
  setTimeout: (fn, ms) => setTimeout(fn, ms),
  clearTimeout: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
};

/** Messages a socket may send in one second before it is closed. */
export const RATE_PER_SECOND = 20;
/** A table nobody has opened for this long is deleted. */
export const EXPIRE_MS = 7 * 24 * 3600 * 1000;
/** An open table with no sockets is dropped from memory after this. */
const IDLE_MS = 10 * 60 * 1000;
/** Intent ids remembered per table, for answering a resend once. */
const INTENTS_KEPT = 500;
/** GIB's readings of people's calls, shared by every table; cleared past this. */
const READINGS_MAX = 20_000;

const b64url = (n: number) => randomBytes(n).toString('base64url');
export const newTableId = () => b64url(16);
const sha256 = (t: string) => createHash('sha256').update(t).digest('hex');

interface Client {
  conn: Conn;
  playerId: string | null;
  greeted: boolean;
  /** Message timestamps in the last second, for the rate limit. */
  recent: number[];
}

interface Live {
  state: TableState;
  clients: Set<Client>;
  sockets: Map<string, number>;
  awaySince: Map<string, number>;
  intents: Map<string, Outcome>;
  robotTimer: unknown;
  checkTimer: unknown;
  idleTimer: unknown;
  /** Persisted so far: board number and how many of its actions. */
  savedBoard: number;
  savedActions: number;
}

export class Tables {
  private live = new Map<string, Live>();
  private readings: Readings = new Map();

  /** `robotDelayMs`: the robots' pace; the tests shorten it. */
  constructor(private store: Store, private clock: Clock = realClock,
              private random: () => number = () => randomBytes(4).readUInt32BE() / 2 ** 32,
              private robotDelayMs = ROBOT_DELAY_MS) {}

  get openTables(): number { return this.live.size; }
  get sockets(): number {
    let n = 0;
    for (const t of this.live.values()) n += t.clients.size;
    return n;
  }

  /** A new, empty table. The first person to join it becomes the host. */
  create(): string {
    const id = newTableId();
    const s = newTable(id, this.clock.now());
    this.store.save(s, this.clock.now(), false, 0, null);
    return id;
  }

  exists(id: string): boolean {
    return this.live.has(id) || this.store.exists(id);
  }

  // ── Connections ────────────────────────────────────────────────────────────

  /** A socket opened on table `id`. Returns the handlers for its messages and
   *  its close, or null when there is no such table. */
  open(id: string, conn: Conn): { message(raw: string): void; close(): void } | null {
    const t = this.load(id);
    if (!t) return null;
    const client: Client = { conn, playerId: null, greeted: false, recent: [] };
    t.clients.add(client);
    if (t.idleTimer !== undefined) {
      this.clock.clearTimeout(t.idleTimer);
      t.idleTimer = undefined;
    }
    return {
      message: (raw) => this.onMessage(t, client, raw),
      close: () => this.onClose(t, client),
    };
  }

  private load(id: string): Live | null {
    const open = this.live.get(id);
    if (open) return open;
    const state = this.store.load(id);
    if (!state) return null;
    const now = this.clock.now();
    const t: Live = {
      state, clients: new Set(), sockets: new Map(),
      // Nobody is connected to a table just loaded: everyone counts as gone
      // from now, so a robot can take a seat whose player never comes back.
      awaySince: new Map(state.players.map((p) => [p.id, now])),
      intents: new Map(), robotTimer: undefined, checkTimer: undefined, idleTimer: undefined,
      savedBoard: state.board?.num ?? 0, savedActions: state.board?.actions.length ?? 0,
    };
    this.live.set(id, t);
    this.scheduleRobot(t);
    return t;
  }

  private ctx(t: Live): Context {
    return {
      now: this.clock.now(),
      connected: (id) => (t.sockets.get(id) ?? 0) > 0,
      awaySince: (id) => ((t.sockets.get(id) ?? 0) > 0 ? null : t.awaySince.get(id) ?? null),
      random: this.random,
    };
  }

  private send(client: Client, m: ServerMessage): void {
    try {
      client.conn.send(JSON.stringify(m));
    } catch { /* a socket closing under us; its close handler tidies up */ }
  }

  private error(client: Client, code: ErrorCode, message: string, id?: string): void {
    this.send(client, { type: 'error', code, message, ...(id ? { id } : {}) });
  }

  private onMessage(t: Live, client: Client, raw: string): void {
    const now = this.clock.now();
    client.recent = client.recent.filter((x) => now - x < 1000);
    client.recent.push(now);
    if (client.recent.length > RATE_PER_SECOND) {
      client.conn.close(1008, 'Too many messages');
      return;
    }
    const m = parseClientMessage(raw);
    if (!m) {
      this.error(client, 'bad_message', 'Not a message this table understands.');
      return;
    }
    if (m.type === 'ping') {
      this.send(client, { type: 'pong' });
      return;
    }
    if (!client.greeted) {
      if (m.type !== 'hello') {
        this.error(client, 'bad_message', 'Say hello first.');
        return;
      }
      this.hello(t, client, m);
      return;
    }
    if (m.type === 'hello') return;
    if (m.type === 'join') {
      this.join(t, client, m.name);
      return;
    }
    if (!client.playerId) {
      this.error(client, 'not_joined', 'Join the table first.');
      return;
    }
    this.intent(t, client, m);
  }

  private hello(t: Live, client: Client, m: Extract<ClientMessage, { type: 'hello' }>): void {
    if (m.v !== PROTOCOL_VERSION) {
      this.error(client, 'version', 'The app is out of date: reload the page.');
      client.conn.close(4000, 'Version');
      return;
    }
    client.greeted = true;
    if (m.token) {
      const hash = sha256(m.token);
      const p = t.state.players.find((x) => x.tokenHash === hash);
      if (!p) {
        // An unknown token: removed, or from another table. Join afresh.
        this.error(client, 'bad_token', 'That seat is no longer yours here.');
      } else {
        client.playerId = p.id;
        this.arrived(t, p.id);
      }
    }
    this.send(client, { type: 'welcome', playerId: client.playerId });
    this.changed(t);
  }

  private join(t: Live, client: Client, name: string): void {
    if (client.playerId) {
      this.error(client, 'not_now', "You've joined already.");
      return;
    }
    const id = b64url(9);
    const token = b64url(16);
    const out = addPlayer(t.state, id, sha256(token), name, this.clock.now());
    if (!out.ok) {
      this.error(client, out.code, out.message);
      return;
    }
    client.playerId = id;
    this.arrived(t, id);
    this.send(client, { type: 'welcome', playerId: id, token });
    this.changed(t);
  }

  private arrived(t: Live, playerId: string): void {
    t.sockets.set(playerId, (t.sockets.get(playerId) ?? 0) + 1);
    t.awaySince.delete(playerId);
  }

  private intent(t: Live, client: Client, m: ClientMessage): void {
    const playerId = client.playerId!;
    const key = 'id' in m ? `${playerId}:${m.id}` : null;
    const seen = key ? t.intents.get(key) : undefined;
    if (seen) {
      // A resend (a double tap, or after a reconnect): the first answer again.
      if (!seen.ok) this.error(client, seen.code, seen.message, (m as { id: string }).id);
      else this.send(client, { type: 'view', view: viewFor(t.state, playerId, this.ctx(t)) });
      return;
    }
    const out = applyIntent(t.state, playerId, m, this.ctx(t));
    if (key) {
      t.intents.set(key, out);
      if (t.intents.size > INTENTS_KEPT) t.intents.delete(t.intents.keys().next().value!);
    }
    if (!out.ok) {
      this.error(client, out.code, out.message, 'id' in m ? m.id : undefined);
      return;
    }
    if (m.type === 'remove') {
      for (const c of t.clients) {
        if (c.playerId === m.player) {
          c.playerId = null;
          this.error(c, 'bad_token', 'The host removed you from the table.');
          c.conn.close(4001, 'Removed');
        }
      }
      t.sockets.delete(m.player);
      t.awaySince.delete(m.player);
    }
    this.changed(t);
  }

  private onClose(t: Live, client: Client): void {
    if (!t.clients.delete(client)) return;
    const id = client.playerId;
    if (id && playerById(t.state, id)) {
      const n = (t.sockets.get(id) ?? 1) - 1;
      if (n > 0) t.sockets.set(id, n);
      else {
        t.sockets.delete(id);
        t.awaySince.set(id, this.clock.now());
        // Once they have been gone long enough, the others get the
        // "Let a robot play" button and the host role may move.
        this.scheduleCheck(t, TAKEOVER_MS + 50);
      }
    }
    this.changed(t, false);
    if (!t.clients.size) {
      t.idleTimer = this.clock.setTimeout(() => this.unload(t), IDLE_MS);
    }
  }

  private unload(t: Live): void {
    if (t.clients.size) return;
    if (t.robotTimer !== undefined) this.clock.clearTimeout(t.robotTimer);
    if (t.checkTimer !== undefined) this.clock.clearTimeout(t.checkTimer);
    this.live.delete(t.state.id);
  }

  private scheduleCheck(t: Live, ms: number): void {
    if (t.checkTimer !== undefined) this.clock.clearTimeout(t.checkTimer);
    t.checkTimer = this.clock.setTimeout(() => {
      t.checkTimer = undefined;
      maintain(t.state, this.ctx(t));
      this.changed(t);
    }, ms);
  }

  // ── After every change ─────────────────────────────────────────────────────

  /** Save what changed, show everyone their view, and wake the robots. */
  private changed(t: Live, persist = true): void {
    const s = t.state;
    if (persist) {
      maintain(s, this.ctx(t));
      this.persist(t);
    }
    this.broadcast(t);
    this.scheduleRobot(t);
  }

  private persist(t: Live): void {
    const s = t.state;
    const b = s.board;
    const newBoard = !!b && b.num !== t.savedBoard;
    const from = newBoard ? 0 : t.savedActions;
    let record = null;
    if (b) {
      const d = derive(b);
      // The board just ended: keep its record, and let the robots' search
      // memory go, so the server's memory stays flat (MULTIPLAYER_PLAN.md).
      if (d.phase === 'done' && (newBoard || from < b.actions.length)) {
        record = finishedRecord(s, d, null);
        clearPositionMemo();
        if (this.readings.size > READINGS_MAX) this.readings.clear();
      }
    }
    this.store.save(s, this.clock.now(), newBoard, from, record);
    t.savedBoard = b?.num ?? 0;
    t.savedActions = b?.actions.length ?? 0;
  }

  private broadcast(t: Live): void {
    const ctx = this.ctx(t);
    for (const c of t.clients) {
      if (!c.greeted) continue;
      this.send(c, { type: 'view', view: viewFor(t.state, c.playerId, ctx) });
    }
  }

  private scheduleRobot(t: Live): void {
    if (t.robotTimer !== undefined || !robotTurn(t.state)) return;
    t.robotTimer = this.clock.setTimeout(() => {
      t.robotTimer = undefined;
      // A person may have taken the seat back since this was scheduled.
      const a = robotAction(t.state, this.readings);
      if (a) {
        applyRobot(t.state, a);
        this.changed(t);
      }
    }, this.robotDelayMs);
  }

  /** Delete tables nobody has opened for a week. */
  sweep(): string[] {
    const busy = new Set([...this.live.values()].filter((t) => t.clients.size).map((t) => t.state.id));
    const gone = this.store.expire(this.clock.now() - EXPIRE_MS, busy);
    for (const id of gone) {
      const t = this.live.get(id);
      if (t) this.unload(t);
    }
    return gone;
  }

  /** Close every socket, saying the server is restarting: clients reconnect. */
  shutdown(): void {
    for (const t of this.live.values()) {
      for (const c of t.clients) c.conn.close(1012, 'Restarting');
      if (t.robotTimer !== undefined) this.clock.clearTimeout(t.robotTimer);
      if (t.checkTimer !== undefined) this.clock.clearTimeout(t.checkTimer);
      if (t.idleTimer !== undefined) this.clock.clearTimeout(t.idleTimer);
    }
    this.live.clear();
  }
}
