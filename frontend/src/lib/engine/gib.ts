// Port of gib.py: GIB 2/1 game force, the robots' default bidding system.
// A line-for-line port, deliberately -- engine.test.ts holds every call and
// alert to the Python engine's exact output. Read gib.py for the reasons.
import { SUITS, maxBy, parseBid, type Card, type Seat, type Suit } from './card';
import { AuctionState, PARTNERS } from './auction';

export type Decision = [string, string];

export const SYM: Record<Suit, string> = { S: '♠', H: '♥', D: '♦', C: '♣' };
const MAJORS: readonly Suit[] = ['H', 'S'];
const MINORS: readonly Suit[] = ['C', 'D'];
const HCP: Record<string, number> = { A: 4, K: 3, Q: 2, J: 1 };

export const OPEN_MIN = 11;
export const NT1: [number, number] = [15, 17];
export const NT2: [number, number] = [20, 21];
export const NT_AFTER_2C: [number, number] = [22, 24];
export const STRONG_2C = 22;
export const WEAK: [number, number] = [5, 10];
export const FOURTH_SEAT: [number, number] = [11, 15];
/** The fewest HCP that respond to a one-level opening (the user's call, 2026-10-23). */
export const RESPONSE_MIN = 7;
export const RAISE: [number, number] = [7, 10];
export const LIMIT: [number, number] = [11, 12];
export const JACOBY_MIN = 13;
export const SPLINTER: [number, number] = [13, 16];
/** Opener's splinter after a single raise, 1M-2M-3♠/4x (roadmap 3.8). */
export const SELF_SPLINTER_MIN = 18;
/** Opener makes that splinter (measurement switch); responder answers it either way. */
export const SELF_SPLINTER = true;
export const TWO_OVER_ONE = 12;
export const JUMP_SHIFT_POINTS = 17;
export const DRURY: [number, number] = [10, 12];
export const INVERTED_MIN = 10;
export const OVERCALL_1: [number, number] = [8, 17];
export const OVERCALL_2: [number, number] = [10, 17];
export const WJO: [number, number] = [3, 9];
export const NT_OVERCALL: [number, number] = [15, 18];
export const TAKEOUT_MIN = 12;
const NEGATIVE: Record<number, number> = { 1: 6, 2: 8, 3: 10 };
export const TWO_SUITED_MIN = 8;
/** Game by judgement points (the user's call, 2026-10-23): GAME for every game
 *  but a major suit's, GAME_MAJOR for a major, NT_GAME opposite our 1NT/2NT. See gib.py. */
export const GAME = 32;
export const GAME_MAJOR = 26;
const NT_GAME = 28;
/** Judge level on the variant's card values (true) or on HCP (false). See gib.py. */
export const settingsGib = { judgeByVariant: true, cueLimitAt3: true };
export const SLAM = 33;
const GRAND = 37;

const isSuit = (s: string | null | undefined): s is Suit =>
  s === 'C' || s === 'D' || s === 'H' || s === 'S';
const isMajor = (s: string | null | undefined) => s === 'H' || s === 'S';
const isMinor = (s: string | null | undefined) => s === 'C' || s === 'D';
const idx = (s: string) => SUITS.indexOf(s as Suit);

function cmpTuple(a: number[], b: number[]): number {
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return a.length - b.length;
}

/** Python's sorted(xs, key=..., reverse=...): stable either way. */
function sortedBy<T>(xs: readonly T[], key: (t: T) => number[], reverse = false): T[] {
  return [...xs].sort((a, b) => (reverse ? cmpTuple(key(b), key(a)) : cmpTuple(key(a), key(b))));
}

// ── Hands ─────────────────────────────────────────────────────────────────────

export class Hand {
  groups: Record<Suit, Card[]>;
  len: Record<Suit, number>;
  hcp: number;
  shape: number[];
  points: number;
  balanced: boolean;
  controls: number;
  judge: number;

  constructor(readonly cards: Card[]) {
    this.groups = { C: [], D: [], H: [], S: [] };
    for (const s of SUITS) this.groups[s] = cards.filter((c) => c.suit === s);
    this.len = { C: 0, D: 0, H: 0, S: 0 };
    for (const s of SUITS) this.len[s] = this.groups[s].length;
    this.hcp = cards.reduce((n, c) => n + (HCP[c.rank] ?? 0), 0);
    this.shape = SUITS.map((s) => this.len[s]).sort((a, b) => b - a);
    const sh = this.shape.join(',');
    this.points = this.hcp + SUITS.reduce((n, s) => n + Math.max(0, this.len[s] - 4), 0)
      - (sh === '4,3,3,3' ? 1 : 0);
    this.balanced = sh === '4,3,3,3' || sh === '4,4,3,2' || sh === '5,3,3,2';
    this.controls = cards.reduce((n, c) => n + (c.rank === 'A' ? 2 : c.rank === 'K' ? 1 : 0), 0);
    // K=Q=3, A=J=10=9=1: a deck holds 40 (the jack counted 0 until 2026-10-23). See gib.py.
    const judge = cards.reduce((n, c) => n + (c.rank === 'K' || c.rank === 'Q' ? 3
      : c.rank === 'A' || c.rank === 'J' || c.rank === '10' || c.rank === '9' ? 1 : 0), 0);
    this.judge = settingsGib.judgeByVariant ? judge : this.hcp;
  }

  has(suit: Suit, rank: string): boolean {
    return this.groups[suit].some((c) => c.rank === rank);
  }

  top(suit: Suit, ranks: readonly string[]): number {
    return this.groups[suit].filter((c) => ranks.includes(c.rank)).length;
  }

  goodSuit(suit: Suit): boolean {
    return this.top(suit, ['A', 'K', 'Q']) >= 2 || this.top(suit, ['A', 'K', 'Q', 'J', '10']) >= 3;
  }

  stopper(suit: Suit): boolean {
    const n = this.len[suit];
    return this.has(suit, 'A') || (this.has(suit, 'K') && n >= 2)
      || (this.has(suit, 'Q') && n >= 3) || (this.has(suit, 'J') && n >= 4);
  }

  short(exclude: string | null = null): Suit[] {
    return sortedBy(SUITS.filter((s) => s !== exclude && this.len[s] <= 1),
      (s) => [this.len[s], idx(s)]);
  }

  keycards(trump: string | null): number {
    const aces = SUITS.filter((s) => this.has(s, 'A')).length;
    return aces + (isSuit(trump) && this.has(trump, 'K') ? 1 : 0);
  }

  aces(): number {
    return SUITS.filter((s) => this.has(s, 'A')).length;
  }

  longest(among: readonly Suit[] = SUITS): Suit {
    return maxBy(among, (s) => [this.len[s], idx(s)]);
  }
}

// ── Calls ─────────────────────────────────────────────────────────────────────

export function levelOf(call: string | null | undefined): number {
  const parsed = call ? parseBid(call) : null;
  return parsed ? parsed[0] : 0;
}

export function strainOf(call: string | null | undefined): string | null {
  const parsed = call ? parseBid(call) : null;
  return parsed ? parsed[1] : null;
}

export function rankOf(call: string): number {
  const [lvl, strain] = parseBid(call)!;
  return (lvl - 1) * 5 + ['C', 'D', 'H', 'S', 'NT'].indexOf(strain);
}

type Rec = [Seat, string];

export class Ctx {
  me: Seat;
  pd: Seat;
  h: Hand;
  calls: Rec[];
  legal: string[];
  ours: Rec[];
  theirs: Rec[];
  seq: string[];
  weOpened: boolean;
  opener: Seat | null;
  ntOvercall: boolean;

  constructor(player: Seat, cards: Card[], readonly auction: AuctionState) {
    this.me = player;
    this.pd = PARTNERS[player];
    this.h = new Hand(cards);
    this.calls = auction.calls.map(([w, c]) => [w, c] as Rec);
    this.legal = auction.legalCalls();
    const us = (w: Seat) => w === this.me || w === this.pd;
    this.ours = this.calls.filter(([w, c]) => us(w) && c !== 'Pass');
    this.theirs = this.calls.filter(([w, c]) => !us(w) && c !== 'Pass');
    this.seq = this.ours.map(([, c]) => c);
    const first = this.calls.find(([, c]) => c !== 'Pass');
    this.weOpened = first !== undefined && us(first[0]);
    this.opener = this.ours.length ? this.ours[0][0] : null;
    // Our 1NT overcall of a one-level opening, and they have only passed
    // since: systems on, the 1NT opening's whole structure, every round.
    this.ntOvercall = false;
    if (!this.weOpened && this.seq.length && this.seq[0] === '1NT'
      && levelOf(first![1]) === 1) {
      const at = this.calls.findIndex(([w, c]) => us(w) && c === '1NT');
      this.ntOvercall = this.calls.slice(at + 1).every(([w, c]) => us(w) || c === 'Pass');
    }
  }

  ok(call: string | null | undefined): boolean {
    return call != null && this.legal.includes(call);
  }

  cheapest(strain: string, floor = 1): string | null {
    for (let lvl = floor; lvl < 8; lvl++) {
      const call = `${lvl}${strain}`;
      if (this.legal.includes(call)) return call;
    }
    return null;
  }

  passedHand(seat: Seat): boolean {
    const first = this.calls.find(([w]) => w === seat);
    return first !== undefined && first[1] === 'Pass';
  }

  mine(): string[] {
    return this.ours.filter(([w]) => w === this.me).map(([, c]) => c);
  }

  partners(): string[] {
    return this.ours.filter(([w]) => w === this.pd).map(([, c]) => c);
  }

  iAmOpener(): boolean {
    return this.opener === this.me;
  }

  current(): string | null {
    const hb = this.auction.highestBid;
    return hb ? `${hb[0]}${hb[1]}` : null;
  }
}

// ── Alerts that recur ─────────────────────────────────────────────────────────

const TO_PLAY = 'To play.';
const natural = (suit: Suit) => `Natural, ${SYM[suit]}.`;

/** `decision`, unless partner has already bid past it. Only a human partner
 *  does that, by not answering a convention (2NT-3♣-3NT): the contract is theirs. */
const placed = (ctx: Ctx, decision: Decision): Decision =>
  ctx.ok(decision[0]) ? decision : ['Pass', 'Partner placed the contract.'];

// ── Entry point ───────────────────────────────────────────────────────────────

/** Calls a branch produced that were not legal, caught by the guard. */
export const ILLEGAL: [Rec[], Decision][] = [];

export function gibBid(player: Seat, cards: Card[], auction: AuctionState): Decision | null {
  const ctx = new Ctx(player, cards, auction);
  if (!ctx.legal.length) return null;
  let decision = decide(ctx);
  const placedByJam = afterJam(ctx);
  if (placedByJam && (!decision || decision[0] !== 'X')) return placedByJam;
  if (!decision || (decision[0] !== 'X' && decision[0] !== 'XX')) {
    decision = jamGame(ctx) ?? decision;   // a penalty double outranks the jam
  }
  decision = totalTricks(ctx, decision) ?? decision;
  decision = majorOverNotrump(ctx, decision) ?? decision;
  if (decision === null) return null;
  if (!ctx.legal.includes(decision[0] as string)) {
    ILLEGAL.push([ctx.calls, decision]);
    decision = continuation(ctx);
    if (!ctx.legal.includes(decision[0])) decision = ['Pass', 'Nothing to add.'];
  }
  return [decision[0], nameTheSuit(decision[0], decision[1])];
}

export function nameTheSuit(call: string, alert: string): string {
  const s = strainOf(call);
  if (isSuit(s) && !alert.includes(SYM[s]) && !alert.toLowerCase().includes('artificial')) {
    return alert.replace(/\.+$/, '') + `, ${SYM[s]}.`;
  }
  return alert;
}

function owns(ctx: Ctx): boolean {
  return ctx.seq.some((c, i) => strainOf(c) === 'NT'
    || (isSuit(strainOf(c)) && shownSuit(ctx.seq, i) !== strainOf(c)));
}

function decide(ctx: Ctx): Decision | null {
  for (const step of [answerAsk, afterMyAsk]) {
    const decision = step(ctx);
    if (decision) return decision;
  }
  if (!ctx.theirs.length) {
    if (!ctx.seq.length) return opening(ctx);
    return uncontested(ctx);
  }
  let decision = contested(ctx);
  if (decision === null && owns(ctx)) decision = continuation(ctx);
  return decision;
}

// ── Openings ──────────────────────────────────────────────────────────────────

function opens(h: Hand): boolean {
  const two = [...h.shape].slice(0, 2).reduce((a, b) => a + b, 0);
  return h.hcp >= 12 || (h.hcp >= OPEN_MIN && h.hcp + two >= 20);
}

function openingSuit(h: Hand): Suit {
  const longest = Math.max(...SUITS.map((s) => h.len[s]));
  if (longest >= 5) return maxBy(SUITS.filter((s) => h.len[s] === longest), (s) => [idx(s)]);
  const c = h.len.C;
  const d = h.len.D;
  if (d > c) return 'D';
  if (c > d) return 'C';
  return c >= 4 ? 'D' : 'C';
}

function oneLevelAlert(suit: Suit): string {
  if (isMajor(suit)) return `5+ ${SYM[suit]}, 11-21 HCP.`;
  if (suit === 'D') return `3+ ${SYM.D}, usually 4. 11-21 HCP.`;
  return `3+ ${SYM.C}, 11-21 HCP.`;
}

function opening(ctx: Ctx): Decision {
  const h = ctx.h;
  const fourth = ctx.calls.length === 3;
  if (h.hcp >= STRONG_2C && ctx.ok('2C')) return ['2C', '22+ HCP. Strong, forcing. Artificial.'];
  if (h.balanced && NT2[0] <= h.hcp && h.hcp <= NT2[1]) return ['2NT', '20-21 HCP, balanced.'];
  if (h.balanced && NT1[0] <= h.hcp && h.hcp <= NT1[1]) return ['1NT', '15-17 HCP, balanced.'];
  const best = h.longest();
  if (fourth && best !== 'C' && h.len[best] >= 6
    && FOURTH_SEAT[0] <= h.points && h.points <= FOURTH_SEAT[1] && ctx.ok(`2${best}`)) {
    return [`2${best}`, `6+ ${SYM[best]}, ${FOURTH_SEAT[0]}-${FOURTH_SEAT[1]} points. Fourth seat.`];
  }
  if (opens(h)) {
    const suit = openingSuit(h);
    return [`1${suit}`, oneLevelAlert(suit)];
  }
  if (!fourth && WEAK[0] <= h.hcp && h.hcp <= WEAK[1]) {
    const n = h.len[best];
    if (isMajor(best) && n >= 8 && ctx.ok(`4${best}`)) {
      return [`4${best}`, `8+ ${SYM[best]}, 5-10 HCP. Pre-emptive.`];
    }
    if (n >= 7 && ctx.ok(`3${best}`)) return [`3${best}`, `7+ ${SYM[best]}, 5-10 HCP. Pre-emptive.`];
    if (n === 6 && best !== 'C' && h.goodSuit(best) && ctx.ok(`2${best}`)) {
      return [`2${best}`, `6 ${SYM[best]}, 5-10 HCP, good suit. Weak two.`];
    }
  }
  return ['Pass', 'Not an opening hand.'];
}

// ── Uncontested auctions ──────────────────────────────────────────────────────

function uncontested(ctx: Ctx): Decision {
  const first = ctx.seq[0];
  if (first === '1NT' || first === '2NT') return notrump(ctx, 0);
  if (first === '2C') return strongTwo(ctx);
  if (levelOf(first) === 1) return oneSuit(ctx);
  return preempt(ctx);
}

// ── 1-of-a-suit openings ──────────────────────────────────────────────────────

function oneSuit(ctx: Ctx): Decision {
  const seq = ctx.seq;
  const n = seq.length;
  const x = strainOf(seq[0]) as Suit;
  if (n === 1) return isMajor(x) ? respondMajor(ctx, x) : respondMinor(ctx, x);
  if (n === 2) return openerRebid(ctx, x, seq[1]);
  if (n === 3) {
    const decision = responderRebid(ctx, x);
    if (decision) return decision;
  }
  if (n === 4) {
    const decision = openerThird(ctx, x);
    if (decision) return decision;
  }
  return continuation(ctx);
}

function jumpShift(ctx: Ctx, x: Suit): Decision | null {
  const h = ctx.h;
  if (ctx.passedHand(ctx.me) || h.points < JUMP_SHIFT_POINTS || h.controls < 4) return null;
  for (const y of sortedBy(SUITS, (s) => [h.len[s], idx(s)], true)) {
    if (idx(y) > idx(x) && h.len[y] >= 5 && h.goodSuit(y) && ctx.ok(`2${y}`)) {
      return [`2${y}`, `5+ ${SYM[y]}, ${JUMP_SHIFT_POINTS}+ points. Strong jump shift.`];
    }
  }
  return null;
}

/** Count the trump length in a raise of 1M (the user's call, 2026-10-28): it
 *  is chosen on HCP plus one point for each trump past three. See gib.py. */
export const RAISE_TRUMP_POINTS = true;

/** 1M-2M / 3M / 4M on four or more trumps, judged on HCP + trumps past three. */
function raiseOnTrumpPoints(ctx: Ctx, x: Suit): Decision | null {
  const value = ctx.h.hcp + ctx.h.len[x] - 3;
  const passed = ctx.passedHand(ctx.me);
  if (value > LIMIT[1] && ctx.ok(`4${x}`)) return [`4${x}`, `4+ ${SYM[x]}, game values.`];
  if (value >= LIMIT[0] && !passed) return [`3${x}`, `4+ ${SYM[x]}. Limit raise.`];
  if (value >= RAISE[0] && !(passed && value >= DRURY[0])) {
    return [`2${x}`, `3+ ${SYM[x]}. Single raise.`];
  }
  return null;
}

