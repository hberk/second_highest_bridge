// Finished boards, remembered per browser, so a reload or a closed tab doesn't
// lose the session. Same rules as settings.svelte.ts: storage can be missing,
// full or blocked (private windows, cleared site data, Safari's 7-day limit),
// so every access is guarded and a failed save never stops play.
//
// The records are the same `HistoryRecord` shape ONLINE_PLAN stores in
// `boards.record`, so boards saved here can be uploaded unchanged once there
// are accounts.
import { RANKS, SUITS, VULNERABILITIES, type Card, type Seat, type Side, type Vulnerability } from './engine/card';
import { PLAYERS, type CallRecord, type Contract } from './engine/auction';
import type { ScoreResult } from './engine/scoring';
import type { TrickLog } from './engine/challenge';

/** One challenge board's result, for the challenge log. */
export interface ChallengeLogEntry {
  deal_id: number;
  board_num: number;
  you: number;
  robot: number;
  margin: number;
  your_bidding_loss: number;
  your_play_loss: number;
  robot_bidding_loss: number;
  robot_play_loss: number;
}

/** One finished board, as History replays it and LIN writes it. Plain data
 *  with no Svelte in it, so the table server builds the same records. */
export interface HistoryRecord {
  board_num: number;
  label?: string;
  /** Loaded from LIN rather than played here: not part of the session score. */
  imported?: boolean;
  /** Played at a multiplayer table: its id, and the seat you sat in. */
  table_id?: string;
  my_seat?: Seat;
  dealer: Seat;
  vulnerability: Vulnerability;
  initial_hands: Record<Seat, Card[]>;
  auction_calls: CallRecord[];
  bid_alerts: Record<number, string>;
  contract: Contract | null;
  passed_out: boolean;
  tricks_log: TrickLog[];
  tricks_taken: Record<Side, number>;
  result: ScoreResult | null;
}

export const SAVE_KEY = 'shb-games-v1';
/** Where an unreadable save is kept rather than overwritten. */
export const BACKUP_KEY = 'shb-games-backup';
/** The newest boards kept; older ones drop off. The .lin export is the archive. */
export const MAX_SAVED_BOARDS = 500;

export interface SavedGames {
  version: 1;
  /** The last board number dealt, so numbering (and with it dealer and
   *  vulnerability rotation) carries on where it left off. */
  boardNum: number;
  history: HistoryRecord[];
  challengeLog: ChallengeLogEntry[];
  passedOut: number;
}

/** `localStorage` in a browser; null in Node (the tests) or when the browser
 *  refuses access to it. */
export function browserStorage(): Storage | null {
  try {
    return (globalThis as { window?: Window }).window?.localStorage ?? null;
  } catch {
    return null;
  }
}

function isSaved(v: unknown): v is SavedGames {
  const s = v as SavedGames;
  return !!s && s.version === 1
    && Number.isInteger(s.boardNum) && s.boardNum >= 0
    && Array.isArray(s.history) && Array.isArray(s.challengeLog)
    && Number.isInteger(s.passedOut) && s.passedOut >= 0;
}

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);
const isCount = (v: unknown): boolean => Number.isInteger(v) && (v as number) >= 0;
const isSeat = (v: unknown): boolean => PLAYERS.includes(v as never);
const isCard = (v: unknown): boolean =>
  isObject(v) && SUITS.includes(v.suit as never) && RANKS.includes(v.rank as string);
const isPlay = (v: unknown): boolean =>
  Array.isArray(v) && v.length === 2 && isSeat(v[0]) && isCard(v[1]);

/** One board, checked as deep as the History view reads it: a board that
 *  fails is left out on load rather than breaking the view. */
export function isRecord(v: unknown): v is HistoryRecord {
  if (!isObject(v)) return false;
  const hands = v.initial_hands;
  const taken = v.tricks_taken;
  return isCount(v.board_num) && isSeat(v.dealer)
    && VULNERABILITIES.includes(v.vulnerability as never)
    && isObject(hands) && PLAYERS.every((p) => Array.isArray(hands[p]) && (hands[p] as unknown[]).every(isCard))
    && Array.isArray(v.auction_calls)
    && v.auction_calls.every((c) => Array.isArray(c) && c.length === 2 && isSeat(c[0]) && typeof c[1] === 'string')
    && isObject(v.bid_alerts) && Object.values(v.bid_alerts).every((a) => typeof a === 'string')
    && (v.contract === null || isObject(v.contract))
    && typeof v.passed_out === 'boolean'
    && Array.isArray(v.tricks_log)
    && v.tricks_log.every((t) => isObject(t) && isCount(t.trick_num) && isSeat(t.leader)
      && Array.isArray(t.plays) && t.plays.every(isPlay) && isSeat(t.winner) && isCard(t.winning_card))
    && isObject(taken) && isCount(taken['N/S']) && isCount(taken['E/W'])
    && (v.result === null || isObject(v.result));
}

