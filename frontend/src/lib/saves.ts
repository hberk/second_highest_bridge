// Finished boards, remembered per browser, so a reload or a closed tab doesn't
// lose the session. Same rules as settings.svelte.ts: storage can be missing,
// full or blocked (private windows, cleared site data, Safari's 7-day limit),
// so every access is guarded and a failed save never stops play.
//
// The records are the same `HistoryRecord` shape ONLINE_PLAN stores in
// `boards.record`, so boards saved here can be uploaded unchanged once there
// are accounts.
import type { ChallengeLogEntry, HistoryRecord } from './game.svelte';

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

/** The saved games, or null when there are none or they can't be read. An
 *  unreadable save is copied to BACKUP_KEY first, so a bug or a future format
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
    if (isSaved(parsed)) return parsed;
  } catch {
    // Fall through to the backup.
  }
  try {
    storage.setItem(BACKUP_KEY, raw);
  } catch {
    // Nothing more to do.
  }
  return null;
}

/** Saves the newest MAX_SAVED_BOARDS boards. Returns false when the browser
 *  wouldn't store them. */
export function saveGames(storage: Storage | null, games: SavedGames): boolean {
  if (!storage) return false;
  const kept: SavedGames = { ...games, history: games.history.slice(-MAX_SAVED_BOARDS) };
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
