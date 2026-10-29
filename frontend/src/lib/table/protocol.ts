// The multiplayer table's messages, imported by the server and the browser.
// JSON over one WebSocket; every message has a `type`. A client message is
// parsed with `parseClientMessage`, which refuses anything not exactly one of
// the shapes below: the server never trusts a field it didn't check.
//
// The server answers every change with the seat's whole `TableView` (a few
// KB), rather than deltas: nothing to get out of step, and a reconnect is the
// same message as any other update.
import { RANKS, SUITS, type Card, type Seat, type Side, type Suit, type Vulnerability } from '../engine/card';
import { PLAYERS, type CallRecord, type Contract, type Play } from '../engine/auction';
import type { ScoreResult } from '../engine/scoring';
import type { TrickLog } from '../engine/challenge';
import type { HistoryRecord } from '../saves';

export const PROTOCOL_VERSION = 1;
/** Inbound messages longer than this close the socket. */
export const MAX_MESSAGE_BYTES = 2048;
export const NAME_MAX = 20;
/** Table ids are 128 random bits as unpadded base64url. */
export const TABLE_ID_RE = /^[A-Za-z0-9_-]{22}$/;
const TOKEN_RE = /^[A-Za-z0-9_-]{22}$/;
const INTENT_RE = /^[A-Za-z0-9_-]{1,40}$/;

export type ClientMessage =
  | { type: 'hello'; v: number; token?: string }
  | { type: 'join'; name: string }
  | { type: 'sit'; seat: Seat }
  | { type: 'stand' }
  | { type: 'call'; id: string; at: number; call: string; alert?: string }
  | { type: 'card'; id: string; at: number; seat: Seat; card: Card }
  | { type: 'deal' }
  | { type: 'robot'; seat: Seat }
  | { type: 'reclaim' }
  | { type: 'lock'; locked: boolean }
  | { type: 'remove'; player: string }
  | { type: 'ping' };

export type ErrorCode =
  | 'bad_message' | 'version' | 'no_table' | 'bad_token' | 'not_joined' | 'locked' | 'full'
  | 'seat_taken' | 'not_your_turn' | 'illegal' | 'stale' | 'not_host' | 'not_now' | 'rate';

export type ServerMessage =
  | { type: 'welcome'; playerId: string | null; token?: string }
  | { type: 'view'; view: TableView }
  | { type: 'error'; id?: string; code: ErrorCode; message: string }
  | { type: 'pong' };

export interface SeatView {
  /** The person sitting there; null when it's a robot's seat. */
  name: string | null;
  playerId: string | null;
  connected: boolean;
  /** A robot plays the seat for now: empty, or handed over. */
  robot: boolean;
  /** The seat's player has been gone long enough for a robot to take over. */
  away: boolean;
  ready: boolean;
}

export interface BoardView {
  num: number;
  dealer: Seat;
  vulnerability: Vulnerability;
  phase: 'bidding' | 'playing' | 'done';
  calls: CallRecord[];
  /** The alerts this seat may see now (all of them once the board is over). */
  alerts: Record<number, string>;
  /** The cards this seat can see; every other hand is empty. */
  hands: Record<Seat, Card[]>;
  counts: Record<Seat, number>;
  contract: Contract | null;
  passedOut: boolean;
  /** The trick in progress; empty between tricks. */
  trick: Play[];
  tricksLog: TrickLog[];
  tricksTaken: Record<Side, number>;
  result: ScoreResult | null;
  /** The seat whose call or card is awaited, and the seat that chooses it
   *  (the declarer, for dummy). */
  toAct: Seat | null;
  actor: Seat | null;
  /** Actions on the board so far: what an intent's `at` must equal. */
  at: number;
  /** The whole board, once it's over: what History saves. */
  record: HistoryRecord | null;
}

export interface TableView {
  tableId: string;
  /** Rises with every change at the table. */
  version: number;
  you: { playerId: string | null; seat: Seat | null; isHost: boolean };
  seats: Record<Seat, SeatView>;
  /** People at the table without a seat. */
  watching: string[];
  locked: boolean;
  board: BoardView | null;
}

// ── Parsing ──────────────────────────────────────────────────────────────────

