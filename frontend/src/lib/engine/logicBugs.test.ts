import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function bid(cards: string, dealer: string, calls: string[]) {
  const a = new AuctionState(dealer as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  const [call, why] = aiBidExplained(a.currentPlayer(), hand(cards), a);
  return { call, why };
}
// tests/test_gib.py: the five logic bugs of the Nov 11 robot review.
test('a natural overcall over Stayman is not Cappelletti', () => {
  const east = '10C 8C 7C 6C 4C AD 6D 5D 4H QS 8S 5S 4S';
  const r = bid(east, 'East', ['Pass', 'Pass', 'Pass', '1NT', 'Pass', '2C', '2H', 'Pass']);
  expect(r.call).not.toBe('2NT');
  expect(bid(east, 'South', ['1NT', '2H', 'Pass']).call).toBe('2NT');
});
test('six cards after a transfer: 3S, never "5"', () => {
  const east = 'QC 8C 4C 9D 5D 10H 3H KS QS 8S 5S 4S 2S';
  const r = bid(east, 'South', ['Pass', '1NT', 'Pass', '2H', 'Pass', '2S', 'Pass']);
  expect(r.call).toBe('3S');
  expect(r.why).toContain('6+');
});
test('opener passes back after responder passed their double', () => {
  const north = 'AC 4C 2C AD KD 8D 2D KH 6H 2H KS 10S 9S';
  expect(bid(north, 'North', ['1NT', 'Pass', '2D', 'Pass', '2H', 'Pass', 'Pass', 'X']).call).toBe('Pass');
});
test('the Lebensohl relay after a runout is answered with 3C', () => {
  const west = 'AC 8C 2C 9D 7D 6D 4D AH KH 9H 3H AS 4S';
  const r = bid(west, 'East', ['Pass', 'Pass', '1NT', 'X', 'Pass', '2H', 'Pass', '2S', '2NT', 'Pass']);
  expect(r.call).toBe('3C');
});
test('a transfer doubled after our 1NT overcall is completed or bid', () => {
  const opener = 'AC QC 9C JD 9D 6D 3D AH 10H 7H KS QS 7S';
  expect(bid(opener, 'East', ['Pass', '1H', '1NT', 'Pass', '2H', 'X']).call).toBe('2S');
  const west = 'JC 6C 5C 4C 2C AD 2D 7H QS JS 8S 4S 3S';
  expect(bid(west, 'South', ['Pass', 'Pass', '1H', '1NT', 'Pass', '2H', 'X', 'Pass', 'Pass']).call).toBe('2S');
});
