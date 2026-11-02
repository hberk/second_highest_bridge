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
// The user's training auctions of 2026-11-01 (tests/test_gib.py), in the port.
test('bidding meanings match the Python engine', () => {
  const north = 'KS 9S 5S 3S 4H AD QD 5D 2D KC JC 5C 2C';
  expect(bid(north, ['1NT', 'Pass', '2D', 'Pass', '3H'], 'West')[0]).toBe('Pass');
  expect(bid(north, ['1NT', 'Pass', '2D', 'Pass', '2H'], 'West')[0]).toBe('X');
  expect(bid('AS JH 10H 9H 4H KD JD 8D 6D 3D JC 10C 9C', ['1S', 'Pass', '1NT', 'Pass', '2D', 'Pass'])).toEqual(['3D', '4+ ♦, 10-11 HCP. Invitational.']);
  expect(bid('KS QS JS 9S 6S 4S 4H AD KD 7D KC QC 10C', ['Pass', '1S', '1NT', 'Pass', '2C'], 'West')[0]).toBe('2S');
  expect(bid('KS QS JS 9S 6S 4H AD 7D KC QC JC 10C 9C', ['Pass', '1S', '1NT', 'Pass', '2C'], 'West')[0]).toBe('X');
  expect(bid('6S 2S 9H 8H 5H AD 2D AC QC JC 7C 6C 3C', ['1C', 'Pass', '1D', 'Pass', '1H'], 'East')).toEqual(['2C', '6+ ♣, 10-17 HCP. Natural.']);
  expect(bid('QS JS 10S 9S 4H 3H 2H QD 10D 8D 5D 3D 4C', ['1C', 'Pass', '1D', 'Pass', '1H', '2C', '2H'], 'East')[0]).toBe('Pass');
  expect(bid('QS JS 10S 9S 4H 3H 2H QD 10D 8D 5D 3D 4C', ['1C', '2C', 'Pass'], 'East')[0]).toBe('2S');
});
