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

// tests/test_gib.py: test_opener_reopens_and_the_passed_responder_answers.
test('opener reopens and the passed responder answers', () => {
  expect(bid('JS AH KH 10H 5H AD JD 7D 2D QC 9C 8C 6C', ['1D', 'Pass', 'Pass', '1S'])).toEqual(['X', 'Reopening: short in ♠, 14+ HCP.']);
  expect(bid('KS QS KH JH 4H 3H 2H JD AC KC 8C 7C 3C', ['1H', 'Pass', 'Pass', '1S'])).toEqual(['2C', '5+ ♥, 5+ ♣, 14+ HCP.']);
  expect(bid('KS 6S 5S JH 10H 9H 4H QD 9D 6D 8C 6C 5C', ['1S', 'Pass', 'Pass', '2D', 'X', 'Pass'])).toEqual(['2S', '3+ ♠ support, answering the double.']);
  expect(bid('QS 9S 8S 2S 5H 4H 3H 2H QD 8D 3D 8C 6C', ['1D', 'Pass', 'Pass', '2C', 'X', 'Pass'])).toEqual(['2H', 'Longest suit other than theirs, ♥. Answering the double.']);
});

// tests/test_gib.py: test_opener_rebids_over_a_one_level_overcall_and_responder_follows.
test('opener rebids over a one-level overcall and responder follows', () => {
  expect(bid('AS 4S 3S JH 4H AD KD 7D 5D 3D JC 3C 2C', ['1D', 'Pass', '1H', '1S'])).toEqual(['1NT', '12-14 HCP, balanced, a stopper in their suit.']);
  expect(bid('KS 9S 3S AH AD QD 10D 5D 3D KC 10C 7C 6C', ['1D', 'Pass', '1H', '1S'])).toEqual(['2C', '4+ ♣, 16+ HCP.']);
  expect(bid('7S 4S AH 4H AD KD 9D 8D KC QC 9C 4C 2C', ['1C', 'Pass', '1H', '1S'])[0]).toBe('Pass');
  expect(bid('KS QS 3S 8H 4H 2H QD JD 6D 5D 3D 2D JC', ['1C', 'Pass', '1D', '1H', '1NT', 'Pass'])).toEqual(['2D', '6+ ♦. Rebidding my own suit.']);
  expect(bid('2S KH JH 10H 9H 5H AD QD 10D 3D JC 10C 4C', ['1D', 'Pass', '1H', '1S', '1NT', 'Pass'])).toEqual(['2D', '5+ ♥, 4+ ♦.']);
});
