import { test, expect } from 'vitest';
import { AuctionState } from './auction';
import { aiBidExplained } from './ai';
import { card } from './card';
function hand(t: string) { return t.split(' ').map((x) => card(x.slice(-1) as any, x.slice(0, -1) as any)); }
function bid(dealer: string, cards: string, calls: string[]) {
  const a = new AuctionState(dealer as any, 'None' as any);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return aiBidExplained(a.currentPlayer(), hand(cards), a);
}
// tests/test_bidding_rebids.py: the user's board, 2026-11-22 (TWO_SUITER_ALONE, ARTIFICIAL_READ).
test('the Michaels bidder comes alive with 6-5, partner places it', () => {
  const after = ['1H', '2H', '3H', 'Pass', 'Pass'];
  expect(bid('East', 'AS JS 6S 3S 2S 10H AC QC 10C 8C 6C 5C 3C', after))
    .toEqual(['4C', '6+ ♣, extra shape. Competing.']);
  expect(bid('East', 'AS JS 6S 3S 2S 10H 9H 4H AC QC 10C 8C 6C', after)[0]).toBe('Pass');
  const rebid = [...after, '4C', 'Pass'];
  expect(bid('East', 'QS 10S QH 9H 3H QD 10D 9D 8D 2D JC 9C 4C', rebid))
    .toEqual(['Pass', "Partner's rebid stands."]);
  expect(bid('East', 'KS QS 5S 4S 9H 3H 2H QD 9D 8D 2D JC 9C', rebid)[0]).toBe('4S');
});

test('artificial bids are read for what they show', () => {
  // Drury is not clubs.
  expect(bid('North', 'QS 6S AH KH JH 9H 2H 10D 8D AC JC 5C 2C',
    ['Pass', 'Pass', '1H', 'Pass', '2C', '2S'])[0]).not.toBe('3C');
  // Cappelletti: a minimum lets partner's choice stand, extras invite.
  const capp = ['1NT', '2D', 'Pass', '2H', 'Pass'];
  expect(bid('West', 'AS JS 5S 4S KH JH 9H 5H 3H 8D 6D KC 7C', capp)[1]).toBe("Partner's choice stands.");
  expect(bid('West', 'AS QS 5S 4S KH QH JH 5H 3H KD 6D AC 7C', capp)[0]).toBe('3H');
  // Partner's cue is never passed.
  expect(bid('West', '9S 5S AH 4H 2H KD 6D AC KC QC 10C 8C 3C',
    ['1C', '2S', 'Pass', 'Pass', '3C', 'Pass', '3S', 'Pass'])[0]).not.toBe('Pass');
});
