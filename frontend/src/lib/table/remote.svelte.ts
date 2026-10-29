// A multiplayer table in the browser: the socket to the table server, and
// the board as the table views draw it. It is a `TableSource`, like the solo
// `Game`, so TableView and DesktopTableView play it unchanged.
//
// The server sends the seat's whole view after every change. The table shows
// the latest one, except that it holds two moments the way solo play does: a
// finished trick stays on the felt until "Next trick" (or fast play), and the
// final contract until "Start play". Views that arrive meanwhile wait; one
// slow reader never holds up the table, they only fall behind and catch up.
import type { Card, Seat, Side, Vulnerability } from '../engine/card';
import { AuctionState, type CallRecord, type Contract, type Play } from '../engine/auction';
import type { TrickLog } from '../engine/challenge';
import type { ScoreResult } from '../engine/scoring';
import type { ChallengeLogEntry, ChallengeResult, Phase } from '../game.svelte';
import type { HistoryRecord } from '../saves';
import type { TableSource } from '../tableModel.svelte';
import {
  PROTOCOL_VERSION, cleanNote, type BoardView, type ClientInfo, type ClientMessage, type ServerMessage, type TableView,
} from './protocol';

/** What the browser needs of a WebSocket; the tests pass a fake. */
export interface SocketLike {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  onopen: ((e: unknown) => void) | null;
  onmessage: ((e: { data: unknown }) => void) | null;
  onclose: ((e: { code: number }) => void) | null;
  onerror: ((e: unknown) => void) | null;
}

export type Status = 'connecting' | 'open' | 'reconnecting' | 'gone' | 'outdated' | 'removed';

/** Where a person's seat tokens are kept, by table id. */
export const TOKENS_KEY = 'shb-tables-v1';
export const NAME_KEY = 'shb-name';
const BACKOFF_MS = [1000, 2000, 4000, 8000, 15000];
const PING_MS = 25_000;
/** No message at all for this long: the socket is dead, whatever it says. */
const SILENT_MS = 60_000;
/** Distinct errors a page sends to the game log. */
const OOPS_MAX = 5;

interface Saved { token: string }

function readTokens(storage: Storage | null): Record<string, Saved> {
  try {
    const v = JSON.parse(storage?.getItem(TOKENS_KEY) ?? '{}');
    return v && typeof v === 'object' ? v : {};
  } catch {
    return {};
  }
}

function writeToken(storage: Storage | null, tableId: string, token: string | null): void {
  try {
    const all = readTokens(storage);
    if (token) all[tableId] = { token };
    else delete all[tableId];
    storage?.setItem(TOKENS_KEY, JSON.stringify(all));
  } catch { /* storage full or blocked: the seat lasts this visit only */ }
}

export interface RemoteOptions {
  storage?: Storage | null;
  /** Opens the socket; the browser's WebSocket by default. */
  socket?: (url: string) => SocketLike;
  /** The socket's address; the page's own host by default. */
  url?: string;
  /** Called once for each finished board, to keep it in History. */
  onfinished?: (record: HistoryRecord) => void;
  timers?: { setTimeout(fn: () => void, ms: number): unknown; clearTimeout(h: unknown): void; now(): number };
}

const EMPTY_HANDS = (): Record<Seat, Card[]> => ({ North: [], East: [], South: [], West: [] });

export class RemoteTable implements TableSource {
  readonly tableId: string;
  status = $state<Status>('connecting');
  /** The latest view from the server. */
  view = $state.raw<TableView | null>(null);
  /** The board as shown: the latest, or the moment being held. */
  private shown = $state.raw<BoardView | null>(null);
  private hold = $state<'none' | 'contract' | 'trick'>('none');
  private queue: BoardView[] = [];
  /** The last refusal, in words, until the next action. */
  error = $state<string | null>(null);
  /** An action sent and not yet seen landing: resent after a reconnect. */
  private outbox: { msg: ClientMessage; board: number; at: number; id: string } | null = null;
  private socket: SocketLike | null = null;
  private attempts = 0;
  private retryTimer: unknown;
  private pingTimer: unknown;
  private lastHeard = 0;
  private closed = false;
  private seq = 0;
  private savedBoards = new Set<string>();
  private records = $state<HistoryRecord[]>([]);
  private passedOut = $state(0);
  private storage: Storage | null;
  private open: (url: string) => SocketLike;
  private url: string;
  private timers: NonNullable<RemoteOptions['timers']>;
  private onfinished: (record: HistoryRecord) => void;
  private oopsSent = new Set<string>();

