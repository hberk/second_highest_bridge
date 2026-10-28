// The multiplayer table's core, driven directly: the robots at a table play
// exactly as at a solo table; no seat is ever sent a card or an alert it
// couldn't see at a real table; every refused intent changes nothing; seats
// pass to robots and back; finished boards survive LIN.
import { describe, expect, it } from 'vitest';
import type { Card, Seat } from '../engine/card';
import { PARTNERSHIP, PLAYERS, legalPlays } from '../engine/auction';
import { Game } from '../game.svelte';
import { prng } from '../meanings';
import { fromLin, toLin } from '../lin';
import {
  TAKEOVER_MS, addPlayer, applyIntent, applyRobot, derive, newTable, robotAction, viewFor,
  type Context, type TableState,
} from './core';
import type { Readings } from '../alerts';
import type { ClientMessage } from './protocol';

const readings: Readings = new Map();

function ctx(over: Partial<Context> = {}): Context {
  return { now: 0, connected: () => true, awaySince: () => null, random: prng(7), ...over };
}

/** A table with a player in each of `seats` (ids p-North, p-East, ...). */
function table(seats: Seat[], c = ctx()): TableState {
  const s = newTable('T'.repeat(22), 0);
  for (const seat of seats) {
    expect(addPlayer(s, `p-${seat}`, 'hash', seat.toLowerCase(), 0).ok).toBe(true);
    expect(applyIntent(s, `p-${seat}`, { type: 'sit', seat }, c).ok).toBe(true);
  }
  return s;
}

function runRobots(s: TableState): void {
  for (let a = robotAction(s, readings); a; a = robotAction(s, readings)) applyRobot(s, a);
}

const intentId = (() => { let n = 0; return () => `i${n++}`; })();

/** The human whose action the table waits on, and what they may do. */
function pending(s: TableState) {
  const d = derive(s.board!);
  if (d.phase === 'done' || !d.toAct) return null;
  const actor = d.phase === 'playing' && d.contract!.dummy === d.toAct ? d.contract!.declarer : d.toAct;
  return { d, seat: d.toAct, actor, player: `p-${actor}` };
}

describe('robots at a table play as at a solo table', () => {
  it('matches Game call for call and card for card, one human at South', () => {
    const boards = 60;
    const game = new Game(null, prng(11));
    for (let n = 0; n < boards; n++) {
      // Drive the solo game with a crude South, recording each decision.
      const decisions: (string | Card)[] = [];
      for (let guard = 0; guard < 500 && game.phase !== 'done' && !game.auction.passedOut; guard++) {
        if (game.phase === 'bidding') {
          const legal = game.auction.legalCalls();
          const bid = legal.find((c) => c === '1NT' || c === '2C' || c === '3H' || c === '4S');
          const call = guard % 3 === 0 && bid ? bid : 'Pass';
          decisions.push(call);
          game.humanBids(call);
        } else if (game.phase === 'auction_done') game.startPlay();
        else if (game.phase === 'trick_done') game.nextTrick();
        else {
          const who = game.whoseTurn()!;
          const led = game.trick.length ? game.trick[0][1].suit : null;
          const c = legalPlays(game.hands[who], led).at(-1)!;
          decisions.push(c);
          game.humanPlays(who, c);
        }
      }

      // The same deal at a table, South a person making the same choices.
      const s = table(['South']);
      s.boardNum = game.boardNum - 1;
      s.board = {
        num: game.boardNum, dealer: game.dealer, vulnerability: game.vulnerability,
        hands: Object.fromEntries(PLAYERS.map((p) => [p, [...game.initialHands[p]]])) as Record<Seat, Card[]>,
        actions: [],
      };
      for (const choice of decisions) {
        runRobots(s);
        const p = pending(s)!;
        expect(p.player, `board ${n}: the table waits on a robot`).toBe('p-South');
        const m: ClientMessage = typeof choice === 'string'
          ? { type: 'call', id: intentId(), at: s.board.actions.length, call: choice }
          : { type: 'card', id: intentId(), at: s.board.actions.length, seat: p.seat, card: choice };
        expect(applyIntent(s, 'p-South', m, ctx())).toEqual({ ok: true });
      }
      runRobots(s);
      const d = derive(s.board);
      const where = `board ${n}`;
      expect(d.calls, where).toEqual(game.calls);
      expect(d.alerts, where).toEqual(game.alerts);
      expect(d.tricksLog.flatMap((t) => t.plays), where).toEqual(game.tricksLog.flatMap((t) => t.plays));
      expect(d.result, where).toEqual(game.result);
      game.newBoard();
    }
  }, 300_000);
});

