import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function bid(cards: string, calls: string[]) {
  const a = new AuctionState('East' as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return aiBidExplained(a.currentPlayer(), hand(cards), a);
}
// tests/test_bidding_rebids.py: the user's board, 2026-11-12.
const before = ['Pass', '1D', '1H', '1S', '4H'];
test('opener new suit shows two suits; partner goes back to the opening suit', () => {
  expect(bid('9S 5S 5H AD 9D 2D AC KC QC 10C 9C 8C 3C', before))
    .toEqual(['5C', 'Two suits: 5+ ♣, ♦ as long or longer.']);
  const after = [...before, '5C', 'Pass'];
  const [call, why] = bid('AS QS JS 4S 3S 2S 10H 7H AD 8D 5D 9C 5C', after);
  expect(call).toBe('5D');
  expect(why).toContain('Preference');
  expect(bid('AS QS JS 4S 3S 2S 10H 7H 8D 5D 9C 5C 2C', after)[0]).not.toBe('5D');
});
