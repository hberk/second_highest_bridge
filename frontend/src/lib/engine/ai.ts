// Port of ai.py. A line-for-line port, deliberately: every constant and branch
// here was measured in Python, and the reasons are recorded beside them in
// ai.py and CLAUDE.md -- read those before changing anything. engine.test.ts
// holds this file to the Python engine's exact calls, alerts and cards.
import {
  RANKS, SUITS, maxBy, minBy, parseBid, value, cardKey, card,
  type Card, type Seat, type Suit,
} from './card';
import {
  AuctionState, PARTNERS, PLAYERS, legalPlays, resolveTrick, type Play,
} from './auction';

const AI_TAG = '__ai__';
type AnyPlay = Play<string>;

// ── Hand valuation ───────────────────────────────────────────────────────────

const HCP: Record<string, number> = { A: 4, K: 3, Q: 2, J: 1 };

export function hcp(hand: Card[]): number {
  return hand.reduce((n, c) => n + (HCP[c.rank] ?? 0), 0);
}

export const TRUMP_CARD = 1.025;
export const LENGTH_BONUS = 0.25;
export const LENGTH_BONUS_FROM = 4;
export const HONOUR_VALUE: Record<string, number> = {
  K: 0.281, Q: 0.281,
  A: 0.117, '10': 0.117, '9': 0.117,
  J: -0.094, '8': -0.094, '7': -0.094, '6': -0.094, '5': -0.094,
  '4': -0.199, '3': -0.199, '2': -0.199,
};

type Groups = Record<Suit, Card[]>;

/** Python 3.12+'s sum() over floats: Neumaier compensated summation
 *  (Objects/bltinmodule.c). A naive loop differs in the last bit, which is
 *  enough to flip a threshold that a hand lands on exactly. Python 3.9-3.11
 *  summed naively, so the Python engine itself differs by an ulp across
 *  versions; the fixtures, and deployment, are 3.12. */
function pythonSum(xs: number[]): number {
  let sum = 0;
  let c = 0;
  for (const x of xs) {
    const t = sum + x;
    c += Math.abs(sum) >= Math.abs(x) ? (sum - t) + x : (x - t) + sum;
    sum = t;
  }
  return c !== 0 && Number.isFinite(c) ? sum + c : sum;
}

export interface HandEval {
  honour_pts: number;
  suit_pts: Record<Suit, number>;
  total_pts: number;
  groups: Groups;
  lengths: number[];
  is_balanced: boolean;
}

/** Expected tricks, fitted to solved double dummy results. See ai.py. */
export function evalHandSh(hand: Card[]): HandEval {
  const groups: Groups = { C: [], D: [], H: [], S: [] };
  for (const c of hand) groups[c.suit].push(c);
  const honour = pythonSum(hand.map((c) => HONOUR_VALUE[c.rank] ?? 0));
  const trumpValue = (n: number) =>
    TRUMP_CARD * n + LENGTH_BONUS * Math.max(0, n - LENGTH_BONUS_FROM);
  const suitPts = {} as Record<Suit, number>;
  for (const s of SUITS) suitPts[s] = honour + trumpValue(groups[s].length);
  const lengths = SUITS.map((s) => groups[s].length).sort((a, b) => b - a);
  const shape = lengths.join(',');
  return {
    honour_pts: honour,
    suit_pts: suitPts,
    total_pts: Math.max(...SUITS.map((s) => suitPts[s])),
    groups,
    lengths,
    is_balanced: shape === '4,3,3,3' || shape === '4,4,3,2' || shape === '5,3,3,2',
  };
}

// ── Bidding thresholds (fitted; see ai.py) ───────────────────────────────────

export const GAME_TRICKS = 10.0;
export const PARTSCORE_LEVEL = 2;
export const OPEN_TRICKS = 4.5;
export const OPEN_SUIT_LENGTH = 5;
export const SUPPORT_LENGTH = 3;
export const OVERCALL_TRICKS = 4.5;
export const OVERCALL_POINTS = 8;
export const PREEMPT_LENGTH = 6;

