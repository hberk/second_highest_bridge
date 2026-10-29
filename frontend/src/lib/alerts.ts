// Which alerts each reader may see, shared by the solo table (`Game`) and the
// multiplayer table (`table/core.ts`), so the two can't hide or show a
// different set. Plain TypeScript: the table server imports it too.
//
// `isHuman(i)` says whether call i was made by a person. A person's alert is
// free text the robots don't read; a robot's pass reason reads its cards out.
import type { Seat, Vulnerability } from './engine/card';
import { AuctionState, type CallRecord } from './engine/auction';
import { shownLengths, type Shown } from './engine/ai';
import { callMeanings } from './meanings';

export type IsHuman = (i: number) => boolean;

/** The alerts the table may see while the board is live: robot passes say
 *  WHY they passed, which reads the robot's cards out, and a real table never
 *  alerts a natural pass. The reasons stay in the record for the post-mortem.
 *  A person's own alerts are shown, though: a pass the player chose to alert
 *  (a forcing pass, say) is shown like any other alerted call. */
export function liveAlerts(calls: CallRecord[], alerts: Record<number, string>,
  isHuman: IsHuman): Record<number, string> {
  const out: Record<number, string> = {};
  for (const [i, why] of Object.entries(alerts)) {
    const call = calls[Number(i)];
    if (call && (call[1] !== 'Pass' || isHuman(Number(i)))) out[Number(i)] = why;
  }
  return out;
}

/** The robots' own alerts, by call: what a robot bidder may read. */
export function robotAlerts(calls: CallRecord[], alerts: Record<number, string>,
  isHuman: IsHuman): Record<number, string> {
  const out: Record<number, string> = {};
  for (const [i, why] of Object.entries(alerts)) {
    const call = calls[Number(i)];
    if (call && !isHuman(Number(i))) out[Number(i)] = why;
  }
  return out;
}

/** GIB's reading of a person's call, by auction; shared between boards, since
 *  it depends only on the auction (`meanings.gib_alert` in Python). */
export type Readings = Map<string, string | null>;

/** The lengths the bidding showed, for the robots' play: a robot's call by
 *  its own alert, a person's by what GIB would mean by it (`callMeanings`) --
 *  the self-alert is free text the robots don't read (docs/CHALLENGE.md). */
export function robotShown(dealer: Seat, vulnerability: Vulnerability, calls: CallRecord[],
  alerts: Record<number, string>, isHuman: IsHuman, readings: Readings): Shown {
  const read = robotAlerts(calls, alerts, isHuman);
  calls.forEach(([, call], i) => {
    if (!isHuman(i)) return;
    const key = `${dealer}|${vulnerability}|${calls.slice(0, i + 1).map(([, c]) => c).join(' ')}`;
    if (!readings.has(key)) {
      const prefix = new AuctionState(dealer, vulnerability);
      for (const [p, c] of calls.slice(0, i)) prefix.applyCall(p, c);
      readings.set(key, call === 'Pass' ? null : callMeanings(prefix).get(call) ?? null);
    }
    const why = readings.get(key);
    if (why) read[i] = why;
  });
  return shownLengths(calls.map(([p, c]) => [p, c] as [Seat, string]), read);
}