function respondMajor(ctx: Ctx, x: Suit): Decision {
  const h = ctx.h;
  const hcp = h.hcp;
  const sup = h.len[x];
  const passed = ctx.passedHand(ctx.me);
  const shortness = h.short(x);
  if (sup >= 5 && hcp < 10 && shortness.length && ctx.ok(`4${x}`)) {
    return [`4${x}`, `5+ ${SYM[x]}, under 10 HCP. Pre-emptive raise.`];
  }
  if (RAISE_TRUMP_POINTS && sup >= 4 && hcp < JACOBY_MIN) {
    const raise = raiseOnTrumpPoints(ctx, x);
    if (raise) return raise;
  }
  if (hcp < RESPONSE_MIN) return ['Pass', `Fewer than ${RESPONSE_MIN} HCP.`];
  if (sup >= 4 && !passed && hcp >= JACOBY_MIN) {
    if (shortness.length && hcp <= SPLINTER[1]) {
      const s = shortness[0];
      const call = splinterCall(x, s);
      if (ctx.ok(call)) {
        return [call, `Splinter: 4+ ${SYM[x]}, short ${SYM[s]}, ${SPLINTER[0]}-${SPLINTER[1]} HCP.`];
      }
    }
    return ['2NT', `Jacoby: 4+ ${SYM[x]}, ${JACOBY_MIN}+ HCP, game forcing.`];
  }
  if (passed && sup >= 3 && DRURY[0] <= hcp && hcp <= DRURY[1]) {
    return ['2C', `Drury: 3+ ${SYM[x]}, ${DRURY[0]}-${DRURY[1]} HCP. Artificial.`];
  }
  if (sup >= 4 && LIMIT[0] <= hcp && hcp <= LIMIT[1] && !passed) {
    if (RAISE_TRUMP_POINTS) return [`3${x}`, `4+ ${SYM[x]}. Limit raise.`];
    return [`3${x}`, `4+ ${SYM[x]}, ${LIMIT[0]}-${LIMIT[1]} HCP. Limit raise.`];
  }
  if (sup >= 3 && RAISE[0] <= hcp && hcp <= RAISE[1]) {
    if (RAISE_TRUMP_POINTS) return [`2${x}`, `3+ ${SYM[x]}. Single raise.`];
    return [`2${x}`, `3+ ${SYM[x]}, ${RAISE[0]}-${RAISE[1]} HCP.`];
  }
  const js = jumpShift(ctx, x);
  if (js) return js;
  if (x === 'H' && h.len.S >= 4) return ['1S', `4+ ${SYM.S}, ${RESPONSE_MIN}+ HCP.`];
  if (!passed && hcp >= TWO_OVER_ONE) {
    if (x === 'S' && h.len.H >= 5) return ['2H', `5+ ${SYM.H}, 12+ HCP. Game forcing.`];
    if (h.len.D >= 4 && h.len.D > h.len.C) return ['2D', `4+ ${SYM.D}, 12+ HCP. Game forcing.`];
    if (h.len.C >= 3) return ['2C', `3+ ${SYM.C}, 12+ HCP. Game forcing.`];
    return ['2D', `4+ ${SYM.D}, 12+ HCP. Game forcing.`];
  }
  if (passed) return ['1NT', `${RESPONSE_MIN}-11 HCP, no fit.`];
  return ['1NT', `${RESPONSE_MIN}-11 HCP. Forcing.`];
}

function respondMinor(ctx: Ctx, x: Suit): Decision {
  const h = ctx.h;
  const hcp = h.hcp;
  const sup = h.len[x];
  const passed = ctx.passedHand(ctx.me);
  if (hcp < RESPONSE_MIN) return ['Pass', `Fewer than ${RESPONSE_MIN} HCP.`];
  const js = jumpShift(ctx, x);
  if (js) return js;
  const majors = MAJORS.filter((s) => h.len[s] >= 4);
  if (x === 'D' && !passed && hcp >= TWO_OVER_ONE && h.len.C >= 5
    && MAJORS.every((m) => h.len.C > h.len[m])) {
    return ['2C', `4+ ${SYM.C}, 12+ HCP. Game forcing.`];
  }
  if (majors.length) {
    const m = majors.length === 2 && h.len.S > h.len.H ? 'S' : majors[0];
    return [`1${m}`, `4+ ${SYM[m]}, ${RESPONSE_MIN}+ HCP.`];
  }
  if (x === 'C' && h.len.D >= 4) return ['1D', `4+ ${SYM.D}, ${RESPONSE_MIN}+ HCP.`];
  if (x === 'D' && !passed && hcp >= TWO_OVER_ONE && h.len.C >= 4) {
    return ['2C', `4+ ${SYM.C}, 12+ HCP. Game forcing.`];
  }
  const need = x === 'C' ? 5 : 4;
  if (sup >= need && hcp >= INVERTED_MIN) {
    return [`2${x}`, `${need}+ ${SYM[x]}, ${INVERTED_MIN}+ HCP. Inverted, forcing.`];
  }
  if (sup >= 5 && hcp <= 9) return [`3${x}`, `5+ ${SYM[x]}, ${RESPONSE_MIN}-9 HCP. Weak raise.`];
  if (hcp <= 10) return ['1NT', `${RESPONSE_MIN}-10 HCP, no 4-card major.`];
  if (hcp <= 12) return ['2NT', '11-12 HCP, invitational.'];
  return ['3NT', '13+ HCP, no 4-card major.'];
}

function openerRebid(ctx: Ctx, x: Suit, r: string): Decision {
  const h = ctx.h;
  const hcp = h.judge;
  const passedResp = ctx.passedHand(ctx.pd);
  const rl = levelOf(r);
  const rs = strainOf(r);

  if (isMajor(x) && r === '2NT' && !passedResp) return jacobyRebid(ctx, x);
  if (isMajor(x) && isSplinter(x, r)) {
    if (hcp >= 16 && h.top(rs as Suit, ['K', 'Q', 'J']) === 0) {
      return ['4NT', `Keycard Blackwood for ${SYM[x]}. Artificial.`];
    }
    return [`4${x}`, TO_PLAY];
  }
  if (isMajor(x) && r === '2C' && passedResp) {
    if (hcp <= 11) return [`2${x}`, `Sub-minimum opening, ${SYM[x]}.`];
    if (hcp <= 14) return ['2D', 'Full opening values. Artificial.'];
    return [`4${x}`, TO_PLAY];
  }
  if (r === `2${x}` && isMajor(x)) return gameTry(ctx, x);
  if (r === `3${x}` && isMajor(x)) {
    return hcp + fitBonus(h, x, 4) >= 14 ? [`4${x}`, TO_PLAY] : ['Pass', 'Declining the invitation.'];
  }
  if (r === `4${x}` || r === '3NT') return ['Pass', 'Partner placed the contract.'];
  if (isMinor(x) && r === `2${x}`) return invertedRebid(ctx, x);
  if (isMinor(x) && r === `3${x}`) {
    return hcp >= 18 ? ['3NT', TO_PLAY] : ['Pass', "Partner's raise is weak."];
  }
  if (isMinor(x) && r === '2NT') {
    if (hcp >= 14) return ['3NT', TO_PLAY];
    if (h.len[x] >= 6) return [`3${x}`, `6+ ${SYM[x]}, minimum.`];
    return ['Pass', 'Minimum.'];
  }
  if (rl === 2 && isSuit(rs) && rs !== x
    && (isTwoOverOne(x, rs) || (x === 'D' && rs === 'C')) && !passedResp) {
    return gfRebid(ctx, x, rs);
  }
  if (rl === 2 && isSuit(rs) && rs !== x && idx(rs) > idx(x)) return gfRebid(ctx, x, rs);
  if (r === '1NT') return rebidOver1nt(ctx, x, passedResp);
  if (rl === 1) return rebidOverNewSuit(ctx, x, rs as Suit);
  return continuation(ctx);
}

export function isTwoOverOne(x: string, y: string | null): boolean {
  return isSuit(y) && idx(y) < idx(x);
}

/** The jump in `s` that splinters for `x`: 3♠ over hearts, else the four level. */
function splinterCall(x: string, s: string): string {
  return x === 'H' && s === 'S' ? `3${s}` : `4${s}`;
}

function isSplinter(x: string, r: string): boolean {
  if (x === 'H') return ['3S', '4C', '4D'].includes(r);
  if (x === 'S') return ['4C', '4D', '4H'].includes(r);
  return false;
}

function jacobyRebid(ctx: Ctx, x: Suit): Decision {
  const h = ctx.h;
  const short = h.short(x);
  if (short.length && ctx.ok(`3${short[0]}`)) {
    const s = short[0];
    return [`3${s}`, `Shortness in ${SYM[s]}.`];
  }
  for (const s of SUITS) {
    if (s !== x && h.len[s] >= 5 && h.goodSuit(s) && ctx.ok(`4${s}`)) {
      return [`4${s}`, `5+ ${SYM[s]}, good second suit.`];
    }
  }
  if (h.hcp >= 18) return [`3${x}`, '18+ HCP, no shortness.'];
  if (h.hcp >= 15) return ['3NT', '15-17 HCP, no shortness.'];
  return [`4${x}`, 'Minimum, no shortness.'];
}

function gameTry(ctx: Ctx, x: Suit): Decision {
  const h = ctx.h;
  const hcp = h.hcp;
  const short = h.short(x);
  const fit = hcp + fitBonus(h, x, 3);
  if (hcp <= 14 && fit < 18) return ['Pass', 'Minimum.'];
  if (SELF_SPLINTER && hcp >= SELF_SPLINTER_MIN && short.length) {
    const s = short[0];
    const call = splinterCall(x, s);
    if (ctx.ok(call)) return [call, `Splinter: short ${SYM[s]}, ${SELF_SPLINTER_MIN}+ HCP. Game forcing.`];
  }
  if (hcp >= 18 || fit >= 18 || (hcp >= 17 && !short.length)) return [`4${x}`, TO_PLAY];
  if (short.length) {
    const step = x === 'H' ? '2S' : '2NT';
    return [step, 'Short-suit game try. Artificial.'];
  }
  for (const s of SUITS) {
    const call = `3${s}`;
    if (s !== x && h.len[s] >= 3 && h.top(s, ['A', 'K']) <= 1
      && ctx.ok(call) && rankOf(call) < rankOf(`3${x}`)) {
      return [call, `3+ ${SYM[s]}, 15-16 HCP. Help-suit game try.`];
    }
  }
  return [`3${x}`, '15-16 HCP, invitational.'];
}

function invertedRebid(ctx: Ctx, x: Suit): Decision {
  const h = ctx.h;
  if (h.balanced && h.hcp <= 14) return ['2NT', '11-14 HCP, balanced.'];
  if (h.balanced && h.hcp >= 18) return ['3NT', TO_PLAY];
  if (h.hcp <= 14) return [`3${x}`, 'Minimum, unbalanced.'];
  for (const s of SUITS) {
    if (s !== x && h.len[s] >= 4 && ctx.ok(`2${s}`)) return [`2${s}`, `4+ ${SYM[s]}, 15+ HCP.`];
  }
  return ['3NT', TO_PLAY];
}

function gfRebid(ctx: Ctx, x: Suit, y: Suit): Decision {
  const h = ctx.h;
  if (isMajor(y) && h.len[y] >= 3) {
    const call = ctx.cheapest(y, 3);
    if (call) return [call, `3+ ${SYM[y]} support, game forcing.`];
  }
  if (isMinor(y) && h.len[y] >= 4) {
    const call = ctx.cheapest(y, 3);
    if (call && levelOf(call) <= 4) return [call, `4+ ${SYM[y]} support, game forcing.`];
  }
  if (h.len[x] >= 6) {
    const call = ctx.cheapest(x, 2);
    if (call) return [call, `5+ ${SYM[x]}. Game forcing.`];
  }
  for (const s of sortedBy(SUITS, (t) => [idx(t)], true)) {
    if (s !== x && s !== y && h.len[s] >= 4) {
      const call = ctx.cheapest(s, 2);
      if (call && levelOf(call) === 2) return [call, `4+ ${SYM[s]}. Game forcing.`];
    }
  }
  if (h.balanced && ctx.ok('2NT')) return ['2NT', 'Balanced or no other bid. Game forcing.'];
  const call = ctx.cheapest(x, 2);
  if (call && levelOf(call) === 2) return [call, `5+ ${SYM[x]}. Game forcing.`];
  for (const s of SUITS) {
    if (s !== x && s !== y && h.len[s] >= 4) {
      const c = ctx.cheapest(s, 3);
      if (c && levelOf(c) === 3 && rankOf(c) < rankOf('3NT')) return [c, `4+ ${SYM[s]}. Game forcing.`];
    }
  }
  if (ctx.ok('2NT')) return ['2NT', 'Balanced or no other bid. Game forcing.'];
  return continuation(ctx);
}

function rebidOver1nt(ctx: Ctx, x: Suit, passedResp: boolean): Decision {
  const h = ctx.h;
  const hcp = h.hcp;
  if (h.balanced && hcp <= 14 && (passedResp || isMinor(x))) return ['Pass', 'Minimum, balanced.'];
  if (h.balanced && hcp >= 18 && hcp <= 19) {
    return isMinor(x) ? ['3NT', TO_PLAY] : ['2NT', '18-19 HCP, balanced.'];
  }
  if (h.len[x] >= 6 && hcp >= 16) {
    if (hcp <= 18 && ctx.ok(`3${x}`)) return [`3${x}`, `6+ ${SYM[x]}, 16-18 HCP.`];
    if (isMajor(x) && ctx.ok(`4${x}`)) return [`4${x}`, TO_PLAY];
    return ['3NT', TO_PLAY];
  }
  if (h.len[x] >= 6 && hcp <= 15) return [`2${x}`, rebid1ntAlert(x)];
  for (const z of sortedBy(SUITS, (s) => [h.len[s], idx(s)], true)) {
    if (z === x || h.len[z] < 4) continue;
    if (idx(z) < idx(x)) {
      if (hcp >= 19 && ctx.ok(`3${z}`)) return [`3${z}`, `4+ ${SYM[z]}, 19+ HCP. Game forcing.`];
      if (ctx.ok(`2${z}`) && hcp <= 18) return [`2${z}`, newSuitOver1nt(z)];
    } else if (hcp >= 16 && ctx.ok(`2${z}`)) {
      return [`2${z}`, `4+ ${SYM[z]}, 16+ HCP. Reverse.`];
    }
  }
  if ((h.len[x] >= 5 || (isMinor(x) && h.len[x] >= 4)) && hcp <= 15) {
    return [`2${x}`, rebid1ntAlert(x)];
  }
  const minors = MINORS.filter((m) => m !== x && h.len[m] >= 3);
  if (minors.length) {
    const m = maxBy(minors, (s) => [h.len[s], -idx(s)]);
    if (ctx.ok(`2${m}`)) return [`2${m}`, newSuitOver1nt(m)];
  }
  if (ctx.ok('2NT') && hcp >= 16) return ['2NT', '18-19 HCP, balanced.'];
  return ['Pass', 'Minimum, balanced.'];
}

function rebid1ntAlert(x: Suit): string {
  return `${isMajor(x) ? 5 : 4}+ ${SYM[x]}, 11-15 HCP.`;
}

function newSuitOver1nt(z: Suit): string {
  return isMinor(z) ? `3+ ${SYM[z]}, 11-18 HCP.` : `4+ ${SYM[z]}, 11-18 HCP.`;
}

function rebidOverNewSuit(ctx: Ctx, x: Suit, y: Suit): Decision {
  const h = ctx.h;
  const hcp = h.hcp;
  if (isMajor(y) && h.len[y] >= 4) {
    if (hcp <= 14) return [`2${y}`, `4+ ${SYM[y]}, 11-14 HCP.`];
    if (hcp <= 17) return [`3${y}`, `4+ ${SYM[y]}, 15-17 HCP.`];
    return [`4${y}`, `4+ ${SYM[y]}, 18+ HCP.`];
  }
  for (const z of ['H', 'S'] as Suit[]) {
    if (idx(z) > idx(y) && z !== x && h.len[z] >= 4 && hcp <= 18 && ctx.ok(`1${z}`)) {
      return [`1${z}`, `4+ ${SYM[z]}, 11-18 HCP.`];
    }
  }
  if (h.balanced && hcp <= 14) return ['1NT', '11-14 HCP, balanced.'];
  if (h.balanced && hcp >= 18 && hcp <= 19) return ['2NT', '18-19 HCP, balanced.'];
  if (y === 'D' && x === 'C' && h.len.D >= 4 && hcp <= 14) return ['2D', `4+ ${SYM.D}, 11-14 HCP.`];
  if (h.len[x] >= 6) {
    if (hcp >= 17 && ctx.ok(`3${x}`)) return [`3${x}`, `6+ ${SYM[x]}, 17-21 HCP.`];
    return [`2${x}`, `5+ ${SYM[x]}, 11-18 HCP.`];
  }
  for (const z of sortedBy(SUITS, (s) => [h.len[s], idx(s)], true)) {
    if (z === x || z === y || h.len[z] < 4) continue;
    if (idx(z) < idx(x)) {
      if (hcp >= 19 && ctx.ok(`3${z}`)) return [`3${z}`, `4+ ${SYM[z]}, 19+ HCP. Game forcing.`];
      if (ctx.ok(`2${z}`) && hcp <= 18) return [`2${z}`, `4+ ${SYM[z]}, 11-18 HCP.`];
    } else if (hcp >= 16 && ctx.ok(`2${z}`)) {
      return [`2${z}`, `4+ ${SYM[z]}, 16+ HCP. Reverse.`];
    }
  }
  if (hcp <= 18) return [`2${x}`, `5+ ${SYM[x]}, 11-18 HCP.`];
  return ['3NT', TO_PLAY];
}

// ── Responder's second call, opener's third ───────────────────────────────────

function openerRange(seq: string[]): [number, number] {
  const x = strainOf(seq[0]) as Suit;
  const r = seq[1];
  const o = seq[2];
  const ol = levelOf(o);
  const os = strainOf(o);
  const y = strainOf(r);
  if (o === '1NT') return [11, 14];
  if (o === '2NT') return [18, 19];
  if (os === y && isSuit(y) && r !== '1NT') {
    return ({ 2: [11, 14], 3: [15, 17] } as Record<number, [number, number]>)[ol] ?? [18, 21];
  }
  if (os === x) {
    if (ol === 2) return r !== '1NT' ? [11, 16] : [11, 15];
    return r !== '1NT' ? [17, 21] : [16, 18];
  }
  if (isSuit(os) && ol === 2 && idx(os) > idx(x)) return [16, 21];
  if (isSuit(os) && ol === 3) return [19, 21];
  return [11, 18];
}

