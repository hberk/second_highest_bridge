import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function bid(h: string, calls: string[], dealer = 'West') {
  const a = new AuctionState(dealer as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return aiBidExplained(a.currentPlayer(), hand(h), a);
}
// tests/test_gib.py: bridgebum's defense to Michaels and the Unusual 2NT
// (2026-11-28), call and alert as the Python engine gives them.
test('the double of a two-suiter shows values, as in the Python engine', () => {
  const south = '2S KH JH 9H 4H AD QD 6D 3D KC 8C 5C 2C';
  expect(bid(south, ['Pass', '1S', '2S'])).toEqual(['X', 'Values, penalty interest in their suits, 2 or fewer ♠.']);
  expect(bid(south, ['Pass', '1S', '2S', 'X', '3H', 'Pass', 'Pass'])).toEqual(['X', 'Penalty: 3+ ♥.']);
  expect(bid('AS KS JS 9S 4S QH 10H 9H 5H KD 6D 3D 8C', ['Pass', '1S', '2S', 'X', '3H'])).toEqual(['X', 'Penalty: 4+ ♥.']);
  expect(bid('AS QS KH JH AD QD 6D 3D KC 8C 5C 2C 3C', ['Pass', '1H', '2H'])[0]).toBe('X');
  expect(bid('AS QS 3S KH JH 2H AD QD 6D KC 8C 5C 2C', ['Pass', '1C', '2C'])).toEqual(['X', 'Values, penalty interest in their suits.']);
});

test('the cuebids over a two-suiter, as in the Python engine', () => {
  expect(bid('2S 3S QS KH JH AD QD 6D 3D KC 8C 5C 2C', ['Pass', '1S', '2S'])).toEqual(
    ['3H', 'Cuebid: 3+ ♠, 10+ HCP. Limit raise or better. Artificial.']);
  expect(bid('2S 3S QS KH JH AD QD 6D 3D KC 8C 5C 2C', ['Pass', '1D', '2D'])[0]).toBe('2S');
  expect(bid('KS QS 10S 4S 3S 4H AD QD 6D 3D KC 8C 5C', ['Pass', '1H', '2NT'])).toEqual(
    ['3C', 'Cuebid: 5+ ♠, 12+ HCP, game forcing. Artificial.']);
  expect(bid('KS QS 10S 4H 3H 2H AD QD 6D 3D KC 8C 5C', ['Pass', '1H', '2NT'])[0]).toBe('3D');
  expect(bid('AH KH JH 9H 4H AS 5S KD 6D 3D 8C 5C 2C', ['Pass', '1H', '2NT', '3D', 'Pass'])).toEqual(['3H', 'Minimum, ♥.']);
});
