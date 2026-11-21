// A deal's double dummy table (tricks in each strain by each declarer) and
// its par, for History. Challenge deals have theirs stored; any other deal is
// solved on a tap in a worker, a minute or more, and kept on this device so
// it's never solved twice.
import library from '$root/data/solved_deals.json';
import { PLAYERS } from '../engine/auction';
import { STRAINS, cardKey, type Card, type Seat, type Side, type Strain, type Vulnerability } from '../engine/card';
import { parFromTricks, type Par } from '../engine/challenge';
import { browserStorage } from '../saves';
import workerUrl from './tableWorker.ts?worker&url';

/** Strain -> declarer -> the declaring side's tricks. */
export type Tricks = Partial<Record<Strain, Record<Seat, number>>>;

const CACHE_KEY = 'shb-dd-tables-v1';
/** Deals kept: History keeps 500 boards. */
const CACHE_MAX = 500;
const SIDES: Record<Side, readonly Seat[]> = { 'N/S': ['North', 'South'], 'E/W': ['East', 'West'] };

/** One string per deal: each seat's cards in a fixed order. */
export function dealKey(hands: Record<Seat, Card[]>): string {
  return PLAYERS.map((p) => hands[p].map(cardKey).sort().join(' ')).join('|');
}

const STORED = new Map<string, Tricks>();
for (const d of (library as { deals: { hands: Record<Seat, string>; tricks: Record<string, number> }[] }).deals) {
  const key = PLAYERS.map((p) => d.hands[p].split(' ').sort().join(' ')).join('|');
  STORED.set(key, Object.fromEntries(STRAINS.map((s) =>
    [s, Object.fromEntries(PLAYERS.map((p) => [p, d.tricks[`${s}:${p}`]]))])) as Tricks);
}

function loadCache(): Record<string, number[]> {
  try {
    const v = JSON.parse(browserStorage()?.getItem(CACHE_KEY) ?? '{}');
    return v && typeof v === 'object' && !Array.isArray(v) ? v : {};
  } catch {
    return {};
  }
}

/** 20 numbers: strains C..NT, declarers North East South West. */
function fromRow(row: unknown): Tricks | null {
  if (!Array.isArray(row) || row.length !== 20 || !row.every((n) => Number.isInteger(n) && n >= 0 && n <= 13)) return null;
  return Object.fromEntries(STRAINS.map((s, i) =>
    [s, Object.fromEntries(PLAYERS.map((p, j) => [p, row[4 * i + j]]))])) as Tricks;
}

function remember(key: string, t: Tricks): void {
  try {
    const cache = loadCache();
    delete cache[key];
    cache[key] = STRAINS.flatMap((s) => PLAYERS.map((p) => t[s]![p]));
    const keys = Object.keys(cache);
    for (const k of keys.slice(0, Math.max(0, keys.length - CACHE_MAX))) delete cache[k];
    browserStorage()?.setItem(CACHE_KEY, JSON.stringify(cache));
  } catch {
    // Storage full or blocked: the table is still shown, just not kept.
  }
}

export function complete(t: Tricks): boolean {
  return STRAINS.every((s) => t[s]);
}

/** Par from N/S's side, both sides bidding. */
export function parOf(t: Tricks, vulnerability: Vulnerability): Par {
  return parFromTricks((strain, side) => Math.max(...SIDES[side].map((p) => t[strain]![p])), 'N/S', vulnerability);
}

export class DdTable {
  tricks = $state<Tricks>({});
  running = $state(false);
  error = $state('');
  private worker: Worker | null = null;
  private key: string;

  constructor(private hands: Record<Seat, Card[]>) {
    this.key = dealKey(hands);
    const known = STORED.get(this.key) ?? fromRow(loadCache()[this.key]);
    if (known) this.tricks = known;
  }

  get done(): boolean {
    return complete(this.tricks);
  }

  start(): void {
    if (this.worker || this.done) return;
    if (typeof Worker === 'undefined') {
      this.error = 'needs a browser with Web Workers.';
      return;
    }
    this.error = '';
    this.tricks = {};
    this.running = true;
    const worker = new Worker(workerUrl, { type: 'module' });
    this.worker = worker;
    worker.onmessage = (e: MessageEvent<{ strain?: Strain; tricks?: Record<Seat, number>; done?: boolean; error?: string }>) => {
      const m = e.data;
      if (m.strain && m.tricks) this.tricks = { ...this.tricks, [m.strain]: m.tricks };
      else if (m.done) {
        remember(this.key, this.tricks);
        this.stop();
      } else if (m.error) {
        this.error = `${m.error.replace(/^double dummy: /, '')}.`;
        this.stop();
      }
    };
    worker.onerror = (e) => {
      e.preventDefault();
      this.error = e.message ? `stopped (${e.message}).` : 'the solver stopped.';
      this.stop();
    };
    worker.postMessage({ hands: $state.snapshot(this.hands) });
  }

  stop(): void {
    this.worker?.terminate();
    this.worker = null;
    this.running = false;
  }
}