function responderRebid(ctx: Ctx, x: Suit): Decision | null {
  const seq = ctx.seq;
  const h = ctx.h;
  const hcp = h.judge;
  const r = seq[1];
  const o = seq[2];
  const y = strainOf(r);
  const os = strainOf(o);
  const ol = levelOf(o);

  if (r === '2NT' && isMajor(x)) {
    const shown = ({ [`4${x}`]: 11, '3NT': 15, [`3${x}`]: 18 } as Record<string, number>)[o] ?? 11;
    if (hcp + shown >= SLAM && ctx.ok('4NT')) return ['4NT', `Keycard Blackwood for ${SYM[x]}. Artificial.`];
    if (ctx.ok(`4${x}`)) return [`4${x}`, TO_PLAY];
    return ['Pass', 'Partner placed the contract.'];
  }
  if (isMajor(x) && isSplinter(x, r)) return ['Pass', 'Partner placed the contract.'];
  if (isMajor(x) && r === '2C' && ctx.passedHand(ctx.me)) {
    if (o === '2D') return hcp >= 11 ? [`3${x}`, 'Invitational.'] : [`2${x}`, 'Sign-off.'];
    return ['Pass', 'Partner placed the contract.'];
  }
  if (r === `2${x}` && isMajor(x)) {
    const fit = hcp + fitBonus(h, x, 5);
    if (isSplinter(x, o)) return [`4${x}`, TO_PLAY];   // opener's splinter: game forcing
    if (o === '3NT') {                                // a choice of games (roadmap 3.7)
      if (h.len[x] >= 4 || h.short(x).length) return [`4${x}`, 'Choice of games: a fourth trump or a short suit.'];
      return ['Pass', 'Choice of games: three trumps, no short suit.'];
    }
    if ((o === '2S' || o === '2NT') && o !== `2${x}`) {
      return fit >= 9 ? [`4${x}`, TO_PLAY] : [`3${x}`, 'Declining the game try.'];
    }
    if (ol === 3 && isSuit(os) && os !== x) {
      const accept = fit >= 9
        || (fit >= 8 && (h.len[os as Suit] <= 1 || h.top(os as Suit, ['A', 'K', 'Q']) >= 1));
      return accept ? [`4${x}`, TO_PLAY] : [`3${x}`, 'Declining the game try.'];
    }
    if (o === `3${x}`) return fit >= 9 ? [`4${x}`, TO_PLAY] : ['Pass', 'Declining the invitation.'];
    return ['Pass', 'Partner placed the contract.'];
  }
  if (isMinor(x) && r === `2${x}`) {
    if (o === '2NT') return hcp >= 13 ? ['3NT', TO_PLAY] : ['Pass', 'No game.'];
    if (o === `3${x}`) return hcp >= 13 ? ['3NT', TO_PLAY] : ['Pass', 'No game.'];
    return null;
  }
  if (levelOf(r) === 2 && isSuit(y) && y !== x) return null;

  const [lo, hi] = openerRange(seq);
  if (r === '1NT') return after1ntResponse(ctx, x, o, lo, hi);

  if (os === y && isSuit(y)) {
    if (isMajor(y)) {
      if (hcp + lo >= SLAM && ctx.ok('4NT')) return ['4NT', `Keycard Blackwood for ${SYM[y]}. Artificial.`];
      if (ol >= 4) return ['Pass', 'Partner placed the contract.'];
      const fit = hcp + fitBonus(h, y, 4);
      if (fit + lo >= GAME_MAJOR) return [`4${y}`, TO_PLAY];
      if (fit + hi >= GAME_MAJOR && ol === 2) return [`3${y}`, 'Invitational.'];
      return ['Pass', 'No game.'];
    }
    if (hcp + lo >= GAME) return placed(ctx, ['3NT', TO_PLAY]);
    return ['Pass', 'No game.'];
  }
  if (o === '1NT') {
    if (isMajor(y) && h.len[y as Suit] >= 5 && hcp >= 11) {
      const nmf = x === 'C' ? '2D' : '2C';
      if (ctx.ok(nmf)) return [nmf, 'New minor forcing. Artificial.'];
    }
    if (hcp + lo >= GAME) {
      if (isMajor(y) && h.len[y as Suit] >= 6) {
        if (hcp + lo >= GAME_MAJOR) return [`4${y}`, TO_PLAY];
        if (ctx.ok(`3${y}`)) return [`3${y}`, `6+ ${SYM[y]}, invitational.`];
      }
      if (hcp + lo >= SLAM) return ['6NT', TO_PLAY];
      if (hcp + hi >= SLAM && ctx.ok('4NT')) return ['4NT', 'Quantitative: invites 6NT.'];
      return ['3NT', TO_PLAY];
    }
    if (hcp + hi >= GAME) {
      if (isSuit(y) && h.len[y] >= 6 && ctx.ok(`3${y}`)) return [`3${y}`, `6+ ${SYM[y]}, invitational.`];
      return ['2NT', 'Invitational.'];
    }
    if (isSuit(y) && h.len[y] >= 6 && ctx.ok(`2${y}`)) return [`2${y}`, `6+ ${SYM[y]}, to play.`];
    return ['Pass', 'No game.'];
  }
  if (o === '2NT') {
    if (hcp + lo >= SLAM) return ['6NT', TO_PLAY];
    if (isMajor(y) && h.len[y as Suit] >= 6) return [`4${y}`, TO_PLAY];
    if (isMajor(x) && h.len[x] >= 3) return [`4${x}`, TO_PLAY];
    return ['3NT', TO_PLAY];
  }
  if (os === x) {
    const fit = h.len[x] >= (ol === 3 ? 2 : 3);
    if (ol === 3) {
      if (isMajor(x) && fit) return [`4${x}`, TO_PLAY];
      return ['3NT', TO_PLAY];
    }
    if (fit) {
      const g = isMajor(x) ? GAME_MAJOR : GAME;
      if (hcp + lo >= g) return isMajor(x) ? [`4${x}`, TO_PLAY] : ['3NT', TO_PLAY];
      if (hcp + hi >= g) return [`3${x}`, 'Invitational.'];
      return ['Pass', 'No game.'];
    }
    if (isSuit(y) && h.len[y] >= 6) {
      if (hcp + lo >= GAME_MAJOR && isMajor(y)) return [`4${y}`, TO_PLAY];
      if (hcp + hi >= GAME_MAJOR && ctx.ok(`3${y}`)) return [`3${y}`, `6+ ${SYM[y]}, invitational.`];
      if (ctx.ok(`2${y}`)) return [`2${y}`, `6+ ${SYM[y]}, to play.`];
    }
    if (hcp + lo >= GAME) return ['3NT', TO_PLAY];
    if (hcp + hi >= GAME && ctx.ok('2NT')) return ['2NT', 'Invitational.'];
    return ['Pass', 'No game.'];
  }
  if (isSuit(os)) {
    const z = os;
    const reverse = ol === 2 && idx(z) > idx(x);
    const forcing = reverse || ol === 3;
    if (forcing) return afterForcingRebid(ctx, x, y, z);
    if (hcp + lo >= GAME) {
      for (const [m, n] of [[z, 4], [x, 3], [y, 6]] as [string, number][]) {
        if (isMajor(m) && h.len[m as Suit] >= n) {
          if (hcp + lo >= GAME_MAJOR) return placed(ctx, [`4${m}`, TO_PLAY]);
          if (ctx.ok(`3${m}`)) return [`3${m}`, 'Invitational.'];
          break;
        }
      }
      const fourth = SUITS.filter((s) => s !== x && s !== y && s !== z);
      if (fourth.length) {
        const call = ctx.cheapest(fourth[0]);
        if (call && levelOf(call) <= 3 && rankOf(call) < rankOf('3NT')) {
          return [call, 'Fourth suit forcing. Artificial.'];
        }
      }
      return placed(ctx, ['3NT', TO_PLAY]);
    }
    if (hcp + hi >= GAME) {
      if (isMajor(z) && h.len[z] >= 4 && ctx.ok(`3${z}`)) return [`3${z}`, 'Invitational.'];
      if (h.len[x] >= 3 && ctx.ok(`3${x}`)) return [`3${x}`, 'Invitational.'];
      if (ctx.ok('2NT')) return ['2NT', 'Invitational.'];
    }
    if (isMajor(z) && h.len[z] >= 4 && ctx.ok(`2${z}`)) return [`2${z}`, `4+ ${SYM[z]}, minimum.`];
    if (isSuit(y) && h.len[y] >= 6 && ctx.ok(`2${y}`)) return [`2${y}`, `6+ ${SYM[y]}, to play.`];
    if (h.len[z] >= 4 && ol === 2) return ['Pass', "Happy in opener's second suit."];
    if (h.len[x] >= 2 && ctx.ok(`2${x}`) && h.len[x] >= h.len[z]) {
      return [`2${x}`, `Preference to ${SYM[x]}.`];
    }
    if (ol === 1 && ctx.ok('1NT')) return ['1NT', 'Minimum.'];
    return ['Pass', 'No game.'];
  }
  return null;
}

function after1ntResponse(ctx: Ctx, x: Suit, o: string, lo: number, hi: number): Decision {
  void lo; void hi;
  const h = ctx.h;
  const hcp = h.judge;
  const os = strainOf(o);
  const ol = levelOf(o);
  if (o === 'Pass') return ['Pass', 'Partner passed.'];
  if (o === '2NT') {
    if (isMajor(x) && h.len[x] >= 3) return [`4${x}`, TO_PLAY];
    return hcp >= 7 ? ['3NT', TO_PLAY] : ['Pass', 'No game.'];
  }
  if (os === x && ol === 3) {
    if (isMajor(x)) return hcp >= 8 || h.len[x] >= 3 ? [`4${x}`, TO_PLAY] : ['Pass', 'No game.'];
    return hcp >= 8 ? ['3NT', TO_PLAY] : ['Pass', 'No game.'];
  }
  if (ol >= 3 || o === `4${x}` || o === '3NT') {
    if (ol === 3 && os !== x && isSuit(os)) return continuation(ctx);
    return ['Pass', 'Partner placed the contract.'];
  }
  if (isSuit(os) && idx(os) > idx(x)) {
    if (hcp >= 9) {
      if (isMajor(x) && h.len[x] >= 2) return [`4${x}`, TO_PLAY];
      return ['3NT', TO_PLAY];
    }
    if (isMajor(x) && h.len[x] >= 2 && ctx.ok(`3${x}`)) return [`3${x}`, `Preference to ${SYM[x]}.`];
    return ['2NT', 'Weak, no fit.'];
  }
  if (isMajor(x) && h.len[x] >= 3 && h.hcp >= 10 && h.hcp <= 11 && ctx.ok(`3${x}`)) {
    return [`3${x}`, `3+ ${SYM[x]} support, 10-11 HCP. Limit raise.`];
  }
  if (os === x) return ['Pass', 'No game.'];
  if (isMajor(x) && h.len[x] >= 2 && h.len[x] >= h.len[os as Suit] && ctx.ok(`2${x}`)) {
    return [`2${x}`, `Preference to ${SYM[x]}.`];
  }
  if (h.hcp >= 10 && h.hcp <= 11 && ctx.ok('2NT')) return ['2NT', '10-11 HCP, invitational.'];
  for (const s of SUITS) {
    if (s !== x && s !== os && h.len[s] >= 6 && ctx.ok(`2${s}`)) return [`2${s}`, `6+ ${SYM[s]}, to play.`];
  }
  return ['Pass', "Happy in opener's suit."];
}

function afterForcingRebid(ctx: Ctx, x: Suit, y: string | null, z: Suit): Decision {
  const h = ctx.h;
  if (h.judge >= 8 || levelOf(ctx.seq[2]) === 3) {
    if (isMajor(z) && h.len[z] >= 4 && ctx.ok(`4${z}`)) return [`4${z}`, TO_PLAY];
    if (isMajor(x) && h.len[x] >= 3 && ctx.ok(`4${x}`)) return [`4${x}`, TO_PLAY];
    if (isMajor(y) && h.len[y as Suit] >= 6 && ctx.ok(`4${y}`)) return [`4${y}`, TO_PLAY];
    if (ctx.ok('3NT')) return ['3NT', TO_PLAY];
    return continuation(ctx);
  }
  if (isSuit(y) && h.len[y] >= 5) {
    const call = ctx.cheapest(y, 2);
    if (call && levelOf(call) <= 3) return [call, `5+ ${SYM[y]}, weak.`];
  }
  const call = ctx.cheapest(x, 2);
  if (call && h.len[x] >= 2 && levelOf(call) <= 3) return [call, `Preference to ${SYM[x]}.`];
  if (ctx.ok('2NT')) return ['2NT', 'Weak, no fit.'];
  return continuation(ctx);
}

function openerThird(ctx: Ctx, x: Suit): Decision | null {
  const seq = ctx.seq;
  const h = ctx.h;
  const hcp = h.judge;
  const r = seq[1];
  const o = seq[2];
  const last = seq[3];
  const y = strainOf(r);
  if (last === '3NT' || last === '6NT') return ['Pass', 'Partner placed the contract.'];
  if (levelOf(last) >= 4 && isSuit(strainOf(last)) && !isSplinter(x, last)) {
    if (isMinor(strainOf(last)) && last !== `4${x}`) return null;
    return ['Pass', 'Partner placed the contract.'];
  }
  if (last === '2NT' && levelOf(o) <= 2) {
    if (hcp >= 13) {
      if (isMajor(x) && h.len[x] >= 6) return [`4${x}`, TO_PLAY];
      return ['3NT', TO_PLAY];
    }
    return ['Pass', 'Minimum.'];
  }
  if (levelOf(last) === 3 && isSuit(strainOf(last)) && last !== o) {
    const s = strainOf(last) as Suit;
    if (hcp >= 14 || (hcp >= 13 && levelOf(o) === 2)) {
      if (isMajor(s)) return [`4${s}`, TO_PLAY];
      return ['3NT', TO_PLAY];
    }
    return ['Pass', 'Declining the invitation.'];
  }
  if (last === '4NT' && (o === '1NT' || o === '2NT')) {
    const [, hi] = openerRange(seq.slice(0, 3));
    return hcp >= hi - 1 ? ['6NT', TO_PLAY] : ['Pass', 'Minimum, declining.'];
  }
  const nmf = x === 'C' ? '2D' : '2C';
  if (o === '1NT' && last === nmf && isMajor(y)) {
    const ys = y as Suit;
    if (h.len[ys] >= 3) {
      return h.hcp >= 13 ? [`3${ys}`, `3 ${SYM[ys]}, 13-14 HCP.`] : [`2${ys}`, `3 ${SYM[ys]}, 11-12 HCP.`];
    }
    const other: Suit = ys === 'S' ? 'H' : 'S';
    if (h.len[other] >= 4 && ctx.ok(`2${other}`)) return [`2${other}`, `4 ${SYM[other]}.`];
    return h.hcp >= 13 ? ['3NT', TO_PLAY] : ['2NT', '11-12 HCP, no fit.'];
  }
  if (isSuit(y) && isSuit(strainOf(o)) && isSuit(strainOf(last))
    && new Set([x, y, strainOf(o), strainOf(last)]).size === 4) {
    if (h.len[y] >= 3) {
      const call = ctx.cheapest(y, 2);
      if (call) return [call, `3+ ${SYM[y]} support, game forcing.`];
    }
    if (h.len[x] >= 5) {
      const call = ctx.cheapest(x, 2);
      if (call) return [call, `5+ ${SYM[x]}. Game forcing.`];
    }
    const call = ctx.ok('2NT') ? '2NT' : '3NT';
    if (ctx.ok(call)) return [call, 'Game forcing, no better bid.'];
  }
  return null;
}

// ── Strong 2C ─────────────────────────────────────────────────────────────────

function strongTwo(ctx: Ctx): Decision {
  const seq = ctx.seq;
  const h = ctx.h;
  const n = seq.length;
  if (n === 1) {
    for (const s of ['S', 'H', 'D', 'C'] as Suit[]) {
      const call = isMajor(s) ? `2${s}` : `3${s}`;
      if (h.hcp >= 8 && h.len[s] >= 5 && h.goodSuit(s) && ctx.ok(call)) {
        return [call, `5+ ${SYM[s]}, 8+ HCP. Positive.`];
      }
    }
    if (h.hcp >= 8 && h.balanced) return ['2NT', '8+ HCP, balanced. Positive.'];
    return ['2D', 'Waiting. Artificial.'];
  }
  if (n === 2) {
    if (seq[1] === '2D') {
      if (h.balanced && NT_AFTER_2C[0] <= h.hcp && h.hcp <= NT_AFTER_2C[1]) {
        return ['2NT', '22-24 HCP, balanced.'];
      }
      if (h.balanced && h.hcp >= 25) return ['3NT', '25+ HCP, balanced.'];
      const s = h.longest();
      const call = ctx.cheapest(s, 2);
      return [call as string, `4+ ${SYM[s]}. Game forcing.`];
    }
    return continuation(ctx);
  }
  if (seq[1] === '2D' && seq[2] === '2NT') return notrump(ctx, 2);
  if (seq[1] === '2D' && seq[2] === '3NT' && n === 3) {
    if (ctx.h.judge >= 8) return ['6NT', TO_PLAY];
    return ['Pass', 'Partner placed the contract.'];
  }
  if (n === 3 && seq[1] === '2D') {
    const s = strainOf(seq[2]);
    if (isSuit(s) && h.len[s] >= 3) {
      if (h.judge >= 5) {
        const call = ctx.cheapest(s, 3);
        if (call && levelOf(call) === 3) return [call, `3+ ${SYM[s]} support, some values.`];
      }
      if (ctx.ok(`4${s}`) && isMajor(s)) return [`4${s}`, `3+ ${SYM[s]} support, weak.`];
    }
  }
  return continuation(ctx);
}

// ── Weak twos and pre-empts ───────────────────────────────────────────────────

function preempt(ctx: Ctx): Decision {
  const seq = ctx.seq;
  const h = ctx.h;
  const x = strainOf(seq[0]) as Suit;
  if (seq.length === 1) {
    if (isMajor(x) && h.len[x] >= 2 && h.judge >= 16 && ctx.ok(`4${x}`)) return [`4${x}`, TO_PLAY];
    if (isMajor(x) && h.len[x] >= 3 && h.judge <= 15) {
      const call = ctx.cheapest(x, 3);
      if (call && levelOf(call) === 3 && levelOf(seq[0]) === 2) {
        return [call, `3+ ${SYM[x]}, pre-emptive raise.`];
      }
    }
    if (h.judge >= 16 && h.balanced && ctx.ok('3NT')) return ['3NT', TO_PLAY];
    return ['Pass', 'Nothing to add.'];
  }
  return continuation(ctx);
}

// ── Notrump systems ───────────────────────────────────────────────────────────

function ntRange(seq: string[], start: number): [number, number] {
  if (start === 2) return NT_AFTER_2C;
  return seq[start] === '1NT' ? NT1 : NT2;
}

function notrump(ctx: Ctx, start: number): Decision {
  const seq = ctx.seq.slice(start);
  const n = seq.length;
  const base = levelOf(seq[0]);
  const [lo, hi] = ctx.ntOvercall ? NT_OVERCALL : ntRange(ctx.seq, start);
  if (n === 1) return ntResponse(ctx, base, lo, hi);
  if (n === 2) return ntOpenerAnswer(ctx, base, seq[1], lo, hi);
  if (n === 3) return ntResponderSecond(ctx, base, seq, lo, hi);
  if (n === 4) return ntOpenerThird(ctx, base, seq, lo, hi);
  return continuation(ctx);
}

interface NtCodes { stayman: string; to_h: string; to_s: string; mss: string; to_c: string | null; to_d: string | null }

function ntCodes(base: number): NtCodes {
  if (base === 1) return { stayman: '2C', to_h: '2D', to_s: '2H', mss: '2S', to_c: '2NT', to_d: '3C' };
  return { stayman: '3C', to_h: '3D', to_s: '3H', mss: '3S', to_c: null, to_d: null };
}