  constructor(tableId: string, o: RemoteOptions = {}) {
    this.tableId = tableId;
    this.storage = o.storage ?? null;
    this.open = o.socket ?? ((url) => new WebSocket(url) as unknown as SocketLike);
    const loc = (globalThis as { location?: Location }).location;
    this.url = o.url ?? `${loc?.protocol === 'https:' ? 'wss' : 'ws'}://${loc?.host}/tables/${tableId}/ws`;
    this.timers = o.timers ?? {
      setTimeout: (fn, ms) => setTimeout(fn, ms), clearTimeout: (h) => clearTimeout(h as number), now: () => Date.now(),
    };
    this.onfinished = o.onfinished ?? (() => {});
    this.connect();
  }

  // ── The socket ─────────────────────────────────────────────────────────────

  private connect(): void {
    if (this.closed) return;
    this.status = this.view ? 'reconnecting' : 'connecting';
    let ws: SocketLike;
    try {
      ws = this.open(this.url);
    } catch {
      this.retry();
      return;
    }
    this.socket = ws;
    ws.onopen = () => {
      this.attempts = 0;
      this.lastHeard = this.timers.now();
      const token = readTokens(this.storage)[this.tableId]?.token;
      this.raw({ type: 'hello', v: PROTOCOL_VERSION, ...(token ? { token } : {}) });
      this.ping();
    };
    ws.onmessage = (e) => {
      this.lastHeard = this.timers.now();
      let m: ServerMessage;
      try {
        m = JSON.parse(String(e.data));
      } catch {
        return;
      }
      this.receive(m);
    };
    ws.onclose = (e) => {
      if (this.socket !== ws) return;
      this.socket = null;
      this.timers.clearTimeout(this.pingTimer);
      if (e.code === 4000) this.status = 'outdated';
      else if (e.code === 4001) this.status = 'removed';
      else if (e.code === 4004) this.status = 'gone';
      else this.retry();
    };
    ws.onerror = () => { /* onclose follows */ };
  }

  private retry(): void {
    if (this.closed) return;
    this.status = this.view ? 'reconnecting' : 'connecting';
    const wait = BACKOFF_MS[Math.min(this.attempts, BACKOFF_MS.length - 1)];
    this.attempts++;
    this.timers.clearTimeout(this.retryTimer);
    this.retryTimer = this.timers.setTimeout(() => this.connect(), wait);
  }

  /** Both sides ping, so a dead phone socket is noticed and a quiet table
   *  isn't cut by a router's idle timeout. */
  private ping(): void {
    this.timers.clearTimeout(this.pingTimer);
    this.pingTimer = this.timers.setTimeout(() => {
      if (!this.socket) return;
      if (this.timers.now() - this.lastHeard > SILENT_MS) {
        const dead = this.socket;
        this.socket = null;
        dead.close();
        this.retry();
        return;
      }
      this.raw({ type: 'ping' });
      this.ping();
    }, PING_MS);
  }

  /** The page came back (a phone unlocked): reconnect now, not on backoff. */
  wake(): void {
    if (this.closed) return;
    if (!this.socket && (this.status === 'reconnecting' || this.status === 'connecting')) {
      this.attempts = 0;
      this.timers.clearTimeout(this.retryTimer);
      this.connect();
    } else if (this.socket) this.raw({ type: 'ping' });
  }

  /** Leave the page: close the socket and stop reconnecting. */
  dispose(): void {
    this.closed = true;
    this.timers.clearTimeout(this.retryTimer);
    this.timers.clearTimeout(this.pingTimer);
    this.socket?.close(1000, 'Leaving');
    this.socket = null;
  }

  private raw(m: ClientMessage): void {
    try {
      if (this.socket && this.socket.readyState === 1) this.socket.send(JSON.stringify(m));
    } catch { /* closing; the close handler reconnects */ }
  }

  private receive(m: ServerMessage): void {
    if (m.type === 'welcome') {
      this.status = 'open';
      if (m.token) writeToken(this.storage, this.tableId, m.token);
      // Anything sent before the drop goes again: the server applies an
      // intent id once, so a resend of one that landed changes nothing.
      if (this.outbox) this.raw(this.outbox.msg);
    } else if (m.type === 'view') {
      this.status = 'open';
      this.accept(m.view);
    } else if (m.type === 'error') {
      if (m.code === 'bad_token') writeToken(this.storage, this.tableId, null);
      if (m.id && this.outbox?.id === m.id) this.outbox = null;
      this.error = m.message;
    }
  }