export const PROMISE_SHIFT = 1.5;
export const PROMISE_OPENED = 4.66 - PROMISE_SHIFT;
export const PROMISE_RESPONDED_1 = 4.39 - PROMISE_SHIFT;
export const PROMISE_TWO_OVER_ONE = 5.66 - PROMISE_SHIFT;
export const PROMISE_RAISED = 3.56 - PROMISE_SHIFT;
export const PROMISE_JUMP_RAISED = 4.67 - PROMISE_SHIFT;
export const PROMISE_DOUBLED = 3.56 - PROMISE_SHIFT;
export const PROMISE_ADVANCED = 3.56 - PROMISE_SHIFT;
export const PROMISE_CUEBID = 4.67 - PROMISE_SHIFT;

export const TWO_OVER_ONE_TRICKS = 5.6;
export const TWO_OVER_ONE_POINTS = 12;
export const FREE_BID_LENGTH = 6;
export const FREE_BID_POINTS = 8;
export const JUMP_RAISE_TRICKS = 6.2;

export const OPEN_POINTS = 12;
export const OVERCALL_POINTS_1 = 8;
export const OVERCALL_POINTS_2 = 10;
export const PREEMPT_POINTS_LOW = 6;
export const PREEMPT_POINTS_HIGH = 11;
export const PREEMPT_LENGTH_3 = 7;
// Fourth seat: no pre-empt; a two-level opening shows 11-15 and six cards.
export const FOURTH_TWO_POINTS_LOW = 11;
export const FOURTH_TWO_POINTS_HIGH = 16;
export const TAKEOUT_POINTS_1 = 12;
export const TAKEOUT_POINTS_2 = 14;
export const TAKEOUT_MAX_THEIRS = 2;
export const TAKEOUT_MIN_ELSEWHERE = 3;
export const ADVANCE_JUMP_POINTS = 8;
export const REBID_MINIMUM = 12;
export const REBID_LENGTH = 6;
export const RAISE_POINTS = 6;
export const JUMP_RAISE_POINTS = 10;
export const RESPONSE_POINTS_SHOWN = 6;

const SUIT_SYM: Record<string, string> = { S: '♠', H: '♥', D: '♦', C: '♣' };

export type Decision = [string, string];
type Bid = [number, string];

const isSuit = (s: string | null): s is Suit => s !== null && (SUITS as readonly string[]).includes(s);
const suitIndex = (s: Suit) => SUITS.indexOf(s);

function bidsBy(seat: Seat, auction: AuctionState): Bid[] {
  const out: Bid[] = [];
  for (const [who, call] of auction.calls) {
    const parsed = parseBid(call);
    if (who === seat && parsed) out.push(parsed);
  }
  return out;
}

function doubledBy(seat: Seat, auction: AuctionState): boolean {
  return auction.calls.some(([who, call]) => who === seat && call === 'X');
}

function theirSuit(player: Seat, auction: AuctionState): string | null {
  const partner = PARTNERS[player];
  for (let i = auction.calls.length - 1; i >= 0; i--) {
    const [who, call] = auction.calls[i];
    const parsed = parseBid(call);
    if (parsed && who !== player && who !== partner) return parsed[1];
  }
  return null;
}

function firstNamer(auction: AuctionState, strain: string): Seat | null {
  for (const [who, call] of auction.calls) {
    const parsed = parseBid(call);
    if (parsed && parsed[1] === strain) return who;
  }
  return null;
}

function isCuebid(player: Seat, auction: AuctionState, strain: string): boolean {
  const namer = firstNamer(auction, strain);
  return namer !== null && namer !== player && namer !== PARTNERS[player];
}

