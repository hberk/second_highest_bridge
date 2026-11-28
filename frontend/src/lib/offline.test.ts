// MP10 (docs/MULTIPLAYER_PLAN.md): solo play, Challenge and Bidding training
// send nothing during play; the one call is the anonymous visit beacon at
// page load on Cloudflare. Two checks, because neither alone is proof:
//
// 1. Behaviour: every way out of the page (fetch, WebSocket, XMLHttpRequest,
//    EventSource, sendBeacon, Worker) is replaced by a trap, and free boards,
//    challenge boards and training boards are played start to finish with
//    every view rendered at every step. One touch of a trap fails the test.
// 2. Source: every place in src/ that can reach the network is listed below
//    with what opens it. None on a solo path talks to a server; the only
//    one a solo screen reaches is the solver loading its own .wasm file from
//    the site. A new one fails here until someone decides it belongs, and
//    says why.
//
// The render is server-side, so a $effect (where the solver starts) doesn't
// run in (1); (2) is what covers it.
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import { Game } from './game.svelte';
import { Trainer } from './trainer.svelte';
import { prng } from './meanings';
import { legalPlays } from './engine/auction';
import TableView from './views/TableView.svelte';
import DesktopTableView from './views/DesktopTableView.svelte';
import HistoryView from './views/HistoryView.svelte';
import ChallengeView from './views/ChallengeView.svelte';
import HomeView from './views/HomeView.svelte';
import HowToPlayView from './views/HowToPlayView.svelte';
import TrainerView from './views/TrainerView.svelte';
import indexHtml from '../../index.html?raw';
import pkg from '../../package.json';

const NETWORK = ['fetch', 'WebSocket', 'XMLHttpRequest', 'EventSource', 'Worker', 'SharedWorker'] as const;
const calls: string[] = [];
const saved = new Map<string, PropertyDescriptor | undefined>();
let beacon: PropertyDescriptor | undefined;

function trap(name: string): unknown {
  const fail = (...args: unknown[]): never => {
    calls.push(`${name}(${args.map((a) => String(a)).join(', ')})`);
    throw new Error(`solo play reached the network: ${name}`);
  };
  // `new WebSocket(...)` and `fetch(...)` both land here.
  return new Proxy(function () {}, { apply: (_t, _this, args) => fail(...args), construct: (_t, args) => fail(...args) });
}

beforeAll(() => {
  const g = globalThis as Record<string, unknown>;
  for (const name of NETWORK) {
    saved.set(name, Object.getOwnPropertyDescriptor(g, name));
    Object.defineProperty(g, name, { value: trap(name), configurable: true, writable: true });
  }
  const nav = (g.navigator ?? {}) as Record<string, unknown>;
  beacon = Object.getOwnPropertyDescriptor(nav, 'sendBeacon');
  if (g.navigator) Object.defineProperty(nav, 'sendBeacon', { value: trap('sendBeacon'), configurable: true });
});

afterAll(() => {
  const g = globalThis as Record<string, unknown>;
  for (const [name, d] of saved) {
    if (d) Object.defineProperty(g, name, d);
    else delete g[name];
  }
  if (g.navigator) {
    const nav = g.navigator as Record<string, unknown>;
    if (beacon) Object.defineProperty(nav, 'sendBeacon', beacon);
    else delete nav.sendBeacon;
  }
});

const noop = (): void => {};

function renderSolo(game: Game): void {
  render(TableView, { props: { game } });
  render(DesktopTableView, { props: { game } });
  render(HistoryView, { props: { records: game.history } });
  render(ChallengeView, { props: { game, ondealt: noop } });
  // Play with friends is on the home screen, but nothing runs until it's tapped.
  render(HomeView, { props: { game, onplay: noop, ontraining: noop, onchallenge: noop, onhowto: noop, onhistory: noop, onsettings: noop, onfriends: noop } });
}

/** South makes the odd bid and plays its first legal card, through every
 *  phase, rendering everything at every step. */
