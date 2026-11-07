// Port of challenge.py: the same deal played by you and by an all-robot table,
// each result split into what the auction cost and what the card play cost.
//
//     par - actual = bidding_loss + play_loss
//
// Par is duplicate par: both sides bid perfectly (challenge.py's `par_from_tricks`).
import library from '$root/data/solved_deals.json';
import { STRAINS, parseHand, removeCard, type Card, type Seat, type Side, type Strain,
  type Vulnerability } from './card';
import {
  AuctionState, PLAYERS, clockwiseFrom, otherSide, resolveTrick,
  type CallRecord, type Contract, type Play,
} from './auction';
import { aiBidExplained, aiPlay, shownLengths, visibleHands } from './ai';
import { scoreContract, type ScoredContract, type ScoreResult } from './scoring';

interface LibraryDeal {
  id: number;
  hands: Record<Seat, string>;
  /** "<strain>:<declarer>" -> tricks the declaring side takes. */
  tricks: Record<string, number>;
}

const DEALS = new Map<number, LibraryDeal>(
  (library.deals as LibraryDeal[]).map((d) => [d.id, d]),
);

/** A board is abandoned if the auction will not terminate. */
const AUCTION_GUARD = 60;

export function dealIds(): number[] {
  return [...DEALS.keys()].sort((a, b) => a - b);
}

export function handsFor(dealId: number): Record<Seat, Card[]> {
  const raw = DEALS.get(dealId)!.hands;
  return Object.fromEntries(PLAYERS.map((s) => [s, parseHand(raw[s])])) as Record<Seat, Card[]>;
}

const PARTNERS: Record<Side, readonly Seat[]> = { 'N/S': ['North', 'South'], 'E/W': ['East', 'West'] };

/** Tricks the declaring side takes, both sides perfect: `declarer`'s count,
 *  or without one the better partner's (a side chooses who declares). */
export function ddTricks(dealId: number, strain: Strain, side: Side, declarer?: Seat): number {
  const tricks = DEALS.get(dealId)!.tricks;
  if (declarer !== undefined) return tricks[`${strain}:${declarer}`];
  return Math.max(...PARTNERS[side].map((s) => tricks[`${strain}:${s}`]));
}

/** The board's score FROM `side`: positive when they gain. */
export function scoreFor(side: Side, contract: ScoredContract, declarerTricks: number): number {
  const declaring = contract.side;
  const taken = { [declaring]: declarerTricks, [otherSide(declaring)]: 13 - declarerTricks } as Record<Side, number>;
  const result = scoreContract(contract, taken);
  return result.winner === side ? result.points : -result.points;
}

export interface Par {
  /** From the side asked for: positive when it gains. */
  score: number;
  level: number;
  strain: Strain | null;
  /** The declaring side, or null when the deal is passed out. */
  side: Side | null;
  doubled: 'None' | 'X';
  /** The declaring side's tricks. */
  tricks: number;
}

/** Every contract in bidding order, 1♣ to 7NT. */
const CONTRACT_LADDER: readonly [number, Strain][] =
  [1, 2, 3, 4, 5, 6, 7].flatMap((level) => STRAINS.map((strain) => [level, strain] as [number, Strain]));

/** Duplicate par from a double dummy table: challenge.py's `par_from_tricks`,
 *  line for line. A side passes the contract standing or bids a higher one of
 *  its own; a failing contract is doubled, a making one isn't. N/S speak first. */
export function parFromTricks(tricks: (strain: Strain, side: Side) => number, side: Side,
  vulnerability: Vulnerability = 'None'): Par {
  const sides: Side[] = ['N/S', 'E/W'];
  const table = new Map<string, number>();
  for (const strain of STRAINS) for (const s of sides) table.set(`${strain}:${s}`, tricks(strain, s));
  const n = CONTRACT_LADDER.length;
  const passedOut: Par = { score: 0, level: 0, strain: null, side: null, doubled: 'None', tricks: 0 };

  const played = (k: number, owner: Side): Par => {
    const [level, strain] = CONTRACT_LADDER[k];
    const taken = table.get(`${strain}:${owner}`)!;
    const doubled = taken < level + 6 ? 'X' : 'None';
    const score = scoreFor('N/S', {
      level, strain, side: owner, tricks_needed: level + 6, doubled, vulnerability,
    }, taken);
    return { score, level, strain, side: owner, doubled, tricks: taken };
  };

  // best[k][owner]: the outcome once `owner` has bid contract k and the other
  // side is to speak. Scores from N/S; the first (lowest) of equal outcomes wins.
  const best: Record<Side, Par>[] = new Array(n);
  for (let k = n - 1; k >= 0; k--) {
    const row = {} as Record<Side, Par>;
    for (const owner of sides) {
      const mover = otherSide(owner);
      const sign = mover === 'N/S' ? 1 : -1;
      let outcome = played(k, owner);
      for (let j = k + 1; j < n; j++) {
        const reply = best[j][mover];
        if (sign * reply.score > sign * outcome.score) outcome = reply;
      }
      row[owner] = outcome;
    }
    best[k] = row;
  }

  const opening = (mover: Side, afterPass: boolean): Par => {
    const sign = mover === 'N/S' ? 1 : -1;
    let outcome = afterPass ? passedOut : opening(otherSide(mover), true);
    for (let k = 0; k < n; k++) {
      if (sign * best[k][mover].score > sign * outcome.score) outcome = best[k][mover];
    }
    return outcome;
  };

  const result = { ...opening('N/S', false) };
  if (side === 'E/W') result.score = -result.score;
  return result;
}

