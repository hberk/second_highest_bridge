// The table from one seat's point of view: you at the bottom, partner across,
// the opponents to your left and right. Solo play sits you South; at a
// multiplayer table you sit wherever you chose, and every view turns with you.
import type { Seat, Side } from './engine/card';
import { PARTNERSHIP } from './engine/auction';

/** Clockwise, the order of play. */
const CLOCKWISE: Seat[] = ['North', 'East', 'South', 'West'];

export type Position = 'bottom' | 'left' | 'top' | 'right';

/** The seat at `pos` when you sit at `me`: your left-hand opponent plays
 *  after you, your right-hand opponent before you. */
export function seatAt(me: Seat, pos: Position): Seat {
  const i = CLOCKWISE.indexOf(me);
  const step = { bottom: 0, left: 1, top: 2, right: 3 }[pos];
  return CLOCKWISE[(i + step) % 4];
}

export function positionOf(me: Seat, seat: Seat): Position {
  return (['bottom', 'left', 'top', 'right'] as Position[]).find((p) => seatAt(me, p) === seat)!;
}

/** The compass class each position is drawn with: the felt's CSS was laid
 *  out for South at the bottom, so `bottom` keeps the `south` styles. */
export const POSITION_CLASS: Record<Position, string> = {
  bottom: 'south', left: 'west', top: 'north', right: 'east',
};

export const partnerOf = (me: Seat): Seat => seatAt(me, 'top');
export const sideOf = (me: Seat): Side => PARTNERSHIP[me];
export const otherSideOf = (me: Seat): Side => (PARTNERSHIP[me] === 'N/S' ? 'E/W' : 'N/S');

/** The side's name as players say it: "North-South". */
export const SIDE_NAME: Record<Side, string> = { 'N/S': 'North-South', 'E/W': 'East-West' };
