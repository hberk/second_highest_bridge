<!-- A hand as four short suit lines, for the X-ray view of the other seats. -->
<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, type Card, type Seat } from '../engine/card';
  import { grouped } from './hand';

  let { seat, cards, trump = null }: { seat: Seat; cards: Card[]; trump?: string | null } = $props();
  const groups = $derived(grouped(cards, trump));
</script>

<div class="mini-hand">
  <div class="mini-who">{seat}</div>
  {#each groups as [suit, cs] (suit)}
    <div class="mini-line">
      <span class="mini-sym" style:color="var(--suit-{suit.toLowerCase()}-lt)" aria-hidden="true">{SUIT_SYMBOLS[suit]}</span>
      <span class="sr-only">{SUIT_NAMES[suit]}: </span>{cs.map((c) => c.rank).join(' ')}
    </div>
  {/each}
</div>
