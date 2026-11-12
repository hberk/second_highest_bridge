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
// tests/test_gib.py: test_no_part_score_penalty_double_after_a_strong_opening.
test('no part-score penalty double after a 2NT opening, a game still doubled', () => {
  const strong = { 0: '20-21 HCP, balanced.' };
  const part = after(['2NT', 'Pass', '3C', 'Pass', '3S']);
  expect(aiBidExplained('West', hand('KS 9S 8S 4S JH 10H 6H 5H KD 10D 3D 4C 2C'), part, strong)[0]).toBe('Pass');
  const game = after(['2NT', 'Pass', '3C', 'Pass', '3S', 'Pass', '4S']);
  expect(aiBidExplained('West', hand('KS QS 9S 8S 4S 10H 6H 5H KD 10D 3D 4C 2C'), game, strong)[0]).toBe('X');
});
// tests/test_gib.py: test_four_trump_penalty_double_needs_no_fit_shown.
test('four trumps do not double once both opponents have named the suit', () => {
  const b = after(['1S', '3D', '4S', 'Pass', 'Pass'], 'North');
  expect(aiBidExplained('East', hand('QS JS 10S 4S AH 5H 3H KD 9D 4D 5C 3C 2C'), b, {})[0]).toBe('Pass');
});
