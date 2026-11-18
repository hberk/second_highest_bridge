// The per-address limits' key, shared by the Node server and the Cloudflare
// Worker (cf/), which must not import server.ts (node:http, ws).

/** What the per-address limits count: an IPv4 address, or an IPv6 /64
 *  (one home or phone holds a whole /64 and can rotate within it). */
export function limitKey(ip: string): string {
  if (!ip.includes(':')) return ip;
  const [head, tail = ''] = ip.toLowerCase().split('::');
  const left = head ? head.split(':') : [];
  const right = tail ? tail.split(':') : [];
  const groups = [...left, ...Array<string>(Math.max(0, 8 - left.length - right.length)).fill('0'), ...right];
  return `${groups.slice(0, 4).map((g) => g.replace(/^0+(?=.)/, '')).join(':')}::/64`;
}
