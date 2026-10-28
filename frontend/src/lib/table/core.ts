// The multiplayer table, as pure data and functions: who sits where, the
// board's deal and every call and card made on it, what each seat may see,
// and what the robots do in the empty seats. The table server wraps it
// (sockets, storage, timers); the tests drive it directly. Nothing here knows
// about WebSockets, Svelte or Node.
//
// A board is its deal plus the list of actions made on it; everything else
// (the auction, the hands left, the tricks, the score) is derived by
// replaying them, so there is one source of truth, and a server restart
// rebuilds a board from what it stored.
import { deal, removeCard, sameCard, type Card, type Seat, type Side, type Vulnerability } from '../engine/card';
import {
  AuctionState, DEALER_ROTATION, PARTNERSHIP, PLAYERS, VUL_ROTATION, cleanAlert, clockwiseFrom, legalPlays,
  resolveTrick, type CallRecord, type Contract, type Play,
} from '../engine/auction';
import { aiBidExplained, aiPlay, visibleHands } from '../engine/ai';
import { scoreContract, type ScoreResult } from '../engine/scoring';
import type { TrickLog } from '../engine/challenge';
import type { HistoryRecord } from '../saves';
import { robotAlerts, robotShown, type Readings } from '../alerts';
import { cleanName, type BoardView, type ClientMessage, type ErrorCode, type SeatView, type TableView } from './protocol';

/** A robot acts this long after the last action, so the table plays at the
 *  pace of a real one. */
export const ROBOT_DELAY_MS = 600;
/** A player gone this long can have a robot take their seat, and loses the
 *  host role to someone still here. */
export const TAKEOVER_MS = 60_000;
/** People at one table, seated or watching. */
export const MAX_PLAYERS = 8;

export interface Player {
  id: string;
  /** SHA-256 of the player's token, hex. The token itself is never kept. */
  tokenHash: string;
  name: string;
  seat: Seat | null;
  joinedAt: number;
}

/** One call or card. `human` says whether a person chose it: a person's
 *  alert is free text the robots don't read. */
export interface Action {
  seat: Seat;
  human: boolean;
  call?: string;
  card?: Card;
  alert?: string;
}

export interface Board {
  num: number;
  dealer: Seat;
  vulnerability: Vulnerability;
  hands: Record<Seat, Card[]>;
  actions: Action[];
}

export interface TableState {
  id: string;
  createdAt: number;
  hostId: string | null;
  locked: boolean;
  players: Player[];
  /** Seats whose player is away, played by a robot until they take it back. */
  robotSeats: Seat[];
  boardNum: number;
  board: Board | null;
  /** Players who have asked for the next board. */
  ready: string[];
  version: number;
}

/** What the server knows that the state doesn't: who is connected, since
 *  when someone has been gone, the time, and the dealing shuffle. */
export interface Context {
  now: number;
  connected(playerId: string): boolean;
  /** When the player's last socket closed; null while connected. */
  awaySince(playerId: string): number | null;
  random: () => number;
}

export type Outcome = { ok: true } | { ok: false; code: ErrorCode; message: string };
const ok: Outcome = { ok: true };
const refuse = (code: ErrorCode, message: string): Outcome => ({ ok: false, code, message });

export function newTable(id: string, now: number): TableState {
  return {
    id, createdAt: now, hostId: null, locked: false, players: [], robotSeats: [], boardNum: 0,
    board: null, ready: [], version: 0,
  };
}

// ── Deriving a board ─────────────────────────────────────────────────────────

export interface Derived {
  calls: CallRecord[];
  alerts: Record<number, string>;
  /** By call: made by a person. */
  humanCall: boolean[];
  auction: AuctionState;
  contract: Contract | null;
  passedOut: boolean;
  /** The cards left in each hand. */
  hands: Record<Seat, Card[]>;
  trick: Play[];
  tricksLog: TrickLog[];
  /** Every card of the completed tricks, as `aiPlay` takes it. */
  played: Card[];
  tricksTaken: Record<Side, number>;
  phase: 'bidding' | 'playing' | 'done';
  result: ScoreResult | null;
  /** The seat whose call or card comes next. */
  toAct: Seat | null;
}

