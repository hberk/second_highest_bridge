// The deal's double dummy table off the page's thread: each strain with each
// of the four declarers, from the opening lead. One load per strain, so its
// four declarers share a table. In: {hands}. Out: {ready} as soon as this
// script runs, {strain, tricks} per strain (each declarer's own tricks),
// {done}, or {error}.
import { STRAINS, type Card, type Seat } from '../engine/card';
import { DdSolver } from './solver';
import wasmUrl from './solver.wasm?url';

const LHO: Record<Seat, Seat> = { North: 'East', East: 'South', South: 'West', West: 'North' };
const DECLARERS: readonly Seat[] = ['North', 'South', 'East', 'West'];

self.onmessage = async (e: MessageEvent<{ hands: Record<Seat, Card[]> }>) => {
  try {
    const r = await fetch(wasmUrl);
    if (!r.ok) throw new Error(`couldn't load the solver (HTTP ${r.status})`);
    const s = await DdSolver.fromBytes(await r.arrayBuffer());
    for (const strain of STRAINS) {
      s.load({ hands: e.data.hands, leader: 'North', strain, plays: [] });
      const tricks = {} as Record<Seat, number>;
      let guess = 7;
      for (const d of DECLARERS) {
        guess = s.value(LHO[d], guess);
        tricks[d] = d === 'North' || d === 'South' ? guess : 13 - guess;
      }
      s.unload();
      self.postMessage({ strain, tricks });
    }
    self.postMessage({ done: true });
  } catch (err) {
    self.postMessage({ error: (err as Error).message });
  }
};

self.postMessage({ ready: true });
