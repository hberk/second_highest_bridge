// Saved games: what survives a reload, and that a broken or full storage never
// gets in the way of play.
import { describe, expect, it } from 'vitest';
import { Game, type HistoryRecord } from './game.svelte';
import { prng } from './meanings';
import { legalPlays } from './engine/auction';
import { BACKUP_KEY, MAX_SAVED_BOARDS, SAVE_KEY, boardKey, loadGames, saveGames, trimHistory } from './saves';

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
    const game = new Game(storage, prng(1));
    finishBoards(game, 2);
    const reloaded = new Game(storage, prng(2));
    expect(reloaded.history).toEqual(game.history);
    expect(reloaded.passedOutCount).toBe(game.passedOutCount);
    // The new page deals the board after the last one saved.
    expect(reloaded.boardNum).toBeGreaterThan(game.history.at(-1)!.board_num);
  });

  it('a passed-out board is saved too', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage, prng(3));
    for (let i = 0; i < 200 && game.passedOutCount === 0; i++) {
      playOut(game);
      game.newBoard();
    }
    expect(game.passedOutCount).toBeGreaterThan(0);
    expect(new Game(storage, prng(4)).passedOutCount).toBe(game.passedOutCount);
  });

  it('restored challenge results keep dealChallenge off those deals', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage, prng(5));
    for (let i = 0; i < 20 && game.challengeLog.length === 0; i++) {
      expect(game.dealChallenge()).toBe(true);
      playOut(game);
    }
    expect(game.challengeLog.length).toBe(1);
    const played = game.challengeLog[0].deal_id;
    const reloaded = new Game(storage, prng(6));
    expect(reloaded.challengeLog).toEqual(game.challengeLog);
    for (let i = 0; i < 30; i++) {
      reloaded.dealChallenge();
      expect(reloaded.challengeId).not.toBe(played);
    }
  });

  it('imported LIN boards are saved', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage, prng(7));
    finishBoards(game, 1);
    const imported: HistoryRecord = { ...game.history[0], label: 'Imported #1', imported: true };
    game.importBoards([imported]);
    expect(new Game(storage, prng(8)).history.at(-1)).toEqual(imported);
  });

  it('an unreadable save starts empty and is kept as a backup', () => {
    for (const raw of ['{not json', JSON.stringify({ version: 2, history: [] }), '"text"']) {
      const storage = new MemoryStorage();
      storage.setItem(SAVE_KEY, raw);
      const game = new Game(storage, prng(9));
      expect(game.history).toEqual([]);
      expect(game.boardNum).toBe(1);
      expect(storage.getItem(BACKUP_KEY)).toBe(raw);
    }
  });

  it('a malformed board is left out, the rest load, and the save is backed up', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage, prng(10));
    finishBoards(game, 3);
    const good = game.history.map((r) => JSON.parse(JSON.stringify(r)));
    const t = good[1].tricks_log.length ? 'tricks_log' : 'initial_hands';
    const broken = [
      { ...good[1], [t]: t === 'tricks_log' ? [{ trick_num: 1, plays: 'AS' }] : { North: null } },
      { ...good[1], dealer: 'Nowhere' },
      { ...good[1], initial_hands: { ...good[1].initial_hands, East: [{ suit: 'X', rank: 'A' }] } },
      // A contract or result the History view can't read blanked the tab.
      { ...good[1], contract: {} },
      { ...good[1], contract: { ...good[1].contract, strain: 'Z' } },
      { ...good[1], result: {} },
      null,
      'board',
    ];
    for (const bad of broken) {
      const raw = JSON.stringify({
        version: 1, boardNum: 5, passedOut: 0,
        history: [good[0], bad, good[2]],
        challengeLog: [{ deal_id: 3 }],
      });
      storage.setItem(SAVE_KEY, raw);
      storage.removeItem(BACKUP_KEY);
      const loaded = loadGames(storage)!;
      expect(loaded.history).toEqual([good[0], good[2]]);
      expect(loaded.challengeLog).toEqual([]);
      expect(loaded.boardNum).toBe(5);
      expect(storage.getItem(BACKUP_KEY)).toBe(raw);
    }
    // A sound save loads untouched and writes no backup.
    storage.removeItem(BACKUP_KEY);
    saveGames(storage, { version: 1, boardNum: 5, passedOut: 0, history: good, challengeLog: [] });
    expect(loadGames(storage)!.history).toEqual(good);
    expect(storage.getItem(BACKUP_KEY)).toBeNull();
  });

  it('a pass-out counted while storage was full is saved once it frees up', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage, prng(12));
    finishBoards(game, 1);
    (storage as unknown as { failWrites: boolean }).failWrites = true;
    const before = game.passedOutCount;
    for (let i = 0; i < 200 && game.passedOutCount === before; i++) {
      playOut(game);
      game.newBoard();
    }
    expect(game.passedOutCount).toBe(before + 1);
    (storage as unknown as { failWrites: boolean }).failWrites = false;
    finishBoards(game, game.history.length + 1);      // the next save goes through
    expect(game.passedOutCount, 'the pass-out was dropped').toBeGreaterThanOrEqual(before + 1);
    expect(new Game(storage, prng(13)).passedOutCount).toBe(game.passedOutCount);
  });

  it('a storage that refuses writes never stops play', () => {
    const game = new Game(new MemoryStorage(true), prng(10));
    finishBoards(game, 2);
    expect(game.history.every((h) => h.tricks_log.length === 13)).toBe(true);
  });

  it('keeps only the newest boards', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage, prng(11));
    finishBoards(game, 1);
    const many = Array.from({ length: MAX_SAVED_BOARDS + 20 }, (_, i) => ({ ...game.history[0], board_num: i + 1 }));
    expect(saveGames(storage, { version: 1, boardNum: many.length, history: many, challengeLog: [], passedOut: 0 })).toBe(true);
    const back = loadGames(storage)!;
    expect(back.history.length).toBe(MAX_SAVED_BOARDS);
    expect(back.history[0].board_num).toBe(21);
  });

  it('Clear saved games forgets everything, on the page and in storage', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage, prng(12));
    finishBoards(game, 1);
    game.clearSaved();
    expect(game.history).toEqual([]);
    expect(game.challengeLog).toEqual([]);
    expect(storage.getItem(SAVE_KEY)).toBeNull();
    expect(new Game(storage, prng(13)).history).toEqual([]);
  });

  it('a big LIN import never pushes out boards you played', () => {
    const storage = new MemoryStorage();
    const game = new Game(storage, prng(14));
    finishBoards(game, 2);
    const mine = game.history.length;
    const imports = Array.from({ length: MAX_SAVED_BOARDS }, (_, i) => (
      { ...game.history[0], board_num: 1000 + i, label: `Imported #${i}`, imported: true }));
    game.importBoards(imports);
    const back = new Game(storage, prng(15)).history;
    expect(back.length).toBe(MAX_SAVED_BOARDS);
    expect(back.filter((r) => !r.imported).length, 'a played board was dropped for an import').toBe(mine);
  });

  it('trims imported boards first, oldest first, then played ones', () => {
    const rec = (n: number, imported: boolean) => ({ board_num: n, imported }) as unknown as HistoryRecord;
    const h = [rec(1, false), rec(2, true), rec(3, false), rec(4, true), rec(5, false)];
    expect(trimHistory(h, 4).map((r) => r.board_num)).toEqual([1, 3, 4, 5]);
    expect(trimHistory(h, 3).map((r) => r.board_num)).toEqual([1, 3, 5]);
    expect(trimHistory(h, 2).map((r) => r.board_num)).toEqual([3, 5]);
    expect(trimHistory(h, 9)).toBe(h);
  });

  it("two tabs never overwrite each other's boards", () => {
    const storage = new MemoryStorage();
    const a = new Game(storage, prng(16));
    const b = new Game(storage, prng(17));          // both loaded the same, empty save
    /** Play until this tab finishes a board of its own; returns that board's
     *  key and how many boards it passed out on the way. */
    const finishOne = (g: Game): [string, number] => {
      let passedOut = 0;
      for (let i = 0; i < 200; i++) {
        playOut(g);
        if (g.result) {
          const mine = g.history.find((r) => r.board_num === g.boardNum
            && JSON.stringify(r.initial_hands) === JSON.stringify(g.initialHands))!;
          g.newBoard();
          return [boardKey(mine), passedOut];
        }
        if (g.auction.passedOut) passedOut++;
        g.newBoard();
      }
      throw new Error('no board finished');
    };
    const [fromA, outA] = finishOne(a);
    const [fromB, outB] = finishOne(b);   // b never saw a's board; its saves must keep it
    const reloaded = new Game(storage, prng(18));
    const saved = reloaded.history.map(boardKey);
    expect(saved, "b's save dropped a's board").toContain(fromA);
    expect(saved).toContain(fromB);
    expect(reloaded.passedOutCount).toBe(outA + outB);
  });

  it('a tab takes on what another tab saves, or clears, as it happens', () => {
    // Node has no window: stand one in, and fire the browser's storage event
    // the way it reaches every OTHER tab after a write.
    const g = globalThis as { window?: unknown };
    const target = new EventTarget();
    g.window = target;
    try {
      const storage = new MemoryStorage();
      const a = new Game(storage, prng(19));
      const b = new Game(storage, prng(20));
      const fire = () => target.dispatchEvent(Object.assign(new Event('storage'), { key: SAVE_KEY, storageArea: storage }));
      finishBoards(a, 1);
      fire();
      expect(b.history.map(boardKey), 'b did not pick up a’s board').toEqual(a.history.map(boardKey));
      a.clearSaved();
      fire();
      expect(b.history, 'a cleared, b kept its copy').toEqual([]);
    } finally {
      delete g.window;
    }
  });
});