/** Every card some other seat holds that `seat` mustn't see: not its own,
 *  not dummy's once the lead is made. */
function forbidden(s: TableState, seat: Seat | null): Card[] {
  const d = derive(s.board!);
  if (d.phase === 'done') return [];
  const dummyDown = !!d.contract && (d.tricksLog.length > 0 || d.trick.length > 0);
  return PLAYERS.filter((p) => p !== seat && !(dummyDown && p === d.contract!.dummy)).flatMap((p) => d.hands[p]);
}

const cardJson = (c: Card) => JSON.stringify({ suit: c.suit, rank: c.rank });

describe('no seat sees what it could not see at a real table', () => {
  it('holds over random tables with one to four people', () => {
    const rnd = prng(5);
    let checks = 0;
    for (let t = 0; t < 120; t++) {
      const humans = PLAYERS.filter(() => rnd() < 0.5);
      if (!humans.length) humans.push(PLAYERS[t % 4]);
      const c = ctx({ random: prng(100 + t) });
      const s = table(humans, c);
      // A watcher without a seat, too.
      addPlayer(s, 'watcher', 'hash', 'watcher', 0);
      expect(applyIntent(s, `p-${humans[0]}`, { type: 'deal' }, c).ok).toBe(true);
      for (let guard = 0; guard < 200; guard++) {
        runRobots(s);
        // Check every viewer now.
        for (const viewer of [...humans.map((h) => `p-${h}`), 'watcher']) {
          const seat = viewer === 'watcher' ? null : viewer.slice(2) as Seat;
          const json = JSON.stringify(viewFor(s, viewer, c));
          for (const card of forbidden(s, seat)) {
            expect(json.includes(cardJson(card)), `table ${t}: ${viewer} sees ${card.rank}${card.suit}`).toBe(false);
          }
          const d = derive(s.board!);
          if (d.phase !== 'done') {
            const alerts = viewFor(s, viewer, c).board!.alerts;
            d.calls.forEach(([who], i) => {
              if (d.humanCall[i] && d.alerts[i] && seat && who !== seat && PARTNERSHIP[who] === PARTNERSHIP[seat]) {
                expect(alerts[i], `table ${t}: ${viewer} sees partner's alert`).toBeUndefined();
              }
              if (!d.humanCall[i] && d.calls[i][1] === 'Pass') expect(alerts[i]).toBeUndefined();
            });
          }
          checks++;
        }
        const p = pending(s);
        if (!p) break;
        const d = p.d;
        const at = s.board!.actions.length;
        const m: ClientMessage = d.phase === 'bidding'
          ? {
            type: 'call', id: intentId(), at,
            call: rnd() < 0.7 ? 'Pass' : d.auction.legalCalls()[Math.floor(rnd() * d.auction.legalCalls().length)],
            ...(rnd() < 0.5 ? { alert: 'a test alert' } : {}),
          }
          : (() => {
            const led = d.trick.length ? d.trick[0][1].suit : null;
            const legal = legalPlays(d.hands[p.seat], led);
            return { type: 'card' as const, id: intentId(), at, seat: p.seat, card: legal[Math.floor(rnd() * legal.length)] };
          })();
        expect(applyIntent(s, p.player, m, c).ok, `table ${t}`).toBe(true);
      }
      expect(derive(s.board!).phase, `table ${t} did not finish`).toBe('done');
    }
    expect(checks).toBeGreaterThan(2000);
  }, 300_000);

  it('shows dummy only once the opening lead is made', () => {
    const c = ctx({ random: prng(3) });
    for (let t = 0; t < 30; t++) {
      const s = table(['North', 'East', 'South', 'West'], ctx({ random: prng(200 + t) }));
      applyIntent(s, 'p-North', { type: 'deal' }, c);
      // Everyone passes but the dealer, who opens 1C: the dealer declares.
      for (;;) {
        const p = pending(s)!;
        if (p.d.phase !== 'bidding') break;
        const call = p.d.calls.length === 0 ? '1C' : 'Pass';
        applyIntent(s, p.player, { type: 'call', id: intentId(), at: s.board!.actions.length, call }, c);
      }
      const d = derive(s.board!);
      const dummy = d.contract!.dummy;
      for (const p of PLAYERS) {
        const v = viewFor(s, `p-${p}`, c).board!;
        expect(v.hands[dummy].length, `${p} sees dummy before the lead`).toBe(p === dummy ? 13 : 0);
      }
      const leader = pending(s)!;
      const card = legalPlays(leader.d.hands[leader.seat], null)[0];
      applyIntent(s, leader.player, { type: 'card', id: intentId(), at: s.board!.actions.length, seat: leader.seat, card }, c);
      for (const p of PLAYERS) expect(viewFor(s, `p-${p}`, c).board!.hands[dummy].length).toBe(13);
    }
  });
});

