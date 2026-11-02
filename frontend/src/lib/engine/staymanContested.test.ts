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
// tests/test_gib.py: test_game_after_they_overcall_stayman and the third-seat
// weak jump overcall (review of the combined PR, 2026-11-02), in the port.
test('game after they overcall Stayman matches the Python engine', () => {
  expect(bid('AS KS 3S AH QH 2H KD QD 5D KC JC 4C 3C', ['2NT', 'Pass', '3C', '3D'])).toEqual(['3NT', '♦ stopper, no major to show.']);
  expect(bid('AS KS 3S AH QH 2H 5D 4D 3D AC KC QC 4C', ['2NT', 'Pass', '3C', '3D'])[0]).toBe('Pass');
  const after2 = ['2NT', 'Pass', '3C', '3D', 'Pass', 'Pass'];
  expect(bid('QS JS 5S 4S KH JH 4H 3H 7D 6D QC 5C 2C', after2)[0]).toBe('X');
  expect(bid('QS JS 5S 4S KH JH 4H 3H KD 6D QC 5C 2C', after2)).toEqual(['3NT', 'To play.']);
  const after1 = ['1NT', 'Pass', '2C', '2D', 'Pass', 'Pass'];
  expect(bid('KS QS 5S 4S KH QH 4H 3H 7D 6D KC QC 2C', after1)).toEqual(['3NT', 'To play.']);
  expect(bid('KS JS 5S 4S AH 3H KD JD 9D 6D QC 5C 2C', after1)).toEqual(['X', 'Penalty: values, no major fit.']);
  expect(bid('AS 9S 4S KH QH 3H KD QD 4D 2D AC 7C 3C', ['1NT', 'Pass', '2C', '2D'])).toEqual(['X', 'Penalty: 4+ ♦.']);
  expect(bid('AS KS 3S QH 3H 2H QD 5D 4D AC JC 4C 3C', ['1NT', 'Pass', '2C', '2D', 'Pass', 'Pass', 'X', 'Pass'])[0]).toBe('Pass');
});

test('a weak jump overcall over a third-seat opening is a pre-empt', () => {
  expect(bid('5S KH QH JH 10H 9H 6H QD 7D 6D 8C 6C 5C', ['Pass', 'Pass', '1C', '2H', 'Pass', '3H', '3S'])).toEqual(['Pass', 'Pre-empted already.']);
});
