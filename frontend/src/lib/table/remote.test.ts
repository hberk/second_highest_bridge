// RemoteTable, the browser's side of a multiplayer table, against a small
// in-process server built on the real core (no network): join, sit, play
// whole boards through the same calls the table views make, rendering both
// layouts at every step; the held trick and contract; and a dropped socket
// that reconnects, takes its seat back and resends what it had sent.
import { describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import type { Seat } from '../engine/card';
import { legalPlays } from '../engine/auction';
import { prng } from '../meanings';
import type { HistoryRecord } from '../saves';
import type { Readings } from '../alerts';
import {
  addPlayer, applyIntent, applyRobot, newTable, robotAction, viewFor, type Context, type TableState,
} from './core';
import { parseClientMessage, type ClientMessage, type ServerMessage } from './protocol';
import { RemoteTable, type SocketLike } from './remote.svelte';
import TableView from '../views/TableView.svelte';
import DesktopTableView from '../views/DesktopTableView.svelte';
import RemoteView from '../views/RemoteView.svelte';

/** Timers the test runs by hand. */
class Clock {
  t = 0;
  private due: { at: number; fn: () => void; id: number }[] = [];
  private n = 0;
  setTimeout = (fn: () => void, ms: number) => { const id = ++this.n; this.due.push({ at: this.t + ms, fn, id }); return id; };
  clearTimeout = (h: unknown) => { this.due = this.due.filter((d) => d.id !== h); };
  now = () => this.t;
  advance(ms: number) {
    const end = this.t + ms;
    for (;;) {
      const next = this.due.filter((d) => d.at <= end).sort((a, b) => a.at - b.at)[0];
      if (!next) break;
      this.due = this.due.filter((d) => d !== next);
      this.t = next.at;
      next.fn();
    }
    this.t = end;
  }
}

class FakeSocket implements SocketLike {
  readyState = 0;
  onopen: SocketLike['onopen'] = null;
  onmessage: SocketLike['onmessage'] = null;
  onclose: SocketLike['onclose'] = null;
  onerror: SocketLike['onerror'] = null;
  /** Messages the client sent, and whether the "network" delivers them. */
  sent: string[] = [];
  deliver = true;
  constructor(readonly server: FakeServer) {}
  send(data: string) {
    this.sent.push(data);
    if (this.deliver) this.server.handle(this, data);
  }
  close(code = 1000) {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.server.drop(this);
    this.onclose?.({ code });
  }
  /** The connection drops under the client. */
  cut() { this.close(1006); }
  receive(m: ServerMessage) {
    if (this.readyState === 1) this.onmessage?.({ data: JSON.stringify(m) });
  }
}

/** The table server's job, in memory: tokens, intents once, robots at once. */
class FakeServer {
  s: TableState = newTable('R'.repeat(22), 0);
  private player = new Map<FakeSocket, string | null>();
  private tokens = new Map<string, string>();
  private intents = new Set<string>();
  private readings: Readings = new Map();
  applied = 0;
  /** Reports and caught errors, as the game log would get them. */
  notes: ClientMessage[] = [];
  connect(): FakeSocket {
    const sock = new FakeSocket(this);
    queueMicrotask(() => {});
    this.player.set(sock, null);
    sock.readyState = 1;
    // Opened at once: the client's onopen runs when it has set it.
    setTimeout(() => sock.onopen?.({}), 0);
    return sock;
  }
  drop(sock: FakeSocket) { this.player.delete(sock); this.broadcast(); }
  private ctx(): Context {
    return { now: 0, connected: (id) => [...this.player.values()].includes(id), awaySince: () => null, random: prng(17) };
  }
  handle(sock: FakeSocket, raw: string) {
    const m = parseClientMessage(raw)!;
    expect(m, `the client sent something the server can't parse: ${raw}`).not.toBeNull();
    if (m.type === 'ping') return sock.receive({ type: 'pong' });
    if (m.type === 'report' || m.type === 'oops') return void this.notes.push(m);
    if (m.type === 'hello') {
      const id = m.token ? this.tokens.get(m.token) ?? null : null;
      this.player.set(sock, id);
      sock.receive({ type: 'welcome', playerId: id });
      return this.broadcast();
    }
    if (m.type === 'join') {
      const id = `p${this.tokens.size}`;
      const token = `${'t'.repeat(21)}${this.tokens.size}`;
      addPlayer(this.s, id, 'h', m.name, 0);
      this.tokens.set(token, id);
      this.player.set(sock, id);
      sock.receive({ type: 'welcome', playerId: id, token });
      return this.broadcast();
    }
    const pid = this.player.get(sock)!;
    if ('id' in m) {
      if (this.intents.has(`${pid}:${m.id}`)) return;
      this.intents.add(`${pid}:${m.id}`);
    }
    const out = applyIntent(this.s, pid, m, this.ctx());
    if (!out.ok) return sock.receive({ type: 'error', code: out.code, message: out.message, ...('id' in m ? { id: m.id } : {}) });
    if (m.type === 'call' || m.type === 'card') this.applied++;
    this.broadcast();
    for (let a = robotAction(this.s, this.readings); a; a = robotAction(this.s, this.readings)) {
      applyRobot(this.s, a);
      this.broadcast();
    }
  }
  broadcast() {
    for (const [sock, id] of this.player) sock.receive({ type: 'view', view: viewFor(this.s, id, this.ctx()) });
  }
}

function memoryStorage(): Storage {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k),
    clear: () => m.clear(), key: (i) => [...m.keys()][i] ?? null, get length() { return m.size; },
  };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

