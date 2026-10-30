import { SUITS, type Card, type Suit } from '../engine/card';

// Spades, hearts, diamonds, clubs: the order printed hand records use.
const DISPLAY_ORDER: Suit[] = ['S', 'H', 'D', 'C'];

/** Display order, with trump pulled to the front (or, `trumpLast`, to the
 *  end). The other suits keep their order, so the colours still alternate. */
export function suitOrder(trump: string | null, trumpLast = false): Suit[] {
  if (trump && (SUITS as readonly string[]).includes(trump)) {
    const rest = DISPLAY_ORDER.filter((s) => s !== trump);
    return trumpLast ? [...rest, trump as Suit] : [trump as Suit, ...rest];
  }
  return [...DISPLAY_ORDER];
}

/** Cards bucketed by suit in display order, empty suits dropped. */
export function grouped(hand: Card[], trump: string | null, trumpLast = false): [Suit, Card[]][] {
  return suitOrder(trump, trumpLast)
    .map((s) => [s, hand.filter((c) => c.suit === s)] as [Suit, Card[]])
    .filter(([, cs]) => cs.length > 0);
}
