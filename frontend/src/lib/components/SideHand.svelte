<!-- A dummy at East or West, drawn on its own side of the table: one short
     row of cards per suit, the way a hand diagram shows a side hand. A void
     shows as a dash, so the shape reads at a glance. -->
<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, type Card } from '../engine/card';
  import { suitOrder } from './hand';
  import Fan from './Fan.svelte';

  let { cards, trump = null, trumpLast = false, title }: {
    cards: Card[];
    trump?: string | null;
    /** Trump as the bottom row instead of the top. */
    trumpLast?: boolean;
    title: string;
  } = $props();

  const rows = $derived(suitOrder(trump, trumpLast).map((suit) => ({ suit, cs: cards.filter((c) => c.suit === suit) })));
</script>

<section class="side-hand dummy-zone" aria-label={title}>
  <div class="side-hand-title">{title}</div>
  {#each rows as { suit, cs } (suit)}
    <div class="side-row">
      <span class="side-sym" style:color="var(--suit-{suit.toLowerCase()}-lt)" aria-hidden="true">{SUIT_SYMBOLS[suit]}</span>
      {#if cs.length}
        <Fan cards={cs} size="sm" label="{title}: {SUIT_NAMES[suit]}" />
      {:else}
        <span class="side-void">—<span class="sr-only"> no {SUIT_NAMES[suit]}</span></span>
      {/if}
    </div>
  {/each}
</section>
