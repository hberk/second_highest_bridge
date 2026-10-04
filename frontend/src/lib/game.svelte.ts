// The table's state machine -- the port of app.py's session-state logic.
//
// State is plain reactive data. The auction is not stored as an object: it is
// rebuilt from `calls` whenever it is read, so there is only one source of
// truth and nothing to keep in sync.
import { deal, removeCard, sameCard, type Card, type Seat, type Side, type Vulnerability } from './engine/card';
import {
  AuctionState, DEALER_ROTATION, PARTNERSHIP, VUL_ROTATION, clockwiseFrom, legalPlays, resolveTrick,
  type CallRecord, type Contract, type Play,
} from './engine/auction';
import { aiBidExplained, aiPlay } from './engine/ai';
import { scoreContract, type ScoreResult } from './engine/scoring';
import * as challenge from './engine/challenge';
import type { Grade, RobotTable, TrickLog } from './engine/challenge';

export type Phase = 'bidding' | 'auction_done' | 'playing' | 'trick_done' | 'done';

export interface HistoryRecord {
  board_num: number;
  label?: string;
  dealer: Seat;
  vulnerability: Vulnerability;
  initial_hands: Record<Seat, Card[]>;
  auction_calls: CallRecord[];
  bid_alerts: Record<number, string>;
  contract: Contract | null;
  passed_out: boolean;
  tricks_log: TrickLog[];
  tricks_taken: Record<Side, number>;
  result: ScoreResult | null;
}

export interface ChallengeResult {
  deal_id: number;
  board_num: number;
  you: Grade;
  robot: Grade;
  your_contract: Contract | null;
  robot_contract: Contract | null;
  robot_record: HistoryRecord;
  margin: number;
}

export interface ChallengeLogEntry {
  deal_id: number;
  you: number;
  robot: number;
  margin: number;
  your_bidding_loss: number;
  your_play_loss: number;
  robot_bidding_loss: number;
  robot_play_loss: number;
}

const HUMAN: Seat = 'South';

const copyHands = (h: Record<Seat, Card[]>) =>
  Object.fromEntries(Object.entries(h).map(([s, cs]) => [s, [...cs]])) as Record<Seat, Card[]>;

export function asHistoryRecord(table: RobotTable, boardNum: number, label: string): HistoryRecord {
  return {
    board_num: boardNum,
    label,
    dealer: table.dealer,
    vulnerability: table.vulnerability,
    initial_hands: table.initial_hands,
    auction_calls: table.calls,
    bid_alerts: table.alerts,
    contract: table.contract,
    passed_out: table.contract === null,
    tricks_log: table.tricks_log,
    tricks_taken: table.tricks_taken,
    result: table.result,
  };
}

export class Game {
  boardNum = $state(0);
  dealer = $state<Seat>('North');
  vulnerability = $state<Vulnerability>('None');
  initialHands = $state.raw<Record<Seat, Card[]>>({ North: [], East: [], South: [], West: [] });
  hands = $state<Record<Seat, Card[]>>({ North: [], East: [], South: [], West: [] });
  calls = $state<CallRecord[]>([]);
  alerts = $state<Record<number, string>>({});
  phase = $state<Phase>('bidding');
  contract = $state.raw<Contract | null>(null);
  order = $state<Seat[]>([]);
  trick = $state<Play[]>([]);
  trickNum = $state(1);
  tricksTaken = $state<Record<Side, number>>({ 'N/S': 0, 'E/W': 0 });
  trickWinner = $state<Seat | null>(null);
  played: Card[] = [];
  tricksLog = $state<TrickLog[]>([]);
  result = $state.raw<ScoreResult | null>(null);
  challengeId = $state<number | null>(null);
  challenge = $state.raw<ChallengeResult | null>(null);
  history = $state<HistoryRecord[]>([]);
  challengeLog = $state<ChallengeLogEntry[]>([]);

  auction = $derived.by(() => {
    const a = new AuctionState(this.dealer, this.vulnerability);
    for (const [p, c] of this.calls) a.applyCall(p, c);
    return a;
  });

  get trump() { return this.contract?.trump ?? null; }
  get gameOver() { return this.result !== null; }

  constructor() {
    this.newBoard();
  }

  newBoard(dealId: number | null = null): void {
    const n = this.boardNum + 1;
    this.boardNum = n;
    this.dealer = DEALER_ROTATION[(n - 1) % 4];
    this.vulnerability = VUL_ROTATION[(n - 1) % 16];
    // A challenge board comes from the solved library, so every contract it
    // can reach already has an exact trick count.
    const hands = dealId === null ? deal() : challenge.handsFor(dealId);
    this.initialHands = copyHands(hands);
    this.hands = hands;
    this.calls = [];
    this.alerts = {};
    this.phase = 'bidding';
    this.contract = null;
    this.order = [];
    this.trick = [];
    this.trickNum = 1;
    this.tricksTaken = { 'N/S': 0, 'E/W': 0 };
    this.trickWinner = null;
    this.played = [];
    this.tricksLog = [];
    this.result = null;
    this.challengeId = dealId;
    this.challenge = null;
    this.advanceAuction();
  }

  dealChallenge(): boolean {
    const done = new Set(this.challengeLog.map((r) => r.deal_id));
    const remaining = challenge.dealIds().filter((i) => !done.has(i));
    if (!remaining.length) return false;
    this.newBoard(remaining[Math.floor(Math.random() * remaining.length)]);
    return true;
  }

  // ── Auction ────────────────────────────────────────────────────────────────