function playBoard(game: Game): void {
  for (let step = 0; step < 500; step++) {
    renderSolo(game);
    if (game.phase === 'bidding') {
      if (game.auction.passedOut) return;
      const bid = game.auction.legalCalls().find((c) => c === '1NT' || c === '2S');
      game.humanBids(step % 3 === 0 && bid ? bid : 'Pass');
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

describe('MP10: solo play sends nothing during play', () => {
  it('plays free boards and challenge boards with the network trapped', () => {
    const game = new Game(null, prng(10));
    let played = 0;
    for (let i = 0; i < 12; i++) {
      game.newBoard();
      playBoard(game);
      if (game.phase === 'done') played++;
    }
    for (let i = 0; i < 6; i++) {
      expect(game.dealChallenge()).toBe(true);
      playBoard(game);
      if (game.phase === 'done') played++;
    }
    renderSolo(game);
    render(HowToPlayView, {});
    expect(played, 'too few boards reached the end to prove anything').toBeGreaterThan(8);
    expect(game.challengeLog.length).toBe(6);
    expect(calls).toEqual([]);
  });

  it('trains bidding with the network trapped', () => {
    const trainer = new Trainer(null, prng(10));
    for (let i = 0; i < 6; i++) {
      trainer.newBoard();
      for (let step = 0; step < 60 && !trainer.recap; step++) {
        render(TrainerView, { props: { trainer } });
        trainer.humanBids('Pass');
      }
      expect(trainer.recap, 'a training board did not finish').not.toBeNull();
      render(TrainerView, { props: { trainer } });
    }
    expect(calls).toEqual([]);
  });

  it('the traps would have caught a call', () => {
    const before = calls.length;
    expect(() => fetch('x')).toThrow(/network/);
    expect(() => new WebSocket('wss://x')).toThrow(/network/);
    calls.splice(before);
  });
});

// ---------------------------------------------------------------------------

/** Every source file under src/, by its path from src/, tests left out. */
const FILES: Record<string, string> = Object.fromEntries(
  Object.entries(import.meta.glob('/src/**/*.{ts,svelte}', { query: '?raw', import: 'default', eager: true }) as Record<string, string>)
    .filter(([p]) => !p.endsWith('.test.ts'))
    .map(([p, text]) => [p.slice('/src/'.length), text]));

/** Every place the app can reach the network, by file, with what opens it.
 *  `server` reaches the table server; `asset` loads one of the site's own
 *  files (the solver's .wasm, from the same origin, as the page loads its
 *  scripts). The challenge's Review the deal starts the solver, so a solo
 *  screen may reach an `asset` file, never a `server` one. */
const ALLOWED: Record<string, { count: number; kind: 'server' | 'asset'; why: string }> = {
  'App.svelte': { count: 2, kind: 'server', why: "fetch('tables') behind Play with friends, and the page-load visit ping (VITE_VISITS, the Cloudflare deploy only)" },
  'lib/table/remote.svelte.ts': { count: 2, kind: 'server', why: 'healthz and the WebSocket: only at a table link (#/t/...)' },
  'lib/dd/worker.ts': { count: 1, kind: 'asset', why: "the solver's own .wasm file: History and Review the deal" },
  'lib/dd/tableWorker.ts': { count: 1, kind: 'asset', why: "the solver's own .wasm file: the tricks table, on a tap" },
  'lib/dd/analysis.svelte.ts': { count: 2, kind: 'asset', why: "the solver's worker, and a HEAD of its script after a failed load" },
  'lib/dd/table.svelte.ts': { count: 1, kind: 'asset', why: "the tricks table's solver worker" },
};

const PATTERN = /\bfetch\s*\(|\bnew\s+(?:WebSocket|XMLHttpRequest|EventSource|Worker|SharedWorker)\b|\bsendBeacon\b|\bimport\s*\(\s*['"`]https?:|\bopen\s*\(\s*['"`]https?:/g;

/** `rel` (./x or ../x) from the file `from`, as a path from src/. */
function resolve(from: string, rel: string): string {
  const parts = from.split('/').slice(0, -1);
  for (const seg of rel.split('/')) {
    if (seg === '..') parts.pop();
    else if (seg !== '.') parts.push(seg);
  }
  return parts.join('/');
}

/** Strips comments so a sentence about fetch() isn't a call. */
function code(text: string): string {
  return text.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
}

describe('MP10: where the app can reach the network', () => {
  const found = new Map<string, number>();
  for (const [f, text] of Object.entries(FILES)) {
    const n = code(text).match(PATTERN)?.length ?? 0;
    if (n) found.set(f, n);
  }

  it('every network call in src/ is one of the known, non-solo ones', () => {
    const unknown = [...found].filter(([f, n]) => ALLOWED[f]?.count !== n);
    expect(unknown, 'a network call was added or moved: check it is off every solo path, then list it in ALLOWED').toEqual([]);
    const gone = Object.keys(ALLOWED).filter((f) => !found.has(f));
    expect(gone, 'listed in ALLOWED but no longer calls out: drop it from the list').toEqual([]);
  });

  it('nothing a solo board, the challenge or training loads imports the table server code', () => {
    // What the solo screens are built from, followed through their imports.
    const roots = ['lib/game.svelte.ts', 'lib/trainer.svelte.ts', 'lib/views/TableView.svelte',
      'lib/views/DesktopTableView.svelte', 'lib/views/ChallengeView.svelte', 'lib/views/TrainerView.svelte',
      'lib/views/HomeView.svelte', 'lib/views/HowToPlayView.svelte'];
    const seen = new Set<string>();
    const queue = [...roots];
    while (queue.length) {
      const f = queue.pop()!;
      if (seen.has(f)) continue;
      seen.add(f);
      const text = code(FILES[f]);
      // `import type` is erased from the build, so it loads nothing.
      for (const m of text.matchAll(/(?:import|export)\s(?!type\s)[^'"`;]*?from\s*['"`](\.[^'"`]+)['"`]/g)) {
        const base = resolve(f, m[1]);
        const target = ['', '.ts', '.svelte.ts', '/index.ts'].map((ext) => base + ext).find((p) => p in FILES);
        if (target && /\.(ts|svelte)$/.test(target)) queue.push(target);
      }
    }
    expect(seen.size, 'the import walk found too little to mean anything').toBeGreaterThan(20);
    const reached = [...seen].filter((f) => ALLOWED[f]?.kind === 'server');
    expect(reached, 'a solo screen now imports code that can reach the table server').toEqual([]);
  });

  it('the page connects only to itself and the table server, and loads nothing from elsewhere', () => {
    const csp = indexHtml.match(/http-equiv="Content-Security-Policy" content="([^"]+)"/)![1];
    const directives = csp.split(';').map((d: string) => d.trim());
    // vite.config.ts adds the table server's socket to connect-src at build
    // time, and nothing else.
    expect(directives.find((d: string) => d.startsWith('connect-src'))).toBe("connect-src 'self'");
    expect(directives.find((d: string) => d.startsWith('script-src'))).toBe("script-src 'self' 'wasm-unsafe-eval'");
    expect(indexHtml, 'a script or stylesheet from another site').not.toMatch(/(?:src|href)="(?:https?:)?\/\//);
    expect(indexHtml).not.toContain('cloudflareinsights');
  });

  it('only the live site sends the visit ping', () => {
    // App.svelte sends it when VITE_VISITS is 1, set only by server/cf's
    // `npm run site` (the Cloudflare deploy); local dev and the tests never set it.
    expect(import.meta.env.VITE_VISITS).not.toBe('1');
    expect(pkg.scripts.build).not.toContain('VITE_VISITS');
    expect(FILES['App.svelte']).toMatch(/if \(import\.meta\.env\.VITE_VISITS === '1'\) \{\s*try \{ navigator\.sendBeacon\('\/visit'/);
  });
});
