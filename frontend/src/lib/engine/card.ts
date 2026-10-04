// Port of card.py. Cards are plain values: compare with sameCard, never ===.

export type Suit = 'C' | 'D' | 'H' | 'S';
export type Strain = Suit | 'NT';
export type Seat = 'North' | 'East' | 'South' | 'West';
export type Side = 'N/S' | 'E/W';
export type Vulnerability = 'None' | 'N/S' | 'E/W' | 'Both';

export interface Card {
  readonly suit: Suit;
  readonly rank: string;
}

export const SUITS: readonly Suit[] = ['C', 'D', 'H', 'S']; // low -> high
export const SUIT_SYMBOLS: Record<Suit, string> = { C: '♣', D: '♦', H: '♥', S: '♠' };
export const SUIT_NAMES: Record<Suit, string> = {
  C: 'Clubs', D: 'Diamonds', H: 'Hearts', S: 'Spades',
};
export const RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
export const RANK_VALUE: Record<string, number> = Object.fromEntries(
  RANKS.map((r, i) => [r, i]),
);

export const STRAINS: readonly Strain[] = ['C', 'D', 'H', 'S', 'NT'];
export const STRAIN_SYMBOLS: Record<Strain, string> = { ...SUIT_SYMBOLS, NT: 'NT' };
export const STRAIN_NAMES: Record<Strain, string> = { ...SUIT_NAMES, NT: 'No-Trump' };
export const LEVELS = [1, 2, 3, 4, 5, 6, 7];
export const VULNERABILITIES: readonly Vulnerability[] = ['None', 'N/S', 'E/W', 'Both'];

export const card = (suit: Suit, rank: string): Card => ({ suit, rank });
export const value = (c: Card): number => RANK_VALUE[c.rank];
export const sameCard = (a: Card, b: Card): boolean => a.suit === b.suit && a.rank === b.rank;
/** Stable string identity, for Sets and Maps. */
export const cardKey = (c: Card): string => `${c.rank}${c.suit}`;
export const cardText = (c: Card): string => `${c.rank}${SUIT_SYMBOLS[c.suit]}`;

/** '10H' -> 10 of hearts; the format data/solved_deals.json stores. */
export function parseCard(token: string): Card {
  return card(token.slice(-1) as Suit, token.slice(0, -1));
}

export function parseHand(text: string): Card[] {
  return text.split(/\s+/).filter(Boolean).map(parseCard);
}

export function removeCard(hand: Card[], c: Card): void {
  const i = hand.findIndex((h) => sameCard(h, c));
  if (i < 0) throw new Error(`${cardKey(c)} not in hand`);
  hand.splice(i, 1);
}

export function bidIndex(level: number, strain: Strain): number {
  return (level - 1) * 5 + STRAINS.indexOf(strain);
}

/** '1C', '3NT' -> [level, strain]; null for Pass/X/XX or anything invalid. */
export function parseBid(call: string): [number, Strain] | null {
  if (!call || call === 'Pass' || call === 'X' || call === 'XX') return null;
  if (call.length < 2 || !/^\d/.test(call)) return null;
  const level = Number(call[0]);
  const strain = call.slice(1) as Strain;
  if (!LEVELS.includes(level) || !STRAINS.includes(strain)) return null;
  return [level, strain];
}

/** Sorted the way card.deal() sorts: spades first, high to low in each suit. */
export function sortHand(hand: Card[]): Card[] {
  return [...hand].sort(
    (a, b) => SUITS.indexOf(b.suit) - SUITS.indexOf(a.suit) || value(b) - value(a),
  );
}

export function deal(random: () => number = Math.random): Record<Seat, Card[]> {
  const deck = SUITS.flatMap((s) => RANKS.map((r) => card(s, r)));
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  const seats: Seat[] = ['North', 'East', 'South', 'West'];
  return Object.fromEntries(
    seats.map((p, i) => [p, sortHand(deck.slice(i * 13, (i + 1) * 13))]),
  ) as Record<Seat, Card[]>;
}

/** Python's max(items, key=...) over tuple keys: first maximal item wins ties. */
export function maxBy<T>(items: Iterable<T>, key: (t: T) => number[]): T {
  let best: T | undefined;
  let bestKey: number[] | undefined;
  for (const item of items) {
    const k = key(item);
    if (bestKey === undefined || compareTuples(k, bestKey) > 0) {
      best = item;
      bestKey = k;
    }
  }
  if (bestKey === undefined) throw new Error('maxBy of empty sequence');
  return best as T;
}

/** Python's min(items, key=...): first minimal item wins ties. */
export function minBy<T>(items: Iterable<T>, key: (t: T) => number[]): T {
  return maxBy(items, (t) => key(t).map((n) => -n));
}

function compareTuples(a: number[], b: number[]): number {
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return a.length - b.length;
}
