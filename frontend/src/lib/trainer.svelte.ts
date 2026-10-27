// Bidding training: you bid South with a robot partner and robot opponents,
// and the board ends with the auction. There is no card play. The contract is
// scored double dummy by lookup and compared with par, so the recap shows the
// moment the auction ends (docs/FRONTEND.md, "Bidding training").
//
// The deals are their own (`data/training_deals.json`, from
// research/solve_training_deals.py), never the challenge library's: a hand
// met in training would be a hand already seen in Challenge (the user's call,
// 2026-10-27). Like the library, every deal is solved in all five strains for
// all four declarers, so any contract the auction reaches has an exact count.
import training from '$root/data/training_deals.json';
import { STRAINS, parseHand, type Card, type Seat, type Strain, type Suit, type Vulnerability } from './engine/card';
import { AuctionState, DEALER_ROTATION, PLAYERS, VUL_ROTATION, type CallRecord, type Contract } from './engine/auction';
import { aiBidExplained } from './engine/ai';
import { Hand } from './engine/gib';
import { scoreFor, type Par } from './engine/challenge';
import { callMeanings } from './meanings';
import { browserStorage } from './saves';

interface TrainingDeal {
  id: number;
  hands: Record<Seat, string>;
  /** "<strain>:<declarer>" -> tricks the declaring side takes, double dummy. */
  tricks: Record<string, number>;
}

const DEALS = new Map<number, TrainingDeal>(
  (training.deals as TrainingDeal[]).map((d) => [d.id, d]),
);

const HUMAN: Seat = 'South';
export const TRAINING_KEY = 'shb-training-v1';
/** A board is abandoned if the auction will not terminate (as challenge.ts). */
const AUCTION_GUARD = 60;

export function trainingDealIds(): number[] {
  return [...DEALS.keys()].sort((a, b) => a - b);
}

function handsOf(dealId: number): Record<Seat, Card[]> {
  const raw = DEALS.get(dealId)!.hands;
  return Object.fromEntries(PLAYERS.map((s) => [s, parseHand(raw[s])])) as Record<Seat, Card[]>;
}

/** N/S's tricks in `strain` with `declarer`, or the better partner's. */
export function nsTricks(dealId: number, strain: Strain, declarer?: Seat): number {
  const t = DEALS.get(dealId)!.tricks;
  const seats: Seat[] = declarer ? [declarer] : ['North', 'South'];
  // E/W declaring: N/S take what E/W don't.
  return Math.max(...seats.map((s) => (s === 'East' || s === 'West' ? 13 - t[`${strain}:${s}`] : t[`${strain}:${s}`])));
}

/** N/S's best contract, double dummy: challenge.ts's `par`, on these deals. */
export function trainingPar(dealId: number, vulnerability: Vulnerability): Par {
  let best: Par | null = null;
  for (const strain of STRAINS) {
    const taken = nsTricks(dealId, strain);
    for (let level = 1; level < 8; level++) {
      if (level + 6 > taken) break;
      const points = scoreFor('N/S', {
        level, strain, side: 'N/S', tricks_needed: level + 6, doubled: 'None', vulnerability,
      }, taken);
      if (best === null || points > best.score) best = { score: points, level, strain, tricks: taken };
    }
  }
  return best ?? { score: 0, level: 0, strain: null, tricks: 0 };
}

/** The double dummy score from N/S of a contract on a training deal. */
export function contractScore(dealId: number, contract: Contract | null): { tricks: number; score: number } {
  if (!contract) return { tricks: 0, score: 0 };
  const t = DEALS.get(dealId)!.tricks[`${contract.strain}:${contract.declarer}`];
  return { tricks: t, score: scoreFor('N/S', contract, t) };
}

/** One of your calls, looked at after the auction. */
export interface CallCheck {
  index: number;
  call: string;
  /** What the robots take the call to mean here (their alert), if anything. */
  meaning: string | null;
  /** What a robot would have called with your hand. */
  robot: string;
  /** What your hand holds where it falls outside the meaning. */
  misfits: string[];
}

