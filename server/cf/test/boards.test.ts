// Shared finished boards (src/boards.ts): what a row holds, what is refused,
// and a batch through the Worker into D1 (in workerd) and back out.
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync, copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { unstable_dev, type Unstable_DevWorker } from 'wrangler';
import { rowFor, storeBoards, type BoardRow } from '../src/boards';
import { playedShare, trainingShare, type SharedBoard } from '../../../frontend/src/lib/shareRecord';
import { fromLin } from '../../../frontend/src/lib/lin';

const DAY = '2026-11-28';
const RANKS = 'AKQJT98765432';
/** Board 1 (North deals, nobody vulnerable): each hand holds one suit, South
 *  the spades. South opens 1♠ and takes all 13: a ruff of every heart lead,
 *  then a lone spade, since a single card of the winning suit wins. */
function soloLin(): string {
  const parts = [`pn|South,West,North,East|st||md|3S${RANKS},H${RANKS},D${RANKS},C${RANKS}|rh||ah|Board 1|sv|o|`];
  for (const c of ['p', 'p', '1S', 'p', 'p', 'p']) parts.push(`mb|${c}|`);
  // A self-alert on South's opening, with typed text: it must not survive.
  parts.push('an|my secret note|pg||');
  for (let t = 0; t < 13; t++) {
    const r = RANKS[t];
    const trick = t === 0 ? [`H${r}`, `D${r}`, `C${r}`, `S${r}`] : [`S${r}`, `H${r}`, `D${r}`, `C${r}`];
    parts.push(...trick.map((c) => `pc|${c}|`), 'pg||');
  }
  return parts.join('');
}

const solo = (): SharedBoard => ({ v: 1, mode: 'solo', app: '0.1.9-alpha', lin: soloLin() });

describe('a shared board becomes one anonymous row', () => {
  it('stores a solo board from its LIN, written again without names or alerts', () => {
    const row = rowFor(solo(), DAY) as BoardRow;
    expect(typeof row).toBe('object');
    expect(row).toMatchObject({
      day: DAY, mode: 'solo', app: '0.1.9-alpha', board_num: 1, dealer: 'North', vul: 'None',
      auction: 'P P 1S P P P', contract: '1S', declarer: 'South', tricks: 13, deal_id: null, you: null,
    });
    expect(row.ns_score).toBe(fromLin(soloLin()).result!.points);
    expect(row.lin).not.toContain('secret');
    expect(row.lin).not.toMatch(/\|an\|/);
    expect(fromLin(row.lin!).tricks_taken['N/S']).toBe(13);
  });

  it('builds the same board from a Hand history record as the app does', () => {
    const record = fromLin(soloLin());
    const shared = playedShare({ ...record, label: 'my label' }, null);
    expect(shared.lin).not.toContain('secret');
    expect(shared.lin).not.toContain('my label');
    expect((rowFor(shared, DAY) as BoardRow).lin).toBe(shared.lin);
  });

  it('keeps a challenge board\'s grade, and works out the margin itself', () => {
    const record = fromLin(soloLin());
    const graded = { deal_id: 17, board_num: 1, you: 210, robot: 140, margin: 999,
      your_bidding_loss: 0, your_play_loss: 0, robot_bidding_loss: 50, robot_play_loss: 20 };
    const row = rowFor(playedShare(record, graded), DAY) as BoardRow;
    expect(row).toMatchObject({ mode: 'challenge', deal_id: 17, you: 210, robot: 140, margin: 70, robot_bidding_loss: 50 });
  });

  it('stores a training board by its deal and calls, replayed', () => {
    const b = trainingShare(5, 1, [['North', 'Pass'], ['East', 'Pass'], ['South', '1S'], ['West', 'Pass'], ['North', 'Pass'], ['East', 'Pass']],
      { score: 140, par: 420, robotScore: 170 });
    const row = rowFor(b, DAY) as BoardRow;
    expect(row).toMatchObject({ mode: 'training', deal_id: 5, board_num: 1, auction: 'P P 1S P P P', contract: '1S',
      declarer: 'South', you: 140, robot: 170, margin: -30, par: 420, lin: null, tricks: null });
  });

  it('refuses what is not a finished, legal board, or carries anything else', () => {
    const bad: [unknown, string][] = [
      [null, 'not a board'],
      [{ ...solo(), v: 2 }, 'not a board'],
      [{ ...solo(), mode: 'spy' }, 'mode'],
      [{ ...solo(), app: 'Mozilla/5.0 (iPhone)' }, 'app'],
      [{ ...solo(), lin: soloLin().replace('pc|SA|', 'pc|HA|') }, 'lin'],
      [{ ...solo(), lin: 'x'.repeat(5000) }, 'lin'],
      [{ ...solo(), mode: 'challenge', deal_id: 1, challenge: { you: 1e9 } }, 'challenge'],
      [{ v: 1, mode: 'training', app: '1', deal_id: 5, board_num: 1, calls: ['1S'], training: { score: 0, par: 0, robot_score: 0 } }, 'calls'],
      [{ v: 1, mode: 'training', app: '1', deal_id: 5, board_num: 1, calls: ['Pass', 'Pass', 'Pass', 'Pass', 'Pass'], training: { score: 0, par: 0, robot_score: 0 } }, 'calls'],
    ];
    for (const [b, why] of bad) expect(rowFor(b, DAY), JSON.stringify(b).slice(0, 80)).toBe(why);
  });

  it('a row has no field for who sent it', () => {
    const row = rowFor(solo(), DAY) as BoardRow;
    expect(Object.keys(row).filter((k) => /ip|addr|user|agent|name|id$/i.test(k))).toEqual(['deal_id']);
  });

  it('skips a refused board, never the batch, and refuses junk', async () => {
    const stored: unknown[][] = [];
    const db = {
      prepare: () => ({ run: async () => ({}), bind: (...v: unknown[]) => (stored.push(v), {}) }),
      batch: async () => [],
    } as unknown as D1Database;
    expect(await storeBoards(db, 'nope')).toEqual({ stored: 0, refused: ['not JSON'] });
    expect(await storeBoards(db, JSON.stringify({ boards: [solo(), { v: 1, mode: 'x' }, solo()] }))).toEqual({ stored: 2, refused: ['mode'] });
    expect(stored.length).toBe(2);
    expect((await storeBoards(db, JSON.stringify({ boards: Array(30).fill(solo()) }))).stored).toBe(20);
  });
});

