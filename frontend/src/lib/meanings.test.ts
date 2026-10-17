// What a call means, found by asking the robots: the bidding box's first tap.
import { describe, expect, it } from 'vitest';
import { AuctionState } from './engine/auction';
import { aiBidExplained } from './engine/ai';
import { deal, type Seat, type Vulnerability } from './engine/card';
import { callMeanings, describeCall } from './meanings';

function auctionOf(dealer: Seat, calls: string[], vul: Vulnerability = 'None'): AuctionState {
  const a = new AuctionState(dealer, vul);
  for (const c of calls) a.applyCall(a.currentPlayer(), c);
  return a;
}

describe('callMeanings', () => {
  it('reads a negative double the way the robots alert it', () => {
    const m = callMeanings(auctionOf('North', ['1D', '1H'], 'N/S'));
    expect(m.get('X')).toBe('Negative: 4+ ♠, 6+ HCP.');
    expect(describeCall('X', m.get('X'))).toEqual({
      title: 'Negative double',
      tags: ['4+ ♠', '6+ HCP'],
      shows: null,
      plain: expect.stringMatching(/^Not for penalty/),
      known: true,
    });
  });

  it('finds the openings, rare ones included', () => {
    const m = callMeanings(auctionOf('South', []));
    expect(m.get('1NT')).toBe('15-17 HCP, balanced.');
    expect(describeCall('2C', m.get('2C')).title).toBe('Strong 2♣');
    expect(describeCall('2H', m.get('2H')).title).toBe('Weak two');
  });

  it('reads the same auction the same way every time', () => {
    const a = auctionOf('North', ['1NT', 'Pass']);
    expect([...callMeanings(a)]).toEqual([...callMeanings(a)]);
  });

  it('leaves the auction it was given alone', () => {
    const a = auctionOf('North', ['1S', '2H']);
    callMeanings(a);
    expect(a.calls.map(([, c]) => c)).toEqual(['1S', '2H']);
    expect(a.currentPlayer()).toBe('South');
  });

  it("agrees with the robots' own alert whenever it found the call", () => {
    // Real robot auctions: at every robot bid, the sampled meaning of the call
    // it made must be the alert it gave. A rare call the sample missed is
    // allowed, but not often.
    let s = 11;
    const rnd = () => ((s = (s * 1103515245 + 12345) % 2147483648) / 2147483648);
    let asked = 0;
    let missed = 0;
    for (let g = 0; g < 12; g++) {
      const hands = deal(rnd);
      const a = new AuctionState((['North', 'East', 'South', 'West'] as const)[g % 4], 'None');
      while (!a.isComplete && a.calls.length < 40) {
        const who = a.currentPlayer();
        const [call, why] = aiBidExplained(who, hands[who], a);
        if (call !== 'Pass') {
          asked += 1;
          const found = callMeanings(a, 1500).get(call);
          if (found === undefined) missed += 1;
          else expect(found, `${a.calls.map(([, c]) => c).join(' ')} ${call}`).toBe(why);
        }
        a.applyCall(who, call);
      }
    }
    expect(asked).toBeGreaterThan(30);
    expect(missed / asked).toBeLessThan(0.15);
  });
});

describe('describeCall', () => {
  it('says plainly when the robots never make a call', () => {
    const m = describeCall('1S', undefined);
    expect(m.known).toBe(false);
    expect(m.title).toBe('No agreed meaning');
    expect(m.plain).toContain('♠');
  });

  it('explains a pass without reading a hand', () => {
    expect(describeCall('Pass', 'Fewer than 6 points.')).toMatchObject({ title: 'Pass', tags: [] });
  });

  it('names conventions from a label or a phrase', () => {
    expect(describeCall('2D', 'Transfer: 5+ ♥. Artificial.')).toMatchObject({ title: 'Transfer', tags: ['5+ ♥'] });
    expect(describeCall('2H', 'Completing the transfer to ♥.').title).toBe('Completing the transfer');
    expect(describeCall('3S', '3+ ♠, pre-emptive raise.')).toMatchObject({ title: 'Pre-emptive raise', tags: ['3+ ♠'] });
    expect(describeCall('2C', '5+ ♣, 10+ HCP. Forcing.')).toMatchObject({ title: 'Natural', tags: ['5+ ♣', '10+ HCP'] });
  });

  it('shows prose as the robots wrote it rather than as tags', () => {
    const m = describeCall('2D', 'Longest suit other than theirs, ♦. Answering the double.');
    expect(m.title).toBe('Answering the double');
    expect(m.tags).toEqual([]);
    expect(m.shows).toBe('Longest suit other than theirs, ♦. Answering the double.');
  });

  it('adds what game forcing and artificial mean', () => {
    const m = describeCall('2D', 'No 4-card major. Artificial.');
    expect(m.plain).toContain("doesn't promise the suit");
    expect(describeCall('2S', '5+ ♠, 12+ HCP. Game forcing.').plain).toContain('until you reach game');
  });
});
