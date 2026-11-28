import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained, PENALTY_FIT_JP } from './ai';
import { card } from './card';
import { GAME_PENALTY_X, gameValuesShown } from './gib';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
// tests/test_gib.py: the user's training deal 374, 2026-11-22 (GAME_PENALTY_X, PENALTY_FIT_JP).
test('a constructive game is told from a pre-emptive raise', () => {
  expect(gameValuesShown([['West', '1H'], ['East', '2H'], ['West', '3S'], ['East', '4H']], '4H')).toBe(true);
  expect(gameValuesShown([['West', '2H'], ['East', '4H']], '4H')).toBe(false);
  expect(gameValuesShown([['West', '1H'], ['East', '4H']], '4H')).toBe(false);
  expect(gameValuesShown([['West', '3H'], ['East', '4H']], '4H')).toBe(false);
  expect(gameValuesShown([['West', '1H'], ['East', '2H']], '2H')).toBe(false);
});
test('North doubles their 4H for penalty on deal 374', () => {
  expect(GAME_PENALTY_X).toBe(true);
  expect(PENALTY_FIT_JP).toBe(4);
  const a = new AuctionState('West' as any, 'Both' as any);
  for (const c of ['1H', 'Pass', '2H', 'Pass', '3S', 'Pass', '4H', 'Pass', 'Pass']) a.applyCall(a.currentPlayer(), c);
  expect(aiBidExplained('North', hand('KS 8S 6S QH 9H 7H 4H 10D 2D 10C 8C 6C 2C'), a)).toEqual(['X', 'Penalty: 4+ ♥.']);
});