  // ── Views, and the moments held ────────────────────────────────────────────

  private accept(v: TableView): void {
    this.view = v;
    const b = v.board;
    if (this.outbox && b && (b.num !== this.outbox.board || b.at > this.outbox.at)) this.outbox = null;
    if (!b) {
      this.shown = null;
      this.queue = [];
      this.hold = 'none';
      return;
    }
    if (b.record && b.phase === 'done') this.save(b);
    if (!this.shown || this.shown.num !== b.num) {
      // A new board (or the first view): show it as it is.
      this.queue = [];
      this.hold = 'none';
      this.shown = b;
      return;
    }
    this.queue.push(b);
    if (this.hold === 'none') this.advance();
  }

  /** Show queued views until one is a moment to hold. */
  private advance(): void {
    while (this.queue.length) {
      const cur = this.shown!;
      const next = this.queue.shift()!;
      if (cur.phase === 'bidding' && next.contract && next.tricksLog.length === 0 && next.trick.length === 0
          && !next.passedOut) {
        this.shown = next;
        this.hold = 'contract';
        return;
      }
      if (next.tricksLog.length === cur.tricksLog.length + 1 && next.trick.length === 0) {
        this.shown = next;
        this.hold = 'trick';
        return;
      }
      this.shown = next;
    }
  }

  private save(b: BoardView): void {
    const key = `${b.num}:${b.dealer}:${b.calls.length}`;
    if (this.savedBoards.has(key)) return;
    this.savedBoards.add(key);
    if (b.passedOut) {
      this.passedOut += 1;
      return;
    }
    this.records = [...this.records, b.record!];
    this.onfinished(b.record!);
  }

  // ── TableSource ────────────────────────────────────────────────────────────

  get mySeat(): Seat { return this.view?.you.seat ?? 'South'; }
  get seated(): boolean { return !!this.view?.you.seat; }
  get boardNum(): number { return this.shown?.num ?? 0; }
  get dealer(): Seat { return this.shown?.dealer ?? 'North'; }
  get vulnerability(): Vulnerability { return this.shown?.vulnerability ?? 'None'; }
  get hands(): Record<Seat, Card[]> { return this.shown?.hands ?? EMPTY_HANDS(); }
  get calls(): CallRecord[] { return this.shown?.calls ?? []; }
  get alerts(): Record<number, string> { return this.shown?.alerts ?? {}; }
  get liveAlerts(): Record<number, string> { return this.alerts; }
  get contract(): Contract | null { return this.shown?.contract ?? null; }
  get result(): ScoreResult | null { return this.shown?.result ?? null; }
  get tricksTaken(): Record<Side, number> { return this.shown?.tricksTaken ?? { 'N/S': 0, 'E/W': 0 }; }
  get tricksLog(): TrickLog[] { return this.shown?.tricksLog ?? []; }
  get challenge(): ChallengeResult | null { return null; }
  get challengeId(): number | null { return null; }
  get challengeLog(): ChallengeLogEntry[] { return []; }
  get history(): HistoryRecord[] { return this.records; }
  get passedOutCount(): number { return this.passedOut; }
  get trump(): string | null { return this.contract?.trump ?? null; }
  get gameOver(): boolean { return this.result !== null; }
  get boardOver(): boolean { return this.gameOver || !!this.shown?.passedOut; }

  auction = $derived.by(() => {
    const a = new AuctionState(this.dealer, this.vulnerability);
    for (const [p, c] of this.calls) a.applyCall(p, c);
    return a;
  });

  get phase(): Phase {
    const b = this.shown;
    if (!b) return 'bidding';
    if (this.hold === 'contract') return 'auction_done';
    if (this.hold === 'trick') return 'trick_done';
    if (b.phase === 'done') return b.passedOut ? 'bidding' : 'done';
    return b.phase;
  }

  get trick(): Play[] {
    const b = this.shown;
    if (!b) return [];
    return this.hold === 'trick' ? b.tricksLog.at(-1)!.plays : b.trick;
  }

  get trickNum(): number {
    const b = this.shown;
    if (!b) return 1;
    // Held or not, the trick on the felt is numbered after the tricks done:
    // a held trick is already in the log, as in Game after endTrick.
    return b.tricksLog.length + 1;
  }

