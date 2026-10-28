// Port of ai.py. A line-for-line port, deliberately: every constant and branch
// here was measured in Python, and the reasons are recorded beside them in
// ai.py and docs/BIDDING.md -- read those before changing anything. engine.test.ts
// holds this file to the Python engine's exact calls, alerts and cards.
import {
  RANKS, SUITS, maxBy, minBy, parseBid, value, cardKey, card,
  type Card, type Seat, type Suit,
} from './card';
import {
  AuctionState, PARTNERS, PARTNERSHIP, PLAYERS, legalPlays, resolveTrick, type Play,
} from './auction';
import { doublerGuard, gibBid, Hand, jamAlert, LOTT, LOTT_ALERT, nameTheSuit, raiseAlert } from './gib';
// meanings.ts imports this module; its functions are only called, never at load.
import { prng, SAMPLE_HANDS, sampleHand, seedOf } from '../meanings';

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

/** Shortness once a fit is agreed: a void adds SHORT_VOID_TRICKS, a singleton
 *  SHORT_SINGLETON_TRICKS, for the shortest side suit (see ai.py). */
export const SHORT_VOID_TRICKS = 5.0;
export const SHORT_SINGLETON_TRICKS = 1.0;

function withShortness(combined: number, groups: Groups, trump: Suit): number {
  if (groups[trump].length < SUPPORT_LENGTH) return combined;
  const shortest = Math.min(...SUITS.filter((s) => s !== trump).map((s) => groups[s].length));
  return combined + (shortest === 0 ? SHORT_VOID_TRICKS : shortest === 1 ? SHORT_SINGLETON_TRICKS : 0.0);
}

/** Our agreed suit bid while they hold the contract carries the alert GIB's
 *  Law of Total Tricks gives the same call (see ai.py, _contest_alert). */