function partnerPromise(player: Seat, partner: Seat, auction: AuctionState, strain: string): number {
  const mine = bidsBy(player, auction);
  const theirs = bidsBy(partner, auction);
  if (!theirs.length) return doubledBy(partner, auction) ? PROMISE_DOUBLED : PROMISE_OPENED;
  if (doubledBy(player, auction) && !mine.length) return PROMISE_ADVANCED;
  const namedHere = theirs.filter((b) => b[1] === strain);
  if (!namedHere.length) return PROMISE_RESPONDED_1;
  const introduced = namedHere[0][0];
  const opened = !mine.length || theirs[0][0] <= mine[0][0];
  if (firstNamer(auction, strain) === player) {
    return introduced >= 3 ? PROMISE_JUMP_RAISED : PROMISE_RAISED;
  }
  if (opened && theirs[0][1] === strain) return PROMISE_OPENED;
  return introduced >= 2 ? PROMISE_TWO_OVER_ONE : PROMISE_RESPONDED_1;
}

function isTwoOverOne(responder: string, opener: string): boolean {
  if (!isSuit(responder) || !isSuit(opener)) return false;
  return suitIndex(responder) < suitIndex(opener);
}

function gameCall(strain: string, legal: string[]): string | null {
  if (strain === 'H' || strain === 'S') {
    const call = `4${strain}`;
    return legal.includes(call) ? call : null;
  }
  return null;
}

function cheapest(strain: string, level: number, legal: string[]): string | null {
  for (let lvl = level; lvl < 8; lvl++) {
    const call = `${lvl}${strain}`;
    if (legal.includes(call)) return call;
  }
  return null;
}

const levelOf = (call: string) => parseBid(call)![0];
const trunc = Math.trunc; // Python int() on a float

function points(groups: Groups): number {
  let high = 0;
  let length = 0;
  for (const s of SUITS) {
    for (const c of groups[s]) high += HCP[c.rank] ?? 0;
    length += Math.max(0, groups[s].length - 4);
  }
  const shape = SUITS.map((s) => groups[s].length).sort((a, b) => b - a).join(',');
  return high + length + (shape === '4,3,3,3' ? -1 : 0);
}

function place(strain: string, combined: number, legal: string[]): Decision {
  if (combined >= GAME_TRICKS) {
    const game = gameCall(strain, legal);
    if (game) return [game, `${SUPPORT_LENGTH}+ ${SUIT_SYM[strain]} support, game values.`];
  }
  const ceiling = Math.max(1, trunc(combined) - 6);
  const call = cheapest(strain, PARTSCORE_LEVEL, legal);
  if (call && levelOf(call) <= Math.max(ceiling, PARTSCORE_LEVEL)) {
    return [call, `${SUPPORT_LENGTH}+ ${SUIT_SYM[strain]} support, limited.`];
  }
  return ['Pass', 'No extra values.'];
}

