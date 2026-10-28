// Bidding training, driven the way a player would: bid boards to the end and
// render the view at every step, check the recap's arithmetic, and that the
// training deals never repeat a challenge deal.
import { describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import { Trainer, TRAINING_KEY, contractScore, misfits, nsTricks, trainingDealIds, trainingPar } from './trainer.svelte';
import { prng } from './meanings';
import { parseHand } from './engine/card';
import { AuctionState } from './engine/auction';
import * as challenge from './engine/challenge';
import TrainerView from './views/TrainerView.svelte';

/** South bids a cheap suit now and then, else passes: crude, but it walks
 *  every state, from passed out to contested auctions. */
function bidBoard(t: Trainer, n: number): void {
  for (let guard = 0; guard < 60 && !t.recap; guard++) {
    const html = render(TrainerView, { props: { trainer: t } }).body;
    expect(html).toContain('Your call');
    const legal = t.auction.legalCalls();
    const bid = legal.find((c) => c === '1S' || c === '2H' || c === '3C' || c === '4S');
    t.humanBids((guard + n) % 2 === 0 && bid ? bid : 'Pass');
  }
}

class MemoryStorage {
  data = new Map<string, string>();
  getItem(k: string) { return this.data.get(k) ?? null; }
  setItem(k: string, v: string) { this.data.set(k, v); }
  removeItem(k: string) { this.data.delete(k); }
}

describe('Bidding training', () => {
  it('uses deals of its own, none from the challenge library', () => {
    const ids = trainingDealIds();
    expect(ids.length).toBeGreaterThan(0);
    const key = (hands: Record<string, unknown[]>) => JSON.stringify(hands.North);
    const library = new Set(challenge.dealIds().map((i) => key(challenge.handsFor(i))));
    for (const i of ids) {
      const t = new Trainer(null, prng(1));
      t.newBoard(i);
      expect(library.has(key(t.hands)), `training deal ${i} is a challenge deal`).toBe(false);
    }
  });

  it('bids boards to the end and recaps each one against par', () => {
    const t = new Trainer(null, prng(7));
    const seen = new Set<number>();
    for (let n = 0; n < 12; n++) {
      bidBoard(t, n);
      const r = t.recap!;
      expect(r).not.toBeNull();
      seen.add(r.dealId);
      expect(r.diff).toBe(r.score - r.par.score);
      expect(r.score).toBe(contractScore(r.dealId, r.contract).score);
      // Par is N/S's best: no N/S contract scores more double dummy.
      if (r.contract?.side === 'N/S') expect(r.score).toBeLessThanOrEqual(r.par.score);
      expect(r.par.score).toBe(trainingPar(r.dealId, t.vulnerability).score);
      for (const s of ['C', 'D', 'H', 'S', 'NT'] as const) expect(r.dd[s]).toBe(nsTricks(r.dealId, s));
      // Every call South made is looked at.
      expect(r.checks.length).toBe(t.calls.filter(([p]) => p === 'South').length);
      // The robots' auction on the same board, and where the two part.
      const robots = new AuctionState(t.dealer, t.vulnerability);
      for (const [p, c] of r.robotCalls) robots.applyCall(p, c);
      expect(robots.isComplete).toBe(true);
      expect(robots.getContract()?.strain ?? null).toBe(r.robotContract?.strain ?? null);
      if (r.parting === null) expect(r.robotCalls).toEqual(t.calls);
      else {
        expect(r.robotCalls.slice(0, r.parting)).toEqual(t.calls.slice(0, r.parting));
        expect(r.robotCalls[r.parting]?.[1]).not.toBe(t.calls[r.parting]?.[1]);
      }
      const html = render(TrainerView, { props: { trainer: t } }).body;
      for (const text of ['against par', 'North · partner', 'Was there a game?', "Robots' auction, same deal", 'Next board']) expect(html).toContain(text);
      expect(html).not.toContain('Your call');
      t.newBoard();
    }
    expect(t.log.length).toBe(12);
    expect(seen.size).toBe(Math.min(12, trainingDealIds().length));
    expect(t.average).toBe(Math.round(t.log.reduce((n, e) => n + e.diff, 0) / 12));
  });

  it('keeps the log between visits', () => {
    const storage = new MemoryStorage() as unknown as Storage;
    const t = new Trainer(storage, prng(3));
    bidBoard(t, 0);
    const again = new Trainer(storage, prng(3));
    expect(again.log).toEqual(t.log);
    expect(again.boardNum).toBe(t.boardNum + 1);
    storage.setItem(TRAINING_KEY, 'not json');
    expect(new Trainer(storage, prng(3)).log).toEqual([]);
  });

  it('carries on with a board half-bid after a reload, rather than dealing another', () => {
    const storage = new MemoryStorage() as unknown as Storage;
    const t = new Trainer(storage, prng(4));
    t.humanBids(t.auction.legalCalls().find((c) => /^\d/.test(c))!, 'my alert');
    const again = new Trainer(storage, prng(99));
    expect(again.dealId).toBe(t.dealId);
    expect(again.boardNum).toBe(t.boardNum);
    expect(again.calls).toEqual(t.calls);
    expect(again.alerts).toEqual(t.alerts);
    bidBoard(again, 0);
    expect(new Trainer(storage, prng(4)).boardNum).toBe(again.boardNum + 1);
  });

  it('loads past a damaged save', () => {
    const storage = new MemoryStorage() as unknown as Storage;
    const entry = { deal_id: 1, board_num: 1, score: 110, par: 140, diff: -30 };
    for (const [save, log] of [
      [{ version: 1, boardNum: 3, log: [null, entry, { deal_id: 'x' }] }, [entry]],
      [{ version: 1, boardNum: -5, log: [] }, []],
      [{ version: 1, boardNum: 2.5, log: [] }, []],
      [{ version: 1, boardNum: 2, log: [], current: { boardNum: 3, dealId: -1, calls: [], alerts: {} } }, []],
      [{ version: 1, boardNum: 2, log: [], current: { boardNum: 3, dealId: trainingDealIds()[0], calls: [['South', '9Z']], alerts: {} } }, []],
      [null, []],
    ] as const) {
      storage.setItem(TRAINING_KEY, JSON.stringify(save));
      const t = new Trainer(storage, prng(3));
      expect(t.log).toEqual(log);
      expect(Number.isInteger(t.boardNum) && t.boardNum > 0).toBe(true);
      expect(['North', 'East', 'South', 'West']).toContain(t.dealer);
    }
  });

  it('lets a person run the auction long: it still ends in the recap', () => {
    // Found by fuzzing: robots stopped calling at 60 calls, and the board froze.
    const t = new Trainer(null, prng(1));
    t.boardNum = 452;
    t.newBoard(307);
    const mine = ['1H', '4C', '4D', '4H', '4S', '4NT', '5C', '6S', '6NT', '7C', '7D', '7H', '7S', '7NT', 'XX'];
    for (const call of mine) {
      if (t.recap) break;
      t.humanBids(t.auction.legalCalls().includes(call) ? call : 'Pass');
    }
    for (let guard = 0; guard < 40 && !t.recap; guard++) t.humanBids('Pass');
    expect(t.calls.length).toBeGreaterThanOrEqual(60);
    expect(t.recap).not.toBeNull();
  });

  it('says where a hand falls outside what a call showed', () => {
    const hand = parseHand('AS KS QS JS 8S 6S AH 7H 4H 3H QC 10C 7C');
    expect(misfits('5+ ♠, 11-15 HCP.', hand)).toEqual(['16 HCP']);
    expect(misfits('6+ ♠, 16-18 HCP.', hand)).toEqual([]);
    expect(misfits('5+ ♥, 12+ HCP.', hand)).toEqual(['4 ♥']);
  });
});