describe('refusals change nothing', () => {
  function snapshot(s: TableState) {
    return JSON.stringify(s);
  }

  it('out of turn, illegal, stale and the wrong hand are each refused', () => {
    const c = ctx({ random: prng(9) });
    const s = table(['North', 'East', 'South', 'West'], c);
    applyIntent(s, 'p-North', { type: 'deal' }, c);
    const first = pending(s)!;
    const other = PLAYERS.find((p) => p !== first.seat)!;
    const before = snapshot(s);
    const tries: [string, ClientMessage, string][] = [
      [`p-${other}`, { type: 'call', id: 'a', at: 0, call: 'Pass' }, 'not_your_turn'],
      [first.player, { type: 'call', id: 'b', at: 0, call: 'XX' }, 'illegal'],
      [first.player, { type: 'call', id: 'c', at: 5, call: 'Pass' }, 'stale'],
      [first.player, { type: 'card', id: 'd', at: 0, seat: first.seat, card: first.d.hands[first.seat][0] }, 'not_now'],
      ['nobody', { type: 'call', id: 'e', at: 0, call: 'Pass' }, 'not_joined'],
      [`p-${other}`, { type: 'lock', locked: true }, 'not_host'],
    ];
    for (const [who, m, code] of tries) {
      const out = applyIntent(s, who, m, c);
      expect(out.ok).toBe(false);
      if (!out.ok) expect(out.code).toBe(code);
      expect(snapshot(s)).toBe(before);
    }

    // Play to the opening lead; then the dummy's owner and a defender each
    // try to play the dummy.
    for (;;) {
      const p = pending(s)!;
      if (p.d.phase !== 'bidding') break;
      const call = p.d.calls.length === 0 ? '1NT' : 'Pass';
      applyIntent(s, p.player, { type: 'call', id: intentId(), at: s.board!.actions.length, call }, c);
    }
    const lead = pending(s)!;
    applyIntent(s, lead.player, {
      type: 'card', id: intentId(), at: s.board!.actions.length, seat: lead.seat,
      card: legalPlays(lead.d.hands[lead.seat], null)[0],
    }, c);
    const d = derive(s.board!);
    const contract = d.contract!;
    expect(d.toAct).toBe(contract.dummy);
    const defender = PLAYERS.find((p) => PARTNERSHIP[p] !== contract.side)!;
    const card = legalPlays(d.hands[contract.dummy], d.trick[0][1].suit)[0];
    const at = s.board!.actions.length;
    const mid = snapshot(s);
    for (const who of [contract.dummy, defender]) {
      const out = applyIntent(s, `p-${who}`, { type: 'card', id: intentId(), at, seat: contract.dummy, card }, c);
      expect(out.ok, `${who} played the dummy`).toBe(false);
      expect(snapshot(s)).toBe(mid);
    }
    expect(applyIntent(s, `p-${contract.declarer}`, { type: 'card', id: intentId(), at, seat: contract.dummy, card }, c).ok).toBe(true);
    // The same intent again is stale: applied once.
    expect(applyIntent(s, `p-${contract.declarer}`, { type: 'card', id: intentId(), at, seat: contract.dummy, card }, c).ok).toBe(false);
  });
});

describe('seats are fixed while a board is played', () => {
  it('refuses sitting in an empty seat, or standing, mid-board: no hand to read', () => {
    const c = ctx({ random: prng(31) });
    const s = table(['South', 'West'], c);
    addPlayer(s, 'watcher', 'hash', 'watcher', 0);
    applyIntent(s, 'p-South', { type: 'deal' }, c);
    const before = JSON.stringify(s);
    for (const [who, m] of [
      ['p-South', { type: 'sit', seat: 'North' }], ['watcher', { type: 'sit', seat: 'East' }],
      ['p-West', { type: 'stand' }],
    ] as [string, ClientMessage][]) {
      const out = applyIntent(s, who, m, c);
      expect(out.ok, `${who} ${m.type}`).toBe(false);
      expect(JSON.stringify(s)).toBe(before);
    }
    expect(viewFor(s, 'watcher', c).board!.hands.East).toEqual([]);
  });
});

