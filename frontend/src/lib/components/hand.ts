import { SUITS, type Card, type Suit } from '../engine/card';

// Spades, hearts, diamonds, clubs: the order printed hand records use.
const DISPLAY_ORDER: Suit[] = ['S', 'H', 'D', 'C'];

// Trump first, then the colours alternate, majors before minors.
const TRUMP_FIRST: Record<Suit, Suit[]> = {
  S: ['S', 'H', 'C', 'D'],
  H: ['H', 'S', 'D', 'C'],
  D: ['D', 'S', 'H', 'C'],
  C: ['C', 'H', 'S', 'D'],
};

/** Display order, with trump pulled to the front (or, `trumpLast`, to the
 *  end), the colours alternating. */
export function suitOrder(trump: string | null, trumpLast = false): Suit[] {
  if (trump && (SUITS as readonly string[]).includes(trump)) {
    const order = [...TRUMP_FIRST[trump as Suit]];
    return trumpLast ? order.reverse() : order;
  }
  return [...DISPLAY_ORDER];
}

/** Cards bucketed by suit in display order, empty suits dropped. */
export function grouped(hand: Card[], trump: string | null, trumpLast = false): [Suit, Card[]][] {
  return suitOrder(trump, trumpLast)
    .map((s) => [s, hand.filter((c) => c.suit === s)] as [Suit, Card[]])
    .filter(([, cs]) => cs.length > 0);
}
