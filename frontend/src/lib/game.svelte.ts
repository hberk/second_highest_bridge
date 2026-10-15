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
import { aiBidExplained, aiPlay, visibleHands } from './engine/ai';
import { scoreContract, type ScoreResult } from './engine/scoring';
import * as challenge from './engine/challenge';
import type { Grade, RobotTable, TrickLog } from './engine/challenge';
import { SAVE_KEY, askPersistence, browserStorage, clearGames, loadGames, mergeGames, saveGames } from './saves';

export type Phase = 'bidding' | 'auction_done' | 'playing' | 'trick_done' | 'done';

export interface HistoryRecord {
  board_num: number;
  label?: string;
  /** Loaded from LIN rather than played here: not part of the session score. */
  imported?: boolean;
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
  /** Your board when it passed out: passed-out boards stay out of `history`,
   *  so the review would otherwise have only the robots' side to show. */
  your_record?: HistoryRecord;
  margin: number;
}

export interface ChallengeLogEntry {
  deal_id: number;
  board_num: number;
  you: number;
  robot: number;
  margin: number;
  your_bidding_loss: number;
  your_play_loss: number;
  robot_bidding_loss: number;
  robot_play_loss: number;
}

const HUMAN: Seat = 'South';

/** The longest alert, the robots' own limit: it has to fit a tooltip. */
export const ALERT_MAX = 70;

/** One line of plain text. Svelte escapes it on the page; LIN export handles
 *  the `|` separator itself. */