  private advanceAuction(): void {
    const auction = new AuctionState(this.dealer, this.vulnerability);
    for (const [p, c] of this.calls) auction.applyCall(p, c);
    while (!auction.isComplete) {
      const who = auction.currentPlayer();
      if (who === HUMAN) break;
      const [call, why] = aiBidExplained(who, this.hands[who], auction);
      this.alerts[auction.calls.length] = why;
      auction.applyCall(who, call);
      this.calls.push([who, call]);
    }
    if (!auction.isComplete || auction.passedOut) return;
    const contract = auction.getContract()!;
    this.contract = contract;
    this.order = clockwiseFrom(contract.leader);
    this.phase = 'auction_done';
  }

  humanBids(call: string): void {
    const auction = this.auction;
    if (auction.isComplete || auction.currentPlayer() !== HUMAN) return;
    if (!auction.legalCalls().includes(call)) return;
    this.calls.push([HUMAN, call]);
    this.advanceAuction();
  }

  // ── Play ───────────────────────────────────────────────────────────────────

  /** South picks South's card, plus North's when North is South's dummy. When
   *  North declares, South is dummy and the North robot plays both hands. */
  isHumanSeat(player: Seat): boolean {
    const declarer = this.contract?.declarer;
    if (player === 'South') return declarer !== 'North';
    return player === 'North' && declarer === 'South';
  }

  whoseTurn(): Seat | null {
    if (this.phase !== 'playing') return null;
    const done = new Set(this.trick.map(([p]) => p));
    for (const p of this.order) {
      if (!done.has(p)) return this.isHumanSeat(p) ? p : null;
    }
    return null;
  }

  startPlay(): void {
    this.phase = 'playing';
    this.advancePlay();
  }

  humanPlays(player: Seat, c: Card): void {
    if (this.whoseTurn() !== player) return;
    const led = this.trick.length ? this.trick[0][1].suit : null;
    if (!legalPlays(this.hands[player], led).some((l) => sameCard(l, c))) return;
    removeCard(this.hands[player], c);
    this.trick.push([player, c]);
    this.advancePlay();
  }

  private advancePlay(): void {
    const contract = this.contract!;
    const done = new Set(this.trick.map(([p]) => p));
    for (const player of this.order) {
      if (done.has(player)) continue;
      if (this.isHumanSeat(player)) return;
      const dummy = contract.dummy;
      const hands = $state.snapshot(this.hands) as Record<Seat, Card[]>;
      const c = aiPlay(player, hands[player], $state.snapshot(this.trick) as Play[],
        contract.trump, this.played, { [dummy]: hands[dummy] });
      removeCard(this.hands[player], c);
      this.trick.push([player, c]);
      done.add(player);
    }
    this.endTrick();
  }

  private endTrick(): void {
    const trick = $state.snapshot(this.trick) as Play[];
    const winner = resolveTrick(trick, this.trump);
    this.tricksTaken[PARTNERSHIP[winner]] += 1;
    this.trickWinner = winner;
    this.phase = 'trick_done';
    this.tricksLog.push({
      trick_num: this.trickNum,
      leader: trick[0][0],
      plays: trick,
      winner,
      winning_card: trick.find(([p]) => p === winner)![1],
    });
    this.trickNum += 1;
    if (this.trickNum > 13) this.finishBoard();
  }

  nextTrick(): void {
    if (this.gameOver) {
      this.phase = 'done';
      return;
    }
    this.played.push(...this.trick.map(([, c]) => $state.snapshot(c) as Card));
    this.trick = [];
    this.order = clockwiseFrom(this.trickWinner!);
    this.phase = 'playing';
    this.advancePlay();
  }

  private finishBoard(): void {
    const contract = this.contract!;
    const taken = { ...this.tricksTaken };
    this.result = scoreContract(contract, taken);
    this.gradeChallenge();
    this.history.push({
      board_num: this.boardNum,
      dealer: this.dealer,
      vulnerability: this.vulnerability,
      initial_hands: this.initialHands,
      auction_calls: $state.snapshot(this.calls) as CallRecord[],
      bid_alerts: { ...this.alerts },
      contract,
      passed_out: false,
      tricks_log: $state.snapshot(this.tricksLog) as TrickLog[],
      tricks_taken: taken,
      result: this.result,
    });
  }

  /** Replay this deal with robots in all four seats and compare. Only South's
   *  side is graded: North is a robot in both runs. */
  private gradeChallenge(): void {
    const dealId = this.challengeId;
    if (dealId === null) return;
    const contract = this.contract!;
    const vul = this.vulnerability;
    const mine = challenge.grade(dealId, 'N/S', contract, this.tricksTaken[contract.side], vul);
    const table = challenge.robotTable(dealId, this.dealer, vul);
    const theirs = challenge.grade(dealId, 'N/S', table.contract, table.declarer_tricks, vul);
    this.challenge = {
      deal_id: dealId,
      board_num: this.boardNum,
      you: mine,
      robot: theirs,
      your_contract: contract,
      robot_contract: table.contract,
      robot_record: asHistoryRecord(table, this.boardNum, "🤖 Robots' board"),
      margin: mine.actual - theirs.actual,
    };
    this.challengeLog.push({
      deal_id: dealId,
      you: mine.actual,
      robot: theirs.actual,
      margin: mine.actual - theirs.actual,
      your_bidding_loss: mine.bidding_loss,
      your_play_loss: mine.play_loss,
      robot_bidding_loss: theirs.bidding_loss,
      robot_play_loss: theirs.play_loss,
    });
  }
}