  get trickWinner(): Seat | null {
    return this.hold === 'trick' ? this.shown!.tricksLog.at(-1)!.winner : null;
  }

  /** The seat you are to play from now, if any: only on the latest view. */
  whoseTurn(): Seat | null {
    const b = this.shown;
    if (!b || this.hold !== 'none' || this.queue.length || b.phase !== 'playing') return null;
    return b.actor === this.view?.you.seat ? b.toAct : null;
  }

  cardCount(p: Seat): number {
    return this.shown?.counts[p] ?? 0;
  }

  playerName(p: Seat): string | null {
    return this.view?.seats[p].name ?? null;
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  private act(m: ClientMessage & { at: number; id: string }): void {
    this.error = null;
    this.outbox = { msg: m, board: this.shown?.num ?? 0, at: m.at, id: m.id };
    this.raw(m);
  }

  private intentId(): string {
    return `${this.timers.now().toString(36)}${(this.seq++).toString(36)}`;
  }

  humanBids(call: string, alert = ''): void {
    const b = this.shown;
    if (!b || this.hold !== 'none' || b.phase !== 'bidding' || b.toAct !== this.view?.you.seat) return;
    this.act({ type: 'call', id: this.intentId(), at: b.at, call, ...(alert.trim() ? { alert } : {}) });
  }

  humanPlays(player: Seat, c: Card): void {
    const b = this.shown!;
    if (this.whoseTurn() !== player) return;
    this.act({ type: 'card', id: this.intentId(), at: b.at, seat: player, card: { suit: c.suit, rank: c.rank } });
  }

  startPlay(): void {
    if (this.hold !== 'contract') return;
    this.hold = 'none';
    this.advance();
  }

  nextTrick(): void {
    if (this.hold !== 'trick') return;
    this.hold = 'none';
    this.advance();
  }

  /** "Deal the next board": you're ready; the host deals at once. */
  newBoard(): void {
    this.error = null;
    this.raw({ type: 'deal' });
  }

  join(name: string): void {
    this.error = null;
    try { this.storage?.setItem(NAME_KEY, name); } catch { /* fine */ }
    this.raw({ type: 'join', name });
  }

  sit(seat: Seat): void { this.error = null; this.raw({ type: 'sit', seat }); }
  stand(): void { this.raw({ type: 'stand' }); }
  robot(seat: Seat): void { this.raw({ type: 'robot', seat }); }
  reclaim(): void { this.raw({ type: 'reclaim' }); }
  lock(locked: boolean): void { this.raw({ type: 'lock', locked }); }
  remove(playerId: string): void { this.raw({ type: 'remove', player: playerId }); }

  // ── The game log ───────────────────────────────────────────────────────────

  /** What only the page knows: its layout and size, its build, and which
   *  moment of the board it shows. */
  private clientInfo(layout: 'phone' | 'desktop'): ClientInfo {
    const g = globalThis as { innerWidth?: number; innerHeight?: number; navigator?: Navigator };
    const size = (n: number | undefined) => Math.max(0, Math.min(99_999, Math.round(n ?? 0)));
    return {
      layout, width: size(g.innerWidth), height: size(g.innerHeight),
      ua: (g.navigator?.userAgent ?? '').slice(0, 200), build: String(import.meta.env.VITE_BUILD ?? 'dev').slice(0, 40),
      board: this.shown?.num ?? null, shownAt: this.shown?.at ?? null, hold: this.hold,
    };
  }

  /** "Report a problem": the note, with what this page shows, to the game
   *  log. False when the table isn't connected, so the page can say so. */
  report(note: string, layout: 'phone' | 'desktop'): boolean {
    if (!this.socket || this.socket.readyState !== 1) return false;
    // Cleaned here as on the server, so escaping can't push it past the size cap.
    this.raw({ type: 'report', note: cleanNote(note), client: this.clientInfo(layout) });
    return true;
  }

  /** An error this page caught, to the game log: each message once, and a
   *  few at most, so a loop can't flood it. */
  oops(message: string, where: string, layout: 'phone' | 'desktop'): void {
    const key = cleanNote(message, 300);
    if (this.oopsSent.has(key) || this.oopsSent.size >= OOPS_MAX) return;
    this.oopsSent.add(key);
    this.raw({ type: 'oops', message: key, where: cleanNote(where, 600), client: this.clientInfo(layout) });
  }
}