function ntResponse(ctx: Ctx, base: number, lo: number, hi: number): Decision {
  const h = ctx.h;
  const hcp = h.judge;
  const code = ntCodes(base);
  const m4 = MAJORS.filter((s) => h.len[s] === 4);
  const m5 = MAJORS.filter((s) => h.len[s] >= 5);
  if (hcp + lo >= SLAM) {
    if (m5.length && h.len[h.longest(MAJORS)] >= 6) {
      const s = h.longest(MAJORS);
      const texas = s === 'H' ? '4D' : '4H';
      if (ctx.ok(texas)) return [texas, `Texas: 6+ ${SYM[s]}. Artificial.`];
    }
    if (hcp + lo >= GRAND && ctx.ok('4C')) return ['4C', 'Gerber: asks for aces. Artificial.'];
    return ['6NT', TO_PLAY];
  }
  if (hcp + hi >= SLAM && !m5.length && ctx.ok('4NT')) return ['4NT', 'Quantitative: invites 6NT.'];
  if (hcp + lo >= NT_GAME) {
    if (m5.length) {
      const s = h.longest(MAJORS);
      if (h.len[s] >= 6) {
        const texas = s === 'H' ? '4D' : '4H';
        return [texas, `Texas: 6+ ${SYM[s]}. Artificial.`];
      }
      const call = s === 'H' ? code.to_h : code.to_s;
      return [call, `Transfer: 5+ ${SYM[s]}. Artificial.`];
    }
    if (m4.length && h.shape.join(',') !== '4,3,3,3') {
      return [code.stayman, 'Stayman: asks for a 4-card major. Artificial.'];
    }
    const minors5 = MINORS.filter((m) => h.len[m] >= 5);
    if (minors5.length && MINORS.every((m) => h.len[m] >= 4) && !h.balanced && ctx.ok(code.mss)) {
      return [code.mss, 'Minor Stayman: 5-4+ minors, game forcing. Artificial.'];
    }
    const short = h.short();
    if (base === 1 && short.length && !m5.length && h.shape[0] <= 5
      && SUITS.every((s) => s === short[0] || h.len[s] >= 4)) {
      const s = short[0];
      const call = `3${s}`;
      if (s !== 'C' && ctx.ok(call)) return [call, `Short ${SYM[s]}, 4+ in the others, game forcing.`];
    }
    return ['3NT', TO_PLAY];
  }
  if (hcp + hi >= NT_GAME && base === 1) {
    if (m5.length) {
      const s = h.longest(MAJORS);
      const call = s === 'H' ? code.to_h : code.to_s;
      return [call, `Transfer: 5+ ${SYM[s]}. Artificial.`];
    }
    return [code.stayman, 'Stayman: asks for a 4-card major. Artificial.'];
  }
  if (m5.length) {
    const s = h.longest(MAJORS);
    const call = s === 'H' ? code.to_h : code.to_s;
    return [call, `Transfer: 5+ ${SYM[s]}. Artificial.`];
  }
  if (base === 1 && h.len.C >= 6) return [code.to_c as string, `Transfer: 6+ ${SYM.C}. Artificial.`];
  if (base === 1 && h.len.D >= 6) return [code.to_d as string, `Transfer: 6+ ${SYM.D}. Artificial.`];
  return ['Pass', 'No game.'];
}

function ntOpenerAnswer(ctx: Ctx, base: number, r: string, lo: number, hi: number): Decision {
  void lo;
  const h = ctx.h;
  const code = ntCodes(base);
  const lvl = base === 1 ? 2 : 3;
  if (r === code.stayman) {
    if (h.len.H >= 4) return [`${lvl}H`, `4+ ${SYM.H}.`];
    if (h.len.S >= 4) return [`${lvl}S`, `4+ ${SYM.S}, fewer than 4 ${SYM.H}.`];
    return [`${lvl}D`, 'No 4-card major. Artificial.'];
  }
  for (const [key, s] of [['to_h', 'H'], ['to_s', 'S']] as ['to_h' | 'to_s', Suit][]) {
    if (r === code[key]) {
      if (base === 1 && h.len[s] >= 4 && h.judge >= hi) return [`3${s}`, `4+ ${SYM[s]}, maximum. Super-accept.`];
      return [`${lvl}${s}`, `Completing the transfer to ${SYM[s]}.`];
    }
  }
  if (r === code.to_c && r) return ['3C', `Completing the transfer to ${SYM.C}.`];
  if (r === code.to_d && r) return ['3D', `Completing the transfer to ${SYM.D}.`];
  if (r === code.mss) {
    const minors = MINORS.filter((m) => h.len[m] >= 4);
    if (minors.length) {
      const m = maxBy(minors, (s) => [h.len[s], idx(s)]);
      return [ctx.cheapest(m, 3) as string, `4+ ${SYM[m]}.`];
    }
    return [ctx.ok('2NT') ? '2NT' : '3NT', 'No 4-card minor.'];
  }
  if (r === '4D' || r === '4H') {
    const s = r === '4D' ? 'H' : 'S';
    return [`4${s}`, `Completing the transfer to ${SYM[s]}.`];
  }
  if (r === '4C') return gerberAnswer(ctx);
  if (r === '4NT') {
    if (h.judge >= hi) return ['6NT', TO_PLAY];
    return ['Pass', 'Minimum, declining.'];
  }
  if (base === 1 && ['3D', '3H', '3S'].includes(r)) {
    const s = strainOf(r) as Suit;
    if (h.stopper(s)) return ['3NT', TO_PLAY];
    for (const m of MAJORS) {
      if (m !== s && h.len[m] >= 4 && ctx.ok(`4${m}`)) return [`4${m}`, TO_PLAY];
    }
    const m = h.longest(MINORS.filter((t) => t !== s));
    const call = ctx.cheapest(m, 4);
    if (call && levelOf(call) <= 5) return [call, natural(m)];
    return ['3NT', TO_PLAY];
  }
  return ['Pass', 'Partner placed the contract.'];
}

function ntResponderSecond(ctx: Ctx, base: number, seq: string[], lo: number, hi: number): Decision {
  const h = ctx.h;
  const hcp = h.judge;
  const code = ntCodes(base);
  const r = seq[1];
  const o = seq[2];
  if (r === code.stayman) {
    const s = strainOf(o);
    if (isMajor(s) && h.len[s as Suit] >= 4) {
      if (hcp + lo >= GAME_MAJOR) return placed(ctx, [`4${s}`, TO_PLAY]);
      return placed(ctx, [`3${s}`, 'Invitational.']);
    }
    if (hcp + lo >= NT_GAME) {
      const m5 = MAJORS.filter((m) => h.len[m] >= 5);
      if (m5.length && o !== '2S' && ctx.ok(`3${m5[0]}`)) return [`3${m5[0]}`, `5+ ${SYM[m5[0]]}, game forcing.`];
      return placed(ctx, ['3NT', TO_PLAY]);
    }
    if (ctx.ok('2NT')) return ['2NT', 'Invitational.'];
    return ['Pass', 'No game.'];
  }
  for (const [key, s] of [['to_h', 'H'], ['to_s', 'S']] as ['to_h' | 'to_s', Suit][]) {
    if (r === code[key]) {
      if (o === `3${s}` && base === 1) return hcp >= 4 ? [`4${s}`, TO_PLAY] : ['Pass', 'Weak.'];
      if (hcp + lo >= SLAM && ctx.ok('4NT')) return ['4NT', 'Quantitative: invites 6NT.'];
      if (hcp + lo >= NT_GAME) return placed(ctx, ['3NT', `5 ${SYM[s]}, choice of games.`]);
      if (hcp + hi >= NT_GAME && ctx.ok('2NT')) return ['2NT', `5 ${SYM[s]}, invitational.`];
      return ['Pass', 'Weak.'];
    }
  }
  if ((r === '4D' || r === '4H') && (o === '4H' || o === '4S')) {
    const s = strainOf(o) as Suit;
    if (hcp + lo >= SLAM && ctx.ok('4NT')) return ['4NT', `Keycard Blackwood for ${SYM[s]}. Artificial.`];
    return ['Pass', 'Partner placed the contract.'];
  }
  if (r === code.mss) {
    const m = strainOf(o);
    if (isMinor(m) && hcp + lo >= 29 && ctx.ok(`5${m}`)) return [`5${m}`, TO_PLAY];
    if (ctx.ok('3NT')) return ['3NT', TO_PLAY];
    return ['Pass', 'Partner placed the contract.'];
  }
  return ['Pass', 'Partner placed the contract.'];
}

function ntOpenerThird(ctx: Ctx, base: number, seq: string[], lo: number, hi: number): Decision {
  void lo;
  const h = ctx.h;
  const code = ntCodes(base);
  const r = seq[1];
  const last = seq[3];
  if (last === '2NT' || ((last === '3H' || last === '3S') && r === code.stayman)) {
    if (h.judge >= hi - 1) {
      if (last === '3H' || last === '3S') return [`4${strainOf(last)}`, TO_PLAY];
      const target = strainOf(seq[2]) as Suit;
      if ((r === code.to_h || r === code.to_s) && h.len[target] >= 3) return [`4${target}`, TO_PLAY];
      return ['3NT', TO_PLAY];
    }
    if (r === code.to_h || r === code.to_s) {
      const target = strainOf(seq[2]) as Suit;
      if (h.len[target] >= 3 && ctx.ok(`3${target}`)) return [`3${target}`, 'Minimum, 3-card support.'];
    }
    return ['Pass', 'Minimum, declining.'];
  }
  if (last === '3NT' && (r === code.to_h || r === code.to_s)) {
    const target = strainOf(seq[2]) as Suit;
    if (h.len[target] >= 3) return [`4${target}`, TO_PLAY];
    return ['Pass', 'Partner placed the contract.'];
  }
  if (last === '4NT') return h.judge >= hi ? ['6NT', TO_PLAY] : ['Pass', 'Minimum, declining.'];
  if (r === code.stayman && levelOf(last) === 3 && isMajor(strainOf(last))) {
    const s = strainOf(last) as Suit;
    if (h.len[s] >= 3 && ctx.ok(`4${s}`)) return [`4${s}`, TO_PLAY];
    return ['3NT', TO_PLAY];
  }
  return ['Pass', 'Partner placed the contract.'];
}

// ── Slam conventions ──────────────────────────────────────────────────────────

export function shownSuit(seq: string[], i: number): string | null {
  const call = seq[i];
  const s = strainOf(call);
  if (s === null || s === 'NT') {
    if (i === 1 && call === '2NT' && isMajor(strainOf(seq[0])) && levelOf(seq[0]) === 1) {
      return strainOf(seq[0]);
    }
    return null;
  }
  const first = seq[0];
  if (first === '1NT' || first === '2NT' || (first === '2C' && seq.length > 2 && seq[2] === '2NT')) {
    const start = first === '1NT' || first === '2NT' ? 0 : 2;
    const base = levelOf(seq[start]);
    const code = ntCodes(base);
    if (i === start + 1) {
      if (call === code.stayman || call === code.mss || call === '4C') return null;
      if (call === code.to_h || call === '4D') return 'H';
      if (call === code.to_s || call === '4H') return 'S';
      if (call === code.to_c || call === code.to_d) return call === code.to_c ? 'C' : 'D';
      if (base === 1 && ['3D', '3H', '3S'].includes(call)) return null;
    }
    if (i === start + 2 && (seq[start + 1] === code.stayman || seq[start + 1] === code.mss)) {
      return (call === '2D' || call === '3D') && seq[start + 1] === code.stayman ? null : s;
    }
    if (i < start) return null;
  }
  if (first === '2C' && i === 0) return null;
  if (first === '2C' && i === 1 && call === '2D') return null;
  if (i === 1 && levelOf(first) === 1 && isMajor(strainOf(first))) {
    const x = strainOf(first) as Suit;
    if (isSplinter(x, call)) return x;
  }
  if (i === 2 && seq[1] === '2NT' && isMajor(strainOf(first)) && levelOf(first) === 1) return null;
  if (i === 3 && seq.length > 3
    && new Set(seq.slice(0, 4).map(strainOf).filter((t) => isSuit(t))).size === 4) {
    return null;
  }
  return s;
}

export function agreedTrump(seq: string[]): string | null {
  const shown: [Set<string>, Set<string>] = [new Set(), new Set()];
  let agreed: string | null = null;
  for (let i = 0; i < seq.length; i++) {
    const s = shownSuit(seq, i);
    if (s === null) continue;
    const side = i % 2;
    if (shown[1 - side].has(s)) agreed = s;
    shown[side].add(s);
  }
  return agreed;
}

function answerAsk(ctx: Ctx): Decision | null {
  const seq = ctx.seq;
  if (seq.length < 2 || ctx.ours[ctx.ours.length - 1][0] !== ctx.pd) return null;
  const h = ctx.h;
  const last = seq[seq.length - 1];
  const prior = seq.slice(0, -1);
  let trump = agreedTrump(prior);
  if (last === '4NT' && trump && !quantitative(prior)) {
    const t = trump as Suit;
    const lastCall = ctx.calls[ctx.calls.length - 1];
    const interfered = ctx.calls.length > 0 && lastCall[0] !== ctx.me && lastCall[0] !== ctx.pd
      && lastCall[1] !== 'Pass';
    const keys = h.keycards(t);
    if (interfered) {
      if (keys % 3 === 0 && ctx.ok('X')) return ['X', 'DOPI: 0 or 3 keycards.'];
      if (keys % 3 === 1) return ['Pass', 'DOPI: 1 or 4 keycards.'];
      const call = ctx.cheapest(t, 5);
      if (call) return [call, 'DOPI: 2 or 5 keycards.'];
      return ['Pass', 'DOPI: no room.'];
    }
    const voids = SUITS.filter((s) => s !== t && h.len[s] === 0);
    if (voids.length && (keys === 2 || keys === 4) && ctx.ok('5NT')) {
      return ['5NT', 'Even keycards and a void. Artificial.'];
    }
    if (voids.length && (keys === 1 || keys === 3)) {
      const v = voids[0];
      const call = rankOf(`6${v}`) < rankOf(`6${t}`) ? `6${v}` : `6${t}`;
      if (ctx.ok(call)) return [call, 'Odd keycards and a void. Artificial.'];
    }
    if (keys === 0 || keys === 3) return ['5C', '0 or 3 keycards. Artificial.'];
    if (keys === 1 || keys === 4) return ['5D', '1 or 4 keycards. Artificial.'];
    if (h.has(t, 'Q')) return ['5S', '2 or 5 keycards, with the trump queen. Artificial.'];
    return ['5H', '2 or 5 keycards, no trump queen. Artificial.'];
  }
  if (prior.length >= 2 && (prior[prior.length - 1] === '5C' || prior[prior.length - 1] === '5D')
    && askedRkcb(prior.slice(0, -1))) {
    trump = agreedTrump(prior.slice(0, -2));
    if (trump && last === queenAsk(prior[prior.length - 1], trump)) {
      if (h.has(trump as Suit, 'Q')) return ['5NT', 'Trump queen. Artificial.'];
      const call = ctx.cheapest(trump, 5);
      if (call) return [call, 'No trump queen.'];
      return ['Pass', 'No trump queen.'];
    }
  }
  if (prior.length >= 2 && last === '5NT' && askedRkcb(prior.slice(0, -1))
    && ['5C', '5D', '5H', '5S'].includes(prior[prior.length - 1])) {
    trump = agreedTrump(prior.slice(0, -2));
    if (trump) {
      for (const s of SUITS) {
        const call = `6${s}`;
        if (s !== trump && h.has(s, 'K') && ctx.ok(call) && rankOf(call) < rankOf(`6${trump}`)) {
          return [call, `King of ${SYM[s]}.`];
        }
      }
      return [`6${trump}`, 'No side king to show.'];
    }
  }
  if (last === '4C' && isGerber(prior) && (ctx.weOpened && !ctx.theirs.length || ctx.ntOvercall)) return gerberAnswer(ctx);
  return null;
}

function quantitative(prior: string[]): boolean {
  return prior.length > 0 && ['1NT', '2NT', '3NT'].includes(prior[prior.length - 1])
    && !prior.slice(-1).some((c) => isSuit(strainOf(c)));
}

function askedRkcb(prior: string[]): boolean {
  return prior.length > 0 && prior[prior.length - 1] === '4NT'
    && agreedTrump(prior.slice(0, -1)) !== null && !quantitative(prior.slice(0, -1));
}

function queenAsk(response: string, trump: string): string {
  const order = response === '5C' ? ['5D', '5H', '5S'] : ['5H', '5S'];
  for (const call of order) {
    if (strainOf(call) !== trump) return call;
  }
  return '5NT';
}

function isGerber(prior: string[]): boolean {
  return prior.length > 0 && (prior[prior.length - 1] === '1NT' || prior[prior.length - 1] === '2NT')
    && (prior.length === 1 || prior.length === 3);
}

function gerberAnswer(ctx: Ctx): Decision {
  const aces = ctx.h.aces();
  if (aces === 0 || aces === 4) return ['4D', '0 or 4 aces. Artificial.'];
  return ({ 1: ['4H', '1 ace. Artificial.'], 2: ['4S', '2 aces. Artificial.'],
    3: ['4NT', '3 aces.'] } as Record<number, Decision>)[aces];
}

function afterMyAsk(ctx: Ctx): Decision | null {
  const seq = ctx.seq;
  if (seq.length < 2 || ctx.ours[ctx.ours.length - 1][0] !== ctx.pd) return null;
  const h = ctx.h;
  const last = seq[seq.length - 1];
  const prior = seq.slice(0, -1);
  const myAsk = prior.length ? prior[prior.length - 1] : null;
  if (myAsk === '4NT' && askedRkcb(prior)) {
    const trump = agreedTrump(prior.slice(0, -1)) as Suit;
    const mine = h.keycards(trump);
    const sets: Record<string, [number, number]> = {
      '5C': [0, 3], '5D': [1, 4], '5H': [2, 5], '5S': [2, 5], '5NT': [2, 4],
    };
    let options: [number, number] | undefined = sets[last];
    if (options === undefined && levelOf(last) === 6) options = [1, 3];
    if (options === undefined) return null;
    const theirs = mine + options[1] <= 5 && mine <= 1 ? options[1] : options[0];
    const missing = 5 - mine - theirs;
    const queen = h.has(trump, 'Q') || last === '5S';
    if (missing >= 2) {
      const call = ctx.cheapest(trump, 5);
      return call ? [call, TO_PLAY] : ['Pass', TO_PLAY];
    }
    if (missing === 1 || levelOf(last) === 6) {
      const call = ctx.cheapest(trump, 6);
      if (call && levelOf(call) === 6) return [call, TO_PLAY];
      return ['Pass', TO_PLAY];
    }
    if ((last === '5C' || last === '5D') && !queen) {
      const ask = queenAsk(last, trump);
      if (ctx.ok(ask)) return [ask, 'Asks for the trump queen. Artificial.'];
    }
    if (ctx.ok('5NT') && h.judge >= 20) return ['5NT', 'All keycards present; asks for kings. Artificial.'];
    return [`6${trump}`, TO_PLAY];
  }
  if (prior.length >= 3 && (prior[prior.length - 2] === '5C' || prior[prior.length - 2] === '5D')
    && askedRkcb(prior.slice(0, -2))) {
    const trump = agreedTrump(prior.slice(0, -3));
    if (trump && prior[prior.length - 1] === queenAsk(prior[prior.length - 2], trump)) {
      if (last === '5NT') return [h.judge >= 22 ? `7${trump}` : `6${trump}`, TO_PLAY];
      if (levelOf(last) === 5) return [`6${trump}`, TO_PLAY];
      return ['Pass', TO_PLAY];
    }
  }
  if (prior.length >= 3 && prior[prior.length - 1] === '5NT' && askedRkcb(prior.slice(0, -2))) {
    const trump = agreedTrump(prior.slice(0, -3));
    if (trump && levelOf(last) === 6) {
      if (strainOf(last) !== trump && h.judge >= 20 && ctx.ok(`7${trump}`)) return [`7${trump}`, TO_PLAY];
      if (strainOf(last) === trump) return ['Pass', TO_PLAY];
      return [`6${trump}`, TO_PLAY];
    }
  }
  if (myAsk === '4C' && isGerber(prior.slice(0, -1)) && (ctx.weOpened && !ctx.theirs.length || ctx.ntOvercall)) {
    let theirs = ({ '4D': 0, '4H': 1, '4S': 2, '4NT': 3 } as Record<string, number>)[last];
    if (theirs === undefined) return null;
    const mine = h.aces();
    if (last === '4D' && mine === 0) theirs = 4;
    const missing = 4 - mine - theirs;
    if (missing >= 2) return ctx.ok('4NT') ? ['4NT', TO_PLAY] : ['5NT', TO_PLAY];
    if (missing === 1) return ['6NT', TO_PLAY];
    return h.judge >= 20 ? ['7NT', TO_PLAY] : ['6NT', TO_PLAY];
  }
  return null;
}

