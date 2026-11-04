import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function after(calls: string[], dealer = 'South') {
  const a = new AuctionState(dealer as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return a;
}
// tests/test_gib.py: test_partner_reads_our_bid_in_their_transfer_suit_as_natural.
test('our first bid in their transfer suit is natural for partner too', () => {
  const a = after(['1NT', 'Pass', '2D', 'Pass', '2H', 'Pass', 'Pass', '3D', 'Pass'], 'North');
  const [call, why] = aiBidExplained('East', hand('AS KS QS 7S 4S 3S KH 5H 3D AC QC 7C 2C'), a);
  expect(call).toBe('4S');
  expect(why).not.toContain('cuebid');
});