/** Duplicate par on a library deal, from `side`. */
export function par(dealId: number, side: Side, vulnerability: Vulnerability = 'None'): Par {
  return parFromTricks((strain, s) => ddTricks(dealId, strain, s), side, vulnerability);
}

export interface TrickLog {
  trick_num: number;
  leader: Seat;
  plays: Play[];
  winner: Seat;
  winning_card: Card;
}

export interface RobotTable {
  contract: Contract | null;
  calls: CallRecord[];
  alerts: Record<number, string>;
  initial_hands: Record<Seat, Card[]>;
  dealer: Seat;
  vulnerability: Vulnerability;
  declarer_tricks: number;
  tricks_log: TrickLog[];
  tricks_taken: Record<Side, number>;
  result: ScoreResult | null;
}

export function robotTable(dealId: number, dealer: Seat, vulnerability: Vulnerability = 'None'): RobotTable {
  const hands = handsFor(dealId);
  const initial = handsFor(dealId);
  const auction = new AuctionState(dealer, vulnerability);
  const alerts: Record<number, string> = {};
  let guard = 0;
  while (!auction.isComplete && guard < AUCTION_GUARD) {
    const who = auction.currentPlayer();
    const [call, why] = aiBidExplained(who, hands[who], auction, alerts);
    alerts[auction.calls.length] = why;
    auction.applyCall(who, call);
    guard++;
  }
  const contract = auction.getContract();
  const base = {
    contract, calls: [...auction.calls], alerts, initial_hands: initial, dealer, vulnerability,
  };
  if (contract === null) {
    return { ...base, declarer_tricks: 0, tricks_log: [], tricks_taken: { 'N/S': 0, 'E/W': 0 }, result: null };
  }

  const trump = contract.trump;
  let leader = contract.leader;
  const shown = shownLengths(auction.calls as [Seat, string][], alerts);
  const played: Card[] = [];
  const taken: Record<Side, number> = { 'N/S': 0, 'E/W': 0 };
  const log: TrickLog[] = [];
  for (let n = 1; n <= 13; n++) {
    const trick: Play[] = [];
    const trickLeader = leader;
    for (const seat of clockwiseFrom(leader)) {
      const c = aiPlay(seat, hands[seat], trick, trump, played, visibleHands(seat, contract, hands),
        log.map((e) => e.plays), shown);
      removeCard(hands[seat], c);
      trick.push([seat, c]);
    }
    const winner = resolveTrick(trick, trump);
    taken[winner === 'North' || winner === 'South' ? 'N/S' : 'E/W']++;
    log.push({
      trick_num: n, leader: trickLeader, plays: trick, winner,
      winning_card: trick.find(([p]) => p === winner)![1],
    });
    played.push(...trick.map(([, c]) => c));
    leader = winner;
  }
  return {
    ...base,
    declarer_tricks: taken[contract.side],
    tricks_log: log,
    tricks_taken: taken,
    result: scoreContract(contract, taken),
  };
}

export interface Grade {
  par: Par;
  passed_out: boolean;
  dd_tricks?: number;
  dd_score: number;
  actual: number;
  bidding_loss: number;
  play_loss: number;
  total_loss: number;
}

/** A loss is reported POSITIVE as points given away. See challenge.py. */
export function grade(dealId: number, side: Side, contract: (ScoredContract & { declarer?: Seat }) | null,
  declarerTricks: number, vulnerability: Vulnerability = 'None'): Grade {
  const target = par(dealId, side, vulnerability);
  if (contract === null) {
    return { par: target, passed_out: true, dd_score: 0, actual: 0,
      bidding_loss: target.score, play_loss: 0, total_loss: target.score };
  }
  const perfect = ddTricks(dealId, contract.strain, contract.side, contract.declarer);
  const ddScore = scoreFor(side, contract, perfect);
  const actual = scoreFor(side, contract, declarerTricks);
  return {
    par: target, passed_out: false, dd_tricks: perfect, dd_score: ddScore, actual,
    bidding_loss: target.score - ddScore,
    play_loss: ddScore - actual,
    total_loss: target.score - actual,
  };
}
