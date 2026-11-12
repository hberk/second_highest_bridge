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
// tests/test_gib.py: FIT_OVER_3NT and its guards (the Opus review, 2026-11-12).
test('bid the fit, not 3NT, in a 2/1 auction', () => {
  const west = '7S 4S 3S AH 5H KD 10D 8D 7D AC KC 4C 2C';
  expect(bid(west, 'East', ['1D', 'Pass', '2C', 'Pass', '2D', 'Pass']).call).toBe('3D');
});
test('New Minor Forcing shows no length in the minor', () => {
  const west = 'JS 7S 6S KH 10H KD 8D 6D 2D AC KC 10C 8C';
  expect(bid(west, 'West', ['1D', 'Pass', '1H', 'Pass', '1NT', 'Pass', '2C', 'Pass']).call).toBe('3NT');
  const w2 = 'KS 7S 9H 8H QD JD 8D 2D AC QC JC 8C 3C';
  expect(bid(w2, 'West', ['1C', 'Pass', '1H', 'Pass', '1NT', 'Pass', '2D', 'Pass']).call).toBe('3NT');
});
test('the fit rule never lands on Stayman over 1NT', () => {
  const south = 'JS KH QH 2H JD KC JC 9C 7C 5C 4C 3C 2C';
  expect(bid(south, 'North', ['1NT', 'Pass']).call).toBe('3NT');
});
