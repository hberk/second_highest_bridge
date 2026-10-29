// LIN, BBO's hand-record format: a deal followed by every call and card, as
// `key|value|` pairs. A record here is a HistoryRecord, which carries far more
// (contract, trick winners, score), but all of that is derived. So `toLin`
// writes only what LIN holds, and `fromLin` rebuilds the rest by replaying the
// board through the engine under this game's rules.
//
// That replay is also the validation: a card played out of turn, a revoke, or
// an illegal call is refused rather than imported. A LIN from ordinary bridge
// is usually refused for that reason: once a trick goes to a different hand
// under the second-highest rule, the next lead comes from the "wrong" seat.
//
// The reverse caveat: BBO's own hand viewer applies ordinary rules, so it
// would credit our tricks to the wrong side and see leads out of turn.
import {
  PLAYERS, AuctionState, PARTNERSHIP, cleanAlert, clockwiseFrom, legalPlays, resolveTrick,
  type CallRecord, type Play,
} from './engine/auction';
import {
  SUITS, cardKey, sameCard, sortHand, card, RANKS,
  type Card, type Seat, type Side, type Suit, type Vulnerability,
} from './engine/card';
import { scoreContract } from './engine/scoring';
import type { TrickLog } from './engine/challenge';
import type { HistoryRecord } from './saves';

/** LIN lists hands, and numbers the dealer, starting from South. */
const LIN_SEATS: readonly Seat[] = ['South', 'West', 'North', 'East'];
const LIN_VUL: Record<Vulnerability, string> = { None: 'o', 'N/S': 'n', 'E/W': 'e', Both: 'b' };
/** A Map, not an object: `sv|constructor|` must not find Object's prototype. */
const VUL_FROM_LIN = new Map<string, Vulnerability>([
  ['o', 'None'], ['0', 'None'], ['-', 'None'], ['n', 'N/S'], ['e', 'E/W'], ['b', 'Both'],
]);

/** The most boards one import reads: what this app keeps on a device. */
export const MAX_LIN_BOARDS = 500;
/** The largest LIN file the app opens; 500 boards are about 200 KB. */
export const MAX_LIN_BYTES = 1_000_000;
const HAND_SUITS: readonly Suit[] = ['S', 'H', 'D', 'C'];
const SYMBOL_TO_LIN: Record<string, string> = { '♠': '!S', '♥': '!H', '♦': '!D', '♣': '!C' };
const LIN_TO_SYMBOL: Record<string, string> = { S: '♠', H: '♥', D: '♦', C: '♣' };

const linRank = (r: string) => (r === '10' ? 'T' : r);
const rankFromLin = (r: string) => (r === 'T' ? '10' : r);
const linCard = (c: Card) => `${c.suit}${linRank(c.rank)}`;

function linCall(call: string): string {
  if (call === 'Pass') return 'p';
  if (call === 'X') return 'd';
  if (call === 'XX') return 'r';
  return call.replace('NT', 'N');
}

function callFromLin(token: string): string {
  const t = token.toUpperCase();
  if (t === 'P' || t === 'PASS') return 'Pass';
  if (t === 'D' || t === 'X' || t === 'DBL') return 'X';
  if (t === 'R' || t === 'XX' || t === 'RDBL') return 'XX';
  if (/^[1-7]N$/.test(t)) return `${t[0]}NT`;
  return t;
}

/** LIN has no escaping: a `|` would end the field early. BBO writes suit
 *  symbols as !S/!H/!D/!C, so the symbols travel that way too. */
function alertToLin(text: string): string {
  return text.replace(/[|\r\n]+/g, '/').replace(/[♠♥♦♣]/g, (s) => SYMBOL_TO_LIN[s]).trim();
}

/** Suit symbols back, then the clean-up a typed alert gets: one line, at most
 *  70 characters. */
function alertFromLin(text: string): string {
  return cleanAlert(text.replace(/!([SHDC])/gi, (_, s: string) => LIN_TO_SYMBOL[s.toUpperCase()]));
}

function handToLin(hand: Card[]): string {
  return HAND_SUITS.map((s) => s + sortHand(hand).filter((c) => c.suit === s).map((c) => linRank(c.rank)).join('')).join('');
}

function handFromLin(text: string): Card[] {
  const out: Card[] = [];
  let suit: Suit | null = null;
  for (const ch of text.toUpperCase()) {
    if ((HAND_SUITS as readonly string[]).includes(ch)) suit = ch as Suit;
    else if (suit && RANKS.includes(rankFromLin(ch))) out.push(card(suit, rankFromLin(ch)));
    else throw new LinError(`Unreadable hand '${text}'`);
  }
  return out;
}

export class LinError extends Error {}

