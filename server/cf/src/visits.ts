// Visitor counts, with Workers Analytics Engine (free on Workers Free: 100,000
// data points written and 10,000 queries a day). One data point per page
// load (the app's beacon to /visit), table created and socket opened to a
// table; `npm run visitors` (visitors.mjs) reads them back.
//
// No cookies and nothing that identifies a person: an address is never
// stored. Each data point carries the country Cloudflare reports, the host of
// an outside referrer, and a "visitor" mark: 16 bits of a hash of the day,
// the address and the browser. 16 bits can't lead back to an address (some
// 65,000 IPv4 addresses share each mark with any one browser), yet a few
// hundred visitors a day rarely collide, so distinct marks in a day count
// people closely. The day is part of the hash, so the same person can't be
// followed from one day to the next.

/** What happened: a page load, a table created, a socket opened to a table. */
export type VisitEvent = 'view' | 'create' | 'join';

/** The blobs' order, which visitors.mjs reads by position (blob1..blob4). */
export const BLOBS = ['event', 'country', 'visitor', 'referrer'] as const;

/** The day's visitor mark: 4 hex digits of SHA-256(day | address | browser). */
export async function visitorMark(day: string, ip: string, userAgent: string): Promise<string> {
  const bytes = new TextEncoder().encode(`${day}|${ip}|${userAgent}`);
  const hash = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return [hash[0], hash[1]].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** The host of a referrer from another site, or '' (none, our own, or junk). */
export function referrerHost(referrer: string | null, ownHost: string): string {
  if (!referrer) return '';
  try {
    const host = new URL(referrer).hostname;
    return host === ownHost ? '' : host.slice(0, 100);
  } catch {
    return '';
  }
}

/** `referrer` is the page's document.referrer, which the beacon sends as its
 *  body (the site's Referrer-Policy keeps it out of the beacon's headers). */
export async function dataPoint(event: VisitEvent, req: Request, referrer = '', now = new Date()): Promise<AnalyticsEngineDataPoint> {
  const day = now.toISOString().slice(0, 10);
  const ip = req.headers.get('cf-connecting-ip') ?? '';
  const ua = req.headers.get('user-agent') ?? '';
  const country = (req as { cf?: { country?: unknown } }).cf?.country;
  return {
    indexes: [event],
    blobs: [
      event,
      typeof country === 'string' ? country : '',
      await visitorMark(day, ip, ua),
      referrerHost(referrer, new URL(req.url).hostname),
    ],
    doubles: [1],
  };
}

/** Record one event. Counting never gets in the way of the game: with no
 *  dataset bound (the tests, `wrangler dev`) or on any error, it does nothing. */
export async function recordVisit(dataset: AnalyticsEngineDataset | undefined, event: VisitEvent, req: Request, referrer = ''): Promise<void> {
  if (!dataset) return;
  try {
    dataset.writeDataPoint(await dataPoint(event, req, referrer));
  } catch (e) {
    console.error('visit not recorded:', e);
  }
}
