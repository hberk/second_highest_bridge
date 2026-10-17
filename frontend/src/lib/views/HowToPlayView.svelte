<!-- How a trick is won in this variant: the rule, then four worked tricks drawn on
     the same felt as the real table. Static; nothing here touches the game. -->
<script lang="ts">
  import FeltTable from '../components/FeltTable.svelte';
  import { card, type Seat, type Card } from '../engine/card';
  import type { Play } from '../engine/auction';

  type Example = {
    title: string;
    setting: string;
    plays: Play[];
    winner: Seat;
    steps: string[];
    takeaway: string;
  };

  const p = (seat: Seat, suit: Card['suit'], rank: string): Play => [seat, card(suit, rank)];

  // West leads every trick, so the cards go down West, North, East, South.
  const examples: Example[] = [
    {
      title: '1. A normal trick',
      setting: 'No trump. Everyone has a spade and follows suit.',
      plays: [p('West', 'S', '7'), p('North', 'S', 'K'), p('East', 'S', '3'), p('South', 'S', 'Q')],
      winner: 'South',
      steps: [
        'West leads the ♠7, so spades are the suit that counts.',
        'The four spades, high to low, are K, Q, 7, 3.',
        'The highest (the ♠K) loses. The second-highest, South’s ♠Q, takes the trick.',
      ],
      takeaway: 'Playing the biggest card is not what wins. The ace or king often loses the trick it is played to.',
    },
    {
      title: '2. Following suit alone still wins',
      setting: 'No trump. Only West and South have a club; North and East discard.',
      plays: [p('West', 'C', '6'), p('North', 'D', 'K'), p('East', 'S', 'A'), p('South', 'C', '2')],
      winner: 'South',
      steps: [
        'West leads the ♣6. North and East have no clubs, so they discard: the ♦K and the ♠A.',
        'Discards can never win, however high. Only clubs count, and only two clubs were played: the 6 and the 2.',
        'Of two cards, the second-highest is the lower one. South’s ♣2 takes the trick.',
      ],
      takeaway: 'If you are the only one to follow the led suit, your card is the second of two, so you win, even with the deuce. (If nobody had followed, West’s lone ♣6 would win outright.)',
    },
    {
      title: '3. A ruff wins the trick',
      setting: 'Hearts are trump. East has no spades and plays a heart.',
      plays: [p('West', 'S', 'A'), p('North', 'S', '5'), p('East', 'H', '2'), p('South', 'S', 'K')],
      winner: 'East',
      steps: [
        'West leads the ♠A. North follows with the ♠5 and South with the ♠K.',
        'East has no spades and trumps with the ♥2.',
        'As soon as any trump is played, trumps are the suit that counts and spades no longer matter.',
        'Only one trump was played, and a single card wins outright. East’s ♥2 beats the ♠A and the ♠K.',
      ],
      takeaway: 'The tricky part: a lone ruff wins even though it is not the second of anything. Compare cards only within the winning suit; with one card, there is nothing to compare.',
    },
    {
      title: '4. An underruff wins the trick',
      setting: 'Hearts are trump. North and South both ruff a diamond lead.',
      plays: [p('West', 'D', 'K'), p('North', 'H', '9'), p('East', 'D', '3'), p('South', 'H', '4')],
      winner: 'South',
      steps: [
        'West leads the ♦K. North has no diamonds and ruffs with the ♥9. East follows with the ♦3.',
        'South has no diamonds either and ruffs lower, with the ♥4.',
        'Two trumps were played, so trumps count: the ♥9 and the ♥4.',
        'The second-highest of the two is the ♥4. South’s underruff takes the trick, and North’s higher ruff loses.',
      ],
      takeaway: 'In ordinary bridge the higher ruff wins. Here the lower of two ruffs wins, and a high ruff can lose the trick it was meant to win.',
    },
  ];
</script>

<p>
  This is Contract Bridge with one change: <strong>the second-highest card in the winning suit takes the
  trick</strong>, not the highest. The auction, the contracts, the vulnerability and the scoring are all
  the same as in ordinary duplicate bridge.
</p>

<div class="notice info">
  <strong>Which suit counts?</strong>
  <ol class="rule-list">
    <li>If anyone played a <strong>trump</strong>, trumps count (in a notrump contract there is no trump).</li>
    <li>Otherwise the suit that was <strong>led</strong> counts. Cards of any other suit never win.</li>
    <li>In the suit that counts, the <strong>second-highest</strong> card wins. If only one card of that suit was played, it wins outright.</li>
  </ol>
  You must still follow suit if you can, exactly as in bridge. Aces are high.
</div>

<h2>Four examples</h2>
<p class="caption">Each trick below is led by West and played clockwise: West, North, East, South. The winning card is starred.</p>

{#each examples as ex}
  <div class="section-title">{ex.title}</div>
  <div class="split example">
    <div>
      <p><em>{ex.setting}</em></p>
      <ol class="rule-list">
        {#each ex.steps as step}<li>{step}</li>{/each}
      </ol>
      <div class="notice success"><strong>{ex.winner} wins.</strong> {ex.takeaway}</div>
    </div>
    <div>
      <FeltTable trick={ex.plays} winner={ex.winner} displayNum={1} />
    </div>
  </div>
{/each}

<style>
  .rule-list { margin: 6px 0 10px; padding-left: 22px; display: grid; gap: 4px; }
  .example { margin-bottom: 18px; align-items: start; }
</style>
