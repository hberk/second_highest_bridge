// What each call would mean if the player made it now, in the robots' system.
//
// A robot's alert depends only on the auction and the call, never on its
// cards: tests/test_bidding_calibration.py checks exactly that, for every call
// but Pass. So the meaning of any call can be found by asking the robots what
// they would bid, in this seat and this auction, with many different hands,
// and keeping the alert each call came with. The answer is the system's own
// words, so it can't drift from what the robots do -- and it is what partner,
// a robot, will take the call to mean.
//
// The sample is seeded from the auction, so the same auction always reads the
// same way. It is skewed towards strong and long hands, which uniform deals
// rarely reach: a 2C opening needs 22+ HCP, about one hand in 400.
import { RANKS, STRAIN_SYMBOLS, SUITS, card, parseBid, sortHand, type Card, type Suit } from './engine/card';
import { AuctionState } from './engine/auction';
import { aiBidExplained } from './engine/ai';

/** Hands asked per auction: about 100 ms on a laptop. */
export const SAMPLE_HANDS = 4000;

const DECK: Card[] = SUITS.flatMap((s) => RANKS.map((r) => card(s, r)));
const HONOURS = new Set(['J', 'Q', 'K', 'A']);

/** mulberry32: small, fast, and good enough to deal cards. */
function prng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** FNV-1a over the auction: the seed, so an auction always samples alike. */
function seedOf(auction: AuctionState): number {
  const text = `${auction.dealer}|${auction.vulnerability}|${auction.calls.map(([, c]) => c).join(' ')}`;
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 0x01000193);
  return h >>> 0;
}

/** One hand of 13, drawn without replacement with a weight per card
 *  (Efraimidis-Spirakis: take the 13 largest of u^(1/w)). */
function weightedHand(rnd: () => number, weight: (c: Card) => number): Card[] {
  const keyed = DECK.map((c) => ({ c, k: Math.pow(rnd(), 1 / weight(c)) }));
  keyed.sort((a, b) => b.k - a.k);
  return sortHand(keyed.slice(0, 13).map((x) => x.c));
}

/** A hand from a mix of shapes and strengths, so rare calls get asked about. */
function sampleHand(rnd: () => number): Card[] {
  const pick = rnd();
  const suit = SUITS[Math.floor(rnd() * 4)];
  const other = SUITS[Math.floor(rnd() * 4)];
  let honour = 1;
  let long: Suit[] = [];
  let boost = 1;
  if (pick < 0.4) { /* uniform */ }
  else if (pick < 0.55) honour = 2.5;
  else if (pick < 0.65) honour = 6;
  else if (pick < 0.8) { long = [suit]; boost = 4; }
  else if (pick < 0.9) { long = [suit, other]; boost = 3; }
  else { long = [suit]; boost = 3; honour = 2.5; }
  return weightedHand(rnd, (c) =>
    (HONOURS.has(c.rank) ? honour : 1) * (long.includes(c.suit) ? boost : 1));
}

/** Every call the robots would make here, other than Pass, with its alert.
 *  A call no sampled hand made is missing: the system has no meaning for it
 *  here that the sample found. */
export function callMeanings(auction: AuctionState, hands = SAMPLE_HANDS): Map<string, string> {
  // A private copy: the robots read the auction, and this one may be reactive.
  const here = new AuctionState(auction.dealer, auction.vulnerability);
  for (const [p, c] of auction.calls) here.applyCall(p, c);
  const who = here.currentPlayer();
  const rnd = prng(seedOf(here));
  const tally = new Map<string, Map<string, number>>();
  for (let i = 0; i < hands; i++) {
    const [call, why] = aiBidExplained(who, sampleHand(rnd), here);
    if (call === 'Pass') continue;
    const forCall = tally.get(call) ?? new Map<string, number>();
    forCall.set(why, (forCall.get(why) ?? 0) + 1);
    tally.set(call, forCall);
  }
  // Each call should read one way. If an auction the robots never reach on
  // their own splits it, take the commonest reading.
  const out = new Map<string, string>();
  for (const [call, whys] of tally) {
    out.set(call, [...whys].sort((a, b) => b[1] - a[1])[0][0]);
  }
  return out;
}

