// LIN round trips and self-alerts. Every finished board must survive
// toLin -> fromLin unchanged, because fromLin rebuilds the contract, trick
// winners and score by replaying the board: a mismatch means either the
// writer dropped something or the replay disagrees with the table.
import { describe, expect, it } from 'vitest';
import { Game, cleanAlert, type HistoryRecord } from './game.svelte';
import { prng } from './meanings';
import { legalPlays } from './engine/auction';
import { fromLin, fromLinFile, toLin, toLinFile, LinError, MAX_LIN_BOARDS } from './lin';
import pythonLin from './engine/__fixtures__/lin.json';
import pythonHostile from './engine/__fixtures__/lin_hostile.json';

const ALERTS = ['Forcing | one round', '5+ ♠, 10-12 HCP!', 'Natural'];

/** South bids now and then with an alert, and plays its first legal card. */
function play(game: Game, board: number): void {
  for (let guard = 0; guard < 500; guard++) {
    if (game.phase === 'bidding') {
      if (game.auction.passedOut) return;
      const legal = game.auction.legalCalls();
      const bid = legal.find((c) => c === '2C' || c === '2S' || c === '3H' || c === '1NT');
      const alert = (board + guard) % 2 === 0 ? ALERTS[(board + guard) % 3] : '';
      game.humanBids(guard % 3 === 0 && bid ? bid : 'Pass', alert);
    } else if (game.phase === 'auction_done') game.startPlay();
    else if (game.phase === 'playing') {
      const who = game.whoseTurn()!;
      const led = game.trick.length ? game.trick[0][1].suit : null;
      game.humanPlays(who, legalPlays(game.hands[who], led)[0]);
    } else if (game.phase === 'trick_done') game.nextTrick();
    else return;
  }
  throw new Error('board did not finish');
}

/** What a record looks like after LIN: alerts pass through cleanAlert's rules
 *  and lose the `|` LIN can't carry. The label is not part of LIN. */
function expected(r: HistoryRecord): HistoryRecord {
  const alerts = Object.fromEntries(Object.entries(r.bid_alerts)
    .map(([i, t]) => [i, t.replace(/[|\r\n]+/g, '/').trim()]));
  const { label: _, ...rest } = r;
  return { ...rest, bid_alerts: alerts } as HistoryRecord;
}

const boards = (() => {
  const game = new Game(null, prng(1));
  for (let i = 0; i < 30; i++) {
    play(game, i);
    game.newBoard();
  }
  return game.history;
})();

