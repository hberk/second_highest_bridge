// What the table shows, worked out once from the game for both layouts:
// whose turn it is, which hands are face up, how each seat is labelled, and
// the last-trick peek. The phone and desktop views only draw it differently.
//
// It reads a `TableSource`: the solo `Game`, or `RemoteTable` at a
// multiplayer table. Every seat is placed from `mySeat`, so you are always at
// the bottom, partner across, the opponents left and right.
import type { Card, Seat, Side, Vulnerability } from './engine/card';
import { legalPlays, type AuctionState, type CallRecord, type Contract, type Play } from './engine/auction';
import { evalHandSh, hcp } from './engine/ai';
import type { TrickLog } from './engine/challenge';
import type { ScoreResult } from './engine/scoring';
import type { ChallengeLogEntry, ChallengeResult, Phase } from './game.svelte';
import type { HistoryRecord } from './saves';
import { otherSideOf, partnerOf, seatAt, sideOf } from './seats';
import { settings } from './settings.svelte';

export const SEATS: Seat[] = ['North', 'East', 'South', 'West'];

/** A table the views can draw and play at: the solo game or a remote one. */
export interface TableSource {
  readonly mySeat: Seat;
  /** The multiplayer table's id; undefined for solo play. */
  readonly tableId?: string;
  readonly boardNum: number;
  readonly dealer: Seat;
  readonly vulnerability: Vulnerability;
  /** The cards you can see in each hand; a hidden hand is empty. */
  readonly hands: Record<Seat, Card[]>;
  readonly calls: CallRecord[];
  readonly alerts: Record<number, string>;
  readonly liveAlerts: Record<number, string>;
  readonly phase: Phase;
  readonly contract: Contract | null;
  readonly trick: Play[];
  readonly trickNum: number;
  readonly tricksTaken: Record<Side, number>;
  readonly trickWinner: Seat | null;
  readonly tricksLog: TrickLog[];
  readonly result: ScoreResult | null;
  readonly challenge: ChallengeResult | null;
  readonly challengeId: number | null;
  readonly auction: AuctionState;
  readonly trump: string | null;
  readonly gameOver: boolean;
  readonly boardOver: boolean;
  readonly history: HistoryRecord[];
  readonly challengeLog: ChallengeLogEntry[];
  readonly passedOutCount: number;
  whoseTurn(): Seat | null;
  cardCount(p: Seat): number;
  humanBids(call: string, alert?: string): void;
  humanPlays(player: Seat, c: Card): void;
  startPlay(): void;
  nextTrick(): void;
  newBoard(): void;
  /** A person's name in the seat, at a multiplayer table; null for a robot. */
  playerName?(p: Seat): string | null;
}

/** Vulnerability from your side of the table. */
export function vulText(v: Vulnerability, me: Seat): string {
  if (v === 'None') return 'nobody vulnerable';
  if (v === 'Both') return 'both vulnerable';
  return v === sideOf(me) ? "you're vulnerable" : "they're vulnerable";
}

/** Vulnerability as South sees it (solo play). */
export const VUL_TEXT: Record<Vulnerability, string> = {
  None: vulText('None', 'South'), Both: vulText('Both', 'South'),
  'N/S': vulText('N/S', 'South'), 'E/W': vulText('E/W', 'South'),
};

/** How long a finished trick stays on the felt with fast play on. */
const FAST_PLAY_MS = 1200;

export class TableModel {
  readonly #game: () => TableSource;
  /** `game` is read through a function so a component's prop stays live. */
  constructor(game: () => TableSource) {
    this.#game = game;
  }
  get game(): TableSource {
    return this.#game();
  }

  /** You, partner and the opponents, by where they sit. */
  me = $derived(this.game.mySeat);
  partner = $derived(partnerOf(this.me));
  left = $derived(seatAt(this.me, 'left'));
  right = $derived(seatAt(this.me, 'right'));
  mySide = $derived<Side>(sideOf(this.me));
  theirSide = $derived<Side>(otherSideOf(this.me));