const copyHands = (h: Record<Seat, Card[]>) =>
  Object.fromEntries(PLAYERS.map((p) => [p, [...h[p]]])) as Record<Seat, Card[]>;

export function derive(board: Board): Derived {
  const auction = new AuctionState(board.dealer, board.vulnerability);
  const calls: CallRecord[] = [];
  const alerts: Record<number, string> = {};
  const humanCall: boolean[] = [];
  const hands = copyHands(board.hands);
  let trick: Play[] = [];
  const tricksLog: TrickLog[] = [];
  const played: Card[] = [];
  const tricksTaken: Record<Side, number> = { 'N/S': 0, 'E/W': 0 };
  let contract: Contract | null = null;
  for (const a of board.actions) {
    if (a.call !== undefined) {
      if (a.alert !== undefined) alerts[calls.length] = a.alert;
      humanCall.push(a.human);
      auction.applyCall(a.seat, a.call);
      calls.push([a.seat, a.call]);
      if (auction.isComplete && !auction.passedOut) contract = auction.getContract();
    } else if (a.card) {
      removeCard(hands[a.seat], a.card);
      trick.push([a.seat, a.card]);
      if (trick.length === 4) {
        const winner = resolveTrick(trick, contract!.trump);
        tricksTaken[PARTNERSHIP[winner]] += 1;
        tricksLog.push({
          trick_num: tricksLog.length + 1, leader: trick[0][0], plays: trick, winner,
          winning_card: trick.find(([p]) => p === winner)![1],
        });
        played.push(...trick.map(([, c]) => c));
        trick = [];
      }
    }
  }
  const passedOut = auction.passedOut;
  const phase = !auction.isComplete ? 'bidding' : passedOut || tricksLog.length === 13 ? 'done' : 'playing';
  let toAct: Seat | null = null;
  if (phase === 'bidding') toAct = auction.currentPlayer();
  else if (phase === 'playing') {
    toAct = trick.length ? clockwiseFrom(trick[0][0])[trick.length]
      : tricksLog.length ? tricksLog.at(-1)!.winner : contract!.leader;
  }
  return {
    calls, alerts, humanCall, auction, contract, passedOut, hands, trick, tricksLog, played, tricksTaken, phase,
    result: phase === 'done' && contract ? scoreContract(contract, { ...tricksTaken }) : null,
    toAct,
  };
}

/** The seat that chooses a card for `seat`: the declarer plays the dummy. */
export function actorOf(d: Derived, seat: Seat): Seat {
  return d.phase === 'playing' && d.contract?.dummy === seat ? d.contract.declarer : seat;
}

// ── Seats ────────────────────────────────────────────────────────────────────

export const playerById = (s: TableState, id: string | null): Player | undefined =>
  id === null ? undefined : s.players.find((p) => p.id === id);
export const playerInSeat = (s: TableState, seat: Seat): Player | undefined =>
  s.players.find((p) => p.seat === seat);

/** The person who plays the seat now; null when a robot does. */
export function ownerOf(s: TableState, seat: Seat): Player | null {
  if (s.robotSeats.includes(seat)) return null;
  return playerInSeat(s, seat) ?? null;
}

function isAway(p: Player, ctx: Context): boolean {
  const since = ctx.awaySince(p.id);
  return !ctx.connected(p.id) && since !== null && ctx.now - since >= TAKEOVER_MS;
}

export function addPlayer(s: TableState, id: string, tokenHash: string, rawName: string, now: number): Outcome {
  if (s.locked) return refuse('locked', 'The table is locked: the host has closed it to new players.');
  if (s.players.length >= MAX_PLAYERS) return refuse('full', 'The table is full.');
  const name = cleanName(rawName);
  if (!name) return refuse('bad_message', 'Choose a name to show at the table.');
  s.players.push({ id, tokenHash, name, seat: null, joinedAt: now });
  if (s.hostId === null) s.hostId = id;
  s.version++;
  return ok;
}