function openingBid(ev: HandEval, groups: Groups, bestSuit: Suit, bestLen: number, legal: string[],
  fourthSeat = false): Decision {
  const pts = points(groups);
  const strong = ev.total_pts >= OPEN_TRICKS && pts >= OPEN_POINTS;
  if (fourthSeat && FOURTH_TWO_POINTS_LOW <= pts && pts < FOURTH_TWO_POINTS_HIGH
    && bestLen >= PREEMPT_LENGTH && legal.includes(`2${bestSuit}`)) {
    return [`2${bestSuit}`,
      `${PREEMPT_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${FOURTH_TWO_POINTS_LOW}-${FOURTH_TWO_POINTS_HIGH - 1} points. Fourth seat.`];
  }
  if (strong && bestLen >= OPEN_SUIT_LENGTH && legal.includes(`1${bestSuit}`)) {
    return [`1${bestSuit}`, `${OPEN_SUIT_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${OPEN_POINTS}+ points.`];
  }
  if (PREEMPT_POINTS_LOW <= pts && pts < PREEMPT_POINTS_HIGH && !fourthSeat) {
    if (bestLen >= PREEMPT_LENGTH_3 && legal.includes(`3${bestSuit}`)) {
      return [`3${bestSuit}`,
        `${PREEMPT_LENGTH_3}+ ${SUIT_SYM[bestSuit]}, ${PREEMPT_POINTS_LOW}-10 points. Pre-emptive.`];
    }
    if (bestLen >= PREEMPT_LENGTH && legal.includes(`2${bestSuit}`)) {
      return [`2${bestSuit}`,
        `${PREEMPT_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${PREEMPT_POINTS_LOW}-10 points. Pre-emptive.`];
    }
  }
  if (strong) {
    const clubs = groups.C.length;
    const diamonds = groups.D.length;
    if (clubs >= 3 || diamonds >= 3) {
      let suit: Suit;
      let shown: number;
      if (clubs > diamonds || (clubs === 3 && diamonds === 3)) {
        suit = 'C';
        shown = 3;
      } else {
        suit = 'D';
        shown = Math.max(3, Math.min(clubs, diamonds));
      }
      if (legal.includes(`1${suit}`)) {
        return [`1${suit}`,
          `${shown}+ ${SUIT_SYM[suit]}, ${OPEN_POINTS}+ points. No five-card major.`];
      }
    }
  }
  if (pts < OPEN_POINTS) return ['Pass', `Fewer than ${OPEN_POINTS} points.`];
  return ['Pass', 'No suit worth opening.'];
}

function takeoutDouble(player: Seat, auction: AuctionState, groups: Groups, pts: number,
  legal: string[]): Decision | null {
  if (!legal.includes('X')) return null;
  const theirs = theirSuit(player, auction);
  if (!isSuit(theirs)) return null;
  if (groups[theirs].length > TAKEOUT_MAX_THEIRS) return null;
  if (SUITS.some((s) => s !== theirs && groups[s].length < TAKEOUT_MIN_ELSEWHERE)) return null;
  let theirLevel = 1;
  let any = false;
  for (const [who, c] of auction.calls) {
    const parsed = parseBid(c);
    if (parsed && who !== player && who !== PARTNERS[player]) {
      theirLevel = any ? Math.max(theirLevel, parsed[0]) : parsed[0];
      any = true;
    }
  }
  const need = theirLevel <= 1 ? TAKEOUT_POINTS_1 : TAKEOUT_POINTS_2;
  if (pts < need) return null;
  return ['X', `${need}+ points, ${TAKEOUT_MAX_THEIRS} or fewer ${SUIT_SYM[theirs]}. Takeout: bid your best suit.`];
}

function advanceDouble(player: Seat, auction: AuctionState, ev: HandEval, groups: Groups,
  legal: string[]): Decision {
  const theirs = theirSuit(player, auction);
  const pts = points(groups);
  const candidates = SUITS.filter((s) => s !== theirs);
  const best = maxBy(candidates, (s) => [groups[s].length, ev.suit_pts[s], suitIndex(s)]);
  const combined = ev.suit_pts[best] + PROMISE_DOUBLED;
  const ceiling = Math.max(1, trunc(combined) - 6);
  const strong = pts >= ADVANCE_JUMP_POINTS;
  const start = 1 + (strong ? 1 : 0);
  const band = strong ? `${ADVANCE_JUMP_POINTS}+` : `0-${ADVANCE_JUMP_POINTS - 1}`;
  const len = groups[best].length;

  let call = cheapest(best, start, legal);
  if (call && levelOf(call) <= Math.max(ceiling, PARTSCORE_LEVEL)) {
    return [call, `${len}+ ${SUIT_SYM[best]}, ${band} points. Answering the double.`];
  }
  call = cheapest(best, 1, legal);
  if (call && strong) {
    return [call, `${len}+ ${SUIT_SYM[best]}, ${band} points. Answering the double.`];
  }
  if (call) {
    return [call, `${len}+ ${SUIT_SYM[best]}, 0-${ADVANCE_JUMP_POINTS - 1} points. Answering the double.`];
  }
  return ['Pass', 'No legal suit to answer the double.'];
}