/** One board as a single LIN line. */
export function toLin(record: HistoryRecord, names?: Partial<Record<Seat, string>>): string {
  const parts: string[] = [];
  const add = (key: string, value: string | number = '') => parts.push(`${key}|${value}|`);
  add('pn', LIN_SEATS.map((s) => (names?.[s] ?? s).replace(/[|,]/g, ' ')).join(','));
  add('st');
  const dealer = LIN_SEATS.indexOf(record.dealer) + 1;
  add('md', `${dealer}${LIN_SEATS.map((s) => handToLin(record.initial_hands[s])).join(',')}`);
  add('rh');
  add('ah', `Board ${record.board_num}`);
  add('sv', LIN_VUL[record.vulnerability]);
  record.auction_calls.forEach(([, call], i) => {
    const alert = record.bid_alerts[i] ? alertToLin(record.bid_alerts[i]) : '';
    add('mb', linCall(call) + (alert ? '!' : ''));
    if (alert) add('an', alert);
  });
  add('pg');
  for (const t of record.tricks_log) {
    for (const [, c] of t.plays) add('pc', linCard(c));
    add('pg');
  }
  // A board that ended in a claim: write the claim back, or the LIN reads as
  // play that just stops, which fromLin (rightly) refuses.
  if (record.contract && record.tricks_log.length < 13) {
    add('mc', record.tricks_taken[record.contract.side]);
  }
  return parts.join('');
}

/** Several boards, one per line: what a .lin file of a session looks like. */
export function toLinFile(records: HistoryRecord[]): string {
  return records.map((r) => toLin(r)).join('\n') + '\n';
}

function tokens(text: string): [string, string][] {
  const fields = text.replace(/^﻿/, '').replace(/\r?\n/g, '').split('|');
  const out: [string, string][] = [];
  for (let i = 0; i + 1 < fields.length; i += 2) out.push([fields[i].trim().toLowerCase(), fields[i + 1]]);
  return out;
}

/** Every board in a LIN text. A new board starts at each `md` (or a `qx`
 *  that follows one), so a whole session file reads in one call. */
export function fromLinFile(text: string): HistoryRecord[] {
  const boards: [string, string][][] = [];
  let current: [string, string][] = [];
  let sawDeal = false;
  for (const tok of tokens(text)) {
    if ((tok[0] === 'md' || tok[0] === 'qx') && sawDeal) {
      boards.push(current);
      current = [];
      sawDeal = false;
    }
    if (tok[0] === 'md') sawDeal = true;
    current.push(tok);
  }
  if (sawDeal) boards.push(current);
  if (!boards.length) throw new LinError('No deal (md) found');
  if (boards.length > MAX_LIN_BOARDS) {
    throw new LinError(`${boards.length} boards; at most ${MAX_LIN_BOARDS} are read at once`);
  }
  return boards.map((b, i) => buildRecord(b, i + 1));
}

export function fromLin(text: string): HistoryRecord {
  const records = fromLinFile(text);
  if (records.length !== 1) throw new LinError(`Expected one board, found ${records.length}`);
  return records[0];
}