async function seated(server: FakeServer, seat: Seat, clock = new Clock(), storage = memoryStorage()) {
  const records: HistoryRecord[] = [];
  const sockets: FakeSocket[] = [];
  const t = new RemoteTable(server.s.id, {
    storage, timers: clock, url: 'ws://test',
    socket: () => { const s = server.connect(); sockets.push(s); return s; },
    onfinished: (r) => records.push(r),
  });
  await tick();
  t.join(seat.toLowerCase());
  t.sit(seat);
  expect(t.view?.you.seat).toBe(seat);
  return { t, records, sockets, clock, storage };
}

/** Play the board out the way a player would, rendering both layouts. */
function playOut(t: RemoteTable) {
  for (let guard = 0; guard < 400; guard++) {
    const htmls = [render(TableView, { props: { game: t } }).body, render(DesktopTableView, { props: { game: t } }).body];
    const phase = t.phase;
    if (phase === 'bidding') {
      if (t.auction.passedOut) return 'passed';
      expect(t.auction.currentPlayer(), 'bidding waits on a robot').toBe(t.mySeat);
      for (const h of htmls) expect(h).toContain('Your call');
      const legal = t.auction.legalCalls();
      const bid = legal.find((c) => c === '1NT' || c === '3H');
      t.humanBids(guard % 4 === 0 && bid ? bid : 'Pass');
    } else if (phase === 'auction_done') {
      for (const h of htmls) expect(h).toContain('Start play');
      t.startPlay();
    } else if (phase === 'trick_done') {
      for (const h of htmls) expect(h).toContain('trick-won');
      t.nextTrick();
    } else if (phase === 'playing') {
      const who = t.whoseTurn();
      expect(who, 'play waits on a robot').not.toBeNull();
      for (const h of htmls) {
        expect(h).toContain('Your turn');
        expect(h).toContain('tf-seat tf-south"><span class="tf-label">You');
      }
      const led = t.trick.length ? t.trick[0][1].suit : null;
      t.humanPlays(who!, legalPlays(t.hands[who!], led)[0]);
    } else {
      for (const h of htmls) expect(h).toContain('Hand complete');
      return 'done';
    }
  }
  throw new Error('board did not finish');
}

