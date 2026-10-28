// Double dummy analysis of one finished board for the History replayer:
// every decision's card values, filled in from the last trick backwards in a
// worker, so the endgame appears at once and the expensive early tricks come
// last. Port of the idea in web/analysis_view.py, on the WebAssembly solver.
import { PARTNERSHIP } from '../engine/auction';
import { cardKey, type Card, type Seat } from '../engine/card';
import type { HistoryRecord } from '../game.svelte';
import type { PlayedBoard } from './solver';
import workerUrl from './worker.ts?worker&url';

/** Decisions with at most this many cards in hand are analysed at once.
 *  The last 11 tricks took 0.9 s median and 4.9 s at worst on a laptop over
 *  38 library boards; the first two tricks take minutes on hard deals, so
 *  they wait for a tap (`deeper`). */
export const AUTO_CARDS = 11;

/** How one card would leave the contract: "+2", "−1" or "=". */
export interface Mark {
  text: string;
  tone: 'over' | 'down' | 'even';
  label: string;
}

/** A card that cost its side tricks against the best card it held. */
export interface Loss {
  /** Decision index: cards played before it. */
  i: number;
  seat: Seat;
  card: Card;
  /** Tricks given away, at least 1. */
  cost: number;
  /** Keys of the cards that would have kept them. */
  best: string[];
}

/** Every analysed decision where the card played was worse for its side than
 *  the best one held, in play order. `seats[i]` and `plays[i]` are the seat and
 *  card of decision i; `values` as on `DdAnalysis`. */
export function tricksLost(seats: Seat[], plays: Card[], values: Record<number, Record<string, number>>): Loss[] {
  const out: Loss[] = [];
  for (let i = 0; i < plays.length; i++) {
    const rest = values[i];
    if (!rest) continue;
    // N/S want the most N/S tricks, E/W the fewest.
    const sign = PARTNERSHIP[seats[i]] === 'N/S' ? 1 : -1;
    const top = Math.max(...Object.values(rest).map((v) => sign * v));
    const cost = top - sign * rest[cardKey(plays[i])];
    if (cost > 0) {
      const best = Object.keys(rest).filter((k) => sign * rest[k] === top);
      out.push({ i, seat: seats[i], card: plays[i], cost, best });
    }
  }
  return out;
}

export class DdAnalysis {
  /** Decision index (cards played before it) -> card key -> N/S tricks for the rest. */
  values = $state<Record<number, Record<string, number>>>({});
  /** Why the analysis stopped, shown after "Double dummy:". */
  error = $state('');
  /** The error may pass on a second try (a download or a crash, not a
   *  refused board or an updated app). */
  canRetry = $state(false);
  running = $state(false);
  /** The early tricks have been asked for. */
  deep = $state(false);

  private worker: Worker | null = null;
  private plays: Card[];
  private seats: Seat[];
  private pending: number[] = [];
  /** The worker's script has run: an error before it means it never loaded. */
  private ready = false;
  /** Quiet retries left for a worker that didn't load (a dropped connection). */
  private retries = 1;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;

  constructor(private record: HistoryRecord) {
    this.plays = record.tricks_log.flatMap((t) => t.plays.map(([, c]) => c));
    this.seats = record.tricks_log.flatMap((t) => t.plays.map(([p]) => p));
  }

  /** Decisions latest first, deepest last. */
  private order(fromCards: number, toCards: number): number[] {
    const out: number[] = [];
    for (let i = this.plays.length - 1; i >= 0; i--) {
      const cards = 13 - Math.floor(i / 4);
      if (cards <= fromCards && cards > toCards) out.push(i);
    }
    return out;
  }

  start(): void {
    const c = this.record.contract;
    if (!c || this.worker || !this.plays.length) return;
    if (typeof Worker === 'undefined') {
      this.error = 'needs a browser with Web Workers.';
      return;
    }
    const board: PlayedBoard = {
      hands: this.record.initial_hands,
      leader: this.record.tricks_log[0].leader,
      strain: c.strain,
      plays: this.plays,
    };
    this.error = '';
    this.canRetry = false;
    this.ready = false;
    const worker = new Worker(workerUrl, { type: 'module' });
    this.worker = worker;
    worker.onmessage = (e) => this.receive(e.data);
    worker.onerror = (e) => {
      e.preventDefault();
      if (this.worker === worker) void this.failed(e.message);
    };
    // Decisions already in (from before a retry) aren't asked for again.
    const order = [...this.order(AUTO_CARDS, 0), ...(this.deep ? this.order(13, AUTO_CARDS) : [])];
    this.send(order.filter((i) => !this.values[i]), $state.snapshot(board));
  }

