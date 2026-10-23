// Port of challenge.py: the same deal played by you and by an all-robot table,
// each result split into what the auction cost and what the card play cost.
//
//     par - actual = bidding_loss + play_loss
//
// See challenge.py for why par is a ceiling rather than true duplicate par.
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
  tricks: Record<string, number>;
  declarers: Record<string, Seat>;
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

export function ddTricks(dealId: number, strain: Strain, side: Side): number {
  return DEALS.get(dealId)!.tricks[`${strain}:${side}`];
}

/** The partner who declared when `ddTricks` was solved; the other partner's
 *  count can differ by a trick or more. */
export function solvedDeclarer(dealId: number, strain: Strain, side: Side): Seat {
  return DEALS.get(dealId)!.declarers[`${strain}:${side}`];
}

/** The board's score FROM `side`: positive when they gain. */
export function scoreFor(side: Side, contract: ScoredContract, declarerTricks: number): number {
  const declaring = contract.side;
  const taken = { [declaring]: declarerTricks, [otherSide(declaring)]: 13 - declarerTricks } as Record<Side, number>;
  const result = scoreContract(contract, taken);
  return result.winner === side ? result.points : -result.points;
}

export interface Par {
  score: number;
  level: number;
  strain: Strain | null;
  tricks: number;
}

export function par(dealId: number, side: Side, vulnerability: Vulnerability = 'None'): Par {
  let best: Par | null = null;
  for (const strain of STRAINS) {
    const taken = ddTricks(dealId, strain, side);
    for (let level = 1; level < 8; level++) {
      if (level + 6 > taken) break;
      const points = scoreFor(side, {
        level, strain, side, tricks_needed: level + 6, doubled: 'None', vulnerability,
      }, taken);
      if (best === null || points > best.score) best = { score: points, level, strain, tricks: taken };
    }
  }
  return best ?? { score: 0, level: 0, strain: null, tricks: 0 };
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
    const [call, why] = aiBidExplained(who, hands[who], auction);
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
export function grade(dealId: number, side: Side, contract: ScoredContract | null,
  declarerTricks: number, vulnerability: Vulnerability = 'None'): Grade {
  const ceiling = par(dealId, side, vulnerability);
  if (contract === null) {
    return { par: ceiling, passed_out: true, dd_score: 0, actual: 0,
      bidding_loss: ceiling.score, play_loss: 0, total_loss: ceiling.score };
  }
  const perfect = ddTricks(dealId, contract.strain, contract.side);
  const ddScore = scoreFor(side, contract, perfect);
  const actual = scoreFor(side, contract, declarerTricks);
  return {
    par: ceiling, passed_out: false, dd_tricks: perfect, dd_score: ddScore, actual,
    bidding_loss: ceiling.score - ddScore,
    play_loss: ddScore - actual,
    total_loss: ceiling.score - actual,
  };
}