describe('RemoteTable', () => {
  it('plays boards to the end from any seat, saving each to History', async () => {
    for (const seat of ['East', 'South'] as Seat[]) {
      const server = new FakeServer();
      const { t, records } = await seated(server, seat);
      render(RemoteView, { props: { table: t, onhome: () => {} } });
      let done = 0;
      for (let n = 0; n < 6; n++) {
        t.newBoard();
        if (playOut(t) === 'done') {
          done++;
          expect(t.tricksTaken['N/S'] + t.tricksTaken['E/W']).toBe(13);
          expect(render(RemoteView, { props: { table: t, onhome: () => {} } }).body).toContain('Deal the next board');
        }
      }
      expect(done).toBeGreaterThan(1);
      expect(records.length).toBe(done);
      expect(records.every((r) => r.table_id === server.s.id && r.my_seat === seat)).toBe(true);
    }
  });

  it('holds a finished trick while the robots play on, then catches up', async () => {
    const server = new FakeServer();
    const { t } = await seated(server, 'South');
    t.newBoard();
    // Play until a trick is held with the robots already leading the next.
    for (let guard = 0; guard < 400; guard++) {
      if (t.phase === 'trick_done') break;
      if (t.phase === 'bidding') { if (t.auction.passedOut) { t.newBoard(); continue; } t.humanBids('Pass'); }
      else if (t.phase === 'auction_done') t.startPlay();
      else if (t.phase === 'playing') {
        const who = t.whoseTurn()!;
        t.humanPlays(who, legalPlays(t.hands[who], t.trick.length ? t.trick[0][1].suit : null)[0]);
      } else t.newBoard();
    }
    expect(t.phase).toBe('trick_done');
    const held = t.trick;
    expect(held.length).toBe(4);
    expect(t.whoseTurn(), 'you can play while a trick is held').toBeNull();
    t.nextTrick();
    expect(t.phase === 'playing' || t.phase === 'trick_done' || t.phase === 'done').toBe(true);
  });

  it('reconnects after a drop, takes the seat back, and resends what it sent once', async () => {
    const server = new FakeServer();
    const clock = new Clock();
    const { t, sockets } = await seated(server, 'South', clock);
    t.newBoard();
    // Get to a call of ours.
    for (let guard = 0; guard < 50 && !(t.phase === 'bidding' && t.auction.currentPlayer() === 'South'); guard++) {
      if (t.auction.passedOut || t.phase === 'done') t.newBoard();
    }
    expect(t.auction.currentPlayer()).toBe('South');
    const before = server.applied;
    // The call goes out as the network drops: the server never sees it.
    sockets.at(-1)!.deliver = false;
    t.humanBids('Pass');
    sockets.at(-1)!.cut();
    expect(t.status).toBe('reconnecting');
    clock.advance(1000);
    await tick();
    expect(t.status).toBe('open');
    expect(t.view?.you.seat, 'the seat came back with the token').toBe('South');
    expect(server.applied, 'the call was resent and applied once').toBe(before + 1);
    // A second resend of the same id changes nothing.
    sockets.at(-1)!.cut();
    clock.advance(1000);
    await tick();
    expect(server.applied).toBe(before + 1);
  });

  it('only acts on the latest view: nothing is sent while a moment is held', async () => {
    const server = new FakeServer();
    const { t, sockets } = await seated(server, 'North');
    t.newBoard();
    for (let guard = 0; guard < 200 && t.phase !== 'auction_done'; guard++) {
      if (t.phase === 'bidding') { if (t.auction.passedOut) { t.newBoard(); continue; } t.humanBids(guard % 2 ? '1NT' : 'Pass'); }
      else t.newBoard();
    }
    expect(t.phase, 'no auction reached a contract').toBe('auction_done');
    const sent = sockets.at(-1)!.sent.length;
    t.humanBids('Pass');
    t.humanPlays('North', t.hands.North[0]);
    expect(sockets.at(-1)!.sent.length, 'sent an action during a held moment').toBe(sent);
  });

  it('reports a problem with the moment on screen, and each caught error once', async () => {
    const server = new FakeServer();
    const { t, sockets } = await seated(server, 'East');
    t.newBoard();
    expect(t.report('Cards on the wrong side\n', 'phone')).toBe(true);
    const [report] = server.notes as Extract<ClientMessage, { type: 'report' }>[];
    expect(report.note).toBe('Cards on the wrong side');
    expect(report.client).toMatchObject({ layout: 'phone', board: 1, hold: 'none', build: 'dev' });
    expect(report.client.shownAt).toBe(server.s.board!.actions.length);
    for (let i = 0; i < 3; i++) t.oops('TypeError: boom', 'here', 'desktop');
    for (let i = 0; i < 10; i++) t.oops(`Error ${i}`, '', 'desktop');
    expect(server.notes.filter((n) => n.type === 'oops').length, 'one per message, five at most').toBe(5);
    // No connection: the page is told, so it can say so.
    sockets.at(-1)!.cut();
    expect(t.report('again', 'phone')).toBe(false);
  });
});
