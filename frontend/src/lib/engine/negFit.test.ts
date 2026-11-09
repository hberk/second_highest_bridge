import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function bid(cards: string, calls: string[]) {
  const a = new AuctionState('North' as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return aiBidExplained(a.currentPlayer(), hand(cards), a)[0];
}
// tests/test_gib.py: test_negative_doubler_and_opener_raise_the_longest_fit.
const c = ['1D', '1S', 'X', 'Pass', '2C', 'Pass'];
const m = ['1S', '2C', 'X', 'Pass', '2D', 'Pass'];
const pref = [...m, '2S', 'Pass'];
const CASES: [string, string[], string][] = [
  ['AS 8S KH JH 3H 2H KD 9D 4D 2D QC 5C 2C', c, '3D'],
  ['8S 4S KH JH 3H 2H AD 9D 4D AC 5C 3C 2C', c, '3C'],
  ['AS QS 8S KH JH 3H 2H KD 9D 4D QC 5C 2C', c, '2D'],
  ['KS 8S 4S KH JH 3H 2H AD 9D 4D QC 5C 2C', m, '3S'],
  ['KS 8S 4S AH KH 3H 2H AD 9D 4D QC 5C 2C', m, '4S'],
  ['AS KS QS 7S 5S AH 4H KD 4D 3D 2D 6C 2C', [...m, '3S', 'Pass'], '4S'],
  ['AS KS 9S 7S 5S QH 4H KD 4D 3D 2D 6C 2C', [...m, '3S', 'Pass'], 'Pass'],
  ['AS KS QS 7S 5S AH 4H AD KD 4D 3D 6C 2C', pref, '3S'],
  ['AS KS QS JS 7S 5S AH 4H AD KD 4D 6C 2C', pref, '4S'],
  ['AS KS QS 7S 5S AH 4H KD 4D 3D 2D 6C 2C', pref, 'Pass'],
  ['KS 8S 4S QH JH 3H 2H KD 9D 4D 6C 5C 2C', [...pref, '3S', 'Pass'], '4S'],
  ['9S 8S 4S QH JH 3H 2H KD 9D 4D 6C 5C 2C', [...pref, '3S', 'Pass'], 'Pass'],
  ['KS 7S AH 9H 4H AD KD QD 8D 3D KC QC 2C', [...c, '3D', 'Pass'], 'Pass'],
  ['KS 7S AH 9H 4H AD KD QD 8D 3D AC KC QC', [...c, '2D', 'Pass'], 'Pass'],
];
test('negative doubler and opener raise the longest fit after the preference spot', () => {
  for (const [cards, cs, want] of CASES) expect([cs.join(' '), cards, bid(cards, cs)]).toEqual([cs.join(' '), cards, want]);
});
