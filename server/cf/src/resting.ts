// The Free plan's daily limits (MULTIPLAYER_PLAN.md, "The Free plan's
// budget"): past one, that kind of operation fails until 00:00 UTC. A table
// then says "resting until <time>" (the app's words) rather than breaking.
//
// How each limit shows up:
// - Worker requests (100,000 a day): Cloudflare answers itself with its 1027
//   page, HTTP 429, before this code runs. The app reads a 429 or 503 that
//   isn't this server's JSON as resting.
// - Durable Object requests, rows written, duration: the call into the object,
//   or a write inside it, throws. `isResting` recognises those errors; the
//   Worker answers 503 `resting`, and a table closes its sockets with
//   RESTING_CLOSE.

/** The wording of Cloudflare's errors for a spent Free plan limit, as far as
 *  it is known; an unrecognised one is logged as an ordinary error, so the
 *  log shows what to add here. */
const LIMIT = /free tier|daily limit|exceeded allowed|exceeded.*(rows|requests|duration)/i;

export function isResting(e: unknown): boolean {
  const msg = e instanceof Error ? e.message : String(e);
  return LIMIT.test(msg);
}

/** What a write throws in development when the measurements endpoint has
 *  told a table to act as if its allowance were spent. */
export const SIMULATED_LIMIT = 'Exceeded allowed rows written in Durable Objects free tier (simulated).';

let unrecognisedLogged = false;

/** Log an error that wasn't recognised as resting, marking the first one so a
 *  changed wording of Cloudflare's limit errors stands out in Workers Logs. */
export function logUnrecognised(where: string, e: unknown): void {
  const first = !unrecognisedLogged;
  unrecognisedLogged = true;
  console.error(`${new Date().toISOString()} ${where}${first ? ' (first unrecognised error: is it a spent limit? see resting.ts)' : ''}:`, e);
}