/** Pass the host role on when the host has gone: to the longest-seated
 *  player still here. Returns whether anything changed. */
export function maintain(s: TableState, ctx: Context): boolean {
  const host = playerById(s, s.hostId);
  if (host && !isAway(host, ctx)) return false;
  const here = s.players.filter((p) => ctx.connected(p.id))
    .sort((a, b) => Number(a.seat === null) - Number(b.seat === null) || a.joinedAt - b.joinedAt);
  const next = here[0]?.id ?? (host ? s.hostId : null);
  if (next === s.hostId) return false;
  s.hostId = next;
  s.version++;
  return true;
}

// ── Dealing ──────────────────────────────────────────────────────────────────

function dealBoard(s: TableState, random: () => number): void {
  const n = s.boardNum + 1;
  s.boardNum = n;
  s.board = {
    num: n, dealer: DEALER_ROTATION[(n - 1) % 4], vulnerability: VUL_ROTATION[(n - 1) % 16],
    hands: deal(random), actions: [],
  };
  s.ready = [];
}

const seated = (s: TableState) => s.players.filter((p) => p.seat !== null);

// ── Intents ──────────────────────────────────────────────────────────────────

/** A person's request. Refused intents change nothing. `join` and `hello`
 *  are the server's business (tokens), not the table's. */
export function applyIntent(s: TableState, playerId: string, m: ClientMessage, ctx: Context): Outcome {
  const me = playerById(s, playerId);
  if (!me) return refuse('not_joined', 'Join the table first.');
  const out = intent(s, me, m, ctx);
  if (out.ok) s.version++;
  return out;
}

