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
export const RESPONSE_MIN = 6;
export const RAISE: [number, number] = [7, 10];
export const LIMIT: [number, number] = [11, 12];
export const JACOBY_MIN = 13;
export const SPLINTER: [number, number] = [13, 16];
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
const GAME = 25;
/** Judge level on the variant's card values (true) or on HCP (false). See gib.py. */
export const settingsGib = { judgeByVariant: true, cueLimitAt3: true };
const SLAM = 33;
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
    const raw = cards.reduce((n, c) => n + (c.rank === 'K' || c.rank === 'Q' ? 3
      : c.rank === 'A' || c.rank === '10' || c.rank === '9' ? 1 : 0), 0);
    this.judge = settingsGib.judgeByVariant ? Math.floor((10 * raw + 4) / 9) : this.hcp;
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

// ── Entry point ───────────────────────────────────────────────────────────────

/** Calls a branch produced that were not legal, caught by the guard. */
export const ILLEGAL: [Rec[], Decision][] = [];

export function gibBid(player: Seat, cards: Card[], auction: AuctionState): Decision | null {
  const ctx = new Ctx(player, cards, auction);
  if (!ctx.legal.length) return null;
  let decision = decide(ctx);
  if (decision === null) return null;
  if (!ctx.legal.includes(decision[0] as string)) {
    ILLEGAL.push([ctx.calls, decision]);
    decision = continuation(ctx);
    if (!ctx.legal.includes(decision[0])) decision = ['Pass', 'Nothing to add.'];
  }
  return [decision[0], nameTheSuit(decision[0], decision[1])];
}