function rebidAlone(player: Seat, auction: AuctionState, ev: HandEval, groups: Groups,
  legal: string[]): Decision {
  const myFirst = bidsBy(player, auction)[0][1] as Suit;
  const pts = points(groups);
  const held = groups[myFirst].length;
  if (held >= REBID_LENGTH || (pts >= REBID_MINIMUM && held >= OPEN_SUIT_LENGTH)) {
    const combined = ev.suit_pts[myFirst] + PROMISE_RESPONDED_1;
    const ceiling = Math.max(1, trunc(combined) - 6);
    const call = cheapest(myFirst, PARTSCORE_LEVEL, legal);
    if (call && levelOf(call) <= ceiling) {
      const why = held >= REBID_LENGTH
        ? `${REBID_LENGTH}+ ${SUIT_SYM[myFirst]}. Rebidding my own suit.`
        : `${OPEN_SUIT_LENGTH}+ ${SUIT_SYM[myFirst]}, ${REBID_MINIMUM}+ points. Rebidding my own suit.`;
      return [call, why];
    }
  }
  return ['Pass', 'Partner has passed; not enough to bid again alone.'];
}

function response(player: Seat, partner: Seat, auction: AuctionState, ev: HandEval,
  groups: Groups, bestSuit: Suit, bestLen: number, legal: string[]): Decision {
  const theirs = bidsBy(partner, auction);
  const [pLevel, pStrain] = theirs[theirs.length - 1];

  if (!isSuit(pStrain)) {
    if (bestLen >= OPEN_SUIT_LENGTH) {
      const call = cheapest(bestSuit, pLevel, legal);
      if (call && levelOf(call) <= PARTSCORE_LEVEL + 1) {
        return [call, `${OPEN_SUIT_LENGTH}+ ${SUIT_SYM[bestSuit]}. Taking it out of notrump.`];
      }
    }
    return ['Pass', 'Nothing to show over notrump.'];
  }

  const held = groups[pStrain].length;

  if (isCuebid(player, auction, pStrain)) {
    const mineNamed = bidsBy(player, auction);
    const agreed = (mineNamed.length ? mineNamed[0][1] : bestSuit) as Suit;
    const [call, why] = place(agreed, ev.suit_pts[agreed] + PROMISE_CUEBID, legal);
    return call !== 'Pass'
      ? [call, `${SUIT_SYM[agreed]} again over the cuebid. Partner showed support, not their suit.`]
      : [call, why];
  }

  if (held >= SUPPORT_LENGTH) {
    // The AI does not cuebid here; measured at -4.1 head to head. See ai.py.
    const combined = ev.suit_pts[pStrain] + partnerPromise(player, partner, auction, pStrain);
    const pts = points(groups);
    if (combined >= GAME_TRICKS) {
      const game = gameCall(pStrain, legal);
      if (game) return [game, `${SUPPORT_LENGTH}+ ${SUIT_SYM[pStrain]} support, game values.`];
    }
    const ceiling = Math.max(1, trunc(combined) - 6);
    if (ev.total_pts >= JUMP_RAISE_TRICKS && pts >= JUMP_RAISE_POINTS
      && ceiling >= PARTSCORE_LEVEL + 1) {
      const jump = cheapest(pStrain, PARTSCORE_LEVEL + 1, legal);
      if (jump && levelOf(jump) <= ceiling) {
        return [jump, `${SUPPORT_LENGTH}+ ${SUIT_SYM[pStrain]} support, ${JUMP_RAISE_POINTS}+ points. Invitational.`];
      }
    }
    if (pts < RAISE_POINTS) return ['Pass', `Fewer than ${RAISE_POINTS} points.`];
    const [call, why] = place(pStrain, combined, legal);
    return call !== 'Pass'
      ? [call, `${SUPPORT_LENGTH}+ ${SUIT_SYM[pStrain]} support, ${RAISE_POINTS}+ points. Limited.`]
      : [call, why];
  }

  if (bestLen >= OPEN_SUIT_LENGTH) {
    const pts = points(groups);
    const one = cheapest(bestSuit, 1, legal);
    if (one && levelOf(one) === 1 && pts >= RESPONSE_POINTS_SHOWN) {
      return [one, `${OPEN_SUIT_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${RESPONSE_POINTS_SHOWN}+ points.`];
    }
    if (isTwoOverOne(bestSuit, pStrain) && ev.total_pts >= TWO_OVER_ONE_TRICKS
      && pts >= TWO_OVER_ONE_POINTS) {
      const two = cheapest(bestSuit, 2, legal);
      if (two && levelOf(two) === 2) {
        return [two, `${OPEN_SUIT_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${TWO_OVER_ONE_POINTS}+ points. Forcing.`];
      }
    }
    const contested = auction.calls.some(
      ([who, c]) => who !== player && who !== partner && parseBid(c) !== null);
    if (contested && bestLen >= FREE_BID_LENGTH && pts >= FREE_BID_POINTS) {
      const [call] = place(bestSuit, ev.suit_pts[bestSuit] + PROMISE_OPENED, legal);
      if (call !== 'Pass') {
        return [call, `${FREE_BID_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${FREE_BID_POINTS}+ points. Free bid.`];
      }
    }
  }

  if (bestLen >= OPEN_SUIT_LENGTH) {
    return ['Pass', 'Not enough to introduce a new suit at this level.'];
  }
  return ['Pass', `Fewer than ${SUPPORT_LENGTH} ${SUIT_SYM[pStrain]} and no five-card suit.`];
}