function intent(s: TableState, me: Player, m: ClientMessage, ctx: Context): Outcome {
  const isHost = s.hostId === me.id;
  switch (m.type) {
    case 'sit': {
      if (playerInSeat(s, m.seat)) return refuse('seat_taken', `${m.seat} is taken.`);
      if (me.seat) s.robotSeats = s.robotSeats.filter((x) => x !== me.seat);
      me.seat = m.seat;
      s.robotSeats = s.robotSeats.filter((x) => x !== m.seat);
      return ok;
    }
    case 'stand': {
      if (!me.seat) return refuse('not_now', "You aren't sitting at the table.");
      s.robotSeats = s.robotSeats.filter((x) => x !== me.seat);
      me.seat = null;
      s.ready = s.ready.filter((id) => id !== me.id);
      return ok;
    }
    case 'deal': {
      const d = s.board ? derive(s.board) : null;
      if (d && d.phase !== 'done') return refuse('not_now', 'The board is still being played.');
      if (!me.seat) return refuse('not_now', 'Take a seat first.');
      if (!s.ready.includes(me.id)) s.ready.push(me.id);
      const waiting = seated(s).filter((p) => ctx.connected(p.id) && !s.ready.includes(p.id));
      if (isHost || !waiting.length) dealBoard(s, ctx.random);
      return ok;
    }
    case 'call': {
      const b = s.board;
      const d = b ? derive(b) : null;
      if (!b || !d || d.phase !== 'bidding') return refuse('not_now', 'The auction is over.');
      if (!me.seat || d.toAct !== me.seat || ownerOf(s, me.seat)?.id !== me.id) {
        return refuse('not_your_turn', "It isn't your call.");
      }
      if (m.at !== b.actions.length) return refuse('stale', 'The table moved on; try again.');
      if (!d.auction.legalCalls().includes(m.call)) return refuse('illegal', `${m.call} isn't a legal call here.`);
      const why = cleanAlert(m.alert ?? '');
      b.actions.push({ seat: me.seat, human: true, call: m.call, ...(why ? { alert: why } : {}) });
      return ok;
    }
    case 'card': {
      const b = s.board;
      const d = b ? derive(b) : null;
      if (!b || !d || d.phase !== 'playing') return refuse('not_now', 'No card is being played now.');
      if (!me.seat || d.toAct !== m.seat || actorOf(d, m.seat) !== me.seat || ownerOf(s, me.seat)?.id !== me.id) {
        return refuse('not_your_turn', "It isn't your turn to play from that hand.");
      }
      if (m.at !== b.actions.length) return refuse('stale', 'The table moved on; try again.');
      const led = d.trick.length ? d.trick[0][1].suit : null;
      if (!legalPlays(d.hands[m.seat], led).some((c) => sameCard(c, m.card))) {
        return refuse('illegal', "That card can't be played now.");
      }
      b.actions.push({ seat: m.seat, human: true, card: { suit: m.card.suit, rank: m.card.rank } });
      return ok;
    }
    case 'robot': {
      const p = playerInSeat(s, m.seat);
      if (!me.seat) return refuse('not_now', 'Take a seat first.');
      if (!p || p.id === me.id || s.robotSeats.includes(m.seat)) return refuse('not_now', 'Nobody to replace there.');
      if (!isAway(p, ctx)) return refuse('not_now', `${p.name} hasn't been gone long enough.`);
      s.robotSeats.push(m.seat);
      return ok;
    }
    case 'reclaim': {
      if (!me.seat || !s.robotSeats.includes(me.seat)) return refuse('not_now', 'Your seat is already yours.');
      s.robotSeats = s.robotSeats.filter((x) => x !== me.seat);
      return ok;
    }
    case 'lock': {
      if (!isHost) return refuse('not_host', 'Only the host can lock the table.');
      s.locked = m.locked;
      return ok;
    }
    case 'remove': {
      if (!isHost) return refuse('not_host', 'Only the host can remove a player.');
      const p = playerById(s, m.player);
      if (!p || p.id === me.id) return refuse('not_now', 'No such player.');
      if (p.seat) s.robotSeats = s.robotSeats.filter((x) => x !== p.seat);
      s.players = s.players.filter((x) => x.id !== p.id);
      s.ready = s.ready.filter((id) => id !== p.id);
      return ok;
    }
    default:
      return refuse('bad_message', 'Not a table action.');
  }
}

// ── Robots ───────────────────────────────────────────────────────────────────

/** A robot is to act next: the board is live and nobody plays that hand. */
export function robotTurn(s: TableState): boolean {
  if (!s.board) return false;
  const d = derive(s.board);
  return d.toAct !== null && !ownerOf(s, actorOf(d, d.toAct));
}

/** The robot's call or card, when a robot is to act; null when a person is
 *  (or the board is over). The robots get exactly what they get at a solo
 *  table, so they bid and play the same (`core.test.ts` checks it). */
export function robotAction(s: TableState, readings: Readings): Action | null {
  const b = s.board;
  if (!b) return null;
  const d = derive(b);
  if (!d.toAct || ownerOf(s, actorOf(d, d.toAct))) return null;
  const isHuman = (i: number) => d.humanCall[i];
  if (d.phase === 'bidding') {
    const who = d.toAct;
    const [call, why] = aiBidExplained(who, d.hands[who], d.auction, robotAlerts(d.calls, d.alerts, isHuman));
    return { seat: who, human: false, call, alert: why };
  }
  const seat = d.toAct;
  const contract = d.contract!;
  const card = aiPlay(seat, d.hands[seat], d.trick, contract.trump, d.played,
    visibleHands(seat, contract, d.hands), d.tricksLog.map((e) => e.plays),
    robotShown(b.dealer, b.vulnerability, d.calls, d.alerts, isHuman, readings));
  return { seat, human: false, card };
}

export function applyRobot(s: TableState, a: Action): void {
  s.board!.actions.push(a);
  s.version++;
}

