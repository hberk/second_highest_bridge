import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function bid(cards: string, calls: string[]) {
  const a = new AuctionState('West' as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return aiBidExplained(a.currentPlayer(), hand(cards), a);
}
// tests/test_gib.py: the user's board 12, 2026-11-19 (TWO_SUITER_FIT_GAME).
test('advancer bids game opposite unusual 2NT on fit and shortness', () => {
  const [call, why] = bid('QS 2S 2H QD 10D 9D 7D 4D KC QC JC 9C 6C', ['1D', '2NT', 'Pass']);
  expect(call).toBe('5C');
  expect(why).toContain('game values');
  // Three trumps never count.
  expect(bid('QS 2S 2H QD 10D 9D 7D 4D 3D 2D KC QC JC', ['1D', '2NT', 'Pass'])[0]).toBe('3C');
});