function rebid(player: Seat, partner: Seat, auction: AuctionState, ev: HandEval,
  groups: Groups, bestSuit: Suit, bestLen: number, legal: string[]): Decision {
  const mine = bidsBy(player, auction);
  const theirs = bidsBy(partner, auction);
  if (!mine.length || !theirs.length) return ['Pass', 'Pass.'];
  const pStrain = theirs[theirs.length - 1][1];
  const myFirst = mine[0][1] as Suit;

  if (isCuebid(player, auction, pStrain)) {
    const [call, why] = place(myFirst, ev.suit_pts[myFirst] + PROMISE_CUEBID, legal);
    return call !== 'Pass'
      ? [call, `${SUIT_SYM[myFirst]} again over the cuebid. Partner showed support, not their suit.`]
      : [call, why];
  }

  if (isSuit(pStrain) && groups[pStrain].length >= SUPPORT_LENGTH) {
    const combined = ev.suit_pts[pStrain] + partnerPromise(player, partner, auction, pStrain);
    const [call, why] = place(pStrain, combined, legal);
    return call !== 'Pass'
      ? [call, `${SUPPORT_LENGTH}+ ${SUIT_SYM[pStrain]} support, agreeing the suit.`]
      : [call, why];
  }

  if (pStrain === myFirst) {
    const combined = ev.suit_pts[myFirst] + partnerPromise(player, partner, auction, myFirst);
    const [call, why] = place(myFirst, combined, legal);
    return call !== 'Pass' ? [call, `${SUIT_SYM[myFirst]} agreed. No extra values shown.`] : [call, why];
  }

  if (bestLen >= OPEN_SUIT_LENGTH + 1) {
    const [call, why] = place(bestSuit, ev.suit_pts[bestSuit] + PROMISE_RESPONDED_1, legal);
    return call !== 'Pass' ? [call, `6+ ${SUIT_SYM[bestSuit]}, rebidding the suit.`] : [call, why];
  }
  return ['Pass', 'No fit, nothing more to show.'];
}