const LOG_FIELDS = ['deal_id', 'board_num', 'you', 'robot', 'margin', 'your_bidding_loss',
  'your_play_loss', 'robot_bidding_loss', 'robot_play_loss'] as const;

export function isLogEntry(v: unknown): v is ChallengeLogEntry {
  return isObject(v) && LOG_FIELDS.every((k) => Number.isFinite(v[k]));
}

/** The saved games, or null when there are none or they can't be read. An
 *  unreadable save is copied to BACKUP_KEY first (and so is a save with a
 *  malformed board, which loads without it), so a bug or a future format
 *  never silently destroys someone's history. */
export function loadGames(storage: Storage | null): SavedGames | null {
  if (!storage) return null;
  let raw: string | null;
  try {
    raw = storage.getItem(SAVE_KEY);
  } catch {
    return null;
  }
  if (raw === null) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isSaved(parsed)) {
      // Boards and log entries are checked one by one: a bad one is dropped
      // (and the whole save backed up first), the rest load.
      const history = parsed.history.filter(isRecord);
      const challengeLog = parsed.challengeLog.filter(isLogEntry);
      if (history.length === parsed.history.length && challengeLog.length === parsed.challengeLog.length) {
        return parsed;
      }
      backUp(storage, raw);
      return { ...parsed, history, challengeLog };
    }
  } catch {
    // Fall through to the backup.
  }
  backUp(storage, raw);
  return null;
}

function backUp(storage: Storage, raw: string): void {
  try {
    storage.setItem(BACKUP_KEY, raw);
  } catch {
    // Nothing more to do.
  }
}

/** At most `max` boards, dropping the oldest IMPORTED ones first: a big LIN
 *  import must never push out boards the player actually played. */
export function trimHistory(history: HistoryRecord[], max = MAX_SAVED_BOARDS): HistoryRecord[] {
  let excess = history.length - max;
  if (excess <= 0) return history;
  const drop = new Set<number>();
  for (const pass of [true, false]) {          // imported first, then played
    for (let i = 0; i < history.length && excess > 0; i++) {
      if (!drop.has(i) && !!history[i].imported === pass) {
        drop.add(i);
        excess--;
      }
    }
  }
  return history.filter((_, i) => !drop.has(i));
}

/** Two copies of a board are the same board. Board numbers alone can't say:
 *  two tabs can each deal "board 11", with different cards. */
export function boardKey(r: HistoryRecord): string {
  return JSON.stringify([r.board_num, r.dealer, r.imported ?? false, r.initial_hands, r.auction_calls]);
}

/** This tab's games plus whatever another tab saved that this one hasn't
 *  seen. This tab's list leads: it's in order, and it still holds boards the
 *  500 cap trimmed out of storage, which must stay oldest, not reappear as
 *  new. `passedOutDelta` is how many boards this tab passed out since it last
 *  read or wrote the save. */
export function mergeGames(stored: SavedGames | null, mine: SavedGames, passedOutDelta: number): SavedGames {
  if (!stored) return mine;
  const have = new Set(mine.history.map(boardKey));
  const logged = new Set(mine.challengeLog.map((e) => JSON.stringify(e)));
  return {
    version: 1,
    boardNum: Math.max(stored.boardNum, mine.boardNum),
    history: [...mine.history, ...stored.history.filter((r) => !have.has(boardKey(r)))],
    challengeLog: [...mine.challengeLog, ...stored.challengeLog.filter((e) => !logged.has(JSON.stringify(e)))],
    passedOut: stored.passedOut + Math.max(0, passedOutDelta),
  };
}

/** Saves at most MAX_SAVED_BOARDS boards (see trimHistory). Returns false
 *  when the browser wouldn't store them. */
export function saveGames(storage: Storage | null, games: SavedGames): boolean {
  if (!storage) return false;
  const kept: SavedGames = { ...games, history: trimHistory(games.history) };
  try {
    storage.setItem(SAVE_KEY, JSON.stringify(kept));
    return true;
  } catch {
    return false;
  }
}

export function clearGames(storage: Storage | null): void {
  try {
    storage?.removeItem(SAVE_KEY);
  } catch {
    // Already unreadable; nothing to clear.
  }
}

let persistAsked = false;

/** Ask once per page load that the browser not evict this site's storage
 *  under disk pressure. Browsers that decline (or lack the API) lose nothing. */
export function askPersistence(): void {
  if (persistAsked) return;
  persistAsked = true;
  try {
    void (globalThis as { navigator?: Navigator }).navigator?.storage?.persist?.().catch(() => {});
  } catch {
    // Not supported.
  }
}
