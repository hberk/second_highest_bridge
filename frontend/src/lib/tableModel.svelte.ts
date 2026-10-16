// What the table shows, worked out once from the game for both layouts:
// whose turn it is, which hands are face up, how each seat is labelled, and
// the last-trick peek. The phone and desktop views only draw it differently.
import type { Seat, Vulnerability } from './engine/card';
import { legalPlays } from './engine/auction';
import { evalHandSh, hcp } from './engine/ai';
import type { Game } from './game.svelte';
import { settings } from './settings.svelte';

export const SEATS: Seat[] = ['North', 'East', 'South', 'West'];

/** Vulnerability from your side of the table. */
export const VUL_TEXT: Record<Vulnerability, string> = {
  None: 'nobody vulnerable', Both: 'both vulnerable', 'N/S': "you're vulnerable", 'E/W': "they're vulnerable",
};

/** How long a finished trick stays on the felt with fast play on. */
const FAST_PLAY_MS = 1200;

export class TableModel {
  readonly #game: () => Game;
  /** `game` is read through a function so a component's prop stays live. */
  constructor(game: () => Game) {
    this.#game = game;
  }
  get game(): Game {
    return this.#game();
  }

  auction = $derived(this.game.auction);
  contract = $derived(this.game.contract);
  bidding = $derived(this.game.phase === 'bidding' || this.game.phase === 'auction_done');
  /** The trick on the felt: once it's over, still the one just finished. */
  displayNum = $derived(this.game.phase === 'trick_done' ? this.game.trickNum - 1 : this.game.trickNum);
  who = $derived(this.game.whoseTurn());
  led = $derived(this.game.trick.length ? this.game.trick[0][1].suit : null);
  // Hands keep the fixed S-H-D-C order unless the player asked for trump first.
  displayTrump = $derived(settings.trumpFirst ? this.game.trump : null);
  counts = $derived(Object.fromEntries(SEATS.map((p) => [p, this.game.hands[p].length])) as Record<Seat, number>);
  usVul = $derived(this.game.vulnerability === 'N/S' || this.game.vulnerability === 'Both');

  /** The dummy goes down once the opening lead is made: the leader leads blind. */
  // Reactive fields only: `game.played` is a plain array, so a derived that
  // read it would stay true into the next board and expose dummy before the lead.
  dummyDown = $derived(this.game.trickNum > 1 || this.game.trick.length > 0);
  /** The hand shown face up above the felt: the dummy once it's down, unless
   *  the dummy is you (your hand is always at the bottom). */
  topSeat = $derived(this.contract && this.dummyDown && this.contract.dummy !== 'South' ? this.contract.dummy : null);
  /** X-ray: every other hand not already on the table. */
  xray = $derived(settings.showAll
    ? (['West', 'North', 'East'] as Seat[]).filter((p) => p !== this.topSeat && this.game.hands[p].length)
    : []);

  labels = $derived(Object.fromEntries(SEATS.map((p) => [p, this.seatLabel(p)])) as Record<Seat, string>);

  /** Legal cards for a seat the player is about to play from; none otherwise. */
  legalFor(p: Seat) {
    return this.who === p ? legalPlays(this.game.hands[p], this.led) : [];
  }

  private seatLabel(p: Seat): string {
    const c = this.contract;
    if (p === 'South') return c?.dummy === 'South' ? 'You · dummy' : 'You';
    if (c?.dummy === p) return `${p} · dummy`;
    if (c?.declarer === p) return `${p} · declarer`;
    return p === 'North' ? 'North · partner' : p;
  }

  /** "you" for South, else the seat. */
  by(p: Seat): string {
    return p === 'South' ? 'you' : p;
  }

  /** Your hand's strength while you bid: HCP, this variant's own valuation
   *  (one decimal) and shape. Null once a card has been played. */
  strength = $derived.by(() => {
    const h = this.game.hands.South;
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
export function useFastPlay(getGame: () => Game): void {
  $effect(() => {
    const game = getGame();
    if (game.phase !== 'trick_done' || !settings.fastPlay) return;
    const timer = setTimeout(() => game.nextTrick(), FAST_PLAY_MS);
    return () => clearTimeout(timer);
  });
}
