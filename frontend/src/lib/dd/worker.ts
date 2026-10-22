// Runs the double dummy solver off the page's thread. One worker per board:
// the replayer terminates it on leaving the board, which also frees the
// solver's table. Messages in: {board, order} once, then {order} for more
// decisions on the same board. Out: {i, values} per decision, {done} after
// each order, {error} if the solver refuses the board.
import { DdSolver, type PlayedBoard } from './solver';
import wasmUrl from './solver.wasm?url';

let solver: Promise<DdSolver> | null = null;

self.onmessage = async (e: MessageEvent<{ board?: PlayedBoard; order: number[] }>) => {
  try {
    solver ??= fetch(wasmUrl).then((r) => r.arrayBuffer()).then((b) => DdSolver.fromBytes(b));
    const s = await solver;
    if (e.data.board) s.load(e.data.board);
    for (const i of e.data.order) self.postMessage({ i, values: [...s.analyse(i)] });
    self.postMessage({ done: true });
  } catch (err) {
    self.postMessage({ error: (err as Error).message });
  }
};