// ── Saying it to a new player ────────────────────────────────────────────────

/** What the bidding box shows when a call is tapped once. */
export interface Meaning {
  /** "Negative double", "Transfer", "Natural", "No agreed meaning". */
  title: string;
  /** The alert's facts, one per tag: "4+ ♠", "6+ HCP". */
  tags: string[];
  /** The alert as the robots word it, when it reads better as a sentence than
   *  as tags ("Longest suit other than theirs, ♦."); null otherwise. */
  shows: string | null;
  /** One or two sentences for someone who doesn't know the convention. */
  plain: string;
  /** False when the robots never make this call here. */
  known: boolean;
}

/** A label before a colon ("Negative: 4+ ♠, 6+ HCP.") names the convention:
 *  the title it gets, by label. */
const LABELS: Record<string, string> = {
  Negative: 'Negative double',
  Penalty: 'Penalty double',
  'Penalty double': 'Penalty double',
  Takeout: 'Takeout double',
  'Support double': 'Support double',
  Responsive: 'Responsive double',
  'Reopening double': 'Reopening double',
  Transfer: 'Transfer',
  Texas: 'Texas transfer',
  Stayman: 'Stayman',
  'Minor Stayman': 'Minor Stayman',
  Gerber: 'Gerber',
  Quantitative: 'Quantitative',
  Cuebid: 'Cuebid raise',
  Michaels: 'Michaels cuebid',
  Unusual: 'Unusual notrump',
  Jacoby: 'Jacoby 2NT',
  Jordan: 'Jordan 2NT',
  Drury: 'Drury',
  Splinter: 'Splinter',
  Lebensohl: 'Lebensohl',
  DOPI: 'Keycard answer',
  'Already described': 'Already described',
};

/** Without a label, a phrase anywhere in the alert names it. First match
 *  wins, so longer phrases come before the shorter ones they contain. */