// ── Generic continuation ──────────────────────────────────────────────────────

function partnerMin(seq: string[], parity: number): number {
  let best = 0;
  const first = seq[0];
  seq.forEach((call, i) => {
    if (i % 2 !== parity) return;
    if (i === 0) {
      best = Math.max(best, ({ '1NT': 15, '2NT': 20, '2C': 22 } as Record<string, number>)[call]
        ?? (levelOf(call) === 1 ? 11 : 5));
    } else if (i === 1) {
      const x = strainOf(first);
      if (levelOf(first) === 1 && isSuit(x)) {
        let v: number;
        if (call === '2NT' && isMajor(x)) v = 13;
        else if (levelOf(call) === 2 && isSuit(strainOf(call)) && strainOf(call) !== x
          && isTwoOverOne(x, strainOf(call))) v = 12;
        else if (call === `3${x}`) v = isMajor(x) ? 11 : 6;
        else v = 6;
        best = Math.max(best, v);
      } else if (first === '2C') {
        best = Math.max(best, call !== '2D' ? 8 : 0);
      }
    }
  });
  return best;
}

function shownLengths(seq: string[], parity: number): Record<Suit, number> {
  const lengths: Record<Suit, number> = { C: 0, D: 0, H: 0, S: 0 };
  for (let i = 0; i < seq.length; i++) {
    if (i % 2 !== parity) continue;
    const s = shownSuit(seq, i);
    if (s === null || !isSuit(s)) continue;
    let times = 0;
    for (let j = 0; j <= i; j++) if (j % 2 === parity && shownSuit(seq, j) === s) times++;
    let base = i === 0 && isMajor(s) ? 5 : 4;
    if (i === 0 && isMinor(s)) base = 3;
    if (['2D', '2H', '2S'].includes(seq[i]) && i === 0) base = 6;
    if (levelOf(seq[i]) >= 3 && i === 0) base = 7;
    lengths[s] = Math.max(lengths[s], base + (times >= 2 ? 1 : 0));
  }
  return lengths;
}

function gameForced(seq: string[], ctx: Ctx): boolean {
  if (!seq.length) return false;
  if (OVERCALL_READ && !ctx.weOpened && theirOpeningSuit(ctx)) return false;
  const first = seq[0];
  const x = strainOf(first);
  if (first === '2C') return !(seq.length > 2 && seq[1] === '2D' && seq[2] === '2NT');
  if (levelOf(first) === 1 && isSuit(x) && seq.length >= 2) {
    const r = seq[1];
    const rs = strainOf(r);
    const responder = ctx.ours[1][0];
    if (!ctx.passedHand(responder)) {
      if (r === '2NT' && isMajor(x)) return true;
      if (levelOf(r) === 2 && isSuit(rs) && rs !== x && (isTwoOverOne(x, rs) || idx(rs) > idx(x))) {
        return true;
      }
      if (isMajor(x) && isSplinter(x, r)) return true;
    }
    if (seq.length >= 4 && new Set(seq.slice(0, 4).map(strainOf).filter((t) => isSuit(t))).size === 4) {
      return true;
    }
    if (seq.length >= 3 && levelOf(seq[2]) === 3 && isSuit(strainOf(seq[2]))
      && strainOf(seq[2]) !== x && strainOf(seq[2]) !== rs) {
      return true;
    }
  }
  return false;
}

/** Our two-suited overcall (Unusual 2NT, Michaels), 8+ HCP and 5-5:
 *  advancer with 3+ in one of the suits and game values (judge + 8 >= 25)
 *  bids game in it instead of the cheapest preference (deal 163). */
export const TWO_SUITER_GAME = true;
/** ...and the later rounds read it as two suits, not as a 2NT opening
 *  whose next bids are Stayman and transfers. */
export const TWO_SUITER_READ = true;

/** The suits our first call showed, when it was a two-suited overcall
 *  straight over their one-level opening. */
function ourTwoSuiter(ctx: Ctx): [Suit, Suit | null] | null {
  if (ctx.weOpened || !ctx.seq.length) return null;
  const i = ctx.calls.findIndex(([, c]) => c !== 'Pass');
  if (i < 0 || ctx.calls.length <= i + 1 || ctx.calls[i + 1][1] !== ctx.seq[0]) return null;
  return twoSuitsShown(ctx.seq[0], ctx.calls[i][1]);
}

/** Overcaller (parity 0): 5 in each shown suit, 6 once rebid, 4 in a new
 *  suit. Advancer: 3 in the suit preferred, 5 in a suit of their own. */
/** Our natural two-level overcall, (1x) 2y, is 5+ y and 10-17 HCP. The later
 *  rounds read it as an opening: (1♦) 2♣ as a strong 2♣, game forcing, so
 *  on deal 67 South bid 3NT on 10 HCP over their 2NT and went six down; and
 *  2♦/2♥/2♠ as a weak two. The opening's forcing rules apply only when we
 *  opened. */
export const OVERCALL_READ = true;

/** Their opening's suit, when they opened at the one level in a suit. */
function theirOpeningSuit(ctx: Ctx): Suit | null {
  const first = ctx.calls.find(([, c]) => c !== 'Pass');
  if (ctx.weOpened || !first || levelOf(first[1]) !== 1) return null;
  const s = strainOf(first[1]);
  return isSuit(s) ? s : null;
}

/** [y, null] when our first call was a natural, non-jump two-level suit
 *  overcall straight over their one-level opening. */
function ourTwoLevelOvercall(ctx: Ctx): [Suit, Suit | null] | null {
  if (ctx.weOpened || !ctx.seq.length) return null;
  const i = ctx.calls.findIndex(([, c]) => c !== 'Pass');
  if (i < 0 || ctx.calls.length <= i + 1 || ctx.calls[i + 1][1] !== ctx.seq[0]) return null;
  const opening = ctx.calls[i][1], call = ctx.seq[0];
  const y = strainOf(call);
  if (!theirOpeningSuit(ctx) || levelOf(call) !== 2 || !isSuit(y)
    || y === strainOf(opening) || rankOf(`1${y}`) > rankOf(opening)) {
    return null;
  }
  return [y, null];
}

function twoSuiterLengths(seq: string[], parity: number, two: [Suit, Suit | null]): Record<Suit, number> {
  const lengths: Record<Suit, number> = { C: 0, D: 0, H: 0, S: 0 };
  const shown = two.filter((t): t is Suit => t !== null);
  for (let i = parity; i < seq.length; i += 2) {
    const s = strainOf(seq[i]);
    if (parity === 0) {
      if (i === 0) {
        for (const t of shown) lengths[t] = 5;
      } else if (isSuit(s) && shown.includes(s)) {
        lengths[s] = 6;
      } else if (isSuit(s)) {
        lengths[s] = Math.max(lengths[s], 4);
      }
    } else if (isSuit(s)) {
      lengths[s] = Math.max(lengths[s], shown.includes(s) ? 3 : 5);
    }
  }
  return lengths;
}

/** When THEY hold the contract at 3NT or the four level, it is not our game
 *  reached: double for penalty if our side has shown game values (bid
 *  game, a game-forcing auction, or judge + partner's minimum >= GAME),
 *  else pass. Before, the robots passed it as "Game reached". */
export const THEIR_CONTRACT_DOUBLE = true;
const OVER_THEIRS = 'Their contract; nothing more to show.';
/** ...and our side bidding to the four level counts as those values. */
export const VALUES_AT_FOUR = true;

function isGameBid(call: string): boolean {
  const st = strainOf(call);
  return call === '3NT' || (levelOf(call) >= 4 && (st === 'H' || st === 'S' || st === 'NT'))
    || (levelOf(call) >= 5 && (st === 'C' || st === 'D'));
}

/** Count the fit (the user's call, 2026-10-22). Here tricks follow the trumps
 *  the partnership holds together, about 0.8 a card, against 0.12 a
 *  judgement point: on the library an 8-card fit makes game 18% of the time,
 *  a 10-card fit 51%. Once a fit is known, game is judged on judgement points
 *  plus FIT_POINTS for each trump the two hands are known to hold past
 *  FIT_BASE, minus as many for each trump short of it, plus VOID_POINTS for a
 *  side void in a hand with three or more trumps. Only where a call is
 *  judged, never in a range a call shows. Head to head it pays by stopping
 *  short on 8- and 9-card fits: a FIT_BASE of 8, which only adds, lost
 *  1.5-2.0 points a board (t = -3.4 to -4.3). */
export const FIT_COUNT = true;
const FIT_POINTS = 3;
const FIT_BASE = 10;
const VOID_POINTS = 3;

/** Judgement points the known fit in `trump` is worth to this hand. */
function fitBonus(h: Hand, trump: string | null, partnerLen: number): number {
  if (!FIT_COUNT || !isSuit(trump) || !partnerLen) return 0;
  let bonus = FIT_POINTS * (h.len[trump] + partnerLen - FIT_BASE);
  if (h.len[trump] >= 3 && SUITS.some((s) => s !== trump && h.len[s] === 0)) bonus += VOID_POINTS;
  return bonus;
}

/** The Law of Total Tricks in competition (the user's call, 2026-10-22):
 *  when they hold the contract and we would pass, bid our fit to the level
 *  of the trumps we hold together (8 trumps the two level, 9 the three,
 *  10 the four), never past LOTT_MAX. In this game the law is close to
 *  exact: a fit of 8, 9 and 10 takes 8.3, 9.0 and 9.9 tricks on the library.
 *  A raise of partner's suit keeps to GIB's free raise, LOTT_RAISE HCP, so
 *  it reads as the raise GIB's own branches make (a weaker or a stronger
 *  hand bidding it would make their "6+" or "6-9 HCP" untrue); a hand
 *  rebidding its own suit needs only to have bid it. */
export const LOTT = true;
const LOTT_MAX = 5;
const LOTT_RAISE = [6, 9];
export const LOTT_ALERT = 'Competing to the level of our fit.';
/** ...and below LOTT_RAISE, a raise with 3+ trumps and a side singleton or
 *  void (the user's call: a weak raise is fine with distribution). GIB's free
 *  raises, the same call in the same auctions, then read COMPETITIVE_RAISE
 *  instead of quoting HCP, so one alert stays true of both. */
export const LOTT_SHORT = true;

export function raiseAlert(x: Suit, text: string): string {
  return LOTT && LOTT_SHORT ? `3+ ${SYM[x]}, competitive.` : text;
}

/** A cuebid raise (our bid in their suit after the other partner bid a suit)
 *  shows 3+ of that suit to the LoTT, both for the partner who cuebid and for
 *  the one who reads it (2026-10-24, deal 338). See gib.py. */
export const CUE_RAISE_FIT = true;

/** The suit our call i raised by cuebidding their suit, or null. */
function cueRaise(ctx: Ctx, i: number): Suit | null {
  if (!CUE_RAISE_FIT) return null;
  const [who, call] = ctx.ours[i];
  if (!theirSuits(ctx).includes(strainOf(call) as Suit)) return null;
  for (let j = i - 1; j >= 0; j--) {
    if (ctx.ours[j][0] !== who) {
      const s = shownSuit(ctx.seq, j);
      return s !== null && (SUITS as readonly string[]).includes(s) && !theirSuits(ctx).includes(s as Suit)
        ? s as Suit : null;
    }
  }
  return null;
}

/** The fewest cards in `s` partner's natural bids have shown. */
function partnerLength(ctx: Ctx, s: Suit): number {
  if (theirSuits(ctx).includes(s)) return 0;
  let n = 0;
  let mineFirst: number | null = null;
  for (let i = 0; i < ctx.ours.length; i++) {
    const [who, call] = ctx.ours[i];
    if (who !== ctx.me && cueRaise(ctx, i) === s) {
      n = Math.max(n, 3);
      continue;
    }
    if (shownSuit(ctx.seq, i) !== s) continue;
    if (who === ctx.me) {
      if (mineFirst === null) mineFirst = i;
      continue;
    }
    if (n) n += 1;                       // partner bid it again
    else if (mineFirst !== null) n = 3;  // a raise of my suit
    else if (i === 0) {
      const lvl = levelOf(call);
      if (ctx.weOpened) n = lvl === 1 ? (isMajor(s) ? 5 : 3) : lvl === 2 ? 6 : 7;
      else n = jump(ctx, i) ? 6 : 5;    // an overcall
    } else n = 4;                        // a new suit
  }
  return n;
}

/** Was our side's call i a jump over the bid before it? */
function jump(ctx: Ctx, i: number): boolean {
  const [who, call] = ctx.ours[i];
  const at = ctx.calls.findIndex(([w, c]) => w === who && c === call);
  const before = ctx.calls.slice(0, at).map(([, c]) => c).filter((c) => levelOf(c));
  if (!before.length) return false;
  const s = strainOf(call);
  let need = 1;
  while (rankOf(`${need}${s}`) <= rankOf(before[before.length - 1])) need++;
  return levelOf(call) > need;
}

function totalTricks(ctx: Ctx, decision: Decision | null): Decision | null {
  if (!LOTT || !ctx.theirs.length || (decision && decision[0] !== 'Pass')) return null;
  const hb = ctx.auction.highestBid;
  if (!hb || hb[2] === ctx.me || hb[2] === ctx.pd || ctx.auction.doubled !== 'None') return null;
  let best: [number[], string] | null = null;
  for (const s of SUITS) {
    const p = partnerLength(ctx, s);
    const n = ctx.h.len[s] + p;
    if (!p || n < 8) continue;
    const mine = ctx.ours.some(([w], i) => w === ctx.me
      && (shownSuit(ctx.seq, i) === s || cueRaise(ctx, i) === s));
    const weak = LOTT_SHORT && ctx.h.hcp < LOTT_RAISE[0] && ctx.h.len[s] >= 3
      && ctx.h.short(s).length > 0;
    if (!mine && !weak && !(LOTT_RAISE[0] <= ctx.h.hcp && ctx.h.hcp <= LOTT_RAISE[1])) continue;
    const call = ctx.cheapest(s, 1);
    if (call === null || levelOf(call) > Math.min(n - 6, LOTT_MAX)) continue;
    const key = [n, isMajor(s) ? 1 : 0, idx(s)];
    if (best === null || cmpTuple(key, best[0]) > 0) best = [key, call];
  }
  if (best === null) return null;
  const s = strainOf(best[1]) as Suit;
  const mine = ctx.ours.some(([w], i) => w === ctx.me
    && (shownSuit(ctx.seq, i) === s || cueRaise(ctx, i) === s));
  if (!mine && ctx.h.len[s] >= 3) return [best[1], raiseAlert(s, LOTT_ALERT)];
  return [best[1], LOTT_ALERT];
}

/** Jam to game on a ten-card fit (the user's call, 2026-10-28). When
 *  partner's opening is the only bid our side has made, my first call is game
 *  in it if my length and partner's shown length make JAM_FIT: over any call
 *  of theirs, and over a pass too after a pre-empt. See gib.py. */
export const JAM_GAME = true;
export const JAM_FIT = 10;
export const JAM_OPENINGS = [1, 2, 3];
export const JAM_OVER_BIDS = true;
export const JAM_UNCONTESTED = true;
export const JAM_MINORS = false;
const jamText = (x: Suit) => `Game in ${SYM[x]}: to make or to jam the auction.`;

/** The game call partner's opening asks of my first call, or null. */
function jamSpot(ctx: Ctx): string | null {
  if (!JAM_GAME || !ctx.weOpened || ctx.iAmOpener() || ctx.seq.length !== 1) return null;
  const at = ctx.calls.findIndex(([w, c]) => w === ctx.ours[0][0] && c === ctx.ours[0][1]);
  if (ctx.calls.slice(at + 1).some(([w]) => w === ctx.me)) return null;   // now or never
  const x = strainOf(ctx.seq[0]);
  if (!isSuit(x) || !JAM_OPENINGS.includes(levelOf(ctx.seq[0])) || ctx.seq[0] === '2C'
    || (isMinor(x) && !JAM_MINORS)) return null;
  if (!ctx.theirs.length && (!JAM_UNCONTESTED || levelOf(ctx.seq[0]) === 1)) return null;
  if (!JAM_OVER_BIDS && ctx.theirs.some(([, c]) => c !== 'X')) return null;
  const game = isMajor(x) ? `4${x}` : `5${x}`;
  return ctx.ok(game) ? game : null;
}

function jamGame(ctx: Ctx): Decision | null {
  const game = jamSpot(ctx);
  if (game === null) return null;
  const x = strainOf(game) as Suit;
  return ctx.h.len[x] + partnerLength(ctx, x) >= JAM_FIT ? [game, jamText(x)] : null;
}

/** Both of us after the jump to game in the jam seat: the contract is placed
 *  and the auction jammed, so pass, whatever they bid next. */
function afterJam(ctx: Ctx): Decision | null {
  if (!JAM_GAME || ctx.seq.length < 2 || !ctx.legal.length) return null;
  const jammer = ctx.ours[1][0];
  if (ctx.ours[0][0] === jammer) return null;
  const at = ctx.calls.findIndex(([w, c]) => w === jammer && c === ctx.ours[1][1]);
  const before = new Ctx(jammer, [], replay(ctx.auction, at));
  return ctx.seq[1] === jamSpot(before) ? ['Pass', 'The contract is placed.'] : null;
}

function replay(auction: AuctionState, n: number): AuctionState {
  const a = new AuctionState(auction.dealer, auction.vulnerability);
  for (const [who, call] of auction.calls.slice(0, n)) a.applyCall(who, call);
  return a;
}