  auction = $derived(this.game.auction);
  contract = $derived(this.game.contract);
  bidding = $derived(this.game.phase === 'bidding' || this.game.phase === 'auction_done');
  /** The trick on the felt: once it's over, still the one just finished. */
  displayNum = $derived(this.game.phase === 'trick_done' ? this.game.trickNum - 1 : this.game.trickNum);
  who = $derived(this.game.whoseTurn());
  led = $derived(this.game.trick.length ? this.game.trick[0][1].suit : null);
  // Hands keep the fixed S-H-D-C order unless the player asked for trump first.
  displayTrump = $derived(settings.trumpFirst ? this.game.trump : null);
  counts = $derived(Object.fromEntries(SEATS.map((p) => [p, this.game.cardCount(p)])) as Record<Seat, number>);
  usVul = $derived(this.game.vulnerability === this.mySide || this.game.vulnerability === 'Both');
  /** "you're vulnerable", "they're vulnerable", ... from your side. */
  vul = $derived(vulText(this.game.vulnerability, this.me));

  /** The dummy goes down once the opening lead is made: the leader leads blind. */
  // Reactive fields only: `game.played` is a plain array, so a derived that
  // read it would stay true into the next board and expose dummy before the lead.
  dummyDown = $derived(this.game.trickNum > 1 || this.game.trick.length > 0);
  /** The dummy, face up once the lead is made; null before then, and when
   *  the dummy is you (your hand is always at the bottom). */
  faceDummy = $derived(this.contract && this.dummyDown && this.contract.dummy !== this.me ? this.contract.dummy : null);
  /** Partner as dummy sits above the felt, across from you. */
  topSeat = $derived(this.faceDummy === this.partner ? this.partner : null);
  /** An opponent's dummy sits on its own side of the felt, so the table
   *  reads the way it does in real life. Never yours to play: when you
   *  declare, the dummy is partner. */
  sideDummy = $derived(this.faceDummy === this.left || this.faceDummy === this.right ? this.faceDummy : null);

  labels = $derived(Object.fromEntries(SEATS.map((p) => [p, this.seatLabel(p)])) as Record<Seat, string>);

  /** Legal cards for a seat the player is about to play from; none otherwise. */
  legalFor(p: Seat) {
    return this.who === p ? legalPlays(this.game.hands[p], this.led) : [];
  }

  /** The seat as players call it: a person's name at a multiplayer table,
   *  else the compass point. */
  name(p: Seat): string {
    return this.game.playerName?.(p) ?? p;
  }

  private seatLabel(p: Seat): string {
    const c = this.contract;
    if (p === this.me) return c?.dummy === p ? 'You · dummy' : 'You';
    if (c?.dummy === p) return `${this.name(p)} · dummy`;
    if (c?.declarer === p) return `${this.name(p)} · declarer`;
    return p === this.partner ? `${this.name(p)} · partner` : this.name(p);
  }

  /** "West deals", or at a multiplayer table "Sam deals" and "You deal".
   *  (Solo play keeps the compass point: "South deals".) */
  get dealsText(): string {
    const d = this.game.dealer;
    return this.game.playerName && d === this.me ? 'You deal' : `${this.name(d)} deals`;
  }

  /** "you" for your own seat, else the seat. */
  by(p: Seat): string {
    return p === this.me ? 'you' : this.name(p);
  }

  /** Your hand's strength while you bid: HCP, this variant's own valuation
   *  (one decimal) and shape. Null once a card has been played. */
  strength = $derived.by(() => {
    const h = this.game.hands[this.me];
    if (h.length !== 13) return null;
    const ev = evalHandSh(h);
    return { hcp: hcp(h), value: ev.total_pts.toFixed(1), shape: ev.lengths.join('-') };
  });

  // ── Last trick ─────────────────────────────────────────────────────────────
  // A peek belongs to the moment it was asked for: as soon as a card is played
  // or the trick moves on, the key changes and the felt shows the live trick
  // again, with no effect needed to reset it.
  lastTrick = $derived(this.game.phase === 'playing' ? this.game.tricksLog.at(-1) ?? null : null);
  private momentKey = $derived(`${this.game.boardNum}:${this.game.trickNum}:${this.game.trick.length}`);
  private peekKey = $state<string | null>(null);
  peeking = $derived(this.lastTrick !== null && this.peekKey === this.momentKey);

  togglePeek(): void {
    this.peekKey = this.peeking ? null : this.momentKey;
  }
}

/** Fast play: move on to the next trick by itself. Call while a component
 *  is being set up; the timer stops with the component. */
export function useFastPlay(getGame: () => TableSource): void {
  $effect(() => {
    const game = getGame();
    if (game.phase !== 'trick_done' || !settings.fastPlay) return;
    const timer = setTimeout(() => game.nextTrick(), FAST_PLAY_MS);
    return () => clearTimeout(timer);
  });
}