describe('seats pass to robots and back', () => {
  it('a robot takes an away player\'s seat mid-auction and mid-play, and gives it back', () => {
    let now = 0;
    let away: string | null = null;
    const c = (): Context => ctx({
      now, random: prng(13),
      connected: (id) => id !== away,
      awaySince: (id) => (id === away ? 0 : null),
    });
    const s = table(['North', 'South'], c());
    applyIntent(s, 'p-North', { type: 'deal' }, c());
    runRobots(s);
    // Whoever is to call goes away; the other asks a robot to take over.
    let p = pending(s)!;
    away = p.player;
    const helper = p.player === 'p-North' ? 'p-South' : 'p-North';
    expect(applyIntent(s, helper, { type: 'robot', seat: p.actor }, c()).ok, 'too soon').toBe(false);
    now = TAKEOVER_MS;
    expect(applyIntent(s, helper, { type: 'robot', seat: p.actor }, c()).ok).toBe(true);
    expect(viewFor(s, helper, c()).seats[p.actor].robot).toBe(true);
    const calls = derive(s.board!).calls.length;
    runRobots(s);
    expect(derive(s.board!).calls.length, 'the robot did not call').toBeGreaterThan(calls);

    // Back again: reclaim, and the seat waits on its person.
    away = null;
    const back = p.player;
    // Robots may have finished the board; deal on until a person is to act.
    for (let guard = 0; guard < 20; guard++) {
      const q = pending(s);
      if (q && q.player === back) break;
      if (!q) { applyIntent(s, helper, { type: 'deal' }, c()); applyIntent(s, back, { type: 'deal' }, c()); }
      runRobots(s);
      if (pending(s)?.player === helper) {
        const h = pending(s)!;
        const m: ClientMessage = h.d.phase === 'bidding'
          ? { type: 'call', id: intentId(), at: s.board!.actions.length, call: 'Pass' }
          : { type: 'card', id: intentId(), at: s.board!.actions.length, seat: h.seat,
              card: legalPlays(h.d.hands[h.seat], h.d.trick.length ? h.d.trick[0][1].suit : null)[0] };
        applyIntent(s, helper, m, c());
      }
    }
    expect(applyIntent(s, back, { type: 'reclaim' }, c()).ok).toBe(true);
    expect(viewFor(s, back, c()).seats[p.actor].robot).toBe(false);
    p = pending(s)!;
    if (p && p.player === back) expect(robotAction(s, readings)).toBeNull();
  });

  it('passes the host role on when the host has gone', async () => {
    const { maintain } = await import('./core');
    let away: string | null = null;
    const c = (now: number): Context => ctx({ now, connected: (id) => id !== away, awaySince: (id) => (id === away ? 0 : null) });
    const s = table(['North', 'East'], c(0));
    expect(s.hostId).toBe('p-North');
    away = 'p-North';
    expect(maintain(s, c(1000))).toBe(false);
    expect(maintain(s, c(TAKEOVER_MS))).toBe(true);
    expect(s.hostId).toBe('p-East');
  });
});

describe('the position memory', () => {
  it('clearing it between boards changes no card', async () => {
    const { clearPositionMemo } = await import('../engine/ai');
    const { robotTable } = await import('../engine/challenge');
    const plays = (clear: boolean) => Array.from({ length: 20 }, (_, id) => {
      if (clear) clearPositionMemo();
      const t = robotTable(id * 7, PLAYERS[id % 4]);
      return JSON.stringify([t.calls, t.tricks_log.map((x) => x.plays)]);
    });
    expect(plays(true)).toEqual(plays(false));
  }, 120_000);
});

describe('finished boards', () => {
  it('round-trip through LIN to the same score', () => {
    const c = ctx({ random: prng(21) });
    const s = table(['South'], c);
    let finished = 0;
    for (let n = 0; n < 12; n++) {
      applyIntent(s, 'p-South', { type: 'deal' }, c);
      for (let guard = 0; guard < 100; guard++) {
        runRobots(s);
        const p = pending(s);
        if (!p) break;
        const m: ClientMessage = p.d.phase === 'bidding'
          ? { type: 'call', id: intentId(), at: s.board!.actions.length, call: 'Pass' }
          : { type: 'card', id: intentId(), at: s.board!.actions.length, seat: p.seat,
              card: legalPlays(p.d.hands[p.seat], p.d.trick.length ? p.d.trick[0][1].suit : null)[0] };
        applyIntent(s, p.player, m, c);
      }
      const record = viewFor(s, 'p-South', c).board!.record!;
      expect(record.table_id).toBe(s.id);
      expect(record.my_seat).toBe('South');
      if (record.passed_out) continue;
      finished++;
      const back = fromLin(toLin(record));
      expect(back.result).toEqual(record.result);
      expect(back.tricks_taken).toEqual(record.tricks_taken);
    }
    expect(finished).toBeGreaterThan(3);
  });
});