const PHRASES: [RegExp, string][] = [
  [/Keycard Blackwood/, 'Keycard Blackwood'],
  [/keycards/i, 'Keycard answer'],
  [/asks for kings/i, 'Asking for kings'],
  [/trump queen/i, 'Trump queen'],
  [/Weak two/, 'Weak two'],
  [/Weak jump overcall/, 'Weak jump overcall'],
  [/Weak jump shift/, 'Weak jump shift'],
  [/Strong jump shift/, 'Strong jump shift'],
  [/Pre-emptive raise/i, 'Pre-emptive raise'],
  [/Pre-emptive/i, 'Pre-empt'],
  [/Help-suit game try/, 'Help-suit game try'],
  [/Short-suit game try/, 'Short-suit game try'],
  [/Fourth suit forcing/, 'Fourth suit forcing'],
  [/Super-accept/, 'Super-accept'],
  [/Inverted/, 'Inverted minor raise'],
  [/Limit raise/, 'Limit raise'],
  [/Free advance/, 'Free advance'],
  [/Waiting/, 'Waiting bid'],
  [/Positive/, 'Positive response'],
  [/Relay/, 'Relay'],
  [/Reverse/, 'Reverse'],
  [/Overcall/, 'Overcall'],
  [/Sign-off|To play/, 'To play'],
  [/22\+ HCP\. Strong/, 'Strong 2♣'],
  [/Penalty/, 'Penalty double'],
  [/[Tt]akeout/, 'Takeout double'],
  [/Minor Stayman/, 'Minor Stayman'],
  [/Stayman/, 'Stayman'],
  [/New minor forcing/, 'New minor forcing'],
  [/Completing the transfer/, 'Completing the transfer'],
  [/Completing the .*relay/, 'Completing the relay'],
  [/Answering the (reopening )?double/, 'Answering the double'],
  [/Choosing between partner's|Preference/, 'Preference'],
  [/support|agreeing the suit|partner's suit/, 'Support'],
  [/Free bid/, 'Free bid'],
  [/^Invitational/, 'Invitation'],
];

/** The sentence for each title. Every one is standard bridge, said plainly. */
const PLAIN: Record<string, string> = {
  'Negative double': 'Not for penalty. It shows length in the suits above and some points, and asks partner to pick the suit.',
  'Penalty double': 'You expect them to go down. Partner usually passes, and you score extra for each trick they fall short.',
  'Takeout double': "Not for penalty. It asks partner to name their best suit, usually one the opponents haven't bid.",
  'Support double': 'Tells partner you have exactly three cards in their suit, without using up bidding room.',
  'Responsive double': 'Not for penalty. Partner has doubled too; this asks partner to choose between the unbid suits.',
  'Reopening double': "Asks partner to bid, but partner may pass and defend if they hold the opponents' suit.",
  Transfer: 'Asks partner to bid the next suit up, so the stronger hand plays the contract.',
  'Texas transfer': 'A transfer at the four level: partner bids the next suit up, and that is usually where you play.',
  Stayman: 'Asks partner whether they have four cards in a major suit. It says nothing about clubs.',
  'Minor Stayman': 'Asks partner about the minor suits, looking for a fit there.',
  Gerber: 'Asks partner how many aces they hold, on the way to a slam.',
  Quantitative: 'Asks partner to bid slam with a maximum, or pass with a minimum.',
  'Cuebid raise': "Bidding the opponents' suit to show a good raise of partner's suit. It says nothing about their suit.",
  'Michaels cuebid': "Bidding the opponents' suit to show two long suits of your own.",
  'Unusual notrump': 'Shows two long suits, usually the two lowest unbid ones. It is not a notrump bid.',
  'Jacoby 2NT': "Shows a strong raise of partner's major. Partner then describes their hand.",
  'Jordan 2NT': "After a takeout double, shows a good raise of partner's suit.",
  Drury: 'After partner opens in third or fourth seat, shows support and asks how strong the opening is.',
  Splinter: "A jump that shows support for partner's suit and a singleton or void in the suit you bid.",
  Lebensohl: 'Asks partner to bid 3♣, so you can then show a weak hand with a long suit.',
  'Keycard Blackwood': 'Asks partner how many of the five keycards (the four aces and the trump king) they hold.',
  'Keycard answer': 'Answers the keycard question, so partner can judge whether slam is there.',
  'Asking for kings': 'Every keycard is present: this asks for kings, on the way to a grand slam.',
  'Trump queen': 'Answers whether you hold the queen of trumps.',
  'Weak two': 'A weak hand with a good six-card suit. It takes bidding room away from the opponents.',
  'Weak jump overcall': 'A jump that shows a weak hand with a long suit, to take bidding room away.',
  'Weak jump shift': 'A jump in a new suit showing a weak hand with a long suit.',
  'Strong jump shift': 'A jump in a new suit showing a strong hand, interested in slam.',
  'Pre-emptive raise': 'A jump raise on a weak hand with good support, to take bidding room away.',
  'Pre-empt': 'A weak hand with a long suit, bid high to take bidding room away from the opponents.',
  'Help-suit game try': 'Asks partner to bid game if they can help in this suit.',
  'Short-suit game try': 'Shows a short suit here and asks partner to bid game if their cards there are not wasted.',
  'Fourth suit forcing': 'Bidding the last unbid suit asks partner to describe their hand further. It says nothing about that suit.',
  'Super-accept': 'Accepts the transfer with a jump, showing a maximum and four-card support.',
  'Inverted minor raise': "A raise of partner's minor that is stronger than it looks. Partner must bid again.",
  'Limit raise': 'Support for partner and an invitation: partner bids game with more than a minimum.',
  'Free advance': "A new suit after partner's overcall, showing some values.",
  'Waiting bid': 'Says nothing about diamonds. It keeps the auction low so the strong hand can describe itself.',
  'Positive response': 'Answers the strong 2♣ with real values and a suit or a balanced hand.',
  Relay: 'Asks partner to make the cheapest bid, so you can describe your hand next.',
  Reverse: 'A second suit bid in a way that shows extra strength.',
  Overcall: 'A bid in your own suit after the opponents opened.',
  'To play': 'Says where you want to play. Partner should normally pass.',
  'Strong 2♣': 'The strongest opening. It says nothing about clubs, and partner must keep bidding.',
  'Already described': 'Your hand is already described, so this adds nothing new.',
  'New minor forcing': 'Asks partner to describe their hand further, usually whether they have support for your major. It says nothing about the minor.',
  'Completing the transfer': 'Partner asked you to bid this suit, so you do. It says nothing new about your hand.',
  'Completing the relay': 'Partner asked you to make this bid, so you do. Partner will say more next.',
  'Answering the double': "Partner's takeout double asked for your best suit. This answers it.",
  Preference: "Picks between suits partner has shown. It doesn't promise extra length.",
  Support: "Support for partner's suit: you're agreeing on trumps.",
  'Free bid': 'You bid even though the opponents gave partner another turn, so it shows real values.',
  Invitation: 'Asks partner to bid game with a little extra, or to stop.',
  Artificial: "Artificial: it doesn't promise the suit it names.",
  Natural: 'A natural bid: it shows the suit or notrump you bid, with the strength above.',
  Double: 'A double: it shows what is above.',
  Redouble: 'A redouble: it shows what is above.',
};

/** Extra lines, added unless the title (third) already says the same. */
const NOTES: [RegExp, string, string][] = [
  [/Game forcing/i, 'Partner must keep bidding until you reach game.', ''],
  [/Invitational|invites/i, 'Partner bids game with a little extra, or stops.', 'Invitation'],
];

/** Phrases that name the convention rather than state a fact: not tags. */
const NOT_TAGS = /^(Natural|Artificial|Forcing|Game forcing|Invitational|Pre-emptive|Pre-emptive raise|Weak two|Positive|Waiting|Relay|Reverse|Overcall|Limit raise|Super-accept|Free advance|Help-suit game try|Short-suit game try|Fourth suit forcing|Strong|Sign-off|To play|Weak jump overcall|Weak jump shift|Strong jump shift|Inverted)$/i;

function natural(call: string): string {
  const bid = parseBid(call);
  if (!bid) return call === 'X' ? 'a penalty double' : 'a redouble';
  return bid[1] === 'NT' ? 'a natural notrump bid' : `natural, showing ${STRAIN_SYMBOLS[bid[1]]}`;
}

/** What a call shows, for the box a first tap opens. `alert` is the robots'
 *  own wording from `callMeanings`, or undefined when they never make it. */
export function describeCall(call: string, alert: string | undefined): Meaning {
  if (call === 'Pass') {
    return {
      title: 'Pass', tags: [], shows: null, known: true,
      plain: 'You have nothing to add for now. Three passes in a row after a bid end the auction.',
    };
  }
  if (alert === undefined) {
    return {
      title: 'No agreed meaning', tags: [], shows: null, known: false,
      plain: `The robots never make this call here, so their system gives it no meaning. Partner will most likely read it as ${natural(call)}.`,
    };
  }
  const label = /^([A-Z][A-Za-z -]*?):\s*/.exec(alert);
  const body = label ? alert.slice(label[0].length) : alert;
  const title = (label ? LABELS[label[1]] ?? label[1] : undefined)
    ?? PHRASES.find(([re]) => re.test(alert))?.[1]
    ?? (/Artificial/.test(alert) ? 'Artificial' : call === 'X' ? 'Double' : call === 'XX' ? 'Redouble' : 'Natural');

  const facts = body.split(/[.;]\s*|,\s*/)
    .map((t) => t.trim())
    .filter((t) => t && !NOT_TAGS.test(t) && t.toLowerCase() !== title.toLowerCase());
  // Short facts ("4+ ♠", "balanced") read well as tags; prose doesn't, so an
  // alert with any prose in it is shown as the robots wrote it.
  const asTags = facts.every((t) => /\d/.test(t) || t.length <= 16);

  const lines = [PLAIN[title] ?? PLAIN.Natural];
  if (/Artificial/.test(alert) && title !== 'Artificial' && !/says nothing|not a notrump|doesn't promise/i.test(lines[0])) {
    lines.push(PLAIN.Artificial);
  }
  for (const [re, line, unless] of NOTES) if (re.test(alert) && title !== unless) lines.push(line);
  return {
    title,
    tags: asTags ? facts : [],
    shows: asTags || !facts.length ? null : body,
    plain: lines.join(' '),
    known: true,
  };
}