function nameTheSuit(call: string, alert: string): string {
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

function respondMajor(ctx: Ctx, x: Suit): Decision {
  const h = ctx.h;
  const hcp = h.hcp;
  const sup = h.len[x];
  const passed = ctx.passedHand(ctx.me);
  const shortness = h.short(x);
  if (sup >= 5 && hcp < 10 && shortness.length && ctx.ok(`4${x}`)) {
    return [`4${x}`, `5+ ${SYM[x]}, under 10 HCP. Pre-emptive raise.`];
  }
  if (hcp < RESPONSE_MIN) return ['Pass', 'Fewer than 6 HCP.'];
  if (sup >= 4 && !passed && hcp >= JACOBY_MIN) {
    if (shortness.length && hcp <= SPLINTER[1]) {
      const s = shortness[0];
      const call = x === 'H' && s === 'S' ? `3${s}` : `4${s}`;
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
    return [`3${x}`, `4+ ${SYM[x]}, ${LIMIT[0]}-${LIMIT[1]} HCP. Limit raise.`];
  }
  if (sup >= 3 && RAISE[0] <= hcp && hcp <= RAISE[1]) {
    return [`2${x}`, `3+ ${SYM[x]}, ${RAISE[0]}-${RAISE[1]} HCP.`];
  }
  const js = jumpShift(ctx, x);
  if (js) return js;
  if (x === 'H' && h.len.S >= 4) return ['1S', `4+ ${SYM.S}, 6+ HCP.`];
  if (!passed && hcp >= TWO_OVER_ONE) {
    if (x === 'S' && h.len.H >= 5) return ['2H', `5+ ${SYM.H}, 12+ HCP. Game forcing.`];
    if (h.len.D >= 4 && h.len.D > h.len.C) return ['2D', `4+ ${SYM.D}, 12+ HCP. Game forcing.`];
    if (h.len.C >= 3) return ['2C', `3+ ${SYM.C}, 12+ HCP. Game forcing.`];
    return ['2D', `4+ ${SYM.D}, 12+ HCP. Game forcing.`];
  }
  if (passed) return ['1NT', '6-11 HCP, no fit.'];
  return ['1NT', '6-11 HCP. Forcing.'];
}

function respondMinor(ctx: Ctx, x: Suit): Decision {
  const h = ctx.h;
  const hcp = h.hcp;
  const sup = h.len[x];
  const passed = ctx.passedHand(ctx.me);
  if (hcp < RESPONSE_MIN) return ['Pass', 'Fewer than 6 HCP.'];
  const js = jumpShift(ctx, x);
  if (js) return js;
  const majors = MAJORS.filter((s) => h.len[s] >= 4);
  if (x === 'D' && !passed && hcp >= TWO_OVER_ONE && h.len.C >= 5
    && MAJORS.every((m) => h.len.C > h.len[m])) {
    return ['2C', `4+ ${SYM.C}, 12+ HCP. Game forcing.`];
  }
  if (majors.length) {
    const m = majors.length === 2 && h.len.S > h.len.H ? 'S' : majors[0];
    return [`1${m}`, `4+ ${SYM[m]}, 6+ HCP.`];
  }
  if (x === 'C' && h.len.D >= 4) return ['1D', `4+ ${SYM.D}, 6+ HCP.`];
  if (x === 'D' && !passed && hcp >= TWO_OVER_ONE && h.len.C >= 4) {
    return ['2C', `4+ ${SYM.C}, 12+ HCP. Game forcing.`];
  }
  const need = x === 'C' ? 5 : 4;
  if (sup >= need && hcp >= INVERTED_MIN) {
    return [`2${x}`, `${need}+ ${SYM[x]}, ${INVERTED_MIN}+ HCP. Inverted, forcing.`];
  }
  if (sup >= 5 && hcp <= 9) return [`3${x}`, `5+ ${SYM[x]}, 6-9 HCP. Weak raise.`];
  if (hcp <= 10) return ['1NT', '6-10 HCP, no 4-card major.'];
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
    return hcp >= 14 ? [`4${x}`, TO_PLAY] : ['Pass', 'Declining the invitation.'];
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
  if (hcp <= 14) return ['Pass', 'Minimum.'];
  if (hcp >= 18 || (hcp >= 17 && !short.length)) return [`4${x}`, TO_PLAY];
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
    if ((o === '2S' || o === '2NT') && o !== `2${x}`) {
      return hcp >= 9 ? [`4${x}`, TO_PLAY] : [`3${x}`, 'Declining the game try.'];
    }
    if (ol === 3 && os !== x) {
      const accept = hcp >= 9
        || (hcp >= 8 && (h.len[os as Suit] <= 1 || h.top(os as Suit, ['A', 'K', 'Q']) >= 1));
      return accept ? [`4${x}`, TO_PLAY] : [`3${x}`, 'Declining the game try.'];
    }
    if (o === `3${x}`) return hcp >= 9 ? [`4${x}`, TO_PLAY] : ['Pass', 'Declining the invitation.'];
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
      if (hcp + lo >= GAME) return [`4${y}`, TO_PLAY];
      if (hcp + hi >= GAME && ol === 2) return [`3${y}`, 'Invitational.'];
      return ['Pass', 'No game.'];
    }
    if (hcp + lo >= GAME) return ['3NT', TO_PLAY];
    return ['Pass', 'No game.'];
  }
  if (o === '1NT') {
    if (isMajor(y) && h.len[y as Suit] >= 5 && hcp >= 11) {
      const nmf = x === 'C' ? '2D' : '2C';
      if (ctx.ok(nmf)) return [nmf, 'New minor forcing. Artificial.'];
    }
    if (hcp + lo >= GAME) {
      if (isMajor(y) && h.len[y as Suit] >= 6) return [`4${y}`, TO_PLAY];
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
      if (hcp + lo >= GAME) return isMajor(x) ? [`4${x}`, TO_PLAY] : ['3NT', TO_PLAY];
      if (hcp + hi >= GAME) return [`3${x}`, 'Invitational.'];
      return ['Pass', 'No game.'];
    }
    if (isSuit(y) && h.len[y] >= 6) {
      if (hcp + lo >= GAME && isMajor(y)) return [`4${y}`, TO_PLAY];
      if (hcp + hi >= GAME && ctx.ok(`3${y}`)) return [`3${y}`, `6+ ${SYM[y]}, invitational.`];
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
      if (isMajor(z) && h.len[z] >= 4) return [`4${z}`, TO_PLAY];
      if (isMajor(x) && h.len[x] >= 3) return [`4${x}`, TO_PLAY];
      if (isMajor(y) && h.len[y as Suit] >= 6) return [`4${y}`, TO_PLAY];
      const fourth = SUITS.filter((s) => s !== x && s !== y && s !== z);
      if (fourth.length) {
        const call = ctx.cheapest(fourth[0]);
        if (call && levelOf(call) <= 3 && rankOf(call) < rankOf('3NT')) {
          return [call, 'Fourth suit forcing. Artificial.'];
        }
      }
      return ['3NT', TO_PLAY];
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
  if (hcp + lo >= GAME) {
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
  if (hcp + hi >= GAME && base === 1) {
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
      if (hcp + lo >= GAME) return [`4${s}`, TO_PLAY];
      return [`3${s}`, 'Invitational.'];
    }
    if (hcp + lo >= GAME) {
      const m5 = MAJORS.filter((m) => h.len[m] >= 5);
      if (m5.length && o !== '2S' && ctx.ok(`3${m5[0]}`)) return [`3${m5[0]}`, `5+ ${SYM[m5[0]]}, game forcing.`];
      return ['3NT', TO_PLAY];
    }
    if (ctx.ok('2NT')) return ['2NT', 'Invitational.'];
    return ['Pass', 'No game.'];
  }
  for (const [key, s] of [['to_h', 'H'], ['to_s', 'S']] as ['to_h' | 'to_s', Suit][]) {
    if (r === code[key]) {
      if (o === `3${s}` && base === 1) return hcp >= 4 ? [`4${s}`, TO_PLAY] : ['Pass', 'Weak.'];
      if (hcp + lo >= SLAM && ctx.ok('4NT')) return ['4NT', 'Quantitative: invites 6NT.'];
      if (hcp + lo >= GAME) return ['3NT', `5 ${SYM[s]}, choice of games.`];
      if (hcp + hi >= GAME && ctx.ok('2NT')) return ['2NT', `5 ${SYM[s]}, invitational.`];
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

function continuation(ctx: Ctx): Decision {
  const seq = ctx.seq;
  const h = ctx.h;
  let meParity = ctx.iAmOpener() ? 0 : 1;
  if (!ctx.weOpened) meParity = ctx.ours.length && ctx.ours[0][0] === ctx.me ? 0 : 1;
  const pParity = 1 - meParity;
  const pmin = partnerMin(seq, pParity);
  const plen = shownLengths(seq, pParity);
  const mylen = shownLengths(seq, meParity);
  const comb = h.judge + pmin;
  const gf = gameForced(seq, ctx);
  const current = ctx.current();
  const curRank = current ? rankOf(current) : -1;
  const trump = agreedTrump(seq);
  const partners = ctx.partners();
  const partnerLast = partners.length ? partners[partners.length - 1] : null;

  const fits: Suit[] = SUITS.filter((s) => plen[s] && plen[s] + h.len[s] >= 8);
  if (isSuit(trump) && !fits.includes(trump)) fits.push(trump);
  let fit: Suit | null = null;
  if (fits.length) fit = maxBy(fits, (s) => [isMajor(s) ? 1 : 0, plen[s] + h.len[s], idx(s)]);

  if (partnerLast && levelOf(partnerLast) >= 6) return ['Pass', 'Partner placed the contract.'];
  if (fit) {
    if (trump === fit && comb >= SLAM && ctx.ok('4NT') && curRank < rankOf('4NT') && !seq.includes('4NT')) {
      return ['4NT', `Keycard Blackwood for ${SYM[fit]}. Artificial.`];
    }
    if (isMajor(fit)) {
      if (comb >= GAME || gf) {
        if (curRank >= rankOf(`4${fit}`)) return ['Pass', 'Game reached.'];
        return [`4${fit}`, TO_PLAY];
      }
      const call = ctx.cheapest(fit, 2);
      if (comb >= GAME - 2 && call && levelOf(call) <= 3) return [call, natural(fit)];
      if (partnerLast && strainOf(partnerLast) === fit) return ['Pass', 'No game.'];
      if (call && levelOf(call) <= 2) return [call, natural(fit)];
      return ['Pass', 'No game.'];
    }
    if (comb >= GAME || gf) {
      if (curRank < rankOf('3NT') && h.balanced) return ['3NT', TO_PLAY];
      if (comb >= 29 && curRank < rankOf(`5${fit}`)) return [`5${fit}`, TO_PLAY];
      if (curRank < rankOf('3NT')) return ['3NT', TO_PLAY];
      return ['Pass', 'Game reached.'];
    }
    if (partnerLast && strainOf(partnerLast) === fit) return ['Pass', 'No game.'];
    const call = ctx.cheapest(fit, 2);
    if (call && levelOf(call) <= 3) return [call, natural(fit)];
    return ['Pass', 'No game.'];
  }

  if ((current && levelOf(current) >= 4) || current === '3NT') return ['Pass', 'Game reached.'];
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
    if (call && levelOf(call) <= 3 && (hcp <= 9 || cueTooHigh)) return [call, `3+ ${SYM[x]}, 6+ HCP.`];
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
  if (lastCall[0] !== ctx.me && lastCall[0] !== ctx.pd && parseBid(lastCall[1])) return null;
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
      if (call && levelOf(call) <= 3) return [call, `3+ ${SYM[ps]}, 6-9 HCP.`];
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
