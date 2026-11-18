// The Tables' clock (../../src/tables.ts, `Clock`) on a Durable Object.
//
// Every timer a table sets (a robot's next move, an away check, the idle
// unload) is kept here in memory, and the object's one alarm is set for the
// earliest. A robot's move then runs in its own alarm invocation, with its own
// CPU allowance, rather than inside whichever request happened to schedule
// it (MULTIPLAYER_PLAN.md, M7: "an alarm per robot tick, never setTimeout").
//
// With no timer pending the alarm is set for `fallback()`: the moment the
// table expires, so a week-old table still closes with nobody connected. A
// timer lost when the object is evicted is never needed: timers are pending
// only while someone is connected, and the object stays in memory while a
// socket is open.
import type { Clock } from '../../src/tables';

interface Timer { at: number; fn: () => void }

export class AlarmClock implements Clock {
  private timers = new Map<number, Timer>();
  private nextHandle = 1;
  /** The time the alarm is set for, as far as this instance knows. */
  private armedAt: number | null = null;
  /** Alarms set, for the measurements. */
  alarmsSet = 0;

  constructor(private storage: DurableObjectStorage, private fallback: () => number | null) {}

  now(): number {
    return Date.now();
  }

  setTimeout(fn: () => void, ms: number): unknown {
    const h = this.nextHandle++;
    this.timers.set(h, { at: Date.now() + ms, fn });
    this.arm();
    return h;
  }

  clearTimeout(handle: unknown): void {
    // The alarm stays: ringing with nothing due just sets the next one.
    this.timers.delete(handle as number);
  }

  /** Set the alarm for the earliest timer, else for `fallback()`. */
  arm(): void {
    let at = Infinity;
    for (const t of this.timers.values()) at = Math.min(at, t.at);
    if (at === Infinity) {
      const f = this.fallback();
      if (f === null) {
        if (this.armedAt !== null) void this.storage.deleteAlarm();
        this.armedAt = null;
        return;
      }
      at = f;
    }
    if (this.armedAt === at) return;
    this.armedAt = at;
    this.alarmsSet++;
    void this.storage.setAlarm(at);
  }

  /** The alarm rang: run every timer that is due, in order, then set the
   *  next alarm. One timer that throws doesn't stop the rest. */
  ring(): void {
    this.armedAt = null;
    const now = Date.now();
    const due = [...this.timers].filter(([, t]) => t.at <= now).sort((a, b) => a[1].at - b[1].at);
    for (const [h, t] of due) {
      if (!this.timers.delete(h)) continue;
      try {
        t.fn();
      } catch (e) {
        console.error(`${new Date().toISOString()} timer:`, e);
      }
    }
    this.arm();
  }
}
