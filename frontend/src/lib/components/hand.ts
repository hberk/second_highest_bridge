import { SUITS, type Card, type Suit } from '../engine/card';

// Spades, hearts, diamonds, clubs: the order printed hand records use.
const DISPLAY_ORDER: Suit[] = ['S', 'H', 'D', 'C'];

/** Display order, with trump pulled to the front when the player asked for it. */
export function suitOrder(trump: string | null): Suit[] {
  if (trump && (SUITS as readonly string[]).includes(trump)) {
    return [trump as Suit, ...DISPLAY_ORDER.filter((s) => s !== trump)];
  }
  return [...DISPLAY_ORDER];
}

/** Cards bucketed by suit in display order, empty suits dropped. */
export function grouped(hand: Card[], trump: string | null): [Suit, Card[]][] {
  return suitOrder(trump)
    .map((s) => [s, hand.filter((c) => c.suit === s)] as [Suit, Card[]])
    .filter(([, cs]) => cs.length > 0);
}
