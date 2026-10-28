// The robots' cost at a table, measured where the server runs: seeded boards
// with four robots, each decision timed alone, the search memory cleared as
// each board ends (as the server does), and the heap after a forced GC.
//   npm run bench                  # 200 boards
//   node --expose-gc dist/bench.js 50
import {
  addPlayer, applyIntent, applyRobot, newTable, robotAction, robotTurn, type Context,
} from '../../frontend/src/lib/table/core';
import { clearPositionMemo } from '../../frontend/src/lib/engine/ai';
import { prng } from '../../frontend/src/lib/meanings';
import type { Readings } from '../../frontend/src/lib/alerts';

const boards = Number(process.argv[2] ?? 200);
const gc = (globalThis as { gc?: () => void }).gc;
const readings: Readings = new Map();
const calls: number[] = [];
const cards: number[] = [];
const perBoard: number[] = [];
const heap: [number, number][] = [];

const ctx: Context = { now: 0, connected: () => true, awaySince: () => null, random: prng(1000) };
const s = newTable('bench', 0);
addPlayer(s, 'host', '', 'host', 0);
applyIntent(s, 'host', { type: 'sit', seat: 'South' }, ctx);
applyIntent(s, 'host', { type: 'stand' }, ctx);
// A seat-less host can't deal, so deal through a seated one, then stand up:
// every seat is a robot's.
for (let b = 0; b < boards; b++) {
  applyIntent(s, 'host', { type: 'sit', seat: 'South' }, ctx);
  applyIntent(s, 'host', { type: 'deal' }, ctx);
  applyIntent(s, 'host', { type: 'stand' }, ctx);
  let total = 0;
  while (robotTurn(s)) {
    const t = performance.now();
    const a = robotAction(s, readings)!;
    const ms = performance.now() - t;
    total += ms;
    (a.call !== undefined ? calls : cards).push(ms);
    applyRobot(s, a);
  }
  perBoard.push(total);
  clearPositionMemo();
  if (gc && [1, 10, 25, 50, 100, 150, 200].includes(b + 1)) {
    gc();
    heap.push([b + 1, Math.round(process.memoryUsage().heapUsed / 1e5) / 10]);
  }
}

const q = (xs: number[], p: number) => [...xs].sort((a, b) => a - b)[Math.min(xs.length - 1, Math.floor(p * xs.length))];
const row = (name: string, xs: number[]) => console.log(
  `${name.padEnd(8)} n=${String(xs.length).padStart(6)}  median ${q(xs, 0.5).toFixed(2)}  p95 ${q(xs, 0.95).toFixed(1)}`
  + `  p99 ${q(xs, 0.99).toFixed(1)}  worst ${Math.max(...xs).toFixed(1)} ms  over 100 ms: ${xs.filter((x) => x > 100).length}`);
console.log(`${boards} robot boards, node ${process.version}`);
row('call', calls);
row('card', cards);
row('board', perBoard);
if (heap.length) console.log('retained heap MB by boards:', heap.map(([n, mb]) => `${n}: ${mb}`).join(', '));
else console.log('(run with node --expose-gc for the heap)');