// ── What a seat sees ─────────────────────────────────────────────────────────

/** The whole board, once it's over, as History keeps it. */
export function finishedRecord(s: TableState, d: Derived, mySeat: Seat | null): HistoryRecord {
  const b = s.board!;
  return {
    board_num: b.num,
    label: 'Table',
    table_id: s.id,
    ...(mySeat ? { my_seat: mySeat } : {}),
    dealer: b.dealer,
    vulnerability: b.vulnerability,
    initial_hands: copyHands(b.hands),
    auction_calls: d.calls,
    bid_alerts: { ...d.alerts },
    contract: d.contract,
    passed_out: d.passedOut,
    tricks_log: d.tricksLog,
    tricks_taken: { ...d.tricksTaken },
    result: d.result,
  };
}

/** The alerts `seat` may see while the board is live. A robot's: everyone,
 *  but not a pass reason (it reads the robot's cards out). A person's: the
 *  opponents and the person, never partner, as at a real table. */
function visibleAlerts(d: Derived, seat: Seat | null): Record<number, string> {
  if (d.phase === 'done') return { ...d.alerts };
  const out: Record<number, string> = {};
  for (const [k, why] of Object.entries(d.alerts)) {
    const i = Number(k);
    const [who, call] = d.calls[i];
    if (d.humanCall[i]) {
      if (seat !== null && (who === seat || PARTNERSHIP[who] !== PARTNERSHIP[seat])) out[i] = why;
    } else if (call !== 'Pass') out[i] = why;
  }
  return out;
}

function boardView(s: TableState, seat: Seat | null): BoardView {
  const b = s.board!;
  const d = derive(b);
  const c = d.contract;
  const dummyDown = !!c && (d.tricksLog.length > 0 || d.trick.length > 0);
  const empty = { North: [], East: [], South: [], West: [] } as Record<Seat, Card[]>;
  const hands = { ...empty };
  for (const p of PLAYERS) {
    if (p === seat || (dummyDown && c!.dummy === p)) hands[p] = d.hands[p];
  }
  return {
    num: b.num,
    dealer: b.dealer,
    vulnerability: b.vulnerability,
    phase: d.phase,
    calls: d.calls,
    alerts: visibleAlerts(d, seat),
    hands,
    counts: Object.fromEntries(PLAYERS.map((p) => [p, d.hands[p].length])) as Record<Seat, number>,
    contract: c,
    passedOut: d.passedOut,
    trick: d.trick,
    tricksLog: d.tricksLog,
    tricksTaken: d.tricksTaken,
    result: d.result,
    toAct: d.toAct,
    actor: d.toAct ? actorOf(d, d.toAct) : null,
    at: b.actions.length,
    record: d.phase === 'done' ? finishedRecord(s, d, seat) : null,
  };
}

/** Everything `playerId` may see, and nothing else: the server sends only
 *  this. A spectator (no seat) sees the public board and no hand. */
export function viewFor(s: TableState, playerId: string | null, ctx: Context): TableView {
  const me = playerById(s, playerId);
  const seat = me?.seat ?? null;
  const seats = Object.fromEntries(PLAYERS.map((p) => {
    const owner = playerInSeat(s, p);
    const v: SeatView = {
      name: owner?.name ?? null,
      playerId: owner?.id ?? null,
      connected: owner ? ctx.connected(owner.id) : false,
      robot: !ownerOf(s, p),
      away: owner ? isAway(owner, ctx) : false,
      ready: owner ? s.ready.includes(owner.id) : false,
    };
    return [p, v];
  })) as Record<Seat, SeatView>;
  return {
    tableId: s.id,
    version: s.version,
    you: { playerId: me?.id ?? null, seat, isHost: !!me && s.hostId === me.id },
    seats,
    watching: s.players.filter((p) => p.seat === null).map((p) => p.name),
    locked: s.locked,
    board: s.board ? boardView(s, seat) : null,
  };
}
