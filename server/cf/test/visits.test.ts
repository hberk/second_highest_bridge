// The visitor count's data point (src/visits.ts): what it stores, and what
// it never does (an address, or a mark that lasts beyond the day).
import { describe, expect, it } from 'vitest';
import { BLOBS, dataPoint, referrerHost, visitorMark } from '../src/visits';

const req = (headers: Record<string, string>, cf?: object) =>
  Object.assign(new Request('https://bridge.second-highest.workers.dev/visit', { method: 'POST', headers }), { cf });

describe('visitor counts', () => {
  it('stores the event, country, a 4-digit day mark and an outside referrer, never the address', async () => {
    const ip = '203.0.113.7', ua = 'Mozilla/5.0 (iPhone)';
    const p = await dataPoint('view', req({ 'cf-connecting-ip': ip, 'user-agent': ua }, { country: 'NL' }),
      'https://www.bridgebase.com/forums/topic/1', new Date('2026-11-19T10:00:00Z'));
    expect(BLOBS).toEqual(['event', 'country', 'visitor', 'referrer']);
    expect(p.indexes).toEqual(['view']);
    expect(p.doubles).toEqual([1]);
    expect(p.blobs![0]).toBe('view');
    expect(p.blobs![1]).toBe('NL');
    expect(p.blobs![2]).toMatch(/^[0-9a-f]{4}$/);
    expect(p.blobs![3]).toBe('www.bridgebase.com');
    expect(JSON.stringify(p)).not.toContain(ip);
    expect(JSON.stringify(p)).not.toContain('iPhone');
  });

  it('gives one person one mark a day, and a new one the next day', async () => {
    const a = await visitorMark('2026-11-19', '203.0.113.7', 'ua');
    expect(await visitorMark('2026-11-19', '203.0.113.7', 'ua')).toBe(a);
    expect(await visitorMark('2026-11-20', '203.0.113.7', 'ua')).not.toBe(a);
    expect(await visitorMark('2026-11-19', '203.0.113.8', 'ua')).not.toBe(a);
  });

  it('keeps only the host of a referrer from another site', () => {
    expect(referrerHost('https://bridge.second-highest.workers.dev/#/t/x', 'bridge.second-highest.workers.dev')).toBe('');
    expect(referrerHost('', 'h')).toBe('');
    expect(referrerHost('not a url', 'h')).toBe('');
    expect(referrerHost('https://l.facebook.com/l.php?u=secret', 'h')).toBe('l.facebook.com');
  });

  it('still makes a point with no country and no headers', async () => {
    const p = await dataPoint('create', req({}));
    expect(p.blobs!.slice(0, 2)).toEqual(['create', '']);
  });
});