/** The call this hand makes, and an alert saying what it shows. */
export function aiBidExplained(player: Seat, hand: Card[], auction: AuctionState): Decision {
  const legal = auction.legalCalls();
  if (!legal.length) return ['Pass', 'Pass. No legal call available.'];

  const ev = evalHandSh(hand);
  const groups = ev.groups;
  let bestSuit = maxBy(SUITS, (s) => [groups[s].length, ev.suit_pts[s], suitIndex(s)]);
  let bestLen = groups[bestSuit].length;

  const partner = PARTNERS[player];
  const myBids = bidsBy(player, auction);
  const partnerBids = bidsBy(partner, auction);
  const opponentsBid = auction.calls.some(
    ([who, c]) => who !== player && who !== partner
      && (parseBid(c) !== null || c === 'X' || c === 'XX'));

  if (doubledBy(partner, auction) && !partnerBids.length && !myBids.length
    && !doubledBy(player, auction)) {
    return advanceDouble(player, auction, ev, groups, legal);
  }
  if (partnerBids.length && myBids.length) {
    return rebid(player, partner, auction, ev, groups, bestSuit, bestLen, legal);
  }
  if (partnerBids.length) {
    return response(player, partner, auction, ev, groups, bestSuit, bestLen, legal);
  }
  if (myBids.length) return rebidAlone(player, auction, ev, groups, legal);
  if (!opponentsBid) {
    const fourthSeat = auction.calls.length === 3
      && auction.calls.every(([, call]) => call === 'Pass');
    return openingBid(ev, groups, bestSuit, bestLen, legal, fourthSeat);
  }

  const pts = points(groups);
  // Never overcall in a suit they have bid.
  const theirsBid = new Set(SUITS.filter((s) => {
    const namer = firstNamer(auction, s);
    return namer !== null && namer !== player && namer !== partner;
  }));
  const own = SUITS.filter((s) => !theirsBid.has(s));
  if (own.length) {
    bestSuit = maxBy(own, (s) => [groups[s].length, ev.suit_pts[s], suitIndex(s)]);
    bestLen = groups[bestSuit].length;
  }
  if (own.length && ev.total_pts >= OVERCALL_TRICKS && bestLen >= OPEN_SUIT_LENGTH) {
    const call = cheapest(bestSuit, 1, legal);
    if (call) {
      const level = levelOf(call);
      const need = level === 1 ? OVERCALL_POINTS_1 : OVERCALL_POINTS_2;
      if (level <= 2 && pts >= need) {
        return [call, `${OPEN_SUIT_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${need}+ points. Overcall.`];
      }
    }
  }
  if (!doubledBy(player, auction)) {
    const double = takeoutDouble(player, auction, groups, pts, legal);
    if (double) return double;
  }
  if (bestLen < OPEN_SUIT_LENGTH) return ['Pass', 'No five-card suit outside theirs to overcall.'];
  if (pts < OVERCALL_POINTS_1) return ['Pass', `Fewer than ${OVERCALL_POINTS_1} points.`];
  return ['Pass', 'Not enough to come in at this level.'];
}

export function aiBid(player: Seat, hand: Card[], auction: AuctionState): string {
  return aiBidExplained(player, hand, auction)[0];
}

// ── Card play ────────────────────────────────────────────────────────────────

const ALL_VALUES = RANKS.map((_, i) => i).reverse();
const FULL_DECK: Card[] = SUITS.flatMap((s) => RANKS.map((r) => card(s, r)));

function unplayedValues(suit: Suit, played: Card[]): number[] {
  const gone = new Set(played.filter((c) => c.suit === suit).map(value));
  return ALL_VALUES.filter((v) => !gone.has(v));
}

function gap(suit: Suit, hand: Card[], played: Card[]): number {
  const mine = hand.filter((c) => c.suit === suit).map(value).sort((a, b) => b - a);
  if (mine.length < 2) return 99;
  const [top, second] = mine;
  const mineSet = new Set(mine);
  return unplayedValues(suit, played)
    .filter((v) => !mineSet.has(v) && second < v && v < top).length;
}

