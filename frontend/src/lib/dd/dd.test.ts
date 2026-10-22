// The WebAssembly solver against the Python one (bridge/solver), an
// independent engine: every legal card's value over the last five tricks of
// 16 boards, exactly. Fixtures from tests/fixtures/export_ts_fixtures.py.
import { describe, expect, it } from 'vitest';
import dd from '../engine/__fixtures__/dd.json';
import { parseCard, parseHand, type Seat, type Strain } from '../engine/card';
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
