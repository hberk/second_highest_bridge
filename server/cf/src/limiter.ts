// How many tables one address may create in an hour: one Durable Object for
// the whole site, holding the last hour's creations in memory, as the Node
// server does (server.ts, `createsPerHour`). It stores nothing: losing the
// counts when it is evicted only resets the limit early.
import { DurableObject } from 'cloudflare:workers';

export const CREATES_PER_HOUR = 10;
const HOUR_MS = 3600_000;

export class Limiter extends DurableObject {
  private creates = new Map<string, number[]>();

  /** May `key` create a table now? Counts it if so. */
  allow(key: string, perHour = CREATES_PER_HOUR): boolean {
    const now = Date.now();
    if (this.creates.size > 10_000) {
      for (const [k, ts] of this.creates) if (!ts.some((t) => now - t < HOUR_MS)) this.creates.delete(k);
    }
    const recent = (this.creates.get(key) ?? []).filter((t) => now - t < HOUR_MS);
    if (recent.length >= perHour) {
      this.creates.set(key, recent);
      return false;
    }
    recent.push(now);
    this.creates.set(key, recent);
    return true;
  }
}
