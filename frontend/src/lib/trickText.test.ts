// The line under the trick: who is winning it, and why.
import { describe, expect, it } from 'vitest';
import { card, type Seat, type Suit } from './engine/card';
import type { Play } from './engine/auction';
import { trickTaken, winningSoFar } from './trickText';

const p = (seat: Seat, suit: Suit, rank: string): Play => [seat, card(suit, rank)];

describe('winningSoFar', () => {
  it('names the second-highest of the counting suit', () => {
    const trick = [p('West', 'H', 'Q'), p('North', 'H', '4'), p('East', 'H', 'J')];
    expect(winningSoFar(trick, 'S')).toBe("East's J♥ is winning: second-highest of Q J 4.");
  });

  it('says when a card is the only one of its suit', () => {
    expect(winningSoFar([p('West', 'C', '6')], 'NT')).toBe("West's 6♣ is winning: the only club so far.");
  });

  it('counts trumps once anyone ruffs', () => {
    const trick = [p('West', 'S', 'A'), p('North', 'S', '5'), p('East', 'H', '2')];
    expect(winningSoFar(trick, 'H')).toBe("East's 2♥ is winning: the only trump so far.");
  });

  it('speaks to you about your own card', () => {
    const trick = [p('South', 'D', 'K'), p('West', 'D', 'A')];
    expect(winningSoFar(trick, 'NT')).toBe('Your K♦ is winning: second-highest of A K.');
  });

  it('speaks to you from whatever seat you sit in', () => {
    const trick = [p('South', 'D', 'K'), p('West', 'D', 'A')];
    expect(winningSoFar(trick, 'NT', 'East')).toBe("South's K♦ is winning: second-highest of A K.");
    const won = [p('South', 'D', '5'), p('West', 'D', 'A'), p('North', 'D', '2'), p('East', 'D', 'K')];
    expect(trickTaken(won, 'NT', 'East', 2, 'East')).toBe('You take trick 2 with the K♦, second-highest of A K 5 2.');
  });
});

describe('trickTaken', () => {
  it('says who took the trick and with what', () => {
    const trick = [p('West', 'S', '7'), p('North', 'S', 'K'), p('East', 'S', '3'), p('South', 'S', 'Q')];
    expect(trickTaken(trick, 'NT', 'South', 3)).toBe('You take trick 3 with the Q♠, second-highest of K Q 7 3.');
  });

  it('explains a lone ruff', () => {
    const trick = [p('West', 'S', 'A'), p('North', 'S', '5'), p('East', 'H', '2'), p('South', 'S', 'K')];
    expect(trickTaken(trick, 'H', 'East', 1)).toBe('East takes trick 1 with the 2♥, the only trump played.');
  });
});