/** Any branch's game bid in the jam seat reads the jam's alert, so the same
 *  call in the same auction says the same thing whoever holds it. */
export function jamAlert(player: Seat, cards: Card[], auction: AuctionState,
  decision: Decision): Decision {
  if (JAM_GAME && decision[0] === jamSpot(new Ctx(player, cards, auction))) {
    return [decision[0], jamText(strainOf(decision[0]) as Suit)];
  }
  return decision;
}

/** A major game, not 3NT, on a known eight-card major fit (the user's call,
 *  2026-10-23): instead of bidding 3NT, or passing partner's 3NT, bid 4M when
 *  my length and what partner's bids have shown (a natural notrump bid shows
 *  two) make eight. A fit both of us have bid is left alone: 1M-2M-3NT is
 *  already a choice of games (roadmap 3.7). See gib.py. */
export const MAJOR_OVER_3NT = true;

function majorOverNotrump(ctx: Ctx, decision: Decision | null): Decision | null {
  if (!MAJOR_OVER_3NT || decision === null) return null;
  const hb = ctx.auction.highestBid;
  const standing = decision[0] === 'Pass' && !!hb && hb[0] === 3 && hb[1] === 'NT'
    && hb[2] === ctx.pd && ctx.auction.doubled === 'None';
  if (decision[0] !== '3NT' && !standing) return null;
  let best: [number, Suit] | null = null;
  for (const s of MAJORS) {
    if (agreed(ctx, s)) continue;
    const nt = ntLength(ctx);
    const n = ctx.h.len[s] + (transferred(ctx, s) ? nt : (partnerLength(ctx, s) || nt));
    if (n >= 8 && ctx.ok(`4${s}`) && (best === null || n > best[0])) best = [n, s];
  }
  if (best === null) return null;
  return [`4${best[1]}`, TO_PLAY];
}

/** Have both of us bid `s` naturally? */
function agreed(ctx: Ctx, s: Suit): boolean {
  return [ctx.me, ctx.pd].every((who) => ctx.ours.some(([w, c], i) =>
    w === who && strainOf(c) === s && shownSuit(ctx.seq, i) === s));
}

/** Did I show `s` with a transfer? Then partner's bid of it completed the
 *  transfer and shows no length of its own. */
function transferred(ctx: Ctx, s: Suit): boolean {
  return ctx.ours.some(([w, c], i) => w === ctx.me && shownSuit(ctx.seq, i) === s && strainOf(c) !== s);
}

/** Partner's natural notrump bid shows a balanced hand: 2+ in every suit. */
function ntLength(ctx: Ctx): number {
  return ctx.ours.some(([w, c]) => w === ctx.pd && strainOf(c) === 'NT') ? 2 : 0;
}

function overTheirContract(ctx: Ctx, values: boolean): Decision {
  if (values && ctx.ok('X')) return ['X', 'Penalty: our side has the values for game.'];
  return ['Pass', OVER_THEIRS];
}

function continuation(ctx: Ctx): Decision {
  const seq = ctx.seq;
  const h = ctx.h;
  let meParity = ctx.iAmOpener() ? 0 : 1;
  if (!ctx.weOpened) meParity = ctx.ours.length && ctx.ours[0][0] === ctx.me ? 0 : 1;
  const pParity = 1 - meParity;
  let pmin = partnerMin(seq, pParity);
  let plen = shownLengths(seq, pParity);
  let mylen = shownLengths(seq, meParity);
  let trump = agreedTrump(seq);
  let two = TWO_SUITER_READ ? ourTwoSuiter(ctx) : null;
  let shows = TWO_SUITED_MIN;
  if (!two && OVERCALL_READ) {
    two = ourTwoLevelOvercall(ctx);
    shows = OVERCALL_2[0];
  }
  if (two) {
    pmin = pParity === 0 ? shows : 0;
    plen = twoSuiterLengths(seq, pParity, two);
    mylen = twoSuiterLengths(seq, meParity, two);
    const p2 = plen, m2 = mylen;
    trump = SUITS.find((s) => p2[s] && m2[s] && p2[s] + m2[s] >= 8) ?? null;
  }
  let comb = h.judge + pmin;
  const gf = gameForced(seq, ctx) && !two;
  const current = ctx.current();
  const curRank = current ? rankOf(current) : -1;
  const partners = ctx.partners();
  const partnerLast = partners.length ? partners[partners.length - 1] : null;

  const fits: Suit[] = SUITS.filter((s) => plen[s] && plen[s] + h.len[s] >= 8);
  if (isSuit(trump) && !fits.includes(trump)) fits.push(trump);
  let fit: Suit | null = null;
  if (fits.length) fit = maxBy(fits, (s) => [isMajor(s) ? 1 : 0, plen[s] + h.len[s], idx(s)]);

  if (partnerLast && levelOf(partnerLast) >= 6) return ['Pass', 'Partner placed the contract.'];
  const hb = ctx.auction.highestBid;
  const theirsHold = THEIR_CONTRACT_DOUBLE && !!hb && hb[2] !== ctx.me && hb[2] !== ctx.pd;
  const values = gf || comb >= GAME || seq.some((c) => isGameBid(c))
    || (VALUES_AT_FOUR && seq.some((c) => levelOf(c) >= 4));
  if (fit) {
    if (trump === fit && comb >= SLAM && ctx.ok('4NT') && curRank < rankOf('4NT') && !seq.includes('4NT')) {
      return ['4NT', `Keycard Blackwood for ${SYM[fit]}. Artificial.`];
    }
    comb += fitBonus(h, fit, plen[fit]);
    if (isMajor(fit)) {
      if (comb >= GAME_MAJOR || gf) {
        if (curRank >= rankOf(`4${fit}`)) {
          if (theirsHold) return overTheirContract(ctx, values);
          return ['Pass', 'Game reached.'];
        }
        return [`4${fit}`, TO_PLAY];
      }
      const call = ctx.cheapest(fit, 2);
      if (comb >= GAME_MAJOR - 2 && call && levelOf(call) <= 3) return [call, natural(fit)];
      if (partnerLast && strainOf(partnerLast) === fit) return ['Pass', 'No game.'];
      if (call && levelOf(call) <= 2) return [call, natural(fit)];
      return ['Pass', 'No game.'];
    }
    if (comb >= GAME || gf) {
      if (curRank < rankOf('3NT') && h.balanced) return ['3NT', TO_PLAY];
      if (comb >= 29 && curRank < rankOf(`5${fit}`)) return [`5${fit}`, TO_PLAY];
      if (curRank < rankOf('3NT')) return ['3NT', TO_PLAY];
      if (theirsHold) return overTheirContract(ctx, values);
      return ['Pass', 'Game reached.'];
    }
    if (partnerLast && strainOf(partnerLast) === fit) return ['Pass', 'No game.'];
    const call = ctx.cheapest(fit, 2);
    if (call && levelOf(call) <= 3) return [call, natural(fit)];
    return ['Pass', 'No game.'];
  }

  if ((current && levelOf(current) >= 4) || current === '3NT') {
    if (theirsHold) return overTheirContract(ctx, values);
    return ['Pass', 'Game reached.'];
  }
  if (gf || comb >= GAME) {
    for (const s of SUITS) {
      if (h.len[s] >= 6 && !mylen[s]) {
        const call = ctx.cheapest(s, 2);
        if (call && rankOf(call) < rankOf('3NT')) return [call, natural(s)];
      }
    }
    if (ctx.ok('3NT')) return ['3NT', TO_PLAY];
    return ['Pass', 'Game reached.'];
  }
  if (partnerLast && forcing(ctx, partnerLast)) {
    const s = h.longest();
    const call = ctx.cheapest(s, 1);
    if (call && levelOf(call) <= 3) return [call, natural(s)];
  }
  return ['Pass', 'No game.'];
}

function forcing(ctx: Ctx, call: string): boolean {
  const seq = ctx.seq;
  const i = seq.length - 1;
  return shownSuit(seq, i) === null && isSuit(strainOf(call));
}

// ── Contested auctions ────────────────────────────────────────────────────────

function contested(ctx: Ctx): Decision | null {
  const seq = ctx.seq;
  if (ctx.weOpened && seq.length && ['1NT', '2NT', '2C'].includes(seq[0])
    && ctx.theirs.every(([, c]) => c === 'X')) {
    return uncontested(ctx);
  }
  // (1x)-1NT and they pass: systems on, as over our 1NT opening.
  if (ctx.ntOvercall) return notrump(ctx, 0);
  if (ctx.weOpened) return weOpenedContested(ctx);
  return theyOpened(ctx);
}

function theirSuits(ctx: Ctx): Suit[] {
  const out: Suit[] = [];
  for (const [, c] of ctx.theirs) {
    const s = strainOf(c);
    if (isSuit(s) && !out.includes(s)) out.push(s);
  }
  return out;
}

function lastTheirBid(ctx: Ctx): string | null {
  for (let i = ctx.theirs.length - 1; i >= 0; i--) {
    if (parseBid(ctx.theirs[i][1])) return ctx.theirs[i][1];
  }
  return null;
}

function weOpenedContested(ctx: Ctx): Decision | null {
  const seq = ctx.seq;
  const h = ctx.h;
  const first = seq[0];
  const x = strainOf(first) as Suit;

  if (['1NT', '2NT', '2C'].includes(first)) return ntInterference(ctx);
  if (ctx.iAmOpener() && levelOf(first) >= 2 && !ctx.partners().length) return ['Pass', 'Pre-empted already.'];
  const reopen = reopening(ctx) ?? answerReopening(ctx) ?? answerExtrasDouble(ctx);
  if (reopen) return reopen;
  const splintered = answerCompetedSplinter(ctx);
  if (splintered) return splintered;
  const support = afterSupportDouble(ctx);
  if (support) return support;
  const forced = openerOverForcingResponse(ctx);
  if (forced) return forced;

  if (seq.length === 1 && !ctx.iAmOpener() && levelOf(first) === 1) return respondOverInterference(ctx, x);

  if (ctx.iAmOpener() && levelOf(first) === 1 && seq.length === 2 && seq[1] === 'X'
    && ctx.ours[1][0] === ctx.pd) {
    const answer = answerNegative(ctx, x);
    if (answer) return answer;
  }
  const cue = cuebidRaiseReply(ctx);
  if (cue) return cue;
  const hb = ctx.auction.highestBid;
  if (ctx.iAmOpener() && levelOf(first) === 1 && seq.length === 1
    && h.hcp >= 18 && ctx.ok('X') && hb && hb[2] !== ctx.me && hb[2] !== ctx.pd) {
    return ['X', '18+ HCP, extra values.'];
  }
  if (ctx.iAmOpener() && levelOf(first) === 1 && seq.length === 2) {
    const y = strainOf(seq[1]);
    const lb = lastTheirBid(ctx);
    if (isSuit(y) && lb && levelOf(seq[1]) === 1 && rankOf(lb) <= rankOf('2H')
      && h.len[y] === 3 && ctx.ok('X') && ctx.calls[ctx.calls.length - 1][1] === lb) {
      return ['X', `Support double: exactly 3 ${SYM[y]}.`];
    }
  }
  return rebidOverTheirOvercall(ctx);
}

/** Opener after 1x (P) 1y (2z): a new suit shows extras; 2NT is 18-19. */
export const REBID_NEW_SUIT_HCP = 16;
export const REBID_2NT: [number, number] = [18, 19];
/** ...and with four of partner's major and 0-1 of their suit, a jump in
 *  their suit (4z) is a splinter, game forcing: HCP plus dummy points for
 *  the shortness (void 5, singleton 3) reach 19. Deal 329: 1♣ (P) 1♥ (2♦)
 *  with ♠K752 ♥Q753 ♦— ♣AKQ63 raised to 2♥ and defended 3♦; 7♥ makes. */
export const COMPETED_SPLINTER = true;
export const COMPETED_SPLINTER_MIN = 19;
const SHORT_POINTS: Record<number, number> = { 0: 5, 1: 3 };

/** 1x (P) 1y (2z) 4z: the splinter for major y in their suit z, when it
 *  sits below game in y. */
function competedSplinterCall(y: string | null, z: string | null): string | null {
  if (!isSuit(y) || !isMajor(y) || !isSuit(z)) return null;
  const call = `4${z}`;
  return rankOf(call) < rankOf(`4${y}`) ? call : null;
}

/** Responder after 1x (P) 1y (2z) 4z: partner's splinter, game forcing.
 *  Bid game in y. If they have bid over it, leave it to the fallback. */
function answerCompetedSplinter(ctx: Ctx): Decision | null {
  if (ctx.iAmOpener() || ctx.seq.length !== 3) return null;
  const i = ctx.calls.findIndex(([, c]) => c !== 'Pass');
  if (i < 0 || ctx.calls.length < i + 5) return null;
  const [[w0, c0], [, c1], [w2, c2], [, c3], [w4, c4]] = ctx.calls.slice(i, i + 5);
  const y = strainOf(c2), z = strainOf(c3);
  if (w0 !== ctx.pd || w2 !== ctx.me || w4 !== ctx.pd || levelOf(c0) !== 1
    || c1 !== 'Pass' || levelOf(c2) !== 1 || levelOf(c3) !== 2
    || c4 !== competedSplinterCall(y, z)) {
    return null;
  }
  const game = `4${y}`;
  if (ctx.ok(game)) return [game, TO_PLAY];
  return null;
}

/** 1x (P) 1y (2z): they overcalled partner's one-level response. Raise
 *  with four -- cheapest with 12-14, a jump with 15-17, game in a major with
 *  18+; else 2NT on 18-19 balanced with z stopped; else rebid a six-card
 *  suit, jumping with 15+; else a new four-card suit at the two level with
 *  16+; else pass. Exactly three of partner's suit is the support double's.
 *  The fallback raised every fit to the two level, 12 HCP or 18. */
function rebidOverTheirOvercall(ctx: Ctx): Decision | null {
  const i = ctx.calls.findIndex(([, c]) => c !== 'Pass');
  if (i < 0 || ctx.calls.length !== i + 4 || !ctx.iAmOpener()) return null;
  const [[, c0], [, c1], [w2, c2], [, c3]] = ctx.calls.slice(i);
  const x = strainOf(c0), y = strainOf(c2), z = strainOf(c3);
  if (levelOf(c0) !== 1 || !isSuit(x) || c1 !== 'Pass' || w2 !== ctx.pd
    || levelOf(c2) !== 1 || !isSuit(y) || y === x
    || levelOf(c3) !== 2 || !isSuit(z) || z === x || z === y) {
    return null;
  }
  const h = ctx.h;
  if (h.len[y] === 3) return null;
  const splinter = competedSplinterCall(y, z);
  if (COMPETED_SPLINTER && splinter && h.len[y] >= 4 && h.len[z] <= 1
    && h.hcp + SHORT_POINTS[h.len[z]] >= COMPETED_SPLINTER_MIN
    && ctx.ok(splinter)) {
    return [splinter, `Splinter: 4+ ${SYM[y]}, 0-1 ${SYM[z]}. Game forcing.`];
  }
  if (h.len[y] >= 4) {
    const cheap = ctx.cheapest(y, 2);
    if (cheap && (levelOf(cheap) <= 3 || h.hcp >= NEG_COMPETED_JUMP_HCP)) {
      let lvl = levelOf(cheap);
      if (h.hcp >= NEG_COMPETED_GAME_HCP && isMajor(y)) lvl = Math.max(lvl, 4);
      else if (h.hcp >= NEG_COMPETED_JUMP_HCP) lvl = Math.min(lvl + 1, 4);
      const call = `${lvl}${y}`;
      if (call === cheap) return [call, `4+ ${SYM[y]} support.`];
      if (ctx.ok(call)) return [call, `4+ ${SYM[y]} support, ${NEG_COMPETED_JUMP_HCP}+ HCP.`];
      return [cheap, `4+ ${SYM[y]} support.`];
    }
  }
  if (h.balanced && REBID_2NT[0] <= h.hcp && h.hcp <= REBID_2NT[1] && h.stopper(z)
    && ctx.ok('2NT')) {
    return ['2NT', `${REBID_2NT[0]}-${REBID_2NT[1]} HCP, balanced, ${SYM[z]} stopper.`];
  }
  if (h.len[x] >= 6) {
    const cheap = ctx.cheapest(x, 2);
    if (cheap && levelOf(cheap) <= 3) {
      const call = `${levelOf(cheap) + 1}${x}`;
      if (h.hcp >= NEG_COMPETED_JUMP_HCP && levelOf(cheap) <= 3 && ctx.ok(call)) {
        return [call, `6+ ${SYM[x]}, ${NEG_COMPETED_JUMP_HCP}+ HCP.`];
      }
      return [cheap, `6+ ${SYM[x]}.`];
    }
  }
  if (h.hcp >= REBID_NEW_SUIT_HCP) {
    const fresh = SUITS.filter((s) => s !== x && s !== y && s !== z && h.len[s] >= 4);
    if (fresh.length) {
      const s = maxBy(fresh, (t) => [h.len[t], -idx(t)]);
      const call = ctx.cheapest(s, 2);
      if (call && levelOf(call) === 2) return [call, `4+ ${SYM[s]}, ${REBID_NEW_SUIT_HCP}+ HCP.`];
    }
  }
  return ['Pass', 'No fit, nothing more to show.'];
}

/** A reopening double on a doubleton in their suit needs extra values. */
export const REOPEN_DOUBLETON_HCP = 15;
const REOPEN = 'Reopening double: takeout. Partner may pass for penalty.';

/** Their suit, when the auction began 1x (y) P (P) -- our one-level
 *  opening, their natural overcall at the one or two level, two passes --
 *  and `extra` more calls have followed. */
function reopenSuit(ctx: Ctx, extra: number): Suit | null {
  const i = ctx.calls.findIndex(([, c]) => c !== 'Pass');
  if (i < 0 || ctx.calls.length !== i + 4 + extra) return null;
  const [[w0, c0], [, c1], [, c2], [, c3]] = ctx.calls.slice(i, i + 4);
  const x = strainOf(c0), y = strainOf(c1);
  if (w0 !== ctx.opener || levelOf(c0) !== 1 || !isSuit(x) || !isSuit(y)
    || y === x || levelOf(c1) > 2 || c2 !== 'Pass' || c3 !== 'Pass') {
    return null;
  }
  return y;
}

/** 1x (y) P (P): partner's pass may be a penalty double that a
 *  negative-doubling responder could not make, so opener short in their
 *  suit reopens with a double -- on 0-1 cards, or 2 with 15+ HCP. A
 *  six-card suit on less rebids it instead. 18+ HCP doubles on any length. */
function reopening(ctx: Ctx): Decision | null {
  const y = reopenSuit(ctx, 0);
  if (y === null || !ctx.iAmOpener() || !ctx.ok('X')) return null;
  const h = ctx.h;
  const x = strainOf(ctx.seq[0]) as Suit;
  if (h.hcp >= 18) return ['X', REOPEN];
  if (h.len[x] >= 6 && h.hcp < REOPEN_DOUBLETON_HCP) return null;
  if (h.len[y] <= 1 || (h.len[y] === 2 && h.hcp >= REOPEN_DOUBLETON_HCP)) return ['X', REOPEN];
  return null;
}

