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
// tests/test_gib.py: test_responsive_game_needs_a_responsive_double (the review of PR #66).
const SOUTH = 'KS 8S 5S AH QH 7H 2H QD 8D 7D JC 9C 2C';
const CASES: [string, string[], string, string][] = [
  ['West', ['1H', 'X', '2H', 'X', 'Pass', '3H', 'Pass'], SOUTH, 'Pass'],
  ['West', ['1D', 'X', '1NT', 'X', 'Pass', '2H', 'Pass'], SOUTH, 'Pass'],
  ['West', ['1C', 'X', '1H', 'Pass', '2H', 'Pass', 'Pass', 'X', 'Pass', '2S', 'Pass'],
    'KS QS 5S 2S QH 7H 2H QD 8D 7D AC 9C 2C', 'Pass'],
  ['North', ['1S', 'Pass', 'Pass', 'X', '2S', 'X', 'Pass', '3H', '3S'],
    'JS 8S 5S AH KH QH 7H QD 8D 7D 2D JC 9C', '4H'],
];
test('game after a responsive double only after a real one, in a suit they did not bid', () => {
  for (const [dealer, calls, cards, want] of CASES) {
    const a = after(calls, dealer);
    const [call] = aiBidExplained(a.currentPlayer(), hand(cards), a);
    expect([calls.join(' '), call]).toEqual([calls.join(' '), want]);
  }
});
