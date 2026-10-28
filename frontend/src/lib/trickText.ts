import { rankText } from './components/format';
// The line under the trick, which says who is winning it and why. The rule
// is the whole game here, so the table spells it out on every trick.
import { SUIT_NAMES, SUIT_SYMBOLS, SUITS, value, type Card, type Seat } from './engine/card';
import { resolveTrick, type Play } from './engine/auction';

const cardText = (c: Card) => `${rankText(c.rank)}${SUIT_SYMBOLS[c.suit]}`;
const whose = (p: Seat) => (p === 'South' ? 'Your' : `${p}'s`);

/** The suit that decides the trick so far, and its cards high to low. */
function counting(trick: Play[], trump: string | null): { word: string; cards: Card[] } {
  const isTrump = (SUITS as readonly string[]).includes(trump ?? '');
  const ruffed = isTrump && trick.some(([, c]) => c.suit === trump);
  const suit = ruffed ? trump! : trick[0][1].suit;
  const cards = trick.map(([, c]) => c).filter((c) => c.suit === suit).sort((a, b) => value(b) - value(a));
  const word = ruffed ? 'trump' : SUIT_NAMES[suit as Card['suit']].toLowerCase().replace(/s$/, '');
  return { word, cards };
}

/** "East's J♥ is winning: second-highest of Q J 4." The rules oracle picks
 *  the winner; this only explains it. */
export function winningSoFar(trick: Play[], trump: string | null): string {
  if (!trick.length) return '';
  const winner = resolveTrick(trick, trump);
  const card = trick.find(([p]) => p === winner)![1];
  const { word, cards } = counting(trick, trump);
  if (cards.length === 1) return `${whose(winner)} ${cardText(card)} is winning: the only ${word} so far.`;
  return `${whose(winner)} ${cardText(card)} is winning: second-highest of ${cards.map((c) => rankText(c.rank)).join(' ')}.`;
}

/** "East takes trick 5 with the J♥, second-highest of Q J 4." */
export function trickTaken(trick: Play[], trump: string | null, winner: Seat, num: number): string {
  const card = trick.find(([p]) => p === winner)![1];
  const { word, cards } = counting(trick, trump);
  const who = winner === 'South' ? 'You take' : `${winner} takes`;
  if (cards.length === 1) return `${who} trick ${num} with the ${cardText(card)}, the only ${word} played.`;
  return `${who} trick ${num} with the ${cardText(card)}, second-highest of ${cards.map((c) => rankText(c.rank)).join(' ')}.`;
}
