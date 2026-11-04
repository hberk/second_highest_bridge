import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function bid(h: string, calls: string[], dealer = 'North') {
  const a = new AuctionState(dealer as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return aiBidExplained(a.currentPlayer(), hand(h), a);
}
// tests/test_gib.py: the cuebids over their Unusual 2NT and our minors over
// their weak two (2026-11-04), call and alert as the Python engine gives them.
test('cuebids over their Unusual 2NT are answered as in the Python engine', () => {
  const north = 'AS JS 5S 4S 3S JH 4H 2H AD 7D 4D KC 10C';
  expect(bid(north, ['Pass', '1S', '2NT', '3C', 'Pass'], 'West')).toEqual(['3S', 'Minimum, ♠.']);
  expect(bid(north, ['Pass', '1S', '2NT', '3D', 'Pass'], 'West')).toEqual(['4H', '3+ ♥. To play.']);
  expect(bid('KS 10S 8S AH QH 10H 9H 8H AD JD 5D 9C 2C',
    ['Pass', '1S', '2NT', '3C', 'Pass', '3S', 'Pass'], 'West')).toEqual(['4S', 'To play, ♠.']);
  expect(bid('AS KH 7H 6H 2H JD 6D QC JC 10C 9C 6C 5C', ['1C', '2NT', '3H', 'Pass'], 'East')).toEqual(['3NT', 'To play.']);
});

test('advancer picks a minor after our minors over a weak two, as in the Python engine', () => {
  const north = '8S 6S 5S KH QH 9H 6H QD JD 9D 5D 2D 10C';
  for (const overcall of ['4S', '4NT']) {
    expect(bid(north, ['Pass', '2S', overcall, 'Pass'])).toEqual(['5D', "Choosing between partner's two suits, ♦."]);
  }
});
