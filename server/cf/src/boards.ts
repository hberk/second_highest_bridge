// Finished boards the app shares, anonymously (docs/SHARED_BOARDS.md), into
// the D1 database `bridge_boards`: one row per board, so the robots can be
// studied on everyone's play, not only on boards we deal ourselves.
//
// What a row never holds: an address, a name, an id of a player or a device,
// or any text a person typed. The app sends none of those, and this file
// rebuilds every row from the board itself, so a forged request can't add
// one either: the LIN is re-parsed and written again without names or
// alerts, the calls are replayed, and every number is range-checked. The day
// comes from this clock, never the client's.
//
// Free plan: D1 allows 100,000 rows written and 5 M read a day, apart from the
// Durable Object allowance the tables use.
import { fromLin, toLin } from '../../../frontend/src/lib/lin';
import {
  AuctionState, DEALER_ROTATION, VUL_ROTATION, type Contract,
} from '../../../frontend/src/lib/engine/auction';
import type { HistoryRecord } from '../../../frontend/src/lib/saves';
import {
  MAX_SHARE_BATCH, MAX_SHARE_BYTES, SHARE_MODES, type SharedBoard,
} from '../../../frontend/src/lib/shareRecord';

/** The table, made on first use (no migration step in the deploy). The
 *  columns are what docs/SHARED_BOARDS.md explains and its queries read. */
export const SCHEMA = `CREATE TABLE IF NOT EXISTS boards (
  id INTEGER PRIMARY KEY,
  day TEXT NOT NULL,
  mode TEXT NOT NULL,
  app TEXT NOT NULL,
  deal_id INTEGER,
  board_num INTEGER NOT NULL,
  dealer TEXT NOT NULL,
  vul TEXT NOT NULL,
  auction TEXT NOT NULL,
  contract TEXT,
  declarer TEXT,
  tricks INTEGER,
  ns_score INTEGER,
  you REAL,
  robot REAL,
  margin REAL,
  your_bidding_loss REAL,
  your_play_loss REAL,
  robot_bidding_loss REAL,
  robot_play_loss REAL,
  par REAL,
  lin TEXT
)`;

/** One row, as inserted (the column order of INSERT below). */
export interface BoardRow {
  day: string;
  mode: string;
  app: string;
  deal_id: number | null;
  board_num: number;
  dealer: string;
  vul: string;
  auction: string;
  contract: string | null;
  declarer: string | null;
  tricks: number | null;
  ns_score: number | null;
  you: number | null;
  robot: number | null;
  margin: number | null;
  your_bidding_loss: number | null;
  your_play_loss: number | null;
  robot_bidding_loss: number | null;
  robot_play_loss: number | null;
  par: number | null;
  lin: string | null;
}

const COLUMNS: (keyof BoardRow)[] = ['day', 'mode', 'app', 'deal_id', 'board_num', 'dealer', 'vul', 'auction',
  'contract', 'declarer', 'tricks', 'ns_score', 'you', 'robot', 'margin', 'your_bidding_loss', 'your_play_loss',
  'robot_bidding_loss', 'robot_play_loss', 'par', 'lin'];
const INSERT = `INSERT INTO boards (${COLUMNS.join(', ')}) VALUES (${COLUMNS.map(() => '?').join(', ')})`;

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const isId = (v: unknown): v is number => Number.isInteger(v) && (v as number) >= 0 && (v as number) < 100_000;
/** A score or a loss: bridge points, never past a grand slam redoubled. */
const isPoints = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && Math.abs(v) <= 10_000;

export const contractText = (c: Contract | null): string | null =>
  c ? `${c.level}${c.strain}${c.doubled === 'None' ? '' : c.doubled}` : null;

/** The calls as one string, from the dealer: "1C P 1H X ...". */
const callsText = (calls: [string, string][]): string => calls.map(([, c]) => (c === 'Pass' ? 'P' : c)).join(' ');

/** N/S's score on a played board, or null. */
function nsScore(r: HistoryRecord): number | null {
  if (r.passed_out) return 0;
  if (!r.result) return null;
  return r.result.winner === 'N/S' ? r.result.points : -r.result.points;
}