/** 1x (y) P (P) X (P): pass for penalty with length and honours in their
 *  suit; otherwise answer the takeout -- a four-card major, notrump with a
 *  stopper, partner's suit, or the longest unbid suit. */
function answerReopening(ctx: Ctx): Decision | null {
  const y = reopenSuit(ctx, 2);
  if (y === null || ctx.iAmOpener() || ctx.seq.length !== 2 || ctx.seq[1] !== 'X'
    || ctx.ours[1][0] !== ctx.pd || ctx.calls[ctx.calls.length - 1][1] !== 'Pass') {
    return null;
  }
  const h = ctx.h;
  const x = strainOf(ctx.seq[0]) as Suit;
  if (h.len[y] >= 4 && h.top(y, ['A', 'K', 'Q', 'J', '10']) >= 2 && h.hcp >= 6) {
    return ['Pass', `Penalty: converting partner's double, length in ${SYM[y]}.`];
  }
  const answer = 'Natural, answering the reopening double.';
  for (const z of [...MAJORS].sort((a, b) => h.len[b] - h.len[a])) {
    if (z !== x && z !== y && h.len[z] >= 4) {
      const call = ctx.cheapest(z, 1);
      if (call) return [call, answer];
    }
  }
  if (h.hcp >= 6 && h.stopper(y)) {
    const call = ctx.cheapest('NT', 1);
    if (call && levelOf(call) <= 2) return [call, `${SYM[y]} stopper, 6+ HCP.`];
  }
  const preference = "Preference to partner's suit.";
  if (h.len[x] >= (isMajor(x) ? 2 : 3)) {
    const call = ctx.cheapest(x, 1);
    if (call) return [call, preference];
  }
  const call = ctx.cheapest(h.longest(SUITS.filter((z) => z !== x && z !== y)), 1);
  if (call) return [call, answer];
  return null;
}

function openerOverForcingResponse(ctx: Ctx): Decision | null {
  const seq = ctx.seq;
  if (!ctx.iAmOpener() || seq.length !== 2 || ctx.ours[1][0] !== ctx.pd) return null;
  const y = strainOf(seq[1]);
  const x = strainOf(seq[0]) as Suit;
  if (!isSuit(y) || y === x || levelOf(seq[1]) !== 2) return null;
  const theirs = theirSuits(ctx);
  if (theirs.includes(y)) return null;
  const h = ctx.h;
  const their = theirs.length ? theirs[theirs.length - 1] : null;
  const game = h.judge >= 15;
  if (h.len[y] >= 3) {
    if (game && isMajor(y) && ctx.ok(`4${y}`)) return [`4${y}`, TO_PLAY];
    const call = ctx.cheapest(y, 3);
    if (call && levelOf(call) === 3) return [call, `3+ ${SYM[y]} support.`];
  }
  if (h.len[x] >= 6) {
    const call = ctx.cheapest(x, 2);
    if (call && levelOf(call) <= 3) return [call, `Rebidding ${SYM[x]}.`];
  }
  if (their && h.stopper(their)) {
    const call = game ? '3NT' : ctx.cheapest('NT', 2);
    if (call && ctx.ok(call) && levelOf(call) <= 3) return [call, `${SYM[their]} stopper.`];
  }
  for (const z of SUITS) {
    if (z !== x && z !== y && !theirs.includes(z) && h.len[z] >= 4) {
      const call = ctx.cheapest(z, 2);
      if (call && levelOf(call) <= 3 && rankOf(call) < rankOf('3NT')) return [call, `4+ ${SYM[z]}.`];
    }
  }
  const call = ctx.cheapest(x, 2);
  if (call && levelOf(call) <= 3) return [call, `Rebidding ${SYM[x]}.`];
  return null;
}

function afterSupportDouble(ctx: Ctx): Decision | null {
  const seq = ctx.seq;
  if (ctx.iAmOpener() || seq.length !== 3 || seq[2] !== 'X'
    || ctx.ours[2][0] !== ctx.pd || levelOf(seq[1]) !== 1) {
    return null;
  }
  const y = strainOf(seq[1]);
  const h = ctx.h;
  if (!isSuit(y)) return null;
  if (h.judge >= 13) {
    if (isMajor(y) && ctx.ok(`4${y}`)) return [`4${y}`, TO_PLAY];
    if (ctx.ok('3NT')) return ['3NT', TO_PLAY];
  }
  const call = ctx.cheapest(y, 2);
  if (call && levelOf(call) <= 3) {
    if (h.judge >= 10 && levelOf(call) === 2 && ctx.ok(`3${y}`)) return [`3${y}`, `Invitational, ${SYM[y]}.`];
    return [call, `Minimum, ${SYM[y]}.`];
  }
  return ['Pass', 'No room.'];
}

function cuebidRaiseReply(ctx: Ctx): Decision | null {
  const h = ctx.h;
  const mine = ctx.mine();
  const partners = ctx.partners();
  if (!mine.length || !partners.length) return null;
  const theirs = theirSuits(ctx);
  const x0 = strainOf(mine[0]);
  const p = partners[partners.length - 1];
  const lastOurs = ctx.ours[ctx.ours.length - 1];
  if (isSuit(x0) && mine.length === 1 && theirs.includes(strainOf(p) as Suit) && strainOf(p) !== x0
    && lastOurs[0] === ctx.pd && lastOurs[1] === p) {
    const x = x0;
    const their = strainOf(p) as Suit;
    if (h.judge >= 14 || (h.judge >= 12 && h.len[x] >= 6)) {
      if (isMajor(x) && ctx.ok(`4${x}`)) return [`4${x}`, TO_PLAY];
      if (h.stopper(their) && ctx.ok('3NT')) return ['3NT', TO_PLAY];
      if (ctx.ok(`5${x}`)) return [`5${x}`, TO_PLAY];
    }
    const call = ctx.cheapest(x, 2);
    if (call && levelOf(call) <= 4) {
      if (call === `4${x}` || call === `5${x}`) return [call, TO_PLAY];
      return [call, `Minimum, ${SYM[x]}.`];
    }
    return ['Pass', 'Minimum.'];
  }
  if (mine.length === 1 && theirs.includes(strainOf(mine[0]) as Suit) && partners.length
    && lastOurs[0] === ctx.pd && partners.length >= 2) {
    const x = strainOf(partners[partners.length - 1]);
    if (isSuit(x) && strainOf(partners[0]) === x && h.judge >= 13) {
      if (isMajor(x) && ctx.ok(`4${x}`)) return [`4${x}`, TO_PLAY];
      if (ctx.ok('3NT')) return ['3NT', TO_PLAY];
    }
    if (isSuit(x)) return ['Pass', 'No game.'];
  }
  return null;
}

/** Responder over 1M (3x), a three-level overcall: with 3+ support and 11+
 *  HCP the cuebid is above three and 3M shows 6-9, so bid game. Before,
 *  these hands passed (deal 346: ♠AK96 ♥K ♦QJ10432 ♣J6 over 1♠ (3♥)). */
export const JUMP_OVERCALL_GAME = true;

function respondOverInterference(ctx: Ctx, x: Suit): Decision {
  const h = ctx.h;
  const hcp = h.hcp;
  const sup = h.len[x];
  const lb = lastTheirBid(ctx);
  if (!lb) {
    if (isMajor(x) && sup >= 4 && hcp >= 10 && ctx.ok('2NT')) return ['2NT', `Jordan: 4+ ${SYM[x]}, 10+ HCP.`];
    if (hcp >= 10 && ctx.ok('XX')) return ['XX', '10+ HCP.'];
    if (sup >= 4 && hcp <= 9 && ctx.ok(`3${x}`)) return [`3${x}`, `4+ ${SYM[x]}, under 10 HCP. Pre-emptive.`];
    if (sup >= 3 && hcp >= 6) {
      const call = ctx.cheapest(x, 2);
      if (call && levelOf(call) === 2) return [call, `3+ ${SYM[x]}, 6-9 HCP.`];
    }
    // Over the double a jump in a new suit is weak, like a weak jump overcall.
    const long = SUITS.filter((s) => s !== x && h.len[s] >= 6);
    if (long.length && WJO[0] <= hcp && hcp <= WJO[1]) {
      const s = maxBy(long, (t) => [h.len[t], idx(t)]);
      const cheap = ctx.cheapest(s, 1);
      if (cheap) {
        const jump = `${levelOf(cheap) + 1}${s}`;
        if (levelOf(jump) === 2 && ctx.ok(jump)) return [jump, `6+ ${SYM[s]}, 3-9 HCP. Weak jump shift.`];
      }
    }
    for (const s of SUITS) {
      if (s !== x && h.len[s] >= 4 && hcp >= 6 && ctx.ok(`1${s}`)) return [`1${s}`, `4+ ${SYM[s]}, 6+ HCP.`];
    }
    return ['Pass', 'Nothing to show.'];
  }
  const [lvl, their] = parseBid(lb)!;
  if (lb === '2NT' && ctx.theirs.length === 1) {
    const shown = SUITS.filter((s) => s !== x).slice(0, 2);
    const rest = SUITS.filter((s) => s !== x && !shown.includes(s));
    const low = ctx.cheapest(shown[0], 3);
    const high = ctx.cheapest(shown[1], 3);
    if (sup >= 3 && hcp >= 10 && low && levelOf(low) === 3) {
      return [low, `Limit raise or better in ${SYM[x]}. Artificial.`];
    }
    if (rest.length && h.len[rest[0]] >= 5 && hcp >= 12 && high && levelOf(high) === 3) {
      return [high, `5+ ${SYM[rest[0]]}, game forcing. Artificial.`];
    }
    if (sup >= 3 && hcp >= 6 && ctx.ok(`3${x}`)) return [`3${x}`, `3+ ${SYM[x]}, competitive.`];
    return ['Pass', 'Nothing to show.'];
  }
  if (their === 'NT') {
    if (hcp >= 9 && ctx.ok('X')) return ['X', '9+ HCP. Penalty.'];
    return ['Pass', 'Nothing to show.'];
  }
  // Over a minor opening the unbid major comes first (see gib.py).
  if (isMinor(x)) {
    const neg = negativeDouble(ctx, x, lvl);
    if (neg) return neg;
  }
  let cueTooHigh = false;
  if (sup >= 3 && hcp >= 10 && their !== x && isSuit(their)) {
    const call = ctx.cheapest(their, 2);
    // A three-level cuebid needs four trumps or 12+ judgement points (gib.py).
    cueTooHigh = settingsGib.cueLimitAt3 && call !== null && levelOf(call) === 3
      && sup < 4 && h.judge < 12;
    if (call && levelOf(call) <= 3 && !cueTooHigh) return [call, `Cuebid: 3+ ${SYM[x]}, 10+ HCP. Artificial.`];
  }
  if (sup >= 4 && hcp <= 9 && ctx.ok(`3${x}`) && lvl <= 2
    && rankOf(`3${x}`) > rankOf(ctx.cheapest(x, 1) ?? '1C')) {
    if (ctx.cheapest(x, 2) !== `3${x}`) return [`3${x}`, `4+ ${SYM[x]}, under 10 HCP. Pre-emptive.`];
  }
  if (sup >= 3 && hcp >= 6) {
    const call = ctx.cheapest(x, 2);
    if (call && levelOf(call) <= 3 && (hcp <= 9 || cueTooHigh)) return [call, raiseAlert(x, `3+ ${SYM[x]}, 6+ HCP.`)];
  }
  if (JUMP_OVERCALL_GAME && isMajor(x) && lvl === 3 && isSuit(their)
    && sup >= 3 && hcp >= 11 && ctx.ok(`4${x}`)) {
    return [`4${x}`, `3+ ${SYM[x]}, 11+ HCP. To play.`];
  }
  for (const s of sortedBy(SUITS, (t) => [h.len[t], idx(t)], true)) {
    if (s === x || s === their) continue;
    const call = ctx.cheapest(s, 1);
    if (!call) continue;
    if (levelOf(call) === 1 && h.len[s] >= 4 && hcp >= 6) return [call, `4+ ${SYM[s]}, 6+ HCP.`];
    if (levelOf(call) === 2 && h.len[s] >= 5 && hcp >= 10) return [call, `5+ ${SYM[s]}, 10+ HCP. Forcing.`];
  }
  const neg = negativeDouble(ctx, x, lvl);
  if (neg) return neg;
  if (isSuit(their) && h.stopper(their) && h.balanced) {
    if (hcp >= 8 && hcp <= 10 && ctx.ok('1NT')) return ['1NT', `8-10 HCP, ${SYM[their]} stopper.`];
    if (hcp >= 11 && hcp <= 12 && ctx.ok('2NT')) return ['2NT', `11-12 HCP, ${SYM[their]} stopper.`];
    if (hcp >= 13 && ctx.ok('3NT')) return ['3NT', `13+ HCP, ${SYM[their]} stopper.`];
  }
  return ['Pass', 'Nothing to show.'];
}

function negativeDouble(ctx: Ctx, x: Suit, lvl: number): Decision | null {
  if (lvl > 3 || !ctx.ok('X')) return null;
  const lb = lastTheirBid(ctx);
  if (ctx.calls[ctx.calls.length - 1][1] !== lb || rankOf(lb as string) > rankOf('3S')) return null;
  const theirs = theirSuits(ctx);
  const unbid = SUITS.filter((s) => s !== x && !theirs.includes(s));
  if (!unbid.length) return null;
  const majors = unbid.filter((s) => isMajor(s));
  const shown = majors.length ? majors : unbid;
  const h = ctx.h;
  if (shown.some((s) => h.len[s] < 4)) return null;
  const need = NEGATIVE[lvl];
  if (h.hcp < need) return null;
  return ['X', `Negative: 4+ ${shown.map((s) => SYM[s]).join(' ')}, ${need}+ HCP.`];
}

function answerNegative(ctx: Ctx, x: Suit): Decision | null {
  const h = ctx.h;
  const lastCall = ctx.calls[ctx.calls.length - 1];
  if (lastCall[0] !== ctx.me && lastCall[0] !== ctx.pd && parseBid(lastCall[1])) return negativeDoubleCompeted(ctx, x);
  const xAt = ctx.calls.findIndex(([w, c]) => w === ctx.pd && c === 'X');
  const before = ctx.calls.slice(0, xAt)
    .filter(([w, c]) => w !== ctx.me && w !== ctx.pd && parseBid(c)).map(([, c]) => c);
  if (!before.length || !isSuit(strainOf(before[before.length - 1]))) {
    return ['Pass', "Partner's double is for penalty."];
  }
  // Each answer says what it shows (see gib.py).
  const theirs = theirSuits(ctx);
  const unbid = SUITS.filter((s) => s !== x && !theirs.includes(s));
  const fours = sortedBy(unbid.filter((s) => h.len[s] >= 4),
    (s) => [isMajor(s) ? 1 : 0, h.len[s], idx(s)], true);
  for (const s of fours) {
    const call = ctx.cheapest(s, 1);
    if (call && levelOf(call) <= 3) return [call, `4+ ${SYM[s]}.`];
  }
  if (fours.length) return ['Pass', 'No room to show my suit.'];
  const denied = [...unbid].reverse().map((s) => SYM[s]).join(' or ');
  if (h.len[x] >= 5) {
    const call = ctx.cheapest(x, 1);
    if (call && levelOf(call) <= 3) return [call, `5+ ${SYM[x]}, fewer than 4 ${denied}.`];
  }
  const call = ctx.cheapest('NT', 1);
  if (call && levelOf(call) <= 2) return [call, `Fewer than 4 ${denied}, fewer than 5 ${SYM[x]}.`];
  return ['Pass', 'Nothing to show.'];
}

/** Opener after 1x (1y) X (2y): jump in partner's suit, bid game in it, or
 *  double with extra values and no fit. */
export const NEG_COMPETED_JUMP_HCP = 15;
export const NEG_COMPETED_GAME_HCP = 18;
export const NEG_COMPETED_DOUBLE_HCP = 17;

/** [suits partner's negative double promised four of, their suit], or null
 *  if partner's double was not a negative double of a suit overcall. */
function negativePromise(ctx: Ctx, x: Suit): [Suit[], Suit] | null {
  const xAt = ctx.calls.findIndex(([w, c]) => w === ctx.pd && c === 'X');
  const before = ctx.calls.slice(0, xAt)
    .filter(([w, c]) => w !== ctx.me && w !== ctx.pd && parseBid(c)).map(([, c]) => c);
  if (!before.length || !isSuit(strainOf(before[before.length - 1]))) return null;
  const bid = before.map((c) => strainOf(c));
  const unbid = SUITS.filter((s) => s !== x && !bid.includes(s));
  const majors = unbid.filter((s) => isMajor(s));
  return [majors.length ? majors : unbid, strainOf(before[before.length - 1]) as Suit];
}

/** 1x (1y) X (2y): they bid over partner's negative double. With four in
 *  a suit the double promised, bid it -- cheapest with a minimum, a jump with
 *  15-17, game in a major with 18+; else rebid a six-card suit; else double
 *  with 17+ (extra values, no fit); else pass. The fallback used to read
 *  partner here as having passed, and never once bid the fit. */
function negativeDoubleCompeted(ctx: Ctx, x: Suit): Decision | null {
  const promise = negativePromise(ctx, x);
  const xAt = ctx.calls.findIndex(([w, c]) => w === ctx.pd && c === 'X');
  if (promise === null || ctx.calls.length !== xAt + 2) return null;
  const [shown] = promise;
  const h = ctx.h;
  const theirs = theirSuits(ctx);
  const fits = shown.filter((s) => !theirs.includes(s) && h.len[s] >= 4);
  if (fits.length) {
    const s = maxBy(fits, (t) => [h.len[t], -idx(t)]);   // ties: cheaper
    const cheap = ctx.cheapest(s, 2);
    if (cheap && (levelOf(cheap) <= 3 || h.hcp >= NEG_COMPETED_JUMP_HCP)) {
      let lvl = levelOf(cheap);
      if (h.hcp >= NEG_COMPETED_GAME_HCP && isMajor(s)) lvl = Math.max(lvl, 4);
      else if (h.hcp >= NEG_COMPETED_JUMP_HCP) lvl = Math.min(lvl + 1, 4);
      const call = `${lvl}${s}`;
      if (call === cheap) return [call, `4+ ${SYM[s]}, partner's suit.`];
      if (ctx.ok(call)) return [call, `4+ ${SYM[s]}, partner's suit, ${NEG_COMPETED_JUMP_HCP}+ HCP.`];
      return [cheap, `4+ ${SYM[s]}, partner's suit.`];
    }
  }
  if (h.len[x] >= 6) {
    const call = ctx.cheapest(x, 2);
    if (call && levelOf(call) <= 3) return [call, `6+ ${SYM[x]}.`];
  }
  // Only over a two-level bid: higher, partner has no cheap answer, and a
  // forced pass leaves the double in for penalty (deal 334: 3S doubled made).
  if (h.hcp >= NEG_COMPETED_DOUBLE_HCP && levelOf(ctx.calls[ctx.calls.length - 1][1]) <= 2 && ctx.ok('X')) {
    return ['X', `${NEG_COMPETED_DOUBLE_HCP}+ HCP, extra values. Partner may pass for penalty.`];
  }
  return ['Pass', 'Minimum, nothing more to show.'];
}