function buildRecord(toks: [string, string][], fallbackNum: number): HistoryRecord {
  let dealer: Seat | null = null;
  let hands: Record<Seat, Card[]> | null = null;
  let vulnerability: Vulnerability = 'None';
  let boardNum = fallbackNum;
  const calls: string[] = [];
  const alerts: Record<number, string> = {};
  const cards: Card[] = [];
  let claim: number | null = null;

  for (const [key, value] of toks) {
    switch (key) {
      case 'md': {
        const d = Number(value[0]);
        if (!(d >= 1 && d <= 4)) throw new LinError(`Bad dealer in md '${value}'`);
        dealer = LIN_SEATS[d - 1];
        hands = parseDeal(value.slice(1));
        break;
      }
      case 'sv': {
        const v = VUL_FROM_LIN.get(value.trim().toLowerCase());
        if (!v) throw new LinError(`Bad vulnerability '${value}'`);
        vulnerability = v;
        break;
      }
      case 'ah': {
        const m = /[0-9]+/.exec(value);
        if (m && m[0].length <= 6) boardNum = Number(m[0]);
        break;
      }
      case 'mb': {
        const raw = value.trim();
        const alerted = raw.endsWith('!');
        calls.push(callFromLin(alerted ? raw.slice(0, -1) : raw));
        break;
      }
      case 'an':
        if (!calls.length) throw new LinError('Alert (an) before any call');
        if (alertFromLin(value)) alerts[calls.length - 1] = alertFromLin(value);
        break;
      case 'pc': {
        const t = value.trim().toUpperCase();
        const suit = t[0] as Suit;
        const rank = rankFromLin(t.slice(1));
        if (!SUITS.includes(suit) || !RANKS.includes(rank)) throw new LinError(`Bad card '${value}'`);
        cards.push(card(suit, rank));
        break;
      }
      case 'mc':
        // Digits only: Number() would read '' as 0 and '0x5' or '1e1' as numbers.
        if (!/^[0-9]{1,2}$/.test(value.trim()) || Number(value) > 13) throw new LinError(`Bad claim '${value}'`);
        claim = Number(value);
        break;
      // pn, st, rh, pg, qx, nt, ...: presentation only.
    }
  }
  if (!dealer || !hands) throw new LinError('No deal (md) found');

  const auction = new AuctionState(dealer, vulnerability);
  for (const call of calls) {
    const who = auction.currentPlayer();
    try {
      auction.applyCall(who, call);
    } catch (e) {
      throw new LinError(`Call ${auction.calls.length + 1} (${call} by ${who}): ${(e as Error).message}`);
    }
  }
  const auctionCalls: CallRecord[] = auction.calls.map(([p, c]) => [p, c]);
  const base = {
    board_num: boardNum,
    dealer,
    vulnerability,
    initial_hands: Object.fromEntries(PLAYERS.map((p) => [p, sortHand(hands![p])])) as Record<Seat, Card[]>,
    auction_calls: auctionCalls,
    bid_alerts: alerts,
  };
  // A record has to be a finished board: there is nothing to score otherwise.
  if (!auction.isComplete) throw new LinError(`Board ${boardNum}: the auction never finished`);
  const contract = auction.getContract();
  if (!contract) {
    if (cards.length) throw new LinError('Cards played on a passed-out board');
    return { ...base, contract: null, passed_out: true, tricks_log: [], tricks_taken: { 'N/S': 0, 'E/W': 0 }, result: null };
  }

  const left = Object.fromEntries(PLAYERS.map((p) => [p, [...hands![p]]])) as Record<Seat, Card[]>;
  const tricksLog: TrickLog[] = [];
  const taken: Record<Side, number> = { 'N/S': 0, 'E/W': 0 };
  let order = clockwiseFrom(contract.leader);
  for (let i = 0; i < cards.length; i += 4) {
    const plays: Play[] = [];
    for (const [k, c] of cards.slice(i, i + 4).entries()) {
      const who = order[k];
      if (!left[who].some((h) => sameCard(h, c))) {
        const holder = PLAYERS.find((p) => left[p].some((h) => sameCard(h, c)));
        throw new LinError(`Trick ${i / 4 + 1}: ${cardKey(c)} is not ${who}'s to play`
          + (holder ? ` (${holder} holds it): not played under second-highest rules?` : ' (already played)'));
      }
      const led = plays.length ? plays[0][1].suit : null;
      if (!legalPlays(left[who], led).some((l) => sameCard(l, c))) {
        throw new LinError(`Trick ${i / 4 + 1}: ${who} revokes with ${cardKey(c)}`);
      }
      left[who].splice(left[who].findIndex((h) => sameCard(h, c)), 1);
      plays.push([who, c]);
    }
    if (plays.length < 4) break; // a trick in progress at a claim
    const winner = resolveTrick(plays, contract.trump);
    taken[PARTNERSHIP[winner]] += 1;
    tricksLog.push({
      trick_num: tricksLog.length + 1,
      leader: plays[0][0],
      plays,
      winner,
      winning_card: plays.find(([p]) => p === winner)![1],
    });
    order = clockwiseFrom(winner);
  }

  const complete = tricksLog.length === 13;
  if (claim !== null) {
    // `mc` is declarer's side's total for the whole board.
    const remaining = 13 - tricksLog.length;
    const defence = contract.side === 'N/S' ? 'E/W' : 'N/S';
    if (claim < taken[contract.side] || claim - taken[contract.side] > remaining) {
      throw new LinError(`Claim of ${claim} is impossible after ${tricksLog.length} tricks`);
    }
    taken[defence] += remaining - (claim - taken[contract.side]);
    taken[contract.side] = claim;
  } else if (!complete) {
    throw new LinError(`Board ${boardNum}: play stops after ${tricksLog.length} tricks and nothing was claimed`);
  }
  return {
    ...base, contract, passed_out: false, tricks_log: tricksLog, tricks_taken: taken,
    result: scoreContract(contract, taken),
  };
}

/** `SAKQ..H..D..C..,<West>,<North>,<East>`: South first; the last hand is
 *  often left out, and is then whatever the other three don't hold. */
function parseDeal(text: string): Record<Seat, Card[]> {
  const parts = text.split(',');
  const hands = {} as Record<Seat, Card[]>;
  LIN_SEATS.forEach((s, i) => (hands[s] = parts[i]?.trim() ? handFromLin(parts[i].trim()) : []));
  const seen = new Set<string>();
  for (const s of LIN_SEATS) {
    for (const c of hands[s]) {
      if (seen.has(cardKey(c))) throw new LinError(`${cardKey(c)} dealt twice`);
      seen.add(cardKey(c));
    }
  }
  const empty = LIN_SEATS.filter((s) => hands[s].length === 0);
  if (empty.length === 1 && seen.size === 39) {
    hands[empty[0]] = SUITS.flatMap((s) => RANKS.map((r) => card(s, r))).filter((c) => !seen.has(cardKey(c)));
  }
  for (const s of LIN_SEATS) {
    if (hands[s].length !== 13) throw new LinError(`${s} holds ${hands[s].length} cards, not 13`);
  }
  return hands;
}
