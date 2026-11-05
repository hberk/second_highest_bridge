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
// tests/test_gib.py: test_a_doubled_transfer_is_still_a_transfer (the review of PR #65).
const CASES: [string, string[], string, string][] = [
  ['West', ['1NT', '2C', '2H', 'X'], 'KS 8S 4S KH JH 4H QD 10D 7D AC 7C 5C 4C', '2S'],
  ['West', ['1NT', '2C', '2H', 'X'], 'KS 8S KH JH 4H 3H QD 10D 7D AC 7C 5C 4C', 'Pass'],
  ['West', ['1NT', '2C', '2H', 'X', 'Pass', 'Pass'], 'JS 10S 7S 6S 2S 9H 3H 8D 4D 2D KC 10C 9C', '2S'],
  ['West', ['1NT', '2C', '2H', '3C'], 'KS 8S 4S KH JH 4H QD 10D 7D AC 7C 5C 4C', '3S'],
  ['West', ['1NT', '2C', '2D', 'X', 'Pass', 'Pass'], 'JS 10S 7S 6H 2H 9H 3H 8H 4D 2D KC 10C 9C', '2H'],
  ['South', ['1NT', 'Pass', 'Pass', 'X', 'Pass', '2H', 'X', 'Pass', 'Pass'], '10S 9S 6S 5S 4S 3S 7H 2H JD 9D 8C 5C 4C', '2S'],
  ['North', ['1NT', 'X', 'Pass', '2H', 'X', 'Pass', 'Pass'], 'AS 10S 6S 5S 4S 3S 7H 2H JD 9D QC 5C 4C', '2S'],
];
test('a doubled or overcalled systems-on transfer is still a transfer', () => {
  for (const [dealer, calls, cards, want] of CASES) {
    const a = after(calls, dealer);
    const [call, why] = aiBidExplained(a.currentPlayer(), hand(cards), a);
    expect([calls.join(' '), call, why]).toEqual([calls.join(' '), want, expect.any(String)]);
  }
});