const isObj = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);
const isSeat = (v: unknown): v is Seat => PLAYERS.includes(v as Seat);
const isStr = (v: unknown, max: number): v is string => typeof v === 'string' && v.length <= max;
const isCount = (v: unknown): v is number => Number.isInteger(v) && (v as number) >= 0 && (v as number) < 1000;
const isCall = (v: unknown): v is string =>
  typeof v === 'string' && (v === 'Pass' || v === 'X' || v === 'XX' || /^[1-7](C|D|H|S|NT)$/.test(v));
const isCard = (v: unknown): v is Card =>
  isObj(v) && SUITS.includes(v.suit as Suit) && RANKS.includes(v.rank as string)
  && Object.keys(v).length === 2;

/** Only these keys, so nothing unexpected rides along into the state. */
function keys(m: Record<string, unknown>, allowed: string[]): boolean {
  return Object.keys(m).every((k) => allowed.includes(k));
}

/** The message, or null if it isn't exactly a known one. */
export function parseClientMessage(raw: string): ClientMessage | null {
  if (raw.length > MAX_MESSAGE_BYTES) return null;
  let m: unknown;
  try {
    m = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isObj(m) || typeof m.type !== 'string') return null;
  switch (m.type) {
    case 'hello':
      if (!keys(m, ['type', 'v', 'token']) || !Number.isInteger(m.v)) return null;
      if (m.token !== undefined && !(typeof m.token === 'string' && TOKEN_RE.test(m.token))) return null;
      return { type: 'hello', v: m.v as number, ...(m.token ? { token: m.token as string } : {}) };
    case 'join':
      if (!keys(m, ['type', 'name']) || !isStr(m.name, 200)) return null;
      return { type: 'join', name: m.name };
    case 'sit':
      if (!keys(m, ['type', 'seat']) || !isSeat(m.seat)) return null;
      return { type: 'sit', seat: m.seat };
    case 'robot':
      if (!keys(m, ['type', 'seat']) || !isSeat(m.seat)) return null;
      return { type: 'robot', seat: m.seat };
    case 'call':
      if (!keys(m, ['type', 'id', 'at', 'call', 'alert'])) return null;
      if (!isStr(m.id, 40) || !INTENT_RE.test(m.id) || !isCount(m.at) || !isCall(m.call)) return null;
      if (m.alert !== undefined && !isStr(m.alert, 500)) return null;
      return { type: 'call', id: m.id, at: m.at, call: m.call, ...(m.alert ? { alert: m.alert as string } : {}) };
    case 'card':
      if (!keys(m, ['type', 'id', 'at', 'seat', 'card'])) return null;
      if (!isStr(m.id, 40) || !INTENT_RE.test(m.id) || !isCount(m.at) || !isSeat(m.seat) || !isCard(m.card)) return null;
      return { type: 'card', id: m.id, at: m.at, seat: m.seat, card: { suit: m.card.suit as Suit, rank: m.card.rank as string } };
    case 'lock':
      if (!keys(m, ['type', 'locked']) || typeof m.locked !== 'boolean') return null;
      return { type: 'lock', locked: m.locked };
    case 'remove':
      if (!keys(m, ['type', 'player']) || !isStr(m.player, 40)) return null;
      return { type: 'remove', player: m.player };
    case 'stand': case 'deal': case 'reclaim': case 'ping':
      if (!keys(m, ['type'])) return null;
      return { type: m.type };
    default:
      return null;
  }
}

/** Control, zero-width, invisible-filler and bidi-override characters, built from code points
 *  so the source holds none of them. */
const INVISIBLE = new RegExp(`[${[[0x00, 0x1f], [0x7f, 0x9f], [0xad, 0xad], [0x200b, 0x200f], [0x2028, 0x202e], [0x2060, 0x2069],
  [0x3164, 0x3164], [0xfeff, 0xfeff]]
  .map(([a, b]) => `${String.fromCharCode(a)}-${String.fromCharCode(b)}`).join('')}]`, 'g');

/** A display name: one line, no control characters, at most 20 characters.
 *  Empty after cleaning means refused. Svelte escapes it when shown. */
export function cleanName(text: string): string {
  const flat = text.replace(INVISIBLE, ' ');
  return [...flat.replace(/\s+/g, ' ').trim()].slice(0, NAME_MAX).join('').trim();
}
