import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card, type Seat } from './card';
import { shownSuit } from './gib';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function bid(cards: string, calls: string[], dealer: Seat = 'North') {
  const a = new AuctionState(dealer, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return aiBidExplained(a.currentPlayer(), hand(cards), a);
}
// tests/test_gib.py: fresh deal 269, seed 7M (the PR #75 review).
test('after a positive answer to 2C the 2NT rebid has no transfers', () => {
  expect(shownSuit(['2C', '2H', '2NT', '3H'], 3)).toBe('H');
  expect(shownSuit(['2C', '2D', '2NT', '3H'], 3)).toBe('S');
  const calls = ['2C', 'Pass', '2H', 'Pass', '2NT', 'Pass'];
  expect(bid('2S AH KH 10H 9H 8H 2H JD 8D 7D JC 10C 2C', calls, 'South')[0]).toBe('4H');
  expect(bid('AS KS QS 8S 6S QH JH AD KD 9D 4D KC 8C', [...calls, '3H', 'Pass'], 'South')[0]).not.toBe('4S');
});
// tests/test_gib.py: the user's board 2026-11-21 (RAISE_PREEMPT_STRONG).
test('a strong hand raises partner\'s weak two over their overcall', () => {
  expect(bid('9S 3S AH KH JH KD JD 10D 9D 8D KC 7C 3C', ['2H', '2S'])).toEqual(['3H', '3+ ♥, competitive.']);
});