/** 1x (1y) X (2y) X (P): opener's double shows extra values without a fit
 *  for my suit. Pass for penalty with length and honours in their suit,
 *  else bid: a five-card suit I promised, partner's suit, my promised suit. */
function answerExtrasDouble(ctx: Ctx): Decision | null {
  const seq = ctx.seq;
  if (ctx.iAmOpener() || seq.length !== 3 || seq[1] !== 'X' || seq[2] !== 'X'
    || ctx.ours[1][0] !== ctx.me || ctx.ours[2][0] !== ctx.pd
    || levelOf(seq[0]) !== 1 || !isSuit(strainOf(seq[0]))
    || ctx.calls[ctx.calls.length - 1][1] !== 'Pass') {
    return null;
  }
  const x = strainOf(seq[0]) as Suit;
  const i = ctx.calls.findIndex(([w, c]) => w === ctx.me && c === 'X');
  const after = ctx.calls.slice(i + 1);
  if (after.length !== 3 || !parseBid(after[0][1]) || after[1][0] !== ctx.pd) return null;
  const before = ctx.calls.slice(0, i)
    .filter(([w, c]) => w !== ctx.me && w !== ctx.pd && parseBid(c)).map(([, c]) => c);
  if (!before.length || !isSuit(strainOf(before[before.length - 1]))) return null;
  const y = strainOf(after[0][1]);
  const h = ctx.h;
  if (isSuit(y) && h.len[y] >= 4 && h.top(y, ['A', 'K', 'Q', 'J', '10']) >= 2) {
    return ['Pass', `Penalty: converting partner's double, length in ${SYM[y]}.`];
  }
  const bid = before.map((c) => strainOf(c));
  const unbid = SUITS.filter((s) => s !== x && !bid.includes(s));
  const majors = unbid.filter((s) => isMajor(s));
  const shown = majors.length ? majors : unbid;
  const mine = shown.filter((s) => s !== y);
  const answer = "Natural, answering partner's double.";
  const byLength = [...mine].sort((a, b) => h.len[b] - h.len[a]);
  for (const s of byLength) {
    if (h.len[s] >= 5) {
      const call = ctx.cheapest(s, 2);
      if (call && levelOf(call) <= 3) return [call, answer];
    }
  }
  if (h.len[x] >= 3) {
    const call = ctx.cheapest(x, 2);
    if (call && levelOf(call) <= 3) return [call, "Preference to partner's suit."];
  }
  for (const s of byLength) {
    const call = ctx.cheapest(s, 2);
    if (call && levelOf(call) <= 3) return [call, answer];
  }
  const call = ctx.cheapest(x, 2);
  if (call && levelOf(call) <= 3) return [call, "Preference to partner's suit."];
  return ['Pass', 'Nothing better than defending.'];
}

function ntInterference(ctx: Ctx): Decision | null {
  const seq = ctx.seq;
  const h = ctx.h;
  const lb = lastTheirBid(ctx);
  if (!lb) return uncontested(ctx);
  const first = seq[0];
  const lastCall = ctx.calls[ctx.calls.length - 1];
  if (first !== '1NT') {
    if (seq.length >= 1 && lastCall[1] !== 'Pass' && h.hcp >= 8) {
      for (const s of SUITS) {
        if (h.len[s] >= 5) {
          const call = ctx.cheapest(s, 1);
          if (call && levelOf(call) <= 3) return [call, natural(s)];
        }
      }
      if (ctx.ok('3NT')) return ['3NT', TO_PLAY];
    }
    return ['Pass', 'Nothing to show.'];
  }
  const their = strainOf(lb);
  if (seq.length === 1 && !ctx.iAmOpener()) {
    if (lb === '2C' && lastCall[1] === '2C' && ctx.ok('X') && MAJORS.some((m) => h.len[m] >= 4) && h.hcp >= 8) {
      return ['X', 'Stayman. Artificial.'];
    }
    if (isSuit(their) && lb !== '2C' && h.len[their] >= 4 && h.hcp >= 8 && ctx.ok('X')) {
      return ['X', 'Penalty: 8+ HCP.'];
    }
    if (h.hcp >= 10) {
      for (const s of sortedBy(SUITS, (t) => [h.len[t]], true)) {
        if (s !== their && h.len[s] >= 5) {
          const call = ctx.cheapest(s, 3);
          if (call && levelOf(call) === 3) return [call, `5+ ${SYM[s]}, game forcing.`];
        }
      }
      if ((!isSuit(their) || h.stopper(their)) && ctx.ok('3NT')) return ['3NT', 'Game values, stopper.'];
    }
    for (const s of sortedBy(SUITS, (t) => [h.len[t]], true)) {
      if (s !== their && h.len[s] >= 5) {
        const call = ctx.cheapest(s, 2);
        if (call && levelOf(call) === 2) return [call, `5+ ${SYM[s]}, to play.`];
        if (call && levelOf(call) === 3 && h.hcp <= 9 && ctx.ok('2NT')) {
          return ['2NT', 'Lebensohl: relay to 3C. Artificial.'];
        }
      }
    }
    return ['Pass', 'Nothing to show.'];
  }
  if (ctx.iAmOpener() && seq[seq.length - 1] === '2NT' && seq.length === 2) {
    if (ctx.ok('3C')) return ['3C', `Completing the Lebensohl relay, ${SYM.C}.`];
    return ['Pass', 'Relay interrupted.'];
  }
  if (!ctx.iAmOpener() && seq.length === 3 && seq[1] === '2NT' && seq[2] === '3C') {
    for (const s of sortedBy(SUITS, (t) => [h.len[t]], true)) {
      if (h.len[s] >= 5) {
        if (s === 'C') return ['Pass', 'Clubs, to play.'];
        const call = ctx.cheapest(s, 3);
        if (call && levelOf(call) === 3) return [call, `5+ ${SYM[s]}, to play.`];
      }
    }
    return ['Pass', 'To play.'];
  }
  if (ctx.iAmOpener() && seq.length >= 4 && seq[1] === '2NT' && seq[2] === '3C') {
    return ['Pass', 'Partner signed off.'];
  }
  if (ctx.iAmOpener() && seq.length === 2 && seq[1] === 'X' && lb === '2C') {
    return ntOpenerAnswer(ctx, 1, '2C', NT1[0], NT1[1]);
  }
  if (seq.length >= 2) {
    const ps = ctx.partners();
    const p = ps.length ? ps[ps.length - 1] : null;
    const s = p ? strainOf(p) : null;
    if (isMajor(s) && h.len[s as Suit] >= 3 && levelOf(p) === 3 && ctx.ok(`4${s}`)) return [`4${s}`, TO_PLAY];
    if (p && levelOf(p) === 3 && isSuit(s) && ctx.ok('3NT') && isSuit(their) && h.stopper(their)) {
      return ['3NT', TO_PLAY];
    }
  }
  return ['Pass', 'Nothing to add.'];
}

// ── When they opened ──────────────────────────────────────────────────────────

function theyOpened(ctx: Ctx): Decision | null {
  const seq = ctx.seq;
  if (!seq.length) return defend(ctx);
  const mine = ctx.mine();
  const partners = ctx.partners();
  if (partners.length && !mine.length) return advance(ctx);
  if (mine.length && !partners.length && defendWasWeak(ctx, mine[0])) return ['Pass', 'Already described: weak.'];
  return cuebidRaiseReply(ctx);
}

function defendWasWeak(ctx: Ctx, call: string): boolean {
  const firstTheir = ctx.calls.find(([, c]) => c !== 'Pass');
  if (!firstTheir || !isSuit(strainOf(call))) return false;
  const s = strainOf(call) as Suit;
  for (let lvl = 1; lvl < 8; lvl++) {
    if (rankOf(`${lvl}${s}`) > rankOf(firstTheir[1])) return levelOf(call) > lvl;
  }
  return false;
}

function openingBidOnly(ctx: Ctx): string | null {
  const bids = ctx.calls.filter(([, c]) => c !== 'Pass');
  if (bids.length !== 1) return null;
  return bids[0][1];
}

function defend(ctx: Ctx): Decision | null {
  const h = ctx.h;
  const hcp = h.hcp;
  const theirs = theirSuits(ctx);
  const lb = lastTheirBid(ctx);
  if (lb === null) return null;
  const opening = openingBidOnly(ctx);
  const [lvl, their] = parseBid(lb)!;

  if (opening === '1NT') {
    if (hcp >= 15 && ctx.ok('X')) return ['X', '15+ HCP. Penalty.'];
    if (hcp >= 10) {
      if (h.len.H >= 4 && h.len.S >= 4 && h.len.H + h.len.S >= 9) {
        return ['2D', `4+ ${SYM.H} and 4+ ${SYM.S}. Artificial.`];
      }
      for (const m of MAJORS) {
        if (h.len[m] >= 5 && MINORS.some((x) => h.len[x] >= 4)) return [`2${m}`, `5+ ${SYM[m]} and a 4+ minor.`];
      }
      if (h.len.C >= 5 && h.len.D >= 5) return ['2NT', `5+ ${SYM.C} and 5+ ${SYM.D}.`];
      if (h.shape[0] >= 6) return ['2C', 'One long suit, 6+. Artificial.'];
    }
    return ['Pass', 'No action over 1NT.'];
  }
  if (opening === '2C' || their === 'NT') return ['Pass', 'No action.'];

  if (opening && levelOf(opening) === 1 && hcp >= TWO_SUITED_MIN) {
    const fives = SUITS.filter((s) => s !== their && h.len[s] >= 5);
    if (fives.length >= 2) {
      const cue = `2${their}`;
      if (isMinor(their) && fives.includes('H') && fives.includes('S') && ctx.ok(cue)) {
        return [cue, `Michaels: 5+ ${SYM.H} and 5+ ${SYM.S}. Artificial.`];
      }
      const other: Suit = their === 'H' ? 'S' : 'H';
      if (isMajor(their) && fives.includes(other) && fives.some((s) => isMinor(s)) && ctx.ok(cue)) {
        return [cue, `Michaels: 5+ ${SYM[other]} and a 5+ minor. Artificial.`];
      }
      const low = SUITS.filter((s) => s !== their).slice(0, 2);
      if (low.every((s) => fives.includes(s)) && ctx.ok('2NT')) {
        return ['2NT', `Unusual: 5+ ${SYM[low[0]]} and 5+ ${SYM[low[1]]}, 8+ HCP.`];
      }
    }
  }
  if ((opening === '2H' || opening === '2S') && h.len.C >= 5 && h.len.D >= 5) {
    if (hcp >= 16 && ctx.ok(`4${their}`)) return [`4${their}`, 'Both minors, 5-5, 16+ HCP. Artificial.'];
    if (hcp >= 10 && hcp <= 15 && ctx.ok('4NT')) return ['4NT', `5+ ${SYM.C} and 5+ ${SYM.D}, 10-15 HCP.`];
  }
  if (lvl === 1 && h.balanced && NT_OVERCALL[0] <= hcp && hcp <= NT_OVERCALL[1]
    && h.stopper(their as Suit) && ctx.ok('1NT')) {
    return ['1NT', `15-18 HCP, balanced, ${SYM[their as Suit]} stopper.`];
  }
  if (opening && levelOf(opening) === 1 && WJO[0] <= hcp && hcp <= WJO[1]) {
    const long = SUITS.filter((s) => s !== their && h.len[s] >= 6);
    if (long.length) {
      const s = maxBy(long, (t) => [h.len[t], idx(t)]);
      const cheap = ctx.cheapest(s, 1);
      if (cheap) {
        const jump = `${levelOf(cheap) + 1}${s}`;
        if (levelOf(jump) <= 3 && ctx.ok(jump)) return [jump, `6+ ${SYM[s]}, 3-9 HCP. Weak jump overcall.`];
      }
    }
  }
  const own = SUITS.filter((s) => !theirs.includes(s) && h.len[s] >= 5);
  if (own.length && hcp <= 17) {
    const s = maxBy(own, (t) => [h.len[t], idx(t)]);
    const call = ctx.cheapest(s, 1);
    if (call) {
      const need = levelOf(call) === 1 ? OVERCALL_1 : OVERCALL_2;
      if (levelOf(call) <= 3 && need[0] <= hcp && hcp <= need[1] && (levelOf(call) <= 2 || hcp >= 12)) {
        return [call, `5+ ${SYM[s]}, ${need[0]}-${need[1]} HCP. Overcall.`];
      }
    }
  }
  if (ctx.ok('X') && rankOf(lb) <= rankOf('4H') && isSuit(their)) {
    const shapeOk = h.len[their] <= 2 && SUITS.every((s) => s === their || h.len[s] >= 3);
    const need = lvl === 1 ? TAKEOUT_MIN : 13;
    if ((shapeOk && hcp >= need) || hcp >= 18) return ['X', `Takeout: ${need}+ HCP.`];
  }
  if (lvl === 3 && h.balanced && hcp >= 16 && isSuit(their) && h.stopper(their) && ctx.ok('3NT')) {
    return ['3NT', `16+ HCP, ${SYM[their]} stopper.`];
  }
  return ['Pass', 'No action.'];
}

function advance(ctx: Ctx): Decision | null {
  const h = ctx.h;
  const hcp = h.hcp;
  const p = ctx.partners()[0];
  const theirs = theirSuits(ctx);
  const their = theirs.length ? theirs[0] : null;
  const openingRec = ctx.calls.find(([, c]) => c !== 'Pass');
  const opening = openingRec ? openingRec[1] : null;
  if (p === '1NT' && levelOf(opening ?? '') === 1) {
    // They have bid again over our 1NT overcall (systems on, when they
    // haven't, is `contested`'s): ai.py answers it.
    return null;
  }
  if (p === 'X' && opening === '1NT') return ['Pass', 'Penalty double: passing.'];
  if (opening === '1NT') {
    if (p === '2C') return ctx.ok('2D') ? ['2D', 'Relay. Artificial.'] : ['Pass', 'No room.'];
    if (p === '2D') {
      const s: Suit = h.len.H >= h.len.S ? 'H' : 'S';
      const call = ctx.cheapest(s, 2);
      return call && levelOf(call) <= 3 ? [call, natural(s)] : ['Pass', 'No room.'];
    }
    if (p === '2H' || p === '2S') {
      const s = strainOf(p) as Suit;
      if (h.len[s] >= 2) return ['Pass', "Happy in partner's major."];
      if (ctx.ok('2NT')) return ['2NT', "Asks for partner's minor. Artificial."];
    }
    if (p === '2NT') {
      const m: Suit = h.len.C >= h.len.D ? 'C' : 'D';
      const call = ctx.cheapest(m, 3);
      return call && levelOf(call) <= 4 ? [call, natural(m)] : ['Pass', 'No room.'];
    }
    return null;
  }
  const two = twoSuitsShown(p, opening);
  if (two) {
    const [a, b] = two;
    let choice: Suit;
    if (b === null) choice = h.len[a] >= 2 ? a : maxBy(MINORS, (s) => [h.len[s], idx(s)]);
    else choice = maxBy([a, b], (s) => [h.len[s], idx(s)]);
    const game = `${isMajor(choice) ? 4 : 5}${choice}`;
    if (TWO_SUITER_GAME && (choice === a || choice === b) && h.len[choice] >= 3
      && h.judge + TWO_SUITED_MIN >= (isMajor(choice) ? GAME_MAJOR : GAME) && ctx.ok(game)) {
      return [game, `3+ ${SYM[choice]}, game values. To play.`];
    }
    const call = ctx.cheapest(choice, 2);
    if (call && levelOf(call) <= 5) return [call, "Choosing between partner's two suits."];
    return ['Pass', 'No room.'];
  }
  if (p === 'X') {
    const lastCall = ctx.calls[ctx.calls.length - 1];
    if (parseBid(lastCall[1]) && lastCall[1] !== opening) {
      const unbid = SUITS.filter((s) => !theirs.includes(s));
      if (hcp >= 8 && unbid.length >= 2 && unbid.slice(-2).every((s) => h.len[s] >= 4) && ctx.ok('X')) {
        return ['X', 'Responsive: 8+ HCP, two places to play.'];
      }
    }
    if (parseBid(lastCall[1]) && lastCall[0] !== ctx.me && lastCall[0] !== ctx.pd) {
      for (const s of sortedBy(SUITS, (t) => [h.len[t], idx(t)], true)) {
        if (!theirs.includes(s) && h.len[s] >= 4 && hcp >= 6) {
          const call = ctx.cheapest(s, 1);
          if (call && levelOf(call) <= 3) return [call, `4+ ${SYM[s]}, 6+ HCP. Free advance.`];
        }
      }
      return ['Pass', 'Not forced after their bid.'];
    }
    return null;
  }
  const ps = strainOf(p);
  if (isSuit(ps) && levelOf(p) <= 3) {
    const sup = h.len[ps];
    if (sup >= 3 && hcp >= 10 && isSuit(their)) {
      const call = ctx.cheapest(their, 2);
      if (call && levelOf(call) <= 3) return [call, `Cuebid: 3+ ${SYM[ps]}, 10+ HCP. Artificial.`];
    }
    if (sup >= 3 && hcp >= 6 && hcp <= 9) {
      const call = ctx.cheapest(ps, 2);
      if (call && levelOf(call) <= 3) return [call, raiseAlert(ps as Suit, `3+ ${SYM[ps as Suit]}, 6-9 HCP.`)];
    }
    if (isSuit(their) && h.stopper(their) && h.balanced) {
      if (hcp >= 8 && hcp <= 11 && ctx.ok('1NT')) return ['1NT', `8-11 HCP, ${SYM[their]} stopper.`];
      if (hcp >= 12 && hcp <= 14 && ctx.ok('2NT')) return ['2NT', `12-14 HCP, ${SYM[their]} stopper.`];
    }
    for (const s of SUITS) {
      if (!theirs.includes(s) && s !== ps && h.len[s] >= 5 && hcp >= 8) {
        const call = ctx.cheapest(s, 1);
        if (call && levelOf(call) <= 2) return [call, `5+ ${SYM[s]}, 8+ HCP.`];
      }
    }
    return ['Pass', 'Nothing to add.'];
  }
  return null;
}

function twoSuitsShown(p: string, opening: string | null): [Suit, Suit | null] | null {
  if (!opening || levelOf(opening) !== 1) return null;
  const their = strainOf(opening);
  if (p === '2NT') {
    const low = SUITS.filter((s) => s !== their).slice(0, 2);
    return [low[0], low[1]];
  }
  if (p === `2${their}` && isSuit(their)) {
    if (isMinor(their)) return ['H', 'S'];
    return [their === 'H' ? 'S' : 'H', null];
  }
  return null;
}
