import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function after(calls: string[], dealer = 'North') {
  const a = new AuctionState(dealer as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return a;
}
// tests/test_gib.py: test_game_over_a_takeout_double_never_in_their_suit (the review of PR #68).
const CALLS = ['2H', 'Pass', '3D', 'X', 'Pass'];
test('game over a takeout double is never in a suit they bid', () => {
  const hearts = after(CALLS);
  const [h] = aiBidExplained(hearts.currentPlayer(), hand('AH KH QH JH 9H 4S 3S 2S KC 3C 2C 5D 4D'), hearts);
  expect(h.slice(1)).not.toBe('H');
  const spades = after(CALLS);
  const [s] = aiBidExplained(spades.currentPlayer(), hand('4H 3H AS KS QS JS 9S 2C KC 3C 7C 5D 4D'), spades);
  expect(s).toBe('4S');
});
