// What the app shares of a finished board (docs/SHARED_BOARDS.md): the cards,
// the calls, the play and the scores, and nothing about who played. No name,
// no id of a player or a device, no alert text (a self-alert is typed text).
// Plain data and no network here: share.ts sends, server/cf/src/boards.ts
// checks and stores, and both read these shapes.
import { toLin } from './lin';
import type { CallRecord } from './engine/auction';
import type { ChallengeLogEntry, HistoryRecord } from './saves';
import pkg from '../../package.json';

export const SHARE_MODES = ['solo', 'challenge', 'training'] as const;
/** Boards one request carries, and its size, at most (the server's limits). */
export const MAX_SHARE_BATCH = 20;
export const MAX_SHARE_BYTES = 48_000;
/** Boards kept waiting on the device when sending fails; the oldest go first. */
export const MAX_SHARE_QUEUE = 40;
export const QUEUE_KEY = 'shb-share-queue';

export interface SharedBoard {
  v: 1;
  mode: (typeof SHARE_MODES)[number];
  /** The app's version, so a robot change can be told apart in the data. */
  app: string;
  /** Solo and challenge: the board as LIN, without names or alerts. */
  lin?: string;
  /** Challenge: data/solved_deals.json; training: data/training_deals.json. */
  deal_id?: number;
  /** Training: the board number (dealer and vulnerability) and the calls. */
  board_num?: number;
  calls?: string[];
  challenge?: Pick<ChallengeLogEntry, 'you' | 'robot' | 'your_bidding_loss' | 'your_play_loss' | 'robot_bidding_loss' | 'robot_play_loss'>;
  training?: { score: number; par: number; robot_score: number };
}

/** A solo or challenge board, from its Hand history record. */
export function playedShare(record: HistoryRecord, challenge: ChallengeLogEntry | null): SharedBoard {
  const lin = toLin({ ...record, bid_alerts: {}, label: undefined });
  if (!challenge) return { v: 1, mode: 'solo', app: pkg.version, lin };
  const { you, robot, your_bidding_loss, your_play_loss, robot_bidding_loss, robot_play_loss } = challenge;
  return {
    v: 1, mode: 'challenge', app: pkg.version, lin, deal_id: challenge.deal_id,
    challenge: { you, robot, your_bidding_loss, your_play_loss, robot_bidding_loss, robot_play_loss },
  };
}

/** A Bidding training board: the deal by its id, and your calls with the robots'. */
export function trainingShare(dealId: number, boardNum: number, calls: CallRecord[],
  scores: { score: number; par: number; robotScore: number }): SharedBoard {
  return {
    v: 1, mode: 'training', app: pkg.version, deal_id: dealId, board_num: boardNum,
    calls: calls.map(([, c]) => c),
    training: { score: scores.score, par: scores.par, robot_score: scores.robotScore },
  };
}

/** The boards waiting to be sent. Every access is guarded: a full or blocked
 *  storage only means a board isn't kept for a retry. */
export function readQueue(storage: Storage | null): SharedBoard[] {
  try {
    const v: unknown = JSON.parse(storage?.getItem(QUEUE_KEY) ?? '[]');
    return Array.isArray(v) ? v.filter((b) => typeof b === 'object' && b !== null && b.v === 1) : [];
  } catch {
    return [];
  }
}

export function writeQueue(storage: Storage | null, queue: SharedBoard[]): void {
  try {
    if (!storage) return;
    if (queue.length) storage.setItem(QUEUE_KEY, JSON.stringify(queue.slice(-MAX_SHARE_QUEUE)));
    else storage.removeItem(QUEUE_KEY);
  } catch {
    // Not kept; it is only lost if this send fails too.
  }
}