export function cleanAlert(text: string): string {
  return text.replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, ALERT_MAX);
}

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
  /** Boards that passed out: not in `history` (there's nothing to replay),
   *  but they were played, so the session scoreboard counts them. */
  passedOutCount = $state(0);
  /** passedOutCount as last read from or written to storage, so a save adds
   *  only this tab's new pass-outs to what another tab may have counted. */
  private passedOutSynced = 0;
  /** Play the human's card for them when it's the only legal one. A display
   *  preference, set from settings by the app; off by default so tests and
   *  the Python port's behaviour are unchanged unless asked. */
  autoPlayForced = false;

  /** The alerts the table may see while the board is live: robot passes say
   *  WHY they passed, which reads the robot's cards out, and a real table never
   *  alerts a natural pass. The reasons stay in `alerts` for the post-mortem.
   *  Port of `web.auction_view.live_alerts`, plus the human's own alerts, which
   *  the Streamlit app has no way to make: a pass the player chose to alert
   *  (a forcing pass, say) is shown like any other alerted call. */
  liveAlerts = $derived.by(() => {
    const out: Record<number, string> = {};
    for (const [i, why] of Object.entries(this.alerts)) {
      const call = this.calls[Number(i)];
      if (call && (call[1] !== 'Pass' || call[0] === HUMAN)) out[Number(i)] = why;
    }
    return out;
  });

  auction = $derived.by(() => {
    const a = new AuctionState(this.dealer, this.vulnerability);
    for (const [p, c] of this.calls) a.applyCall(p, c);
    return a;
  });

  get trump() { return this.contract?.trump ?? null; }
  get gameOver() { return this.result !== null; }
  /** Played out or passed out: nothing more happens on this board. */
  get boardOver() { return this.gameOver || this.auction.passedOut; }

  /** `storage` is where finished boards are kept between visits: the
   *  browser's localStorage by default, null (nothing kept) in Node. */
  constructor(private storage: Storage | null = browserStorage()) {
    const saved = loadGames(storage);
    if (saved) {
      this.boardNum = saved.boardNum;
      this.adopt(saved);
    }
    // Another tab saved (or cleared) the games: take its copy, so this tab
    // never writes back a stale one over it. Browsers only; tests pass null.
    if (storage && typeof window !== 'undefined') {
      window.addEventListener('storage', (e) => {
        if (e.storageArea !== storage || (e.key !== SAVE_KEY && e.key !== null)) return;
        const now = loadGames(storage);
        this.adopt(now ?? { history: [], challengeLog: [], passedOut: 0 });
      });
    }
    this.newBoard();
  }

  /** Take saved games as this tab's own. The board in play is untouched. */
  private adopt(saved: { history: HistoryRecord[]; challengeLog: ChallengeLogEntry[]; passedOut: number }): void {
    this.history = saved.history;
    this.challengeLog = saved.challengeLog;
    this.passedOutCount = saved.passedOut;
    this.passedOutSynced = saved.passedOut;
  }

  // ── Saved games ────────────────────────────────────────────────────────────

  /** Remember the finished boards. Called whenever one is added; a failed
   *  save (storage full or blocked) is ignored, so play never stops for it. */
  private persist(): void {
    if (!this.storage) return;
    // Merge with what's stored first: another tab may have saved boards
    // since this one last looked, and writing our copy alone would drop them.
    const merged = mergeGames(loadGames(this.storage), {
      version: 1,
      boardNum: this.boardNum,
      history: $state.snapshot(this.history) as HistoryRecord[],
      challengeLog: $state.snapshot(this.challengeLog) as ChallengeLogEntry[],
      passedOut: this.passedOutCount,
    }, this.passedOutCount - this.passedOutSynced);
    this.adopt(merged);
    if (saveGames(this.storage, merged)) askPersistence();
  }

  /** Boards loaded from LIN join the history (outside the session score, as
   *  `imported`) and are saved with it. */
  importBoards(boards: HistoryRecord[]): void {
    this.history.push(...boards);
    this.persist();
  }

  /** Forget every saved board on this device. The board in play carries on. */
  clearSaved(): void {
    this.adopt({ history: [], challengeLog: [], passedOut: 0 });
    clearGames(this.storage);
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
    if (!auction.isComplete) return;
    if (auction.passedOut) {
      this.passedOutCount += 1;
      // A challenge board is graded even so: passing out scores 0 against
      // whatever the robots made of the same cards.
      this.gradeChallenge();
      this.persist();
      return;
    }
    const contract = auction.getContract()!;
    this.contract = contract;
    this.order = clockwiseFrom(contract.leader);
    this.phase = 'auction_done';
  }

  /** `alert` is the player's own explanation of the call, as a self-alert on
   *  BBO. The robots don't read it; it goes into the record and the LIN. */
  humanBids(call: string, alert = ''): void {
    const auction = this.auction;
    if (auction.isComplete || auction.currentPlayer() !== HUMAN) return;
    if (!auction.legalCalls().includes(call)) return;
    const why = cleanAlert(alert);
    if (why) this.alerts[this.calls.length] = why;
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

  /** The human's only legal card, when auto-play is on; otherwise null. */
  private forcedCard(player: Seat): Card | null {
    if (!this.autoPlayForced) return null;
    const led = this.trick.length ? this.trick[0][1].suit : null;
    const legal = legalPlays(this.hands[player], led);
    return legal.length === 1 ? legal[0] : null;
  }

  /** Pick up auto-play after the setting is switched on mid-trick. */
  resumeAutoPlay(): void {
    if (this.phase === 'playing' && this.whoseTurn() !== null) this.advancePlay();
  }

  private advancePlay(): void {
    const contract = this.contract!;
    const done = new Set(this.trick.map(([p]) => p));
    for (const player of this.order) {
      if (done.has(player)) continue;
      if (this.isHumanSeat(player)) {
        const forced = this.forcedCard(player);
        if (!forced) return;
        removeCard(this.hands[player], forced);
        this.trick.push([player, forced]);
        done.add(player);
        continue;
      }
      const hands = $state.snapshot(this.hands) as Record<Seat, Card[]>;
      const c = aiPlay(player, hands[player], $state.snapshot(this.trick) as Play[],
        contract.trump, this.played, visibleHands(player, contract, hands),
        ($state.snapshot(this.tricksLog) as TrickLog[]).map((e) => e.plays));
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
    this.persist();
  }

  /** Replay this deal with robots in all four seats and compare. Only South's
   *  side is graded: North is a robot in both runs. */
  private gradeChallenge(): void {
    const dealId = this.challengeId;
    if (dealId === null) return;
    const contract = this.contract;   // null when the board passed out
    const vul = this.vulnerability;
    const mine = challenge.grade(dealId, 'N/S', contract,
      contract ? this.tricksTaken[contract.side] : 0, vul);
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
      your_record: contract ? undefined : {
        board_num: this.boardNum,
        dealer: this.dealer,
        vulnerability: vul,
        initial_hands: this.initialHands,
        auction_calls: $state.snapshot(this.calls) as CallRecord[],
        bid_alerts: { ...this.alerts },
        contract: null,
        passed_out: true,
        tricks_log: [],
        tricks_taken: { 'N/S': 0, 'E/W': 0 },
        result: null,
      },
      margin: mine.actual - theirs.actual,
    };
    this.challengeLog.push({
      deal_id: dealId,
      board_num: this.boardNum,
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