export interface Recap {
  dealId: number;
  contract: Contract | null;
  tricks: number;
  score: number;
  par: Par;
  /** score - par: zero at best, negative when the auction gave points away. */
  diff: number;
  robotContract: Contract | null;
  robotScore: number;
  checks: CallCheck[];
  /** N/S tricks double dummy per strain, the better declarer. */
  dd: Record<Strain, number>;
  judge: { you: number; partner: number };
  hcp: { you: number; partner: number };
  /** The longest suit N/S hold together, and its length. */
  fit: { suit: Suit; length: number };
}

export interface TrainingLogEntry {
  deal_id: number;
  board_num: number;
  score: number;
  par: number;
  diff: number;
}

interface SavedTraining {
  version: 1;
  boardNum: number;
  log: TrainingLogEntry[];
}

const SYM: Record<string, string> = { S: '♠', H: '♥', D: '♦', C: '♣' };

/** Where `hand` falls outside an alert's HCP range or suit lengths, as what
 *  the hand holds instead ("16 HCP", "4 ♠"). */
export function misfits(alert: string, hand: Card[]): string[] {
  const h = new Hand(hand);
  const out: string[] = [];
  const range = /(\d+)-(\d+) HCP/.exec(alert);
  const floor = /(\d+)\+ HCP/.exec(alert);
  if (range && (h.hcp < +range[1] || h.hcp > +range[2])) out.push(`${h.hcp} HCP`);
  else if (floor && h.hcp < +floor[1]) out.push(`${h.hcp} HCP`);
  for (const m of alert.matchAll(/(\d+)\+ ([♠♥♦♣])/g)) {
    const suit = (Object.keys(SYM) as Suit[]).find((s) => SYM[s] === m[2])!;
    if (h.len[suit] < +m[1]) out.push(`${h.len[suit]} ${m[2]}`);
  }
  return out;
}

export class Trainer {
  boardNum = $state(0);
  dealId = $state(0);
  dealer = $state<Seat>('North');
  vulnerability = $state<Vulnerability>('None');
  hands = $state.raw<Record<Seat, Card[]>>({ North: [], East: [], South: [], West: [] });
  calls = $state<CallRecord[]>([]);
  alerts = $state<Record<number, string>>({});
  recap = $state.raw<Recap | null>(null);
  log = $state<TrainingLogEntry[]>([]);

  auction = $derived.by(() => {
    const a = new AuctionState(this.dealer, this.vulnerability);
    for (const [p, c] of this.calls) a.applyCall(p, c);
    return a;
  });

  /** Robot passes say why they passed, which reads their cards out; hidden
   *  until the auction is over, as at the table. */
  liveAlerts = $derived.by(() => {
    if (this.recap) return this.alerts;
    const out: Record<number, string> = {};
    for (const [i, why] of Object.entries(this.alerts)) {
      const call = this.calls[Number(i)];
      if (call && (call[1] !== 'Pass' || call[0] === HUMAN)) out[Number(i)] = why;
    }
    return out;
  });

  /** Average against par per board, over the boards trained so far. */
  get average(): number | null {
    return this.log.length ? Math.round(this.log.reduce((n, e) => n + e.diff, 0) / this.log.length) : null;
  }

  constructor(private storage: Storage | null = browserStorage(),
              private random: () => number = Math.random) {
    const saved = this.load();
    if (saved) {
      this.boardNum = saved.boardNum;
      this.log = saved.log;
    }
    this.newBoard();
  }

  private load(): SavedTraining | null {
    try {
      const raw = this.storage?.getItem(TRAINING_KEY);
      const v = raw ? JSON.parse(raw) : null;
      return v && v.version === 1 && Array.isArray(v.log) && typeof v.boardNum === 'number' ? v : null;
    } catch {
      return null;
    }
  }

  private save(): void {
    try {
      this.storage?.setItem(TRAINING_KEY, JSON.stringify({
        version: 1, boardNum: this.boardNum, log: $state.snapshot(this.log),
      } satisfies SavedTraining));
    } catch { /* storage full or blocked: training carries on */ }
  }

