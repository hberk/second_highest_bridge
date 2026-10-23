// The WebAssembly solver against the Python one (bridge/solver), an
// independent engine: every legal card's value over the last five tricks of
// 16 boards, exactly. Fixtures from tests/fixtures/export_ts_fixtures.py.
import { describe, expect, it } from 'vitest';
import dd from '../engine/__fixtures__/dd.json';
import { PARTNERSHIP, resolveTrick, type Play } from '../engine/auction';
import { cardKey, parseCard, parseHand, type Seat, type Strain } from '../engine/card';
import { tricksLost } from './analysis.svelte';
import { DdSolver, type PlayedBoard } from './solver';
import wasmData from './solver.wasm?inline';

const bytes = await (await fetch(wasmData)).arrayBuffer();

function boardOf(fx: (typeof dd)[number]): PlayedBoard {
  return {
    hands: Object.fromEntries(Object.entries(fx.hands).map(([s, t]) => [s, parseHand(t)])) as Record<Seat, ReturnType<typeof parseHand>>,
    leader: fx.leader as Seat,
    strain: fx.strain as Strain,
    plays: fx.plays.map(([, t]) => parseCard(t)),
  };
}

describe('double dummy (WebAssembly)', () => {
  it('matches the Python solver on every decision of the last five tricks', async () => {
    const solver = await DdSolver.fromBytes(bytes);
    let checked = 0;
    for (const fx of dd) {
      solver.load(boardOf(fx));
      for (const d of fx.decisions) {
        expect(Object.fromEntries(solver.analyse(d.index))).toEqual(d.values);
        checked++;
      }
      solver.unload();
    }
    expect(dd.length).toBe(16);
    expect(checked).toBe(16 * 20);
  });

  it('gives the same values with a tiny table', async () => {
    const solver = await DdSolver.fromBytes(bytes);
    const fx = dd[0];
    solver.load(boardOf(fx), 7);
    for (const d of fx.decisions) expect(Object.fromEntries(solver.analyse(d.index))).toEqual(d.values);
  });

  it('refuses a board it cannot read, saying why', async () => {
    const solver = await DdSolver.fromBytes(bytes);
    const board = boardOf(dd[0]);
    const next: Seat = { North: 'East', East: 'South', South: 'West', West: 'North' }[board.leader] as Seat;
    const outOfTurn = [board.hands[next][0], ...board.plays.slice(1)];
    expect(() => solver.load({ ...board, plays: outOfTurn })).toThrow(/play 1 is not legal/);
    expect(() => solver.load({ ...board, hands: { ...board.hands, East: board.hands.North } })).toThrow(/overlap/);
    expect(() => solver.analyse(0)).toThrow(/no play 0/);
  });
});

const NEXT: Record<Seat, Seat> = { North: 'East', East: 'South', South: 'West', West: 'North' };

/** The seat of every card played, by replaying the tricks. */
function seatsOf(board: PlayedBoard): { seats: Seat[]; winners: Seat[] } {
  const seats: Seat[] = [], winners: Seat[] = [];
  let leader = board.leader;
  for (let t = 0; t * 4 < board.plays.length; t++) {
    const trick: Play[] = [];
    let p = leader;
    for (const c of board.plays.slice(t * 4, t * 4 + 4)) {
      seats.push(p);
      trick.push([p, c]);
      p = NEXT[p];
    }
    if (trick.length === 4) leader = resolveTrick(trick, board.strain === 'NT' ? null : board.strain);
    winners.push(leader);
  }
  return { seats, winners };
}

describe('tricks lost', () => {
  it('names the cards worse than the best for the side that played them', () => {
    const seats: Seat[] = ['West', 'North'];
    const plays = [parseCard('5H'), parseCard('2S')];
    // West wants N/S to take few tricks: the 5H gives one away against the KH or AH.
    // North's 2S is as good as anything North held.
    const values = { 0: { '5H': 3, KH: 2, AH: 2 }, 1: { '2S': 2, AS: 2 } };
    expect(tricksLost(seats, plays, values)).toEqual([{ i: 0, seat: 'West', card: plays[0], cost: 1, best: ['KH', 'AH'] }]);
    expect(tricksLost(seats, plays, { 1: { '2S': 1, AS: 3 } })).toEqual([{ i: 1, seat: 'North', card: plays[1], cost: 2, best: ['AS'] }]);
  });

  it('accounts for every trick between perfect play and the result', async () => {
    // From the first decision analysed, N/S end with the best they could
    // force, less what N/S gave away, plus what E/W gave away.
    const solver = await DdSolver.fromBytes(bytes);
    let mistakes = 0;
    for (const fx of dd) {
      const board = boardOf(fx);
      solver.load(board);
      const values: Record<number, Record<string, number>> = {};
      for (const d of fx.decisions) values[d.index] = Object.fromEntries(solver.analyse(d.index));
      solver.unload();
      const { seats, winners } = seatsOf(board);
      const first = Math.min(...fx.decisions.map((d) => d.index));
      const sign = PARTNERSHIP[seats[first]] === 'N/S' ? 1 : -1;
      const perfect = sign * Math.max(...Object.values(values[first]).map((v) => sign * v));
      const won = winners.slice(first / 4).filter((w) => PARTNERSHIP[w] === 'N/S').length;
      const losses = tricksLost(seats, board.plays, values);
      const swing = losses.reduce((n, l) => n + (PARTNERSHIP[l.seat] === 'N/S' ? -l.cost : l.cost), 0);
      expect(won).toBe(perfect + swing);
      for (const l of losses) expect(l.best).not.toContain(cardKey(l.card));
      mistakes += losses.length;
    }
    expect(mistakes).toBeGreaterThan(0);
  });
});