/** The row for one shared board, or why it was refused. */
export function rowFor(b: unknown, day: string): BoardRow | string {
  if (!isObject(b) || b.v !== 1) return 'not a board';
  const mode = b.mode as string;
  if (!SHARE_MODES.includes(mode as SharedBoard['mode'])) return 'mode';
  if (typeof b.app !== 'string' || !/^[0-9a-z.-]{1,20}$/.test(b.app)) return 'app';
  const empty = {
    day, mode, app: b.app, deal_id: null, contract: null, declarer: null, tricks: null, ns_score: null,
    you: null, robot: null, margin: null, your_bidding_loss: null, your_play_loss: null,
    robot_bidding_loss: null, robot_play_loss: null, par: null, lin: null,
  };

  if (mode === 'training') {
    // Bidding only: the deal is data/training_deals.json's `deal_id`, dealt
    // as board `board_num`, so only the calls are sent.
    const t = b.training;
    if (!isId(b.deal_id) || !Number.isInteger(b.board_num) || (b.board_num as number) < 1 || (b.board_num as number) > 1e6) return 'board';
    if (!Array.isArray(b.calls) || b.calls.length > 100 || !b.calls.every((c) => typeof c === 'string' && c.length <= 4)) return 'calls';
    if (!isObject(t) || !isPoints(t.score) || !isPoints(t.par) || !isPoints(t.robot_score)) return 'training';
    const n = b.board_num as number;
    const auction = new AuctionState(DEALER_ROTATION[(n - 1) % 4], VUL_ROTATION[(n - 1) % 16]);
    try {
      for (const c of b.calls as string[]) auction.applyCall(auction.currentPlayer(), c);
    } catch {
      return 'calls';
    }
    if (!auction.isComplete) return 'calls';
    const contract = auction.getContract();
    return {
      ...empty, deal_id: b.deal_id, board_num: n, dealer: auction.dealer, vul: auction.vulnerability,
      auction: callsText(auction.calls), contract: contractText(contract), declarer: contract?.declarer ?? null,
      you: t.score, robot: t.robot_score, margin: t.score - t.robot_score, par: t.par,
    };
  }

  // Solo and challenge: the whole board as LIN, replayed under this game's
  // rules (fromLin refuses an illegal call or card), then written again.
  if (typeof b.lin !== 'string' || b.lin.length > 4000) return 'lin';
  let r: HistoryRecord;
  try {
    r = fromLin(b.lin);
  } catch {
    return 'lin';
  }
  const row: BoardRow = {
    ...empty, board_num: r.board_num, dealer: r.dealer, vul: r.vulnerability,
    auction: callsText(r.auction_calls), contract: contractText(r.contract), declarer: r.contract?.declarer ?? null,
    tricks: r.contract ? r.tricks_taken[r.contract.side] : null, ns_score: nsScore(r),
    lin: toLin({ ...r, bid_alerts: {} }),
  };
  if (mode === 'challenge') {
    const c = b.challenge;
    if (!isId(b.deal_id)) return 'deal';
    if (!isObject(c)) return 'challenge';
    const keys = ['you', 'robot', 'your_bidding_loss', 'your_play_loss', 'robot_bidding_loss', 'robot_play_loss'] as const;
    if (!keys.every((k) => isPoints(c[k]))) return 'challenge';
    Object.assign(row, { deal_id: b.deal_id, margin: (c.you as number) - (c.robot as number) },
      Object.fromEntries(keys.map((k) => [k, c[k]])));
  }
  return row;
}

let ready: Promise<unknown> | null = null;

/** Store a batch the app sent. Returns how many rows went in; a refused
 *  board is skipped, never the batch. */
export async function storeBoards(db: D1Database, text: string, now = new Date()): Promise<{ stored: number; refused: string[] }> {
  if (text.length > MAX_SHARE_BYTES) return { stored: 0, refused: ['too big'] };
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    return { stored: 0, refused: ['not JSON'] };
  }
  const boards = isObject(body) && Array.isArray(body.boards) ? body.boards.slice(0, MAX_SHARE_BATCH) : [];
  const day = now.toISOString().slice(0, 10);
  const rows: BoardRow[] = [];
  const refused: string[] = [];
  for (const b of boards) {
    const row = rowFor(b, day);
    if (typeof row === 'string') refused.push(row);
    else rows.push(row);
  }
  if (!rows.length) return { stored: 0, refused };
  ready ??= db.prepare(SCHEMA).run().catch((e) => { ready = null; throw e; });
  await ready;
  await db.batch(rows.map((row) => db.prepare(INSERT).bind(...COLUMNS.map((k) => row[k]))));
  return { stored: rows.length, refused };
}
