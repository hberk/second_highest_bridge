import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function bid(cards: string, calls: string[]) {
  const a = new AuctionState('North' as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return aiBidExplained(a.currentPlayer(), hand(cards), a);
}
// tests/test_gib.py: test_opener_bids_game_over_a_preemptive_raise_with_judgement_points.
test('opener bids game over a pre-emptive raise on 16+ judgement points', () => {
  expect(bid('QS JS 9S KH QH 10H 8H 6H 10D 8D KC QC 2C', ['1H', '2D', '3H', 'Pass'])).toEqual(['4H', 'To play, ♥.']);
  expect(bid('AS 10S 8S KH QH JH 8H 5H AD 10D 10C 6C 2C', ['1H', '2D', '3H', 'Pass'])[0]).toBe('Pass');
  expect(bid('KS 9S KH 10H 5H 2H QD 4D 3D AC QC 9C 7C', ['1C', '2S', '3C', 'Pass'])).toEqual(['3NT', 'To play.']);
});
