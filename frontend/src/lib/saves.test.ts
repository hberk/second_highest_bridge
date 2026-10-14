// Saved games: what survives a reload, and that a broken or full storage never
// gets in the way of play.
import { describe, expect, it } from 'vitest';
import { Game, type HistoryRecord } from './game.svelte';
import { legalPlays } from './engine/auction';
import { BACKUP_KEY, MAX_SAVED_BOARDS, SAVE_KEY, loadGames, saveGames } from './saves';

/** localStorage's interface over a Map; `failWrites` makes every write throw,
 *  as a full or blocked storage does. */
class MemoryStorage implements Storage {
  private data = new Map<string, string>();
  constructor(private failWrites = false) {}
  get length() { return this.data.size; }
  clear() { this.data.clear(); }
  getItem(k: string) { return this.data.get(k) ?? null; }
  key(i: number) { return [...this.data.keys()][i] ?? null; }
  removeItem(k: string) { this.data.delete(k); }
  setItem(k: string, v: string) {
    if (this.failWrites) throw new DOMException('quota', 'QuotaExceededError');
    this.data.set(k, String(v));
  }
}

/** South passes and plays its first legal card until the board is over
 *  (finished or passed out). */
function playOut(game: Game): void {
  for (let guard = 0; guard < 500; guard++) {
    if (game.phase === 'bidding') {
      if (game.auction.passedOut) return;
      game.humanBids('Pass');
    } else if (game.phase === 'auction_done') {
      game.startPlay();
    } else if (game.phase === 'playing') {
      const who = game.whoseTurn()!;
      const led = game.trick.length ? game.trick[0][1].suit : null;
      game.humanPlays(who, legalPlays(game.hands[who], led)[0]);
    } else if (game.phase === 'trick_done') {
      game.nextTrick();
    } else {
      return;
    }
  }
  throw new Error('board did not finish');
}

/** Play boards until at least `n` have been finished. */
function finishBoards(game: Game, n: number): void {
  for (let i = 0; i < 200 && game.history.length < n; i++) {
    playOut(game);
    game.newBoard();
  }
  expect(game.history.length).toBeGreaterThanOrEqual(n);
}

describe('saved games', () => {
  it('a finished board survives a reload, and numbering carries on', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage);
    finishBoards(game, 2);
    const reloaded = new Game(storage);
    expect(reloaded.history).toEqual(game.history);
    expect(reloaded.passedOutCount).toBe(game.passedOutCount);
    // The new page deals the board after the last one saved.
    expect(reloaded.boardNum).toBeGreaterThan(game.history.at(-1)!.board_num);
  });

  it('a passed-out board is saved too', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage);
    for (let i = 0; i < 200 && game.passedOutCount === 0; i++) {
      playOut(game);
      game.newBoard();
    }
    expect(game.passedOutCount).toBeGreaterThan(0);
    expect(new Game(storage).passedOutCount).toBe(game.passedOutCount);
  });

  it('restored challenge results keep dealChallenge off those deals', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage);
    for (let i = 0; i < 20 && game.challengeLog.length === 0; i++) {
      expect(game.dealChallenge()).toBe(true);
      playOut(game);
    }
    expect(game.challengeLog.length).toBe(1);
    const played = game.challengeLog[0].deal_id;
    const reloaded = new Game(storage);
    expect(reloaded.challengeLog).toEqual(game.challengeLog);
    for (let i = 0; i < 30; i++) {
      reloaded.dealChallenge();
      expect(reloaded.challengeId).not.toBe(played);
    }
  });

  it('imported LIN boards are saved', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage);
    finishBoards(game, 1);
    const imported: HistoryRecord = { ...game.history[0], label: 'Imported #1', imported: true };
    game.importBoards([imported]);
    expect(new Game(storage).history.at(-1)).toEqual(imported);
  });

  it('an unreadable save starts empty and is kept as a backup', () => {
    for (const raw of ['{not json', JSON.stringify({ version: 2, history: [] }), '"text"']) {
      const storage = new MemoryStorage();
      storage.setItem(SAVE_KEY, raw);
      const game = new Game(storage);
      expect(game.history).toEqual([]);
      expect(game.boardNum).toBe(1);
      expect(storage.getItem(BACKUP_KEY)).toBe(raw);
    }
  });

  it('a storage that refuses writes never stops play', () => {
    const game = new Game(new MemoryStorage(true));
    finishBoards(game, 2);
    expect(game.history.every((h) => h.tricks_log.length === 13)).toBe(true);
  });

  it('keeps only the newest boards', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage);
    finishBoards(game, 1);
    const many = Array.from({ length: MAX_SAVED_BOARDS + 20 }, (_, i) => ({ ...game.history[0], board_num: i + 1 }));
    expect(saveGames(storage, { version: 1, boardNum: many.length, history: many, challengeLog: [], passedOut: 0 })).toBe(true);
    const back = loadGames(storage)!;
    expect(back.history.length).toBe(MAX_SAVED_BOARDS);
    expect(back.history[0].board_num).toBe(21);
  });

  it('Clear saved games forgets everything, on the page and in storage', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage);
    finishBoards(game, 1);
    game.clearSaved();
    expect(game.history).toEqual([]);
    expect(game.challengeLog).toEqual([]);
    expect(storage.getItem(SAVE_KEY)).toBeNull();
    expect(new Game(storage).history).toEqual([]);
  });
});
