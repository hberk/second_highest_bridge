// Port of bridge/auction.py, bridge/trick.py and the rotations in game.py.
import {
  LEVELS, STRAINS, SUITS, bidIndex, parseBid, value,
  type Card, type Seat, type Side, type Strain, type Suit, type Vulnerability,
} from './card';

export const PLAYERS: readonly Seat[] = ['North', 'East', 'South', 'West'];
export const PARTNERS: Record<Seat, Seat> = {
  North: 'South', South: 'North', East: 'West', West: 'East',
};
export const PARTNERSHIP: Record<Seat, Side> = {
  North: 'N/S', South: 'N/S', East: 'E/W', West: 'E/W',
};

export const DEALER_ROTATION: readonly Seat[] = ['North', 'East', 'South', 'West'];
export const VUL_ROTATION: readonly Vulnerability[] = [
  'None', 'N/S', 'E/W', 'Both',
  'N/S', 'E/W', 'Both', 'None',
  'E/W', 'Both', 'None', 'N/S',
  'Both', 'None', 'N/S', 'E/W',
];

export type Doubled = 'None' | 'X' | 'XX';
export type CallRecord = [Seat, string];

export interface Contract {
  level: number;
  strain: Strain;
  declarer: Seat;
  dummy: Seat;
  leader: Seat;
  tricks_needed: number;
  trump: Suit | 'NT';
  doubled: Doubled;
  vulnerability: Vulnerability;
  side: Side;
}

export function clockwiseFrom(player: Seat): Seat[] {
  const start = PLAYERS.indexOf(player);
  return [0, 1, 2, 3].map((i) => PLAYERS[(start + i) % 4]);
}

export function otherSide(side: Side): Side {
  return side === 'N/S' ? 'E/W' : 'N/S';
}

export class AuctionState {
  calls: CallRecord[] = [];
  highestBid: [number, Strain, Seat] | null = null;
  doubled: Doubled = 'None';
  doubledBy: Seat | null = null;
  isComplete = false;
  passedOut = false;

  constructor(
    readonly dealer: Seat = 'North',
    readonly vulnerability: Vulnerability = 'None',
  ) {}

  currentPlayer(): Seat {
    return PLAYERS[(PLAYERS.indexOf(this.dealer) + this.calls.length) % 4];
  }

  legalCalls(): string[] {
    if (this.isComplete) return [];
    const calls = ['Pass'];
    const side = PARTNERSHIP[this.currentPlayer()];
    if (this.highestBid && this.doubled === 'None' && PARTNERSHIP[this.highestBid[2]] !== side) {
      calls.push('X');
    }
    if (this.highestBid && this.doubled === 'X' && PARTNERSHIP[this.highestBid[2]] === side) {
      calls.push('XX');
    }
    const min = this.highestBid ? bidIndex(this.highestBid[0], this.highestBid[1]) : -1;
    for (const lvl of LEVELS) {
      for (const strain of STRAINS) {
        if (bidIndex(lvl, strain) > min) calls.push(`${lvl}${strain}`);
      }
    }
    return calls;
  }

  applyCall(player: Seat, call: string): void {
    if (this.isComplete) throw new Error('Auction is already complete');
    if (player !== this.currentPlayer()) {
      throw new Error(`Not ${player}'s turn to bid (expected ${this.currentPlayer()})`);
    }
    if (!this.legalCalls().includes(call)) throw new Error(`Illegal call '${call}' for ${player}`);

    this.calls.push([player, call]);
    const n = this.calls.length;
    if (call === 'Pass') {
      if (n === 4 && this.calls.every(([, c]) => c === 'Pass')) {
        this.isComplete = true;
        this.passedOut = true;
      } else if (n >= 4 && this.calls.slice(-3).every(([, c]) => c === 'Pass')) {
        this.isComplete = true;
      }
    } else if (call === 'X' || call === 'XX') {
      this.doubled = call;
      this.doubledBy = player;
    } else {
      const parsed = parseBid(call);
      if (parsed) {
        this.highestBid = [parsed[0], parsed[1], player];
        this.doubled = 'None';
        this.doubledBy = null;
      }
    }
  }

  getContract(): Contract | null {
    if (!this.isComplete || this.passedOut || !this.highestBid) return null;
    const [level, strain, winningBidder] = this.highestBid;
    const side = PARTNERSHIP[winningBidder];
    let declarer: Seat | null = null;
    for (const [p, call] of this.calls) {
      const parsed = parseBid(call);
      if (parsed && parsed[1] === strain && PARTNERSHIP[p] === side) {
        declarer = p;
        break;
      }
    }
    declarer ??= winningBidder;
    return {
      level, strain, declarer,
      dummy: PARTNERS[declarer],
      leader: clockwiseFrom(declarer)[1],
      tricks_needed: 6 + level,
      trump: strain === 'NT' ? 'NT' : strain,
      doubled: this.doubled,
      vulnerability: this.vulnerability,
      side,
    };
  }
}

// ── Trick rules (bridge/trick.py) ────────────────────────────────────────────

export type Play<P extends string = Seat> = [P, Card];

export function legalPlays(hand: Card[], ledSuit: Suit | null): Card[] {
  if (ledSuit === null) return [...hand];
  const inSuit = hand.filter((c) => c.suit === ledSuit);
  return inSuit.length ? inSuit : [...hand];
}

/** The second-highest card of the winning suit takes the trick; a lone card
 *  of that suit wins outright. Trump wins if any was played, else the led suit. */
export function resolveTrick<P extends string>(trick: Play<P>[], trump: string | null): P {
  const led = trick[0][1].suit;
  const isTrump = (SUITS as readonly string[]).includes(trump ?? '');
  const winningSuit = isTrump && trick.some(([, c]) => c.suit === trump) ? trump : led;
  // Array.sort is stable, like Python's sorted(reverse=True).
  const suitPlays = trick
    .filter(([, c]) => c.suit === winningSuit)
    .sort((a, b) => value(b[1]) - value(a[1]));
  return suitPlays[Math.min(1, suitPlays.length - 1)][0];
}