describe('the Worker stores a batch in D1', () => {
  const ORIGIN = 'https://bridge.example';
  let w: Unstable_DevWorker;
  let url: string;
  const dir = mkdtempSync(join(tmpdir(), 'bridge-boards-'));
  const here = new URL('..', import.meta.url).pathname;

  beforeAll(async () => {
    writeFileSync(join(dir, 'index.html'), '<!doctype html><title>site</title>');
    copyFileSync(join(here, '_headers'), join(dir, '_headers'));
    w = await unstable_dev(join(here, 'src/worker.ts'), {
      config: join(here, 'wrangler.jsonc'), assets: dir,
      vars: { ALLOWED_ORIGINS: ORIGIN, BRIDGE_DEV: '1', BOARDS_PER_HOUR: '3' },
      ip: '127.0.0.1', port: 0, inspect: false, logLevel: 'error', persist: false,
      experimental: { disableExperimentalWarning: true, disableDevRegistry: true },
    });
    url = `http://127.0.0.1:${w.port}`;
  });
  afterAll(async () => {
    await w?.stop();
    rmSync(dir, { recursive: true, force: true });
  });

  const post = (body: string, origin = ORIGIN) => fetch(`${url}/boards`, { method: 'POST', headers: { origin }, body });

  it('stores what the app sends, ignores other sites, and limits an address', async () => {
    const res = await post(JSON.stringify({ boards: [solo()] }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ stored: 1, refused: [] });
    expect((await post(JSON.stringify({ boards: [solo()] }), 'https://evil.example')).status).toBe(204);
    const rows = await (await fetch(`${url}/dev/boards`)).json() as BoardRow[];
    expect(rows.length).toBe(1);
    expect(rows[0]).toMatchObject({ mode: 'solo', contract: '1S', tricks: 13 });
    expect(rows[0].day).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(JSON.stringify(rows)).not.toContain('127.0.0.1');
    expect((await post('{}')).status).toBe(200);
    expect((await post('{}')).status).toBe(200);
    expect((await post('{}')).status).toBe(429);
    expect((await fetch(`${url}/boards`)).status).toBe(404);
  });
});