function contestAlert(player: Seat, auction: AuctionState, call: string, why: string): string {
  const hb = auction.highestBid;
  const bid = parseBid(call);
  const s = bid ? bid[1] : null;
  if (!LOTT || hb === null || s === null || !isSuit(s) || auction.doubled !== 'None'
    || PARTNERSHIP[hb[2]] === PARTNERSHIP[player]) return why;
  const mine = bidsBy(player, auction).some(([, strain]) => strain === s);
  return nameTheSuit(call, mine ? LOTT_ALERT : raiseAlert(s as Suit, LOTT_ALERT));
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

/** What a one-level opening SHOWS: a major five, a minor three -- the same
 *  for every hand, so the alert cannot read the minor lengths out. */
function oneLevelOpeningAlert(suit: Suit): string {
  const shown = suit === 'H' || suit === 'S' ? OPEN_SUIT_LENGTH : 3;
  return `${shown}+ ${SUIT_SYM[suit]}, ${OPEN_POINTS}+ points.`;
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
    return [`1${bestSuit}`, oneLevelOpeningAlert(bestSuit)];
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
      const suit: Suit = clubs > diamonds || (clubs === 3 && diamonds === 3) ? 'C' : 'D';
      if (legal.includes(`1${suit}`)) return [`1${suit}`, oneLevelOpeningAlert(suit)];
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
  const lowest = cheapest(best, 1, legal);
  // What the answer SHOWS, never what the hand holds: 8+ only when it jumps.
  const answer = (c: string): string => {
    const sym = SUIT_SYM[parseBid(c)![1] as Suit];
    return c !== lowest
      ? `${ADVANCE_JUMP_POINTS}+ points, longest suit, ${sym}. Answering the double.`
      : `Longest suit other than theirs, ${sym}. Answering the double.`;
  };

  let call = cheapest(best, start, legal);
  if (call && levelOf(call) <= Math.max(ceiling, PARTSCORE_LEVEL)) return [call, answer(call)];
  call = lowest;
  if (call && strong) return [call, answer(call)];
  if (call) return [call, answer(call)];
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
      // One text for both reasons it fires; only their common floor is quoted.
      return [call, `${OPEN_SUIT_LENGTH}+ ${SUIT_SYM[myFirst]}. Rebidding my own suit.`];
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
    const combined = withShortness(
      ev.suit_pts[pStrain] + partnerPromise(player, partner, auction, pStrain), groups, pStrain as Suit);
    const pts = points(groups);
    if (combined >= GAME_TRICKS) {
      const game = gameCall(pStrain, legal);
      if (game) return [game, `${SUPPORT_LENGTH}+ ${SUIT_SYM[pStrain]} support, game values.`];
    }
    const ceiling = Math.max(1, trunc(combined) - 6);
    if (ev.total_pts >= JUMP_RAISE_TRICKS && pts >= JUMP_RAISE_POINTS
      && ceiling >= PARTSCORE_LEVEL + 1) {
      const jump = cheapest(pStrain, PARTSCORE_LEVEL + 1, legal);
      // Only a JUMP is a jump raise (see ai.py).
      if (jump && levelOf(jump) <= ceiling && jump !== cheapest(pStrain, PARTSCORE_LEVEL, legal)) {
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
    // In competition a 2/1 and a free bid can be the same call: quote what both share.
    const contested = auction.calls.some(
      ([who, c]) => who !== player && who !== partner && parseBid(c) !== null);
    const ambiguous = contested && isTwoOverOne(bestSuit, pStrain);
    const either = `${OPEN_SUIT_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${FREE_BID_POINTS}+ points.`;
    if (isTwoOverOne(bestSuit, pStrain) && ev.total_pts >= TWO_OVER_ONE_TRICKS
      && pts >= TWO_OVER_ONE_POINTS) {
      const two = cheapest(bestSuit, 2, legal);
      if (two && levelOf(two) === 2) {
        return [two, ambiguous ? either
          : `${OPEN_SUIT_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${TWO_OVER_ONE_POINTS}+ points. Forcing.`];
      }
    }
    if (contested && bestLen >= FREE_BID_LENGTH && pts >= FREE_BID_POINTS) {
      const [call] = place(bestSuit, ev.suit_pts[bestSuit] + PROMISE_OPENED, legal);
      if (call !== 'Pass') {
        return [call, ambiguous ? either
          : `${FREE_BID_LENGTH}+ ${SUIT_SYM[bestSuit]}, ${FREE_BID_POINTS}+ points. Free bid.`];
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
    const combined = withShortness(
      ev.suit_pts[pStrain] + partnerPromise(player, partner, auction, pStrain), groups, pStrain as Suit);
    const [call, why] = place(pStrain, combined, legal);
    return call !== 'Pass'
      ? [call, contestAlert(player, auction, call,
        `${SUPPORT_LENGTH}+ ${SUIT_SYM[pStrain]} support, agreeing the suit.`)]
      : [call, why];
  }

  if (pStrain === myFirst) {
    const combined = withShortness(
      ev.suit_pts[myFirst] + partnerPromise(player, partner, auction, myFirst), groups, myFirst);
    const [call, why] = place(myFirst, combined, legal);
    return call !== 'Pass'
      ? [call, contestAlert(player, auction, call, `${SUIT_SYM[myFirst]} agreed. No extra values shown.`)]
      : [call, why];
  }

  if (bestLen >= OPEN_SUIT_LENGTH + 1) {
    const [call, why] = place(bestSuit, ev.suit_pts[bestSuit] + PROMISE_RESPONDED_1, legal);
    return call !== 'Pass' ? [call, `6+ ${SUIT_SYM[bestSuit]}, rebidding the suit.`] : [call, why];
  }
  return ['Pass', 'No fit, nothing more to show.'];
}

/** The call this hand makes, and an alert saying what it shows. */
/** GIB 2/1 is the default system (gib.ts); false plays the previous one. */
export const settingsAi = { useGib: true };

/** Penalty double (the user's rule, 2026-10-24). Where the robot would pass
 *  an opponents' natural suit bid, double it with 5+ trumps, or 4+ trumps at
 *  the three level or higher, when our judgement points -- mine plus the
 *  middle of the range partner's alerts show -- reach PENALTY_JUDGE. See ai.py. */
export const PENALTY_DOUBLE = true;
export const PENALTY_JUDGE = 20;
const RANGE_RE = /(\d+)-(\d+) (?:HCP|points)/g;
const MIN_RE = /(\d+)\+ (?:HCP|points)/g;
const MAX_RE = /Fewer than (\d+) (?:HCP|points)/g;

/** The middle of the point range partner's alerts show. An open range
 *  ("8+ HCP") is taken as seven points wide; no range at all as a third of
 *  the points I don't hold. */
function partnerMiddle(partner: Seat, auction: AuctionState, alerts: Record<number, string>,
  mine: number): number {
  let lo = 0;
  let hi = 40 - mine;
  let shown = false;
  auction.calls.forEach(([who], i) => {
    if (who !== partner) return;
    const text = alerts[i] ?? '';
    for (const m of text.matchAll(RANGE_RE)) {
      lo = Math.max(lo, Number(m[1])); hi = Math.min(hi, Number(m[2])); shown = true;
    }
    for (const m of text.matchAll(MIN_RE)) { lo = Math.max(lo, Number(m[1])); shown = true; }
    for (const m of text.matchAll(MAX_RE)) { hi = Math.min(hi, Number(m[1]) - 1); shown = true; }
  });
  if (!shown) return (40 - mine) / 3;
  if (hi === 40 - mine && lo > 0) hi = Math.min(hi, lo + 7);
  return (lo + Math.max(lo, hi)) / 2;
}

function penaltyDouble(player: Seat, hand: Card[], auction: AuctionState,
  alerts: Record<number, string>): Decision | null {
  const hb = auction.highestBid;
  if (!hb || hb[2] === player || hb[2] === PARTNERS[player] || auction.doubled !== 'None') return null;
  const [level, suit] = hb;
  if (!(SUITS as readonly string[]).includes(suit) || !auction.legalCalls().includes('X')) return null;
  let at = -1;
  auction.calls.forEach(([, c], i) => {
    const p = parseBid(c);
    if (p && p[0] === level && p[1] === suit) at = i;
  });
  if ((alerts[at] ?? '').toLowerCase().includes('artificial')) return null;
  const n = hand.filter((c) => c.suit === suit).length;
  const need = level <= 2 ? 5 : 4;
  if (n < need) return null;
  const mine = new Hand(hand).judge;
  if (mine + partnerMiddle(PARTNERS[player], auction, alerts, mine) < PENALTY_JUDGE) return null;
  if (!doubleIsFree(auction)) return null;
  return ['X', `Penalty: ${need}+ ${SUIT_SYM[suit]}.`];
}

const FREE = new Map<string, boolean>();
let sampling = false;

/** Does the system leave a double here without a meaning of its own? Where X
 *  is takeout, negative, responsive or another penalty, a penalty double for
 *  some hands would make the same call mean two things. Asked the way the
 *  bidding box asks (meanings.ts), with the penalty double switched off; one
 *  sampled X is enough. See `_double_is_free` in ai.py. */
function doubleIsFree(auction: AuctionState): boolean {
  const key = `${auction.dealer}|${auction.vulnerability}|${auction.calls.map(([, c]) => c).join(' ')}`;
  let free = FREE.get(key);
  if (free === undefined) {
    const here = new AuctionState(auction.dealer, auction.vulnerability);
    for (const [p, c] of auction.calls) here.applyCall(p, c);
    const who = here.currentPlayer();
    const rnd = prng(seedOf(here));
    sampling = true;
    try {
      free = true;
      for (let i = 0; i < SAMPLE_HANDS; i++) {
        if (aiBidExplained(who, sampleHand(rnd), here, {})[0] === 'X') { free = false; break; }
      }
    } finally {
      sampling = false;
    }
    FREE.set(key, free);
  }
  return free;
}

/** Partner's penalty double is the last call made on the current bid. */
function partnerPenaltyStands(player: Seat, auction: AuctionState,
  alerts: Record<number, string>): boolean {
  if (!auction.highestBid || auction.doubled === 'None') return false;
  for (let i = auction.calls.length - 1; i >= 0; i--) {
    const [who, call] = auction.calls[i];
    if (call === 'X') return who === PARTNERS[player] && (alerts[i] ?? '').startsWith('Penalty');
    if (call !== 'Pass' && call !== 'XX') return false;
  }
  return false;
}

/** `alerts` maps a call's index to the robot's alert for it -- robots' calls
 *  only, as a person's self-alert is free text the robots don't read. The
 *  penalty double reads partner's range from it. */
export function aiBidExplained(player: Seat, hand: Card[], auction: AuctionState,
  alerts?: Record<number, string>): Decision {
  const known = alerts ?? robotAlerts(auction);
  const decision = penaltyOrBase(player, hand, auction, known);
  if (!robotSaid.has(auction)) robotSaid.set(auction, new Map());
  robotSaid.get(auction)!.set(auction.calls.length, decision);
  return decision;
}

/** What this function said on each auction object, by call index. Left out,
 *  `alerts` is the robots' alerts for the calls since made (`_robot_alerts`
 *  in ai.py): an alert depends only on the auction and the call. */
const robotSaid = new WeakMap<AuctionState, Map<number, Decision>>();

function robotAlerts(auction: AuctionState): Record<number, string> {
  const out: Record<number, string> = {};
  for (const [i, [call, why]] of robotSaid.get(auction) ?? new Map<number, Decision>()) {
    if (i < auction.calls.length && auction.calls[i][1] === call) out[i] = why;
  }
  return out;
}

function passesSinceDouble(auction: AuctionState): number {
  let n = 0;
  for (let i = auction.calls.length - 1; i >= 0 && auction.calls[i][1] === 'Pass'; i--) n++;
  return n;
}

function penaltyOrBase(player: Seat, hand: Card[], auction: AuctionState,
  alerts: Record<number, string>): Decision {
  const decision = doubledOrBase(player, hand, auction, alerts);
  const hb = auction.highestBid;
  const bid = parseBid(decision[0]);
  if (hb && auction.doubled === 'X' && (hb[2] === player || hb[2] === PARTNERS[player])
    && bid && bid[1] === hb[1]
    && (alerts[auction.calls.length - 1 - passesSinceDouble(auction)] ?? '').startsWith('Penalty')) {
    // Doubled for penalty in our own strain: bidding it again only goes down more.
    return ['Pass', 'Doubled: no higher in the same strain.'];
  }
  return decision;
}

function doubledOrBase(player: Seat, hand: Card[], auction: AuctionState,
  alerts: Record<number, string>): Decision {
  if (PENALTY_DOUBLE && !sampling && auction.legalCalls().length) {
    if (partnerPenaltyStands(player, auction, alerts)) {
      return ['Pass', "Partner's penalty double stands."];
    }
    const decision = baseBidExplained(player, hand, auction);
    if (decision[0] === 'Pass') return penaltyDouble(player, hand, auction, alerts) ?? decision;
    return decision;
  }
  return baseBidExplained(player, hand, auction);
}

function baseBidExplained(player: Seat, hand: Card[], auction: AuctionState): Decision {
  const decision = systemBidExplained(player, hand, auction);
  return settingsAi.useGib
    ? doublerGuard(player, hand, auction, jamAlert(player, hand, auction, decision))
    : decision;
}

function systemBidExplained(player: Seat, hand: Card[], auction: AuctionState): Decision {
  const legal = auction.legalCalls();
  if (!legal.length) return ['Pass', 'Pass. No legal call available.'];

  // GIB 2/1 is the system; the logic below answers only the contested
  // situations GIB's notes leave to judgment.
  if (settingsAi.useGib) {
    const decision = gibBid(player, hand, auction);
    if (decision) return decision;
  }

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
  visible: Partial<Record<Seat, Card[]>>, out: Record<string, Set<string>> | null = null): Card[] {
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
  // An opponent who has shown out of a suit holds none of it (see ai.py).
  if (out) {
    for (const p of opponents) {
      if (!(p in visible) && out[p]?.size) {
        for (const [k, c] of [...pool]) if (out[p].has(c.suit)) pool.delete(k);
      }
    }
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
  later: Card[], voidChance = 1.0): [string, number] {
  const plays: AnyPlay[] = [...trick, [player, c]];
  const holder = resolveTrick(plays, trump);
  const suit = winningSuit(plays.map(([, x]) => x), trump);
  const ours = [player, PARTNERS[player]] as string[];
  // An overruff only comes if the opponent is out of the led suit (see ai.py).
  let takers = 0;
  let follows = 0;
  for (const l of later) {
    if (l.suit === suit && !ours.includes(resolveTrick([...plays, [AI_TAG, l]], trump))) {
      takers++;
      if (l.suit === plays[0][1].suit) follows++;
    }
  }
  return [holder, follows + voidChance * (takers - follows)];
}

/** Port of ai.visible_hands: dummy, and declarer's hand for the declaring side. */
export function visibleHands(seat: Seat, contract: { dummy: Seat; declarer: Seat },
  hands: Record<Seat, Card[]>): Partial<Record<Seat, Card[]>> {
  const view: Partial<Record<Seat, Card[]>> = { [contract.dummy]: hands[contract.dummy] };
  if (seat === contract.dummy || seat === contract.declarer) view[contract.declarer] = hands[contract.declarer];
  return view;
}

/** `played`: every card from completed tricks. `visible`: hands every seat
 *  can see (the dummy, once exposed). */
export function aiPlay(player: Seat, hand: Card[], trick: AnyPlay[], trump: string | null,
  played: Card[], visible: Partial<Record<Seat, Card[]>> = {},
  history: AnyPlay[][] | null = null, shown: Shown | null = null): Card {
  const led = trick.length ? trick[0][1].suit : null;
  const legal = legalPlays(hand, led);
  if (NO_PEEK_OPENING_LEAD && !trick.length && !played.length) visible = {};
  if (!AUCTION_IN_PLAY) shown = null;
  if (!trick.length && !played.length && shown) {
    const lead0 = partnerSuitLead(player, hand, trump, shown) ?? fitLead(player, hand, trump, shown, history, visible);
    if (lead0 !== null) return lead0;
  }
  let choice: Card;
  if (!trick.length) {
    let sure: Card | null = null;
    const chosen = (DRAW_TRUMPS ? drawTrump(player, hand, trump, played, visible, history, shown) : null)
      ?? (RUFF_LEAD ? ruffLead(player, hand, trump, played, visible) : null)
      ?? (RUN_LONG_SUIT ? runLongSuit(player, hand, trump, played, visible, history, shown) : null)
      ?? (RUFF_RETURN && !(PARTNERS[player] in visible) ? ruffReturn(player, hand, trump, history, visible, shown) : null)
      ?? (SURE_LEAD ? (sure = sureLead(player, hand, trump, played, visible, history)) : null)
      ?? (shown && !(PARTNERS[player] in visible) ? fitLead(player, hand, trump, shown, history, visible) : null)
      ?? (NT_LONG_LEAD ? ntLongLead(player, hand, trump, played, visible) : null);
    if (chosen !== null) {
      choice = chosen;
      // A sure trick is cashed as it is (see ai.py).
      if (DEFENDER_SUIT_PLAN && choice !== sure) {
        choice = defenderSuitPlan(player, hand, trump, played, visible, history, shown, choice) ?? choice;
      }
    } else {
      choice = lead(hand, trump, played);
      if (DEFENDER_SUIT_PLAN) {
        choice = defenderSuitPlan(player, hand, trump, played, visible, history, shown, choice) ?? choice;
      }
      if (SURE_LEAD_DECLARER) {
        choice = sureLeadDeclarer(player, hand, trump, played, visible, history, choice.suit) ?? choice;
      }
      if (FORCE_DUMMY && choice.suit === trump) choice = forceDummy(player, hand, trump, visible, played) ?? choice;
    }
  }
  else if (trick.length === 3) choice = playLast(legal, trick, trump, hand, played);
  else {
    const out = SHOWOUT_MIDDLE && history !== null ? shownOut(history, trick) : null;
    const voidChance = RUFF_IF_FOLLOWS && history !== null && trick.length === 2
      ? voidChanceOf(player, hand, trick, played, visible, history, out ?? shownOut(history, trick))
      : 1.0;
    choice = middlePlay(player, legal, trick, trump,
      laterHoldings(player, hand, trick, played, visible, out), voidChance);
  }

  const partner = PARTNERS[player];
  if (trick.length === 1 && Object.keys(visible).length && partner in visible && legal.length > 1) {
    choice = coverForPartner(player, hand, legal, trick, trump, played, visible, choice);
  }

  if (history !== null && Object.keys(visible).length && legal.length > 1
    && hand.length <= (DEEP_ENDGAME ? DEEP_ENDGAME_CARDS : ENDGAME_CARDS)) {
    const totals = endgameTotals(player, hand, trick, trump, played, visible, history, legal, shown);
    if (totals) {
      const best = Math.max(...totals.values());
      const tied = legal.filter((c) => totals.get(cardKey(c)) === best);
      if (!tied.some((c) => cardKey(c) === cardKey(choice))) choice = minBy(tied, (c) => [value(c)]);
    }
  }
  return choice;
}

// ── Second hand, partner last and in view (see ai.py) ────────────────────────

function coverForPartner(player: Seat, hand: Card[], legal: Card[], trick: AnyPlay[], trump: string | null,
  played: Card[], visible: Partial<Record<Seat, Card[]>>, choice: Card): Card {
  const partner = PARTNERS[player];
  const third = PLAYERS[(PLAYERS.indexOf(player) + 1) % 4];
  const ledSuit = trick[0][1].suit;
  let candidates: Card[];
  if (third in visible) {
    candidates = [...visible[third]!];
  } else {
    // The whole hand, not just the legal cards (see ai.py).
    const seen = new Set([...played, ...trick.map(([, c]) => c), ...hand].map(cardKey));
    for (const cards of Object.values(visible)) for (const c of cards!) seen.add(cardKey(c));
    candidates = FULL_DECK.filter((c) => !seen.has(cardKey(c)));
  }
  const follows = candidates.filter((c) => c.suit === ledSuit);
  const options = [...follows];
  if (!follows.length || !(third in visible)) {
    if (isSuit(trump) && trump !== ledSuit) {
      const ruffs = candidates.filter((c) => c.suit === trump);
      if (ruffs.length) options.push(minBy(ruffs, (c) => [value(c)]));
    }
    const discards = candidates.filter((c) => c.suit !== ledSuit && c.suit !== trump);
    if (discards.length) options.push(minBy(discards, cardOrder));
  }
  if (!options.length) return choice;
  const ours = new Set<string>([player, partner]);
  const score = (c: Card): number => {
    let wins = 0;
    for (const opp of options) {
      const plays: AnyPlay[] = [...trick, [player, c], [third, opp]];
      if (legalPlays(visible[partner]!, ledSuit).some(
        (reply) => ours.has(resolveTrick([...plays, [partner, reply]], trump)))) wins++;
    }
    return wins;
  };
  const scores = new Map(legal.map((c) => [cardKey(c), score(c)]));
  const best = Math.max(...scores.values());
  if (scores.get(cardKey(choice))! >= best) return choice;
  return minBy(legal.filter((c) => scores.get(cardKey(c)) === best), (c) => [value(c)]);
}

// ── Endgame: single dummy search (see ai.py) ─────────────────────────────────

export const ENDGAME_CARDS = 3;
/** Search every layout from DEEP_ENDGAME_CARDS a hand (see ai.py). */
export const DEEP_ENDGAME = true;
export const DEEP_ENDGAME_CARDS = 5;
/** One memory of searched positions (N/S tricks) for every search, robot and
 *  board, one table per trump suit, bounded (see ai.py). */
export const SHARED_POSITIONS = true;
const POSITION_MEMO = new Map<number, Map<string, number>>();
const POSITION_MEMO_MAX = 600_000;

function positionMemo(trump: number): Map<string, number> {
  let table = POSITION_MEMO.get(trump);
  if (!table) { table = new Map(); POSITION_MEMO.set(trump, table); }
  if (table.size > POSITION_MEMO_MAX) table.clear();
  return table;
}

const cardOrder = (c: Card): number[] => [suitIndex(c.suit), value(c)];

// ── What the auction told the play (see ai.py) ───────────────────────────────

export const NO_PEEK_OPENING_LEAD = true;
export const SHOWOUT_MIDDLE = true;
export const AUCTION_IN_PLAY = true;
export const PARTNER_LEAD_MIN = 5;
export const FIT_LEAD_MIN = 3;
export const RUFF_RETURN = true;
export const SHORT_LEAD_RETURN = true;
export const SHORT_LEAD_PCT = 20;
export const SHORT_LEAD_HONOUR = 9;

/** The fewest cards each seat's bidding showed in each suit. */
export type Shown = Partial<Record<Seat, Partial<Record<Suit, number>>>>;

const SUIT_OF_SYM: Record<string, Suit> = { '\u2660': 'S', '\u2665': 'H', '\u2666': 'D', '\u2663': 'C' };
const SHOWN_RE = /(\d+)\+ ([\u2660\u2665\u2666\u2663](?: [\u2660\u2665\u2666\u2663])*)/g;
const EXACT_RE = /exactly (\d+) ([\u2660\u2665\u2666\u2663])/g;

/** The fewest cards each seat's alerts promise in each suit (see ai.py). */
export function shownLengths(calls: [Seat, string][], alerts: Record<number, string>): Shown {
  const shown: Shown = { North: {}, East: {}, South: {}, West: {} };
  calls.forEach(([seat, call], i) => {
    const text = alerts[i] ?? '';
    if (naturalSuit(call, text)) {
      const s = call[1] as Suit;
      shown[seat]![s] = Math.max(shown[seat]![s] ?? 0, 1);
    }
    for (const m of text.matchAll(SHOWN_RE)) {
      for (const sym of m[2].split(' ')) {
        const s = SUIT_OF_SYM[sym];
        shown[seat]![s] = Math.max(shown[seat]![s] ?? 0, Number(m[1]));
      }
    }
    for (const m of text.matchAll(EXACT_RE)) {
      const s = SUIT_OF_SYM[m[2]];
      shown[seat]![s] = Math.max(shown[seat]![s] ?? 0, Number(m[1]));
    }
  });
  return shown;
}

/** Is `call` a bid of its own suit (see ai.py)? */
function naturalSuit(call: string, text: string): boolean {
  if (typeof call !== 'string' || call.length !== 2 || !/[0-9]/.test(call[0]) || !SUITS.includes(call[1] as Suit)) return false;
  const sym = Object.keys(SUIT_OF_SYM).find((k) => SUIT_OF_SYM[k] === call[1])!;
  return text.includes(sym) && !text.includes('Artificial') && !text.includes('Completing')
    && !text.includes('relay') && !text.includes(`short ${sym}`);
}

function playedIn(seat: Seat, suit: string, history: AnyPlay[][], trick: AnyPlay[]): number {
  let n = 0;
  for (const plays of [...history, trick]) for (const [p, c] of plays) if (p === seat && c.suit === suit) n++;
  return n;
}

function fitsAuction(seat: Seat, cards: Card[], history: AnyPlay[][], trick: AnyPlay[], shown: Shown): boolean {
  for (const [suit, n] of Object.entries(shown[seat] ?? {}) as [Suit, number][]) {
    if (cards.filter((c) => c.suit === suit).length + playedIn(seat, suit, history, trick) < n) return false;
  }
  return true;
}

function partnerSuitLead(player: Seat, hand: Card[], trump: string | null, shown: Shown): Card | null {
  const partner = PARTNERS[player];
  const mine = shown[partner] ?? {};
  const suits = (Object.entries(mine) as [Suit, number][])
    .filter(([s, n]) => n >= PARTNER_LEAD_MIN && s !== trump && hand.some((c) => c.suit === s))
    .map(([s]) => s);
  if (!suits.length) return null;
  const s = maxBy(suits, (t) => [mine[t]!, suitIndex(t)]);
  const cards = hand.filter((c) => c.suit === s).sort((a, b) => value(b) - value(a));
  return cards[Math.min(1, cards.length - 1)];
}

function fitLead(player: Seat, hand: Card[], trump: string | null, shown: Shown,
  history: AnyPlay[][] | null, visible: Partial<Record<Seat, Card[]>>): Card | null {
  const partner = PARTNERS[player];
  const out = shownOut(history ?? [], []);
  const dummySeat = (Object.keys(visible) as Seat[]).find((seat) => seat !== partner);
  const dummy = dummySeat === undefined ? null : visible[dummySeat]!;
  const theirs = shown[partner] ?? {};
  const suits: Suit[] = [];
  for (const s of Object.keys(theirs) as Suit[]) {
    const mine = hand.filter((c) => c.suit === s);
    if (s === trump || mine.length < FIT_LEAD_MIN || out[partner].has(s)
      || PLAYERS.some((p) => p !== player && p !== partner && out[p].has(s))
      || (dummy !== null && !dummy.some((c) => c.suit === s))) continue;
    suits.push(s);
  }
  if (!suits.length) return null;
  const s = maxBy(suits, (t) => [theirs[t]! + hand.filter((c) => c.suit === t).length, suitIndex(t)]);
  const cards = hand.filter((c) => c.suit === s).sort((a, b) => value(b) - value(a));
  return cards[Math.min(1, cards.length - 1)];
}

/** A suit partner has shown out of while partner may still hold a trump,
 *  or partner's opening-lead suit read as a singleton, for the ruff (see ai.py). */
function ruffReturn(player: Seat, hand: Card[], trump: string | null, history: AnyPlay[][] | null,
  visible: Partial<Record<Seat, Card[]>>, shown: Shown | null): Card | null {
  if (trump === null || !(SUITS as readonly string[]).includes(trump) || !history || !history.length) return null;
  const partner = PARTNERS[player];
  const out = shownOut(history, []);
  if (out[partner].has(trump)) return null;
  let cards = hand.filter((c) => c.suit !== trump && out[partner].has(c.suit));
  if (!cards.length && SHORT_LEAD_RETURN) {
    const suit = shortLead(player, hand, trump, history, visible, shown);
    cards = hand.filter((c) => c.suit === suit);
  }
  return cards.length ? minBy(cards, (c) => [value(c), suitIndex(c.suit)]) : null;
}

function comb(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  let r = 1;
  for (let i = 0; i < k; i++) r = (r * (n - i)) / (i + 1);
  return r;
}

/** The suit of partner's opening lead if it was a singleton at least
 *  SHORT_LEAD_PCT percent of the time (see ai.py `_short_lead`). */
function shortLead(player: Seat, hand: Card[], trump: string, history: AnyPlay[][],
  visible: Partial<Record<Seat, Card[]>>, shown: Shown | null): string | null {
  const [partner, lead] = history[0][0];
  if (partner !== PARTNERS[player]) return null;
  const suit = lead.suit;
  if (suit === trump || (shown?.[partner as Seat]?.[suit as Suit] ?? 0) >= 2) return null;
  if (history.slice(1).some((plays) => plays.some(([p, c]) => p === partner && c.suit === suit))) return null;
  const dummySeat = (Object.keys(visible) as Seat[]).find((p) => p !== player);
  if (dummySeat === undefined) return null;
  const dummy = visible[dummySeat]!;
  const declarer = PLAYERS.find((p) => p !== player && p !== partner && p !== dummySeat)!;
  const seen = new Set<string>([...hand, ...dummy].map(cardKey));
  for (const plays of history) for (const [, c] of plays) seen.add(cardKey(c));
  const unseen = FULL_DECK.filter((c) => !seen.has(cardKey(c)));
  const higher = unseen.filter((c) => c.suit === suit && value(c) > value(lead)).length;
  const lower = unseen.filter((c) => c.suit === suit && value(c) < value(lead)).length;
  const others = unseen.filter((c) => c.suit !== suit).length;
  let held = 13;
  for (const plays of history) for (const [p] of plays) if (p === partner) held--;
  const floor = Math.max(0, (shown?.[declarer]?.[suit as Suit] ?? 0) - playedIn(declarer, suit, history, []));
  const total = higher + lower;
  const single = total >= floor ? comb(others, held) : 0;
  let longer = 0;
  if (value(lead) >= SHORT_LEAD_HONOUR) {
    // An honour's card says nothing: any split counts (see ai.py).
    for (let k = 1; k <= total; k++) {
      if (total - k >= floor && held - k >= 0) longer += comb(total, k) * comb(others, held - k);
    }
  } else {
    for (let j = 0; j <= lower; j++) {
      if (total - 1 - j >= floor && held - 1 - j >= 0) longer += higher * comb(lower, j) * comb(others, held - 1 - j);
    }
  }
  if (single === 0 || 100 * single < SHORT_LEAD_PCT * (single + longer)) return null;
  return suit;
}

function shownOut(history: AnyPlay[][], trick: AnyPlay[]): Record<string, Set<string>> {
  const out: Record<string, Set<string>> = {};
  for (const p of PLAYERS) out[p] = new Set();
  for (const plays of [...history, trick]) {
    if (!plays.length) continue;
    const ledSuit = plays[0][1].suit;
    for (const [seat, c] of plays.slice(1)) if (c.suit !== ledSuit) out[seat].add(ledSuit);
  }
  return out;
}

function search(hands: Record<string, Card[]>, trick: AnyPlay[], leader: Seat,
  trump: string | null, side: string, memo: Map<string, number>): number {
  if (trick.length === 4) {
    const winner = resolveTrick(trick, trump) as Seat;
    const won = PARTNERSHIP[winner] === side ? 1 : 0;
    if (!hands[winner].length) return won;
    return won + search(hands, [], winner, trump, side, memo);
  }
  let key: string | null = null;
  if (!trick.length) {
    key = leader + '|' + PLAYERS.map((p) => hands[p].map(cardOrder)
      .sort((a, b) => a[0] - b[0] || a[1] - b[1]).map((o) => o.join('.')).join(',')).join('|');
    const hit = memo.get(key);
    if (hit !== undefined) return hit;
  }
  const seat = PLAYERS[(PLAYERS.indexOf(leader) + trick.length) % 4];
  const ledSuit = trick.length ? trick[0][1].suit : null;
  const ours = PARTNERSHIP[seat] === side;
  let best = ours ? -1 : 99;
  for (const c of legalPlays(hands[seat], ledSuit)) {
    const at = hands[seat].findIndex((x) => cardKey(x) === cardKey(c));
    hands[seat].splice(at, 1);
    const v = search(hands, [...trick, [seat, c]], leader, trump, side, memo);
    hands[seat].splice(at, 0, c);
    best = ours ? Math.max(best, v) : Math.min(best, v);
  }
  if (key !== null) memo.set(key, best);
  return best;
}

// ── The same search on bit patterns (see ai.py `_bit_search`) ─────────────
//
// A hand is four 13-bit suit masks (rank 0 = the 2), so legal moves, rank
// equivalence and position keys are integer operations. JS bit operators are
// 32-bit, so a 52-bit hand as in ai.py doesn't fit one number; four masks do.
// Same answers as `search`, so the same cards are played, faster.

/** hands[4 * seat + suit], seats in PLAYERS order, suits in SUITS order. */
type BitHands = number[];
/** A play in a trick: seat * 64 + 13 * suit + rank. */
const NS_SEAT = [true, false, true, false];
/** The seat winning a full trick: resolveTrick's rule on bit numbers. */
function bitWinner(trick: number[], trump: number): number {
  let suit = ((trick[0] & 63) / 13) | 0;
  if (trump >= 0 && trick.some((t) => (((t & 63) / 13) | 0) === trump)) suit = trump;
  let top = -1, second = -1, topSeat = -1, secondSeat = -1;
  for (const t of trick) {
    const b = t & 63;
    if (((b / 13) | 0) !== suit) continue;
    if (b > top) { second = top; secondSeat = topSeat; top = b; topSeat = t >> 6; }
    else if (b > second) { second = b; secondSeat = t >> 6; }
  }
  return second >= 0 ? secondSeat : topSeat;
}

/** The memory's key: the leader and each suit's unplayed cards renumbered
 *  0, 1, 2, ... from the lowest, since a position's value depends only on how
 *  the cards still out rank against each other (see ai.py `_relative`). */
function relativeKey(leader: number, hands: BitHands): string {
  const out = new Array<number>(16).fill(0);
  for (let suit = 0; suit < 4; suit++) {
    const m0 = hands[suit], m1 = hands[4 + suit], m2 = hands[8 + suit], m3 = hands[12 + suit];
    let left = m0 | m1 | m2 | m3;
    let bit = 1;
    while (left) {
      const low = left & -left;
      left ^= low;
      if (m0 & low) out[suit] |= bit;
      else if (m1 & low) out[4 + suit] |= bit;
      else if (m2 & low) out[8 + suit] |= bit;
      else out[12 + suit] |= bit;
      bit <<= 1;
    }
  }
  return String.fromCharCode(leader, ...out);
}

/** Tricks for N/S from here, both sides perfect (see ai.py `_bit_search`).
 *  The memo holds (lo, hi) bounds packed as lo * 16 + hi; `trump` is -1 in NT. */
function bitSearch(hands: BitHands, trick: number[], leader: number, trump: number,
  memo: Map<string, number>, alpha = -1, beta = 14): number {
  if (trick.length === 4) {
    const winner = bitWinner(trick, trump);
    const won = NS_SEAT[winner] ? 1 : 0;
    const w = 4 * winner;
    if (!(hands[w] | hands[w + 1] | hands[w + 2] | hands[w + 3])) return won;
    return won + bitSearch(hands, [], winner, trump, memo, alpha - won, beta - won);
  }
  let key: string | null = null;
  if (!trick.length) {
    key = relativeKey(leader, hands);
    const hit = memo.get(key) ?? 13;
    const lo = hit >> 4, hi = hit & 15;
    if (lo >= beta || lo === hi) return lo; // known exactly: never search an empty window
    if (hi <= alpha) return hi;
    if (lo > alpha) alpha = lo;
    if (hi < beta) beta = hi;
  }
  const a0 = alpha, b0 = beta;
  const seat = (leader + trick.length) % 4;
  const s4 = 4 * seat;
  let only = -1;
  if (trick.length) {
    const led = ((trick[0] & 63) / 13) | 0;
    if (hands[s4 + led]) only = led;
  }
  const ours = NS_SEAT[seat];
  let best = ours ? -1 : 99;
  outer:
  for (let suit = 0; suit < 4; suit++) {
    if (only >= 0 && suit !== only) continue;
    const held = hands[s4 + suit];
    let mine = held;
    if (!mine) continue;
    let rest = 0;
    for (let p = 0; p < 4; p++) if (p !== seat) rest |= hands[4 * p + suit];
    for (const t of trick) {
      const b = t & 63;
      if (((b / 13) | 0) === suit) rest |= 1 << (b - 13 * suit);
    }
    let previous = -1;
    while (mine) {
      const low = mine & -mine;
      mine ^= low;
      const r = 31 - Math.clz32(low);
      // One card from each run with no other unplayed card between.
      if (previous >= 0 && !(rest & (((1 << r) - 1) ^ ((1 << (previous + 1)) - 1)))) {
        previous = r;
        continue;
      }
      previous = r;
      hands[s4 + suit] = held ^ low;
      trick.push(seat * 64 + 13 * suit + r);
      const v = bitSearch(hands, trick, leader, trump, memo, alpha, beta);
      trick.pop();
      hands[s4 + suit] = held;
      if (ours) { if (v > best) { best = v; if (best > alpha) alpha = best; } }
      else if (v < best) { best = v; if (best < beta) beta = best; }
      if (alpha >= beta) break outer;
    }
  }
  if (key !== null) {
    const hit = memo.get(key) ?? 13;
    let lo = hit >> 4, hi = hit & 15;
    if (best <= a0) hi = Math.min(hi, best);
    else if (best >= b0) lo = Math.max(lo, best);
    else { lo = best; hi = best; }
    memo.set(key, lo * 16 + hi);
  }
  return best;
}

function* combinations(n: number, k: number): Generator<number[]> {
  const idx = Array.from({ length: k }, (_, i) => i);
  if (k > n) return;
  while (true) {
    yield [...idx];
    let i = k - 1;
    while (i >= 0 && idx[i] === i + n - k) i--;
    if (i < 0) return;
    idx[i]++;
    for (let j = i + 1; j < k; j++) idx[j] = idx[j - 1] + 1;
  }
}

function endgameTotals(player: Seat, hand: Card[], trick: AnyPlay[], trump: string | null,
  played: Card[], visible: Partial<Record<Seat, Card[]>>, history: AnyPlay[][],
  legal: Card[], shown: Shown | null = null): Map<string, number> | null {
  const known: Record<string, Card[]> = { [player]: [...hand] };
  const seen = new Set([...played, ...trick.map(([, c]) => c), ...hand].map(cardKey));
  for (const [seat, cards] of Object.entries(visible) as [Seat, Card[]][]) {
    if (seat !== player) {
      known[seat] = [...cards];
      for (const c of cards) seen.add(cardKey(c));
    }
  }
  const hidden = PLAYERS.filter((p) => !(p in known));
  const already = new Set(trick.map(([seat]) => seat));
  const size: Record<string, number> = {};
  for (const p of PLAYERS) size[p] = hand.length - (already.has(p) ? 1 : 0);
  const unseen = FULL_DECK.filter((c) => !seen.has(cardKey(c)))
    .sort((a, b) => suitIndex(a.suit) - suitIndex(b.suit) || value(a) - value(b));
  if (hidden.length !== 2 || unseen.length !== size[hidden[0]] + size[hidden[1]]) return null;
  const [first, second] = hidden;
  const out = shownOut(history, trick);
  const leader = (trick.length ? trick[0][0] : player) as Seat;
  const side = PARTNERSHIP[player];
  const totals = new Map<string, number>(legal.map((c) => [cardKey(c), 0]));
  let layouts = 0;
  for (const picked of combinations(unseen.length, size[first])) {
    const chosen = new Set(picked);
    const a = unseen.filter((_, i) => chosen.has(i));
    const b = unseen.filter((_, i) => !chosen.has(i));
    if (a.some((c) => out[first].has(c.suit)) || b.some((c) => out[second].has(c.suit))) continue;
    if (shown && !(fitsAuction(first, a, history, trick, shown)
      && fitsAuction(second, b, history, trick, shown))) continue;
    layouts++;
    const hands: Record<string, Card[]> = {};
    for (const [seat, cards] of Object.entries(known)) hands[seat] = [...cards];
    hands[first] = a;
    hands[second] = b;
    const masks: BitHands = new Array(16).fill(0);
    for (const p of PLAYERS) {
      for (const c of hands[p]) masks[4 * PLAYERS.indexOf(p) + suitIndex(c.suit)] |= 1 << value(c);
    }
    const bitsTrick = trick.map(([p, c]) => PLAYERS.indexOf(p as Seat) * 64 + 13 * suitIndex(c.suit) + value(c));
    const trumpBit = trump !== null && (SUITS as readonly string[]).includes(trump) ? suitIndex(trump as Suit) : -1;
    const bounds = SHARED_POSITIONS ? positionMemo(trumpBit) : new Map<string, number>();
    const me = PLAYERS.indexOf(player);
    let cardsLeft = trick.length;
    for (const p of PLAYERS) cardsLeft += hands[p].length;
    const left = cardsLeft / 4;
    for (const c of legal) {
      const at = 4 * me + suitIndex(c.suit);
      masks[at] ^= 1 << value(c);
      const ns = bitSearch(masks, [...bitsTrick, me * 64 + 13 * suitIndex(c.suit) + value(c)],
        PLAYERS.indexOf(leader), trumpBit, bounds);
      totals.set(cardKey(c), totals.get(cardKey(c))! + (side === 'N/S' ? ns : left - ns));
      masks[at] ^= 1 << value(c);
    }
  }
  return layouts ? totals : null;
}

// ── Declarer draws trumps (see ai.py) ────────────────────────────────────────

export const DRAW_TRUMPS = true;

type Trumps = readonly number[];

/** One card from each run of `cards` with none of `others` in between (see ai.py). */
function distinct(cards: Trumps, others: Trumps): number[] {
  const keep: number[] = [];
  let previous: number | null = null;
  for (const card of [...cards].sort((a, b) => a - b)) {
    if (previous === null || others.some((v) => previous! < v && v < card)) keep.push(card);
    previous = card;
  }
  return keep;
}

/** A seat's distinct cards in the suit, or a discard when it has none. */
function suitOptions(cards: Trumps, others: Trumps): (number | null)[] {
  return cards.length ? distinct(cards, others) : [null];
}

/** Trump tricks the defence wins before running out, trumps led throughout. */
function trumpLosers(ours: [Trumps, Trumps], theirs: [Trumps, Trumps], leader: number,
  memo: Map<string, number>): number {
  if (!theirs[0].length && !theirs[1].length) return 0;
  if (!ours[0].length && !ours[1].length) return theirs[0].length + theirs[1].length;
  const all = [...ours[0], ...ours[1], ...theirs[0], ...theirs[1]].sort((a, b) => a - b);
  const order = new Map(all.map((v, i) => [v, i]));
  const ranks = (cards: Trumps) => cards.map((v) => order.get(v)).join(',');
  const key = `${ranks(ours[0])}|${ranks(ours[1])}|${ranks(theirs[0])}|${ranks(theirs[1])}|${leader}`;
  const hit = memo.get(key);
  if (hit !== undefined) return hit;
  const [leadHand, partner] = leader === 0 ? [ours[0], ours[1]] : [ours[1], ours[0]];
  const [left, right] = leader === 0 ? [theirs[0], theirs[1]] : [theirs[1], theirs[0]];
  if (!leadHand.length) {
    const result = trumpLosers(ours, theirs, 1 - leader, memo);
    memo.set(key, result);
    return result;
  }
  const drop = (cards: Trumps, c: number | null): Trumps => (c === null ? cards : cards.filter((x) => x !== c));

  let best: number | null = null;
  for (const a of distinct(leadHand, [...partner, ...left, ...right])) {
    let worst: number | null = null;
    for (const b of suitOptions(left, [...leadHand, ...partner, ...right])) {
      let oursBest: number | null = null;
      for (const c of suitOptions(partner, [...leadHand, ...left, ...right])) {
        let defenceBest: number | null = null;
        for (const d of suitOptions(right, [...leadHand, ...partner, ...left])) {
          const winner = trickWinner([a, b, c, d]);
          const newLead = drop(leadHand, a);
          const newPartner = drop(partner, c);
          const newLeft = drop(left, b);
          const newRight = drop(right, d);
          const newOurs: [Trumps, Trumps] = leader === 0 ? [newLead, newPartner] : [newPartner, newLead];
          const newTheirs: [Trumps, Trumps] = leader === 0 ? [newLeft, newRight] : [newRight, newLeft];
          let v: number;
          if (winner === 0 || winner === 2) {
            v = trumpLosers(newOurs, newTheirs, winner === 0 ? leader : 1 - leader, memo);
          } else if (newOurs[0].length || newOurs[1].length) {
            v = 1 + Math.min(...[0, 1].filter((h) => newOurs[h].length)
              .map((h) => trumpLosers(newOurs, newTheirs, h, memo)));
          } else {
            v = 1 + newTheirs[0].length + newTheirs[1].length;
          }
          if (defenceBest === null || v > defenceBest) defenceBest = v;
        }
        if (oursBest === null || defenceBest! < oursBest) oursBest = defenceBest;
      }
      if (worst === null || oursBest! > worst) worst = oursBest;
    }
    if (best === null || worst! < best) best = worst;
  }
  memo.set(key, best!);
  return best!;
}

/** Who wins a trick of trumps, by position in play order; null means a discard. */
function trickWinner(played: (number | null)[]): number {
  const trumps = played.map((v, who) => [v, who] as const).filter(([v]) => v !== null)
    .sort((x, y) => x[0]! - y[0]! || x[1] - y[1]);
  return trumps.length === 1 ? trumps[0][1] : trumps[trumps.length - 2][1];
}

/** Trump losers once `led` is on the table (see ai.py `_after_lead`). */
function afterLead(led: number, rest: Trumps, partner: Trumps, left: Trumps, right: Trumps,
  memo: Map<string, number>): number {
  const leadHand = [...rest, led];
  let worst: number | null = null;
  for (const b of suitOptions(left, [...leadHand, ...partner, ...right])) {
    let oursBest: number | null = null;
    for (const c of suitOptions(partner, [...leadHand, ...left, ...right])) {
      let defenceBest: number | null = null;
      for (const d of suitOptions(right, [...leadHand, ...partner, ...left])) {
        const winner = trickWinner([led, b, c, d]);
        const newOurs: [Trumps, Trumps] = [rest, partner.filter((x) => x !== c)];
        const newTheirs: [Trumps, Trumps] = [left.filter((x) => x !== b), right.filter((x) => x !== d)];
        let v: number;
        if (winner === 0 || winner === 2) {
          v = trumpLosers(newOurs, newTheirs, winner === 0 ? 0 : 1, memo);
        } else if (newOurs[0].length || newOurs[1].length) {
          v = 1 + Math.min(...[0, 1].filter((h) => newOurs[h].length)
            .map((h) => trumpLosers(newOurs, newTheirs, h, memo)));
        } else {
          v = 1 + newTheirs[0].length + newTheirs[1].length;
        }
        if (defenceBest === null || v > defenceBest) defenceBest = v;
      }
      if (oursBest === null || defenceBest! < oursBest) oursBest = defenceBest;
    }
    if (worst === null || oursBest! > worst) worst = oursBest;
  }
  return worst!;
}

/** Every way the defence's cards in `suit` can lie, as [left, right, weight] (see ai.py). */
function splits(player: Seat, hand: Card[], suit: Suit, outstanding: number[], seen: Set<string>,
  history: AnyPlay[][] | null, shown: Shown | null = null): [Trumps, Trumps, number][] {
  const left = PLAYERS[(PLAYERS.indexOf(player) + 1) % 4];
  const right = PLAYERS[(PLAYERS.indexOf(player) + 3) % 4];
  const out = shownOut(history ?? [], []);
  const gone: Record<string, number> = {};
  for (const p of PLAYERS) gone[p] = playedIn(p, suit, history ?? [], []);
  const unseen = FULL_DECK.filter((c) => !seen.has(cardKey(c))).length;
  const slots = hand.length;
  const others = unseen - outstanding.length;
  const sorted = [...outstanding].sort((a, b) => a - b);
  const layouts: [Trumps, Trumps, number][] = [];
  for (let n = 0; n <= sorted.length; n++) {
    for (const picked of combinations(sorted.length, n)) {
      const leftCards = picked.map((i) => sorted[i]);
      const rightCards = sorted.filter((v) => !leftCards.includes(v));
      if ((leftCards.length && out[left].has(suit)) || (rightCards.length && out[right].has(suit))) continue;
      if (leftCards.length > slots || rightCards.length > slots) continue;
      if (shown && (leftCards.length + gone[left] < (shown[left]?.[suit] ?? 0)
        || rightCards.length + gone[right] < (shown[right]?.[suit] ?? 0))) continue;
      const weight = choose(others, slots - leftCards.length);
      if (weight) layouts.push([leftCards, rightCards, weight]);
    }
  }
  return layouts;
}

// ── Declarer runs a long suit (see ai.py) ────────────────────────────────────

export const RUN_LONG_SUIT = true;
export const RUN_MAX_LOSERS = 0.5;

/** A lead that runs the partnership's long suit without loss, or null (see ai.py). */
function runLongSuit(player: Seat, hand: Card[], trump: string | null, played: Card[],
  visible: Partial<Record<Seat, Card[]>>, history: AnyPlay[][] | null,
  shown: Shown | null = null): Card | null {
  const partner = PARTNERS[player];
  if (!Object.keys(visible).length || !(partner in visible)) return null;
  const partnerHand = visible[partner]!;
  const seen = new Set([...played, ...hand, ...partnerHand].map(cardKey));
  if (isSuit(trump) && FULL_DECK.some((c) => c.suit === trump && !seen.has(cardKey(c)))) return null;
  let best: [number[], Card] | null = null;
  for (const suit of SUITS) {
    if (suit === trump) continue;
    const mine = hand.filter((c) => c.suit === suit).map(value).sort((a, b) => a - b);
    const theirsPartner = partnerHand.filter((c) => c.suit === suit).map(value).sort((a, b) => a - b);
    if (!mine.length) continue;
    const outstanding = FULL_DECK.filter((c) => c.suit === suit && !seen.has(cardKey(c))).map(value);
    if (outstanding.length && mine.length + theirsPartner.length < 7) continue;
    const tricks = Math.max(mine.length, theirsPartner.length);
    const cards = hand.filter((c) => c.suit === suit).sort((a, b) => value(a) - value(b));
    let expected: number;
    let lead: Card;
    if (outstanding.length) {
      const layouts = splits(player, hand, suit, outstanding, seen, history, shown);
      if (!layouts.length) continue;
      const memo = new Map<string, number>();
      const scored: [number, number, number, Card][] = [];
      for (const c of cards) {
        let total = 0;
        let weights = 0;
        let worst = 0;
        for (const [leftCards, rightCards, weight] of layouts) {
          const losers = afterLead(value(c), mine.filter((v) => v !== value(c)), theirsPartner,
            leftCards, rightCards, memo);
          total += losers * weight;
          weights += weight;
          worst = Math.max(worst, losers);
        }
        // Ties go to the highest card (see ai.py).
        scored.push([total / weights, worst, -value(c), c]);
      }
      const pick = minBy(scored, (t) => [t[0], t[1], t[2]]);
      expected = pick[0];
      lead = pick[3];
    } else {
      expected = 0;
      lead = cards[cards.length - 1];
    }
    if (expected > RUN_MAX_LOSERS) continue;
    const rank = [tricks - expected, -suitIndex(suit)];
    if (best === null || compareRank(rank, best[0]) > 0) best = [rank, lead];
  }
  return best ? best[1] : null;
}

// ── Defender cashes a sure trick (see ai.py) ─────────────────────────────────

export const SURE_LEAD = true;

/** The lowest card that wins the trick on every layout, or null (see ai.py). */
function sureLead(player: Seat, hand: Card[], trump: string | null, played: Card[],
  visible: Partial<Record<Seat, Card[]>>, history: AnyPlay[][] | null): Card | null {
  const partner = PARTNERS[player];
  if (!Object.keys(visible).length || partner in visible || player in visible) return null;
  const dummy = Object.keys(visible)[0] as Seat;
  const dummyHand = visible[dummy]!;
  const seen = new Set([...played, ...hand, ...dummyHand].map(cardKey));
  const unseen = FULL_DECK.filter((c) => !seen.has(cardKey(c)));
  const out = shownOut(history ?? [], []);
  const hidden = PLAYERS.filter((p) => p !== player && p !== dummy);
  const order = [1, 2, 3].map((k) => PLAYERS[(PLAYERS.indexOf(player) + k) % 4]);
  const ours = [player, partner] as string[];
  const slots = hand.length;
  const ruffing = isSuit(trump) ? trump : null;

  const candidates = [...hand].sort((a, b) => value(a) - value(b) || suitIndex(a.suit) - suitIndex(b.suit));
  for (const c of candidates) {
    const led = c.suit;
    const follows = unseen.filter((x) => x.suit === led);
    const trumps = ruffing && ruffing !== led ? unseen.filter((x) => x.suit === ruffing) : [];
    const trumpKeys = new Set(trumps.map(cardKey));
    const discard = card(SUITS.find((s) => s !== led && s !== ruffing)!, '2');

    const loses = (at: number, plays: AnyPlay[], options: Record<string, Card[]>,
      used: Set<string>): boolean => {
      if (at === 3) return !ours.includes(resolveTrick(plays, trump));
      const seat = order[at];
      for (const x of options[seat]) {
        if (used.has(cardKey(x))) continue;
        // Both hidden seats may be void: they can't ruff with the same trump.
        const next = trumpKeys.has(cardKey(x)) ? new Set([...used, cardKey(x)]) : used;
        if (loses(at + 1, [...plays, [seat, x]], options, next)) return true;
      }
      return false;
    };

    let sure = true;
    for (let n = 0; n <= follows.length && sure; n++) {
      for (const picked of combinations(follows.length, n)) {
        const chosen = new Set(picked);
        const held: Record<string, Card[]> = {
          [hidden[0]]: follows.filter((_, i) => chosen.has(i)),
          [hidden[1]]: follows.filter((_, i) => !chosen.has(i)),
        };
        if (hidden.some((p) => held[p].length && out[p].has(led))) continue;
        if (hidden.some((p) => held[p].length > slots)) continue;
        const options: Record<string, Card[]> = { [dummy]: legalPlays(dummyHand, led) };
        for (const p of hidden) {
          options[p] = held[p].length ? held[p]
            : [discard, ...(ruffing && !out[p].has(ruffing) ? trumps : [])];
        }
        if (loses(0, [[player, c]], options, new Set())) {
          sure = false;
          break;
        }
      }
    }
    if (sure) return c;
  }
  return null;
}

// ── Four rules from the user's review of deals 92, 156 and 174 (see ai.py) ───

export const SURE_LEAD_DECLARER = true;
export const RUFF_LEAD = false;
export const FORCE_DUMMY = false;
export const DEAD_CARD_LAST = true;
/** Of the cards that win the trick, fourth hand spends a dead one first (see ai.py). */
export const DEAD_WINNER_FIRST = true;

/** No other seat can play a higher card of this suit: every one is gone or ours. */
function dead(c: Card, hand: Card[], gone: Set<string>): boolean {
  const mine = new Set(hand.map(cardKey));
  return FULL_DECK.every((x) => x.suit !== c.suit || value(x) <= value(c)
    || gone.has(cardKey(x)) || mine.has(cardKey(x)));
}

/** The card of a suit to give up first: the lowest dead card, else the lowest. */
function shedFirst(cards: Card[], hand: Card[], played: Card[]): Card {
  const gone = new Set(played.map(cardKey));
  const deadOnes = cards.filter((c) => dead(c, hand, gone));
  return minBy(deadOnes.length ? deadOnes : cards, (c) => [value(c)]);
}

/** A lead for partner to ruff, once the defence has no trumps, or null (see ai.py). */
function ruffLead(player: Seat, hand: Card[], trump: string | null, played: Card[],
  visible: Partial<Record<Seat, Card[]>>): Card | null {
  const partner = PARTNERS[player];
  if (!isSuit(trump) || !Object.keys(visible).length || !(partner in visible)) return null;
  const partnerHand = visible[partner]!;
  const seen = new Set([...played, ...hand, ...partnerHand].map(cardKey));
  if (FULL_DECK.some((c) => c.suit === trump && !seen.has(cardKey(c)))) return null;
  if (!partnerHand.some((c) => c.suit === trump)) return null;
  const gone = new Set(played.map(cardKey));
  let best: [number[], Card] | null = null;
  for (const suit of SUITS) {
    if (suit === trump || partnerHand.some((c) => c.suit === suit)) continue;
    const cards = hand.filter((c) => c.suit === suit);
    if (!cards.length) continue;
    const hasDead = cards.some((c) => dead(c, hand, gone)) ? 1 : 0;
    const rank = [hasDead, cards.length, -suitIndex(suit)];
    if (best === null || compareRank(rank, best[0]) > 0) best = [rank, shedFirst(cards, hand, played)];
  }
  return best ? best[1] : null;
}

/** The lowest card of `suit` that wins the trick on every layout, or null:
 *  card choice within a suit already chosen, for the declaring side (see ai.py). */
function sureLeadDeclarer(player: Seat, hand: Card[], trump: string | null, played: Card[],
  visible: Partial<Record<Seat, Card[]>>, history: AnyPlay[][] | null, suit: string): Card | null {
  const partner = PARTNERS[player];
  if (!Object.keys(visible).length || !(partner in visible)) return null;
  const partnerHand = visible[partner]!;
  const seen = new Set([...played, ...hand, ...partnerHand].map(cardKey));
  const unseen = FULL_DECK.filter((c) => !seen.has(cardKey(c)));
  const out = shownOut(history ?? [], []);
  const i = PLAYERS.indexOf(player);
  const left = PLAYERS[(i + 1) % 4];
  const right = PLAYERS[(i + 3) % 4];
  const ours = [player, partner] as string[];
  const slots = hand.length;
  const ruffing = isSuit(trump) ? trump : null;

  const candidates = hand.filter((c) => c.suit === suit).sort((a, b) => value(a) - value(b));
  for (const c of candidates) {
    const led = c.suit;
    if (led === ruffing) continue;      // trumps are drawTrump's
    const follows = unseen.filter((x) => x.suit === led);
    const trumps = ruffing && ruffing !== led ? unseen.filter((x) => x.suit === ruffing) : [];
    const trumpKeys = new Set(trumps.map(cardKey));
    const discard = unseen.filter((x) => x.suit !== led && x.suit !== ruffing).slice(0, 1);
    const rest = hand.filter((x) => cardKey(x) !== cardKey(c));
    const partnerView: Partial<Record<Seat, Card[]>> = { [player]: rest, [partner]: partnerHand };
    const replies = new Map<string, Card>();
    const partnerCard = (b: Card): Card => {
      if (!replies.has(cardKey(b))) {
        const trick: AnyPlay[] = [[player, c], [left, b]];
        const legal = legalPlays(partnerHand, led);
        const later = laterHoldings(partner, partnerHand, trick, played, partnerView);
        replies.set(cardKey(b), middlePlay(partner, legal, trick, trump, later));
      }
      return replies.get(cardKey(b))!;
    };

    let sure = true;
    for (let n = 0; n <= follows.length && sure; n++) {
      for (const picked of combinations(follows.length, n)) {
        const chosen = new Set(picked);
        const held: Record<string, Card[]> = {
          [left]: follows.filter((_, k) => chosen.has(k)),
          [right]: follows.filter((_, k) => !chosen.has(k)),
        };
        if ([left, right].some((p) => held[p].length && out[p].has(led))) continue;
        if ([left, right].some((p) => held[p].length > slots)) continue;
        const options: Record<string, Card[]> = {};
        for (const p of [left, right]) {
          options[p] = held[p].length ? held[p]
            : [...discard, ...(ruffing && !out[p].has(ruffing) ? trumps : [])];
        }
        for (const b of options[left]) {
          const pc = partnerCard(b);
          for (const d of options[right]) {
            // Both hidden seats can't ruff with the same trump.
            if (cardKey(d) === cardKey(b) && trumpKeys.has(cardKey(d))) continue;
            const plays: AnyPlay[] = [[player, c], [left, b], [partner, pc], [right, d]];
            if (!ours.includes(resolveTrick(plays, trump))) { sure = false; break; }
          }
          if (!sure) break;
        }
        if (!sure) break;
      }
    }
    if (sure) return c;
  }
  return null;
}

/** A defender's lead in a suit dummy is void in while dummy has trumps, or null (see ai.py). */
function forceDummy(player: Seat, hand: Card[], trump: string | null,
  visible: Partial<Record<Seat, Card[]>>, played: Card[]): Card | null {
  if (!isSuit(trump) || !Object.keys(visible).length || PARTNERS[player] in visible) return null;
  const dummy = Object.keys(visible)[0] as Seat;
  const dummyHand = visible[dummy]!;
  if (!dummyHand.some((c) => c.suit === trump)) return null;
  let best: [number[], Card] | null = null;
  for (const suit of SUITS) {
    if (suit === trump || dummyHand.some((c) => c.suit === suit)) continue;
    const cards = hand.filter((c) => c.suit === suit);
    if (!cards.length) continue;
    const rank = [cards.length, -suitIndex(suit)];
    if (best === null || compareRank(rank, best[0]) > 0) best = [rank, shedFirst(cards, hand, played)];
  }
  return best ? best[1] : null;
}

// ── Defenders lead long suits in notrump (see ai.py) ─────────────────────────

export const NT_LONG_LEAD = true;
export const NT_LONG_LEAD_OPENING_ONLY = false;

/** A defender's lead from its longest suit in notrump, or null (see ai.py). */
function ntLongLead(player: Seat, hand: Card[], trump: string | null, played: Card[],
  visible: Partial<Record<Seat, Card[]>>): Card | null {
  if (isSuit(trump) || (Object.keys(visible).length && PARTNERS[player] in visible)) return null;
  if (NT_LONG_LEAD_OPENING_ONLY && played.length) return null;
  const groups = new Map<Suit, Card[]>();
  for (const c of hand) {
    if (!groups.has(c.suit)) groups.set(c.suit, []);
    groups.get(c.suit)!.push(c);
  }
  const longest = Math.max(...[...groups.values()].map((cards) => cards.length));
  if (longest < 4) return null;
  const tied = [...groups.keys()].filter((s) => groups.get(s)!.length === longest);
  const best = maxBy(tied, (s) => [-gap(s, hand, played), suitIndex(s)]);
  const cards = [...groups.get(best)!].sort((a, b) => value(b) - value(a));
  return cards[1];
}

function choose(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  let result = 1;
  for (let i = 0; i < k; i++) result = Math.floor(result * (n - i) / (i + 1));
  return result;
}

const NO_DRAW = Symbol('no draw');

/** Ruffs in the short-trump hand that drawing trumps would throw away (see ai.py). */
function ruffFirst(hand: Card[], partnerHand: Card[], trump: Suit, outstanding: number): Card | typeof NO_DRAW | null {
  const mine = hand.filter((c) => c.suit === trump);
  const theirs = partnerHand.filter((c) => c.suit === trump);
  if (mine.length === theirs.length) return null;
  const [longHand, shortHand] = mine.length > theirs.length ? [hand, partnerHand] : [partnerHand, hand];
  const shortTrumps = Math.min(mine.length, theirs.length);
  let ruffs = 0;
  let target: [number[], Card] | null = null;
  for (const suit of SUITS) {
    if (suit === trump) continue;
    const longCards = longHand.filter((c) => c.suit === suit);
    const shortCount = shortHand.filter((c) => c.suit === suit).length;
    if (shortCount <= 1 && longCards.length > shortCount) {
      ruffs += longCards.length - shortCount;
      const rank = [shortCount, -longCards.length, suitIndex(suit)];
      if (target === null || compareRank(rank, target[0]) < 0) {
        target = [rank, minBy(longCards, (c) => [value(c)])];
      }
    }
  }
  const rounds = Math.floor((outstanding + 1) / 2);
  if (!ruffs || shortTrumps - rounds >= ruffs) return null;
  return longHand === hand ? target![1] : NO_DRAW;
}

function compareRank(a: number[], b: number[]): number {
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  return 0;
}

/** The trump the declaring side should lead to draw trumps, or null (see ai.py). */
function drawTrump(player: Seat, hand: Card[], trump: string | null, played: Card[],
  visible: Partial<Record<Seat, Card[]>>, history: AnyPlay[][] | null,
  shown: Shown | null = null): Card | null {
  const partner = PARTNERS[player];
  if (!isSuit(trump) || !Object.keys(visible).length || !(partner in visible)) return null;
  const partnerHand = visible[partner]!;
  const mine = hand.filter((c) => c.suit === trump).map(value).sort((a, b) => a - b);
  const theirsPartner = partnerHand.filter((c) => c.suit === trump).map(value).sort((a, b) => a - b);
  if (!mine.length) return null;
  const seen = new Set([...played, ...hand, ...partnerHand].map(cardKey));
  const outstanding = FULL_DECK.filter((c) => c.suit === trump && !seen.has(cardKey(c))).map(value);
  if (!outstanding.length || mine.length + theirsPartner.length <= outstanding.length) return null;

  const ruff = ruffFirst(hand, partnerHand, trump, outstanding.length);
  if (ruff !== null) return ruff === NO_DRAW ? null : ruff;

  const layouts = splits(player, hand, trump, outstanding, seen, history, shown);
  if (!layouts.length) return null;

  const memo = new Map<string, number>();
  const scored: [number, number, number, Card][] = [];
  for (const c of hand.filter((x) => x.suit === trump).sort((a, b) => value(a) - value(b))) {
    let total = 0;
    let worst = 0;
    let weights = 0;
    for (const [leftTrumps, rightTrumps, weight] of layouts) {
      const losers = afterLead(value(c), mine.filter((v) => v !== value(c)), theirsPartner,
        leftTrumps, rightTrumps, memo);
      total += losers * weight;
      weights += weight;
      worst = Math.max(worst, losers);
    }
    scored.push([total / weights, worst, value(c), c]);
  }
  return minBy(scored, (t) => [t[0], t[1], t[2]])[3];
}

// ── Defender plans the suit it leads (see ai.py) ─────────────────────────────

export const DEFENDER_SUIT_PLAN = true;
export const SUIT_PLAN_MAX_UNSEEN = 9;

const RUFF = -1;                          // ai.py's _RUFF: a void seat ruffs
type PlanCard = number | null;            // a value, a discard (null) or RUFF
type PlanHands = readonly [Trumps, Trumps, Trumps, Trumps];
const SUIT_PLAN_MEMO = new Map<string, number>();

function planOptions(seat: number, hands: PlanHands, ruffs: readonly boolean[]): PlanCard[] {
  const cards = hands[seat];
  if (cards.length) return distinct(cards, hands.flatMap((h, k) => (k === seat ? [] : h)));
  return ruffs[seat] ? [null, RUFF] : [null];
}

function planTrick(hands: PlanHands, ruffs: readonly boolean[], plays: [number, PlanCard][],
  order: number[], memo: Map<string, number>): number {
  if (plays.length === 4) {
    const ruffers = plays.filter(([, c]) => c === RUFF).map(([seat]) => seat);
    let winner: number;
    if (ruffers.length) winner = ruffers[0];
    else {
      const ranked = plays.filter(([, c]) => c !== null)
        .map(([seat, c]) => [c as number, seat] as const)
        .sort((x, y) => x[0] - y[0] || x[1] - y[1]);
      winner = ranked.length === 1 ? ranked[0][1] : ranked[ranked.length - 2][1];
    }
    const put = new Map(plays);
    const left = [0, 1, 2, 3].map((k) => hands[k].filter((v) => v !== put.get(k))) as unknown as PlanHands;
    if (winner === 0 || winner === 2) return 1 + planSuit(left, ruffs, winner, memo);
    return planSuit(left, ruffs, null, memo);
  }
  const seat = order[plays.length];
  const values = planOptions(seat, hands, ruffs)
    .map((c) => planTrick(hands, ruffs, [...plays, [seat, c]], order, memo));
  return seat === 0 || seat === 2 ? Math.max(...values) : Math.min(...values);
}

/** Defence tricks in the suit, seats 0 and 2 the defence (see ai.py `_plan_suit`). */
function planSuit(hands: PlanHands, ruffs: readonly boolean[], leader: number | null,
  memo: Map<string, number>): number {
  if (!hands[0].length && !hands[2].length) return 0;
  if (leader !== null && !hands[leader].length) leader = 2 - leader;
  const order = new Map(hands.flat().sort((a, b) => a - b).map((v, i) => [v, i]));
  const key = `${hands.map((h) => h.map((v) => order.get(v)).join(',')).join('|')}|${ruffs.map(Number).join('')}|${leader}`;
  const hit = memo.get(key);
  if (hit !== undefined) return hit;
  const leaders = leader !== null ? [leader] : [0, 2].filter((k) => hands[k].length);
  let best = 0;
  for (const lead0 of leaders) {
    const seats = [0, 1, 2, 3].map((k) => (lead0 + k) % 4);
    for (const c of planOptions(lead0, hands, ruffs)) {
      best = Math.max(best, planTrick(hands, ruffs, [[lead0, c]], seats, memo));
    }
  }
  memo.set(key, best);
  return best;
}

/** The card of `choice`'s suit that takes the most tricks in it, or null (see ai.py). */
function defenderSuitPlan(player: Seat, hand: Card[], trump: string | null, played: Card[],
  visible: Partial<Record<Seat, Card[]>>, history: AnyPlay[][] | null, shown: Shown | null,
  choice: Card): Card | null {
  if (!Object.keys(visible).length || PARTNERS[player] in visible || player in visible) return null;
  const suit = choice.suit;
  if (isSuit(trump) && suit === trump) return null;
  const mine = hand.filter((c) => c.suit === suit);
  if (mine.length < 2) return null;
  const dummy = Object.keys(visible)[0] as Seat;
  const dummyHand = visible[dummy]!;
  const i = PLAYERS.indexOf(player);
  const seatOf = (p: Seat) => (PLAYERS.indexOf(p) - i + 4) % 4;
  const partner = PARTNERS[player];
  const declarer = PLAYERS.find((p) => p !== player && p !== partner && p !== dummy)!;
  const seen = new Set([...played, ...hand, ...dummyHand].map(cardKey));
  const unseenSuit = FULL_DECK.filter((c) => c.suit === suit && !seen.has(cardKey(c)))
    .map(value).sort((a, b) => a - b);
  if (unseenSuit.length > SUIT_PLAN_MAX_UNSEEN) return null;
  const out = shownOut(history ?? [], []);
  const ruffing = isSuit(trump);
  const ruffs = [false, false, false, false];
  ruffs[seatOf(dummy)] = ruffing && dummyHand.some((c) => c.suit === trump);
  ruffs[seatOf(declarer)] = ruffing && !out[declarer].has(trump!);
  const slots = hand.length;
  const others = FULL_DECK.filter((c) => !seen.has(cardKey(c))).length - unseenSuit.length;
  const floor = (p: Seat) => (shown?.[p]?.[suit] ?? 0) - playedIn(p, suit, history ?? [], []);
  const floorPartner = floor(partner);
  const floorDeclarer = floor(declarer);
  const dummyCards = dummyHand.filter((c) => c.suit === suit).map(value).sort((a, b) => a - b);
  const own = mine.map(value).sort((a, b) => a - b);
  const memo = SUIT_PLAN_MEMO;
  if (memo.size > POSITION_MEMO_MAX) memo.clear();
  const totals = new Map(mine.map((c) => [cardKey(c), 0]));
  let weights = 0;
  for (let n = 0; n <= unseenSuit.length; n++) {
    for (const picked of combinations(unseenSuit.length, n)) {
      const toPartner = picked.map((k) => unseenSuit[k]);
      const toDeclarer = unseenSuit.filter((v) => !toPartner.includes(v));
      if ((toPartner.length && out[partner].has(suit)) || (toDeclarer.length && out[declarer].has(suit))) continue;
      if (toPartner.length > slots || toDeclarer.length > slots) continue;
      if (toPartner.length < floorPartner || toDeclarer.length < floorDeclarer) continue;
      const weight = choose(others, slots - toPartner.length);
      if (!weight) continue;
      const hands: Trumps[] = [own, [], toPartner, []];
      hands[seatOf(dummy)] = dummyCards;
      hands[seatOf(declarer)] = toDeclarer;
      weights += weight;
      for (const c of mine) {
        totals.set(cardKey(c), totals.get(cardKey(c))!
          + weight * planTrick(hands as unknown as PlanHands, ruffs, [[0, value(c)]], [0, 1, 2, 3], memo));
      }
    }
  }
  if (!weights) return null;
  const best = Math.max(...totals.values());
  if (totals.get(cardKey(choice)) === best) return choice;
  return maxBy(mine.filter((c) => totals.get(cardKey(c)) === best), (c) => [value(c)]);
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

// ── Giving up a trick ── (ai.py: a void robot keeps its trumps, roadmap 3.11)

/** A void robot giving up a trick discards rather than throws a trump (measurement switch). */
export const KEEP_TRUMPS = true;

/** The card to play on a trick this hand isn't trying to win. */
function shed(legal: Card[], trump: string | null): Card {
  if (KEEP_TRUMPS) {
    const side = legal.filter((c) => c.suit !== trump);
    if (side.length) return minBy(side, (c) => [value(c)]);
  }
  return minBy(legal, (c) => [value(c)]);
}

/** Third hand counts an overruff threat by the chance the opponent is out of
 *  the led suit (see ai.py: challenge deal 276). */
export const RUFF_IF_FOLLOWS = true;

/** Port of ai._void_chance. */
function voidChanceOf(player: Seat, hand: Card[], trick: AnyPlay[], played: Card[],
  visible: Partial<Record<Seat, Card[]>>, history: AnyPlay[][],
  out: Record<string, Set<string>>): number {
  const i = PLAYERS.indexOf(player);
  const later: Seat[] = [];
  for (let k = 1; k < 4 - trick.length; k++) later.push(PLAYERS[(i + k) % 4]);
  const opponents = later.filter((p) => p !== PARTNERS[player]);
  if (!opponents.length) return 1.0;
  const opp = opponents[0];
  const led = trick[0][1].suit;
  if (opp in visible) return visible[opp]!.some((c) => c.suit === led) ? 0.0 : 1.0;
  if (out[opp]?.has(led)) return 1.0;
  const seen = new Set<string>([
    ...played.map(cardKey), ...trick.map(([, c]) => cardKey(c)), ...hand.map(cardKey)]);
  for (const h of Object.values(visible)) for (const c of h!) seen.add(cardKey(c));
  const unseen = FULL_DECK.filter((c) => c.suit === led && !seen.has(cardKey(c))).length;
  if (unseen === 0) return 1.0;
  const inTrick = new Set<string>(trick.map(([p]) => p));
  const size = (p: Seat) => 13 - history.length - (inTrick.has(p) ? 1 : 0);
  let rest = 0;
  for (const p of PLAYERS) {
    if (!(p in visible) && p !== player && p !== opp && !out[p]?.has(led)) rest += size(p);
  }
  if (rest < unseen) return 0.0;
  return comb(rest, unseen) / comb(rest + size(opp), unseen);
}

function middlePlay(player: Seat, legal: Card[], trick: AnyPlay[], trump: string | null,
  later: Card[], voidChance = 1.0): Card {
  const options: [number, number, Card][] = [];
  for (const c of legal) {
    const [holder, exposed] = outlook(player, c, trick, trump, later, voidChance);
    if ((holder === player || holder === PARTNERS[player]) && exposed <= 1) {
      options.push([exposed, value(c), c]);
    }
  }
  if (options.length) return minBy(options, (o) => [o[0], o[1]])[2];
  return shed(legal, trump);
}

/** Fourth hand counts partner's winning as its own (see ai.py). */
export const settingsPlay = { lastHandForPartner: true };

function playLast(legal: Card[], trick: AnyPlay[], trump: string | null,
  hand: Card[] | null = null, played: Card[] | null = null): Card {
  const partner = trick[1][0];
  const ours = settingsPlay.lastHandForPartner ? [AI_TAG, partner] : [AI_TAG];
  const winning = legal.filter((c) => ours.includes(resolveTrick([...trick, [AI_TAG, c]], trump)));
  if (winning.length) {
    if (DEAD_WINNER_FIRST && hand !== null) {
      const gone = new Set([...(played ?? []), ...trick.map(([, c]) => c)].map(cardKey));
      const deadOnes = winning.filter((c) => dead(c, hand, gone));
      if (deadOnes.length) return minBy(deadOnes, (c) => [value(c)]);
    }
    return minBy(winning, (c) => [value(c)]);
  }
  if (DEAD_CARD_LAST && hand !== null) {
    const led = trick[0][1].suit;
    const gone = new Set([...(played ?? []), ...trick.map(([, c]) => c)].map(cardKey));
    const deadOnes = legal.filter((c) => c.suit === led && dead(c, hand, gone));
    if (deadOnes.length) return minBy(deadOnes, (c) => [value(c)]);
  }
  return shed(legal, trump);
}
