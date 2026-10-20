// The TypeScript engine must reproduce the Python engine exactly: every call,
// alert, card, score and grade. Fixtures come from
// tests/fixtures/export_ts_fixtures.py; rerun it whenever the Python changes.
import { describe, expect, it } from 'vitest';
import games from './__fixtures__/games.json';
import evals from './__fixtures__/evals.json';
import scoring from './__fixtures__/scoring.json';
import challengeFx from './__fixtures__/challenge.json';
import { parseCard, parseHand, removeCard, cardKey, type Card, type Seat, type Suit } from './card';
import { AuctionState, clockwiseFrom, legalPlays, resolveTrick, type Play } from './auction';
import { aiBidExplained, aiPlay, evalHandSh, hcp, visibleHands } from './ai';
import { scoreContract } from './scoring';
import { grade, par, robotTable } from './challenge';

type FxCall = [Seat, string, string | null, string[]];
interface FxGame {
  dealer: Seat; vul: any; hands: Record<Seat, string>; calls: FxCall[];
  contract: any; plays: [Seat, string][]; tricks: any; result: any;
}

describe('scoring', () => {
  it('matches every contract, doubling, vulnerability and trick count', () => {
    for (const [level, strain, doubled, vul, side, won, winner, made, points, detail] of scoring as any[]) {
      const other = side === 'N/S' ? 'E/W' : 'N/S';
      const r = scoreContract(
        { level, strain, doubled, vulnerability: vul, side, tricks_needed: level + 6 },
        { [side]: won, [other]: 13 - won } as any,
      );
      expect([r.winner, r.made, r.points, r.detail]).toEqual([winner, made, points, detail]);
    }
  });
});

describe('hand evaluation', () => {
  it('reproduces eval_hand_sh to the last bit', () => {
    for (const e of evals as any[]) {
      const hand = parseHand(e.hand);
      const ev = evalHandSh(hand);
      expect(hcp(hand)).toBe(e.hcp);
      expect(ev.honour_pts).toBe(e.honour_pts);
      expect(ev.suit_pts).toEqual(e.suit_pts);
      expect(ev.total_pts).toBe(e.total_pts);
      expect(ev.lengths).toEqual(e.lengths);
      expect(ev.is_balanced).toBe(e.is_balanced);
    }
  });
});

// The two replays below are the slowest tests by far: about 40s and 20s alone
// on an idle machine (2026-10-19), and npm test runs the test files in
// parallel, so the global 60s limit failed them on a busy machine. Their own
// limit keeps the global one tight for everything else.
const LONG = 300_000;

describe('games', () => {
  it(`replays ${(games as FxGame[]).length} boards call for call and card for card`, () => {
    for (const [gi, g] of (games as FxGame[]).entries()) {
      const where = `game ${gi}`;
      const hands = Object.fromEntries(
        Object.entries(g.hands).map(([s, t]) => [s, parseHand(t)])) as Record<Seat, Card[]>;
      const auction = new AuctionState(g.dealer, g.vul);
      for (const [ci, [who, call, why, legal]] of g.calls.entries()) {
        expect(auction.currentPlayer(), where).toBe(who);
        expect(auction.legalCalls(), `${where} call ${ci}`).toEqual(legal);
        if (why !== null) {
          expect(aiBidExplained(who, hands[who], auction), `${where} call ${ci}`).toEqual([call, why]);
        }
        auction.applyCall(who, call);
      }
      expect(auction.getContract(), where).toEqual(g.contract);
      if (!g.contract) continue;

      // South's cards were random in odd games; replay them rather than ask the AI.
      const human = gi % 2 === 1;
      const { trump, dummy } = g.contract;
      const played: Card[] = [];
      const history: Play[][] = [];
      const taken = { 'N/S': 0, 'E/W': 0 };
      let leader: Seat = g.contract.leader;
      let k = 0;
      for (let t = 0; t < 13; t++) {
        const trick: Play[] = [];
        for (const seat of clockwiseFrom(leader)) {
          const [fxSeat, fxCard] = g.plays[k++];
          expect(seat, where).toBe(fxSeat);
          const expected = parseCard(fxCard);
          if (human && seat === 'South') {
            const legal = legalPlays(hands[seat], trick.length ? trick[0][1].suit as Suit : null);
            expect(legal.map(cardKey), where).toContain(cardKey(expected));
          } else {
            const got = aiPlay(seat, hands[seat], trick, trump, played,
              visibleHands(seat, g.contract, hands), history);
            expect(cardKey(got), `${where} trick ${t + 1} ${seat}`).toBe(fxCard);
          }
          removeCard(hands[seat], expected);
          trick.push([seat, expected]);
        }
        const winner = resolveTrick(trick, trump);
        taken[winner === 'North' || winner === 'South' ? 'N/S' : 'E/W']++;
        played.push(...trick.map(([, c]) => c));
        history.push([...trick]);
        leader = winner;
      }
      expect(taken, where).toEqual(g.tricks);
      expect(scoreContract(g.contract, taken), where).toEqual(g.result);
    }
  }, LONG);
});

describe('challenge', () => {
  it('reproduces every robot table, grade and par in the library', () => {
    for (const fx of challengeFx as any[]) {
      const where = `deal ${fx.deal_id}`;
      const table = robotTable(fx.deal_id, fx.dealer, fx.vul);
      expect(table.calls, where).toEqual(fx.calls);
      expect(Object.fromEntries(Object.entries(table.alerts).map(([k, v]) => [String(k), v])), where)
        .toEqual(fx.alerts);
      expect(table.contract, where).toEqual(fx.contract);
      expect(table.tricks_log.flatMap((t) => t.plays.map(([p, c]) => [p, cardKey(c)])), where)
        .toEqual(fx.plays);
      expect(table.tricks_taken, where).toEqual(fx.tricks_taken);
      expect(table.result, where).toEqual(fx.result);
      expect(grade(fx.deal_id, 'N/S', table.contract, table.declarer_tricks, fx.vul), where)
        .toEqual(fx.grade);
      for (const vul of ['None', 'N/S', 'E/W', 'Both'] as const) {
        for (const side of ['N/S', 'E/W'] as const) {
          expect(par(fx.deal_id, side, vul), `${where} ${vul} ${side}`).toEqual(fx.par[vul][side]);
        }
      }
    }
  }, LONG);
});