function laterHoldings(player: Seat, hand: Card[], trick: AnyPlay[], played: Card[],
  visible: Partial<Record<Seat, Card[]>>): Card[] {
  const i = PLAYERS.indexOf(player);
  const later: Seat[] = [];
  for (let k = 1; k < 4 - trick.length; k++) later.push(PLAYERS[(i + k) % 4]);
  const opponents = later.filter((p) => p !== PARTNERS[player]);
  const pool = new Map<string, Card>();
  if (opponents.some((p) => !(p in visible))) {
    const seen = new Set<string>([
      ...played.map(cardKey), ...trick.map(([, c]) => cardKey(c)), ...hand.map(cardKey)]);
    for (const h of Object.values(visible)) for (const c of h!) seen.add(cardKey(c));
    for (const c of FULL_DECK) if (!seen.has(cardKey(c))) pool.set(cardKey(c), c);
  }
  for (const p of opponents) {
    for (const c of visible[p] ?? []) pool.set(cardKey(c), c);
  }
  return [...pool.values()];
}

function winningSuit(cards: Card[], trump: string | null): string {
  if (isSuit(trump) && cards.some((c) => c.suit === trump)) return trump;
  return cards[0].suit;
}

function outlook(player: Seat, c: Card, trick: AnyPlay[], trump: string | null,
  later: Card[]): [string, number] {
  const plays: AnyPlay[] = [...trick, [player, c]];
  const holder = resolveTrick(plays, trump);
  const suit = winningSuit(plays.map(([, x]) => x), trump);
  const ours = [player, PARTNERS[player]] as string[];
  let exposed = 0;
  for (const l of later) {
    if (l.suit === suit && !ours.includes(resolveTrick([...plays, [AI_TAG, l]], trump))) exposed++;
  }
  return [holder, exposed];
}

/** `played`: every card from completed tricks. `visible`: hands every seat
 *  can see (the dummy, once exposed). */
export function aiPlay(player: Seat, hand: Card[], trick: AnyPlay[], trump: string | null,
  played: Card[], visible: Partial<Record<Seat, Card[]>> = {}): Card {
  const led = trick.length ? trick[0][1].suit : null;
  const legal = legalPlays(hand, led);
  if (!trick.length) return lead(hand, trump, played);
  if (trick.length === 3) return playLast(legal, trick, trump);
  return middlePlay(player, legal, trick, trump, laterHoldings(player, hand, trick, played, visible));
}

function lead(hand: Card[], trump: string | null, played: Card[]): Card {
  const groups = new Map<Suit, Card[]>();
  for (const c of hand) {
    if (!groups.has(c.suit)) groups.set(c.suit, []);
    groups.get(c.suit)!.push(c);
  }
  const best = maxBy(groups.keys(), (s) => [
    -gap(s, hand, played),
    -(isSuit(trump) && s === trump ? 1 : 0),
    groups.get(s)!.length,
    suitIndex(s),
  ]);
  const cards = [...groups.get(best)!].sort((a, b) => value(b) - value(a));
  return cards[Math.min(1, cards.length - 1)];
}

function middlePlay(player: Seat, legal: Card[], trick: AnyPlay[], trump: string | null,
  later: Card[]): Card {
  const options: [number, number, Card][] = [];
  for (const c of legal) {
    const [holder, exposed] = outlook(player, c, trick, trump, later);
    if ((holder === player || holder === PARTNERS[player]) && exposed <= 1) {
      options.push([exposed, value(c), c]);
    }
  }
  if (options.length) return minBy(options, (o) => [o[0], o[1]])[2];
  return minBy(legal, (c) => [value(c)]);
}

function playLast(legal: Card[], trick: AnyPlay[], trump: string | null): Card {
  const winning = legal.filter((c) => resolveTrick([...trick, [AI_TAG, c]], trump) === AI_TAG);
  return minBy(winning.length ? winning : legal, (c) => [value(c)]);
}