describe('LIN', () => {
  it('round-trips every finished board exactly', () => {
    expect(boards.length).toBeGreaterThan(5);
    const human = boards.flatMap((b) => Object.entries(b.bid_alerts)
      .filter(([i]) => b.auction_calls[Number(i)][0] === 'South').map(([, t]) => t));
    expect(human.some((t) => t.includes('|')), 'no alert with a | was exercised').toBe(true);
    expect(human.some((t) => t.includes('♠')), 'no alert with a suit symbol was exercised').toBe(true);
    for (const r of boards) expect(fromLin(toLin(r))).toEqual(expected(r));
  });

  it('round-trips a whole session file', () => {
    expect(fromLinFile(toLinFile(boards))).toEqual(boards.map(expected));
  });

  it('writes BBO conventions', () => {
    const lin = toLin(boards[0]);
    expect(lin).toMatch(/^pn\|South,West,North,East\|st\|\|md\|[1-4]S/);
    expect(lin).toMatch(/sv\|[oneb]\|/);
    expect(lin).not.toMatch(/mb\|(Pass|X|XX|\dNT)!?\|/); // p, d, r and 1N, as BBO writes them
    // T for ten, in the deal and in every card played (alerts may say "10+").
    expect(/md\|([^|]*)\|/.exec(lin)![1]).not.toContain('10');
    expect([...lin.matchAll(/pc\|([^|]*)\|/g)].map((m) => m[1]).join(' ')).not.toContain('10');
    for (const r of boards) {
      for (const t of Object.values(r.bid_alerts)) {
        if (t.includes('♠')) expect(toLin(r)).toContain('!S');
      }
    }
  });

  it('reads a BBO-style record: three hands given, a claim, lower case', () => {
    const r = boards.find((b) => b.tricks_log.length === 13)!;
    let lin = toLin(r);
    // Drop East (the fourth hand), as BBO often does.
    lin = lin.replace(/(md\|[^|,]*,[^|,]*,[^|,]*),[^|]*\|/, '$1,|');
    // Stop after eight tricks and claim the rest.
    const pcs = [...lin.matchAll(/pc\|[^|]+\|/g)];
    const cut = pcs[8 * 4].index!;
    const declarerTotal = r.tricks_taken[r.contract!.side];
    lin = `${lin.slice(0, cut)}mc|${declarerTotal}|`.replace(/mb\|p\|/g, 'mb|P|');
    const back = fromLin(lin);
    expect(back.tricks_taken).toEqual(r.tricks_taken);
    expect(back.result).toEqual(r.result);
    expect(back.tricks_log.length).toBe(8);
    expect(back.initial_hands).toEqual(r.initial_hands);
    // ...and writes the claim back out, so the board round-trips. It used to
    // export as play that just stops, which import refuses.
    const again = toLin(back);
    expect(again).toMatch(/mc\|\d+\|$/);
    expect(fromLin(again).tricks_taken).toEqual(r.tricks_taken);
    expect(toLin(r)).not.toContain('mc|');
  });

  it('refuses a card played out of turn', () => {
    const r = boards.find((b) => b.tricks_log.length === 13)!;
    const lin = toLin(r);
    const [a, b] = [...lin.matchAll(/pc\|([^|]+)\|/g)].slice(0, 2).map((m) => m[1]);
    const swapped = lin.replace(`pc|${a}|pc|${b}|`, `pc|${b}|pc|${a}|`);
    expect(() => fromLin(swapped)).toThrow(LinError);
  });

  it('matches bridge/lin.py byte for byte, reading and writing', () => {
    // The Streamlit app writes LIN with bridge/lin.py. One format, two
    // implementations: each fixture is Python's LIN for a robot (or random
    // human) board, which must parse to Python's result and write back
    // unchanged.
    expect(pythonLin.length).toBeGreaterThan(250);
    for (const fx of pythonLin) {
      const r = fromLin(fx.lin);
      expect(r.contract).toEqual(fx.contract);
      expect(r.tricks_taken).toEqual(fx.tricks_taken);
      expect(r.result).toEqual(fx.result);
      expect(toLin(r)).toBe(fx.lin);
    }
  });

  it('refuses a board that stops before it is finished', () => {
    const lin = toLin(boards.find((b) => b.tricks_log.length === 13)!);
    // Play cut off after five tricks, with no claim.
    const cut = [...lin.matchAll(/pc\|/g)][5 * 4].index!;
    expect(() => fromLin(lin.slice(0, cut))).toThrow(/nothing was claimed/);
    // Auction cut off after its first call.
    const firstCall = lin.indexOf('mb|');
    const second = lin.indexOf('mb|', firstCall + 3);
    expect(() => fromLin(lin.slice(0, second))).toThrow(/auction never finished/);
  });

  it('refuses a deal with a card twice', () => {
    expect(() => fromLin('md|1SAKQJT98765432H,SA,,|')).toThrow(/twice/);
  });

  it('accepts and refuses exactly what bridge/lin.py does', () => {
    // Odd and hostile texts with Python's verdict: prototype keys as a
    // vulnerability, claims Number() would read, other scripts' digits, a
    // byte-order mark, a long alert with control characters.
    const cases = pythonHostile as { lin: string; ok: boolean; board_num?: number; bid_alerts?: Record<string, string> }[];
    expect(cases.length).toBeGreaterThan(15);
    for (const fx of cases) {
      if (!fx.ok) {
        expect(() => fromLin(fx.lin), JSON.stringify(fx.lin.slice(-40))).toThrow(LinError);
        continue;
      }
      const r = fromLin(fx.lin);
      expect(r.board_num).toBe(fx.board_num);
      expect(r.bid_alerts).toEqual(fx.bid_alerts);
    }
  });

  it(`reads at most ${MAX_LIN_BOARDS} boards at once`, () => {
    const lin = toLin(boards[0]);
    expect(fromLinFile(Array(MAX_LIN_BOARDS).fill(lin).join('\n'))).toHaveLength(MAX_LIN_BOARDS);
    expect(() => fromLinFile(Array(MAX_LIN_BOARDS + 1).fill(lin).join('\n'))).toThrow(LinError);
  });

  it('importing the same boards twice adds them once', () => {
    const game = new Game(null, prng(3));
    const imported = boards.slice(0, 4).map((b) => ({ ...b, label: `Imported #${b.board_num}`, imported: true }));
    expect(game.importBoards(imported)).toBe(4);
    expect(game.importBoards(imported)).toBe(0);
    expect(game.history.filter((h) => h.imported)).toHaveLength(4);
  });
});

describe('self-alerts', () => {
  it('stores the alert against the call and shows it live, even on a pass', () => {
    const game = new Game(null, prng(2));
    for (let i = 0; i < 20 && game.auction.currentPlayer() !== 'South'; i++) game.newBoard();
    expect(game.auction.currentPlayer()).toBe('South');
    const index = game.calls.length;
    game.humanBids('Pass', '  Forcing\n pass  ');
    expect(game.alerts[index]).toBe('Forcing pass');
    expect(game.liveAlerts[index]).toBe('Forcing pass');
    // Robot pass reasons stay hidden while the board is live.
    for (const [i, [who, call]] of game.calls.entries()) {
      if (who !== 'South' && call === 'Pass') expect(game.liveAlerts[i]).toBeUndefined();
    }
  });

  it('ignores a blank alert and caps a long one', () => {
    expect(cleanAlert('   ')).toBe('');
    expect(cleanAlert('x'.repeat(200)).length).toBe(70);
  });

  it('never renders raw HTML, now that players type text', () => {
    const sources = import.meta.glob('../**/*.svelte', { query: '?raw', import: 'default', eager: true });
    expect(Object.keys(sources).length).toBeGreaterThan(5);
    for (const [path, text] of Object.entries(sources)) {
      expect(text as string, path).not.toContain('{@html');
    }
  });
});
