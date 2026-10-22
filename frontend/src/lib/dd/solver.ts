// The double dummy solver (research/solver-rs, compiled to WebAssembly by
// `npm run wasm`) for one played board. Runs anywhere WebAssembly does: the
// History replayer's worker, and Node in dd.test.ts.
import { RANKS, SUITS, type Card, type Seat, type Strain } from '../engine/card';

const SEATS: readonly Seat[] = ['North', 'East', 'South', 'West'];

/** Table entries per board. About 130 MB of WebAssembly memory at its peak:
 *  enough for a phone, and the last 11 tricks never reach it. */
export const TABLE_LIMIT = 1_000_000;

interface Exports {
  memory: WebAssembly.Memory;
  input(words: number): number;
  output(): number;
  load(): number;
  analyse(i: number): number;
  table_entries(): number;
  unload(): void;
}

export interface PlayedBoard {
  hands: Record<Seat, Card[]>;
  leader: Seat;
  strain: Strain;
  /** Every card played, in order. A claimed board stops early. */
  plays: Card[];
}

const index = (c: Card): number => 13 * SUITS.indexOf(c.suit) + RANKS.indexOf(c.rank);
const fromIndex = (i: number): string => `${RANKS[i % 13]}${SUITS[Math.floor(i / 13)]}`;

export class DdSolver {
  private x: Exports;

  constructor(instance: WebAssembly.Instance) {
    this.x = instance.exports as unknown as Exports;
  }

  static async fromBytes(bytes: BufferSource): Promise<DdSolver> {
    const { instance } = await WebAssembly.instantiate(bytes, {});
    return new DdSolver(instance);
  }

  /** Load a board. Throws, naming the problem, on one the solver can't read. */
  load(board: PlayedBoard, limit = TABLE_LIMIT): void {
    const words = [SEATS.indexOf(board.leader), board.strain === 'NT' ? 4 : SUITS.indexOf(board.strain),
      limit, board.plays.length];
    for (const seat of SEATS) {
      let lo = 0, hi = 0;
      for (const c of board.hands[seat]) {
        const i = index(c);
        if (i < 32) lo |= 1 << i; else hi |= 1 << (i - 32);
      }
      words.push(lo >>> 0, hi >>> 0);
    }
    words.push(...board.plays.map(index));
    const ptr = this.x.input(words.length);
    new Uint32Array(this.x.memory.buffer, ptr, words.length).set(words);
    const status = this.x.load();
    if (status === -1) throw new Error('double dummy: malformed board');
    if (status === -2) throw new Error('double dummy: the hands overlap or differ in size');
    if (status <= -100) throw new Error(`double dummy: play ${status * -1 - 100 + 1} is not legal`);
  }

  /** Each legal card before play `i` (0-based), keyed like "10H", with N/S's
   *  tricks for the rest of the hand after it, both sides perfect. */
  analyse(i: number): Map<string, number> {
    const n = this.x.analyse(i);
    if (n < 0) throw new Error(`double dummy: no play ${i} on the loaded board`);
    const out = new Uint32Array(this.x.memory.buffer, this.x.output(), 2 * n);
    const values = new Map<string, number>();
    for (let k = 0; k < n; k++) values.set(fromIndex(out[2 * k]), out[2 * k + 1]);
    return values;
  }

  tableEntries(): number {
    return this.x.table_entries();
  }

  unload(): void {
    this.x.unload();
  }
}