  /** The next deal not trained yet (all of them once used up, over again),
   *  dealer and vulnerability rotating with the board number. */
  newBoard(dealId: number | null = null): void {
    const done = new Set(this.log.map((e) => e.deal_id));
    const ids = trainingDealIds();
    const fresh = ids.filter((i) => !done.has(i));
    const pool = fresh.length ? fresh : ids;
    const n = this.boardNum + 1;
    this.boardNum = n;
    this.dealId = dealId ?? pool[Math.floor(this.random() * pool.length)];
    this.dealer = DEALER_ROTATION[(n - 1) % 4];
    this.vulnerability = VUL_ROTATION[(n - 1) % 16];
    this.hands = handsOf(this.dealId);
    this.calls = [];
    this.alerts = {};
    this.recap = null;
    this.advance();
  }

  humanBids(call: string, alert = ''): void {
    const auction = this.auction;
    if (auction.isComplete || auction.currentPlayer() !== HUMAN) return;
    if (!auction.legalCalls().includes(call)) return;
    if (alert.trim()) this.alerts[this.calls.length] = alert.trim();
    this.calls.push([HUMAN, call]);
    this.advance();
  }

  /** The robots' alerts by call, the human's left out (as Game.robotAlerts). */
  private robotAlerts(upTo = this.calls.length): Record<number, string> {
    const out: Record<number, string> = {};
    for (const [i, why] of Object.entries(this.alerts)) {
      const call = this.calls[Number(i)];
      if (Number(i) < upTo && call && call[0] !== HUMAN) out[Number(i)] = why;
    }
    return out;
  }

  private advance(): void {
    const auction = new AuctionState(this.dealer, this.vulnerability);
    for (const [p, c] of this.calls) auction.applyCall(p, c);
    while (!auction.isComplete && auction.currentPlayer() !== HUMAN && auction.calls.length < AUCTION_GUARD) {
      const who = auction.currentPlayer();
      const [call, why] = aiBidExplained(who, this.hands[who], auction, this.robotAlerts());
      this.alerts[auction.calls.length] = why;
      auction.applyCall(who, call);
      this.calls.push([who, call]);
    }
    if (auction.isComplete) this.finish(auction);
  }

  private finish(auction: AuctionState): void {
    const id = this.dealId;
    const contract = auction.getContract();
    const mine = contractScore(id, contract);
    const par = trainingPar(id, this.vulnerability);

    // The robots in all four seats, the same board.
    const robots = new AuctionState(this.dealer, this.vulnerability);
    const robotAlerts: Record<number, string> = {};
    while (!robots.isComplete && robots.calls.length < AUCTION_GUARD) {
      const who = robots.currentPlayer();
      const [call, why] = aiBidExplained(who, this.hands[who], robots, robotAlerts);
      robotAlerts[robots.calls.length] = why;
      robots.applyCall(who, call);
    }
    const robotContract = robots.getContract();

    const checks: CallCheck[] = [];
    this.calls.forEach(([who, call], i) => {
      if (who !== HUMAN) return;
      const prefix = new AuctionState(this.dealer, this.vulnerability);
      for (const [p, c] of this.calls.slice(0, i)) prefix.applyCall(p, c);
      const [robot] = aiBidExplained(HUMAN, this.hands.South, prefix, this.robotAlerts(i));
      const meaning = call === 'Pass' ? null : callMeanings(prefix).get(call) ?? null;
      checks.push({ index: i, call, meaning, robot, misfits: meaning ? misfits(meaning, this.hands.South) : [] });
    });

    const you = new Hand(this.hands.South);
    const partner = new Hand(this.hands.North);
    const fitSuit = (['S', 'H', 'D', 'C'] as Suit[]).reduce((a, s) =>
      (you.len[s] + partner.len[s] > you.len[a] + partner.len[a] ? s : a));
    this.recap = {
      dealId: id,
      contract,
      tricks: mine.tricks,
      score: mine.score,
      par,
      diff: mine.score - par.score,
      robotContract,
      robotScore: contractScore(id, robotContract).score,
      checks,
      dd: Object.fromEntries(STRAINS.map((s) => [s, nsTricks(id, s)])) as Record<Strain, number>,
      judge: { you: you.judge, partner: partner.judge },
      hcp: { you: you.hcp, partner: partner.hcp },
      fit: { suit: fitSuit, length: you.len[fitSuit] + partner.len[fitSuit] },
    };
    this.log.push({ deal_id: id, board_num: this.boardNum, score: mine.score, par: par.score, diff: mine.score - par.score });
    this.save();
  }
}