  /** Start again after an error that may pass. */
  retry(): void {
    this.stop();
    this.start();
  }

  /** The worker died. One that never ran its script didn't load: after a
   *  deploy, the page's copy points at a file the site no longer has. */
  private async failed(message: string): Promise<void> {
    const loaded = this.ready;
    this.stop();
    if (!loaded) {
      let status = 0;
      try {
        status = (await fetch(workerUrl, { method: 'HEAD', cache: 'no-store' })).status;
      } catch {
        // Offline: status stays 0.
      }
      if (status === 404) {
        this.error = 'the app has been updated. Reload the page.';
        return;
      }
      if (this.retries-- > 0) {
        this.running = true;
        this.retryTimer = setTimeout(() => this.start(), 1000);
        return;
      }
      this.error = "couldn't load the solver. Check the connection.";
    } else {
      this.error = message ? `stopped (${message}).` : 'the solver stopped.';
    }
    this.canRetry = true;
  }

  /** Analyse the tricks AUTO_CARDS leaves out. */
  deeper(): void {
    if (this.deep || !this.worker) return;
    this.deep = true;
    this.send(this.order(13, AUTO_CARDS));
  }

  stop(): void {
    clearTimeout(this.retryTimer);
    this.worker?.terminate();
    this.worker = null;
    this.pending = [];
    this.running = false;
  }

  private send(order: number[], board?: PlayedBoard): void {
    this.pending.push(...order);
    this.running = true;
    this.worker!.postMessage({ board, order });
  }

  private receive(msg: { ready?: boolean; i?: number; values?: [string, number][]; done?: boolean; error?: string }): void {
    if (msg.ready) {
      this.ready = true;
    } else if (msg.error) {
      // The solver's own messages start "double dummy:", which the view says.
      this.error = `${msg.error.replace(/^double dummy: /, '')}.`;
      this.canRetry = msg.error.startsWith("couldn't load");
      this.stop();
    } else if (msg.values && msg.i !== undefined) {
      this.values[msg.i] = Object.fromEntries(msg.values);
      this.pending = this.pending.filter((p) => p !== msg.i);
    } else if (msg.done) {
      this.running = this.pending.length > 0;
    }
  }

  /** The earliest trick (1-13) from which every decision to the end is in;
   *  past the last trick played (14 on a full board) before any. */
  get doneFrom(): number {
    let t = Math.ceil(this.plays.length / 4);
    while (t >= 1 && [0, 1, 2, 3].every((k) => (t - 1) * 4 + k >= this.plays.length || this.values[(t - 1) * 4 + k])) t--;
    return t + 1;
  }

  /** The marks for decision `i`, keyed by card, or null while it's pending. */
  marks(i: number): Record<string, Mark> | null {
    const rest = this.values[i];
    const c = this.record.contract;
    if (!rest || !c) return null;
    let won = 0;
    for (const t of this.record.tricks_log.slice(0, Math.floor(i / 4))) if (PARTNERSHIP[t.winner] === 'N/S') won++;
    const out: Record<string, Mark> = {};
    for (const [key, tricks] of Object.entries(rest)) {
      const ns = won + tricks;
      const diff = (c.side === 'N/S' ? ns : 13 - ns) - c.tricks_needed;
      out[key] = diff > 0 ? { text: `+${diff}`, tone: 'over', label: `makes with ${diff} overtrick${diff === 1 ? '' : 's'}` }
        : diff < 0 ? { text: `−${-diff}`, tone: 'down', label: `down ${-diff}` }
        : { text: '=', tone: 'even', label: 'makes exactly' };
    }
    return out;
  }

  /** The cards that gave tricks away, among the decisions analysed so far. */
  get losses(): Loss[] {
    return tricksLost(this.seats, this.plays, this.values);
  }

  /** The card actually played at decision `i`. */
  played(i: number): string | null {
    return this.plays[i] ? cardKey(this.plays[i]) : null;
  }
}
