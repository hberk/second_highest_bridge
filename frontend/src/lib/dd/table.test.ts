// The deal's double dummy table for History: the solver's whole-deal value
// against a stored training table, and stored challenge tables giving the
// challenge's own par.
import { describe, expect, it } from 'vitest';
import training from '$root/data/training_deals.json';
import { PLAYERS } from '../engine/auction';
import { STRAINS, parseHand, type Card, type Seat } from '../engine/card';
import { dealIds, handsFor, par } from '../engine/challenge';
import { DdSolver } from './solver';
import { DdTable, parOf } from './table.svelte';
import wasmData from './solver.wasm?inline';

const LHO: Record<Seat, Seat> = { North: 'East', East: 'South', South: 'West', West: 'North' };

describe("History's tricks and par", () => {
  it("solves a whole deal's table as stored", async () => {
    const solver = await DdSolver.fromBytes(await (await fetch(wasmData)).arrayBuffer());
    const d = training.deals[0];
    const hands = Object.fromEntries(PLAYERS.map((p) => [p, parseHand(d.hands[p])])) as Record<Seat, Card[]>;
    for (const strain of STRAINS) {
      solver.load({ hands, leader: 'North', strain, plays: [] });
      for (const decl of PLAYERS) {
        const ns = solver.value(LHO[decl]);
        expect(decl === 'North' || decl === 'South' ? ns : 13 - ns)
          .toBe((d.tricks as Record<string, number>)[`${strain}:${decl}`]);
      }
    }
  }, 300_000);

  it('knows every challenge deal, with the challenge par', () => {
    for (const id of dealIds().slice(0, 40)) {
      const t = new DdTable(handsFor(id));
      expect(t.done).toBe(true);
      expect(parOf(t.tricks, 'E/W')).toEqual(par(id, 'N/S', 'E/W'));
    }
  });

  it('leaves any other deal to solve', () => {
    const d = training.deals[1];
    const hands = Object.fromEntries(PLAYERS.map((p) => [p, parseHand(d.hands[p])])) as Record<Seat, Card[]>;
    expect(new DdTable(hands).done).toBe(false);
  });
});
