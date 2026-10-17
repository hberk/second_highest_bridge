<!-- A hand as a fan of overlapping cards, grouped by suit. The cards overlap
     only as much as the width needs: each one sits in a box that may shrink,
     while the card itself keeps its size and runs under the next. When the
     hand is playable, legal cards rise and the rest are greyed and disabled. -->
<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, sameCard, type Card } from '../engine/card';
  import { grouped } from './hand';

  let { cards, trump = null, size = 'lg', playable = false, legal = [], label, onplay }: {
    cards: Card[];
    trump?: string | null;
    size?: 'lg' | 'md' | 'sm';
    playable?: boolean;
    legal?: Card[];
    label: string;
    onplay?: (c: Card) => void;
  } = $props();

  const groups = $derived(grouped(cards, trump));
  const isLegal = (c: Card) => legal.some((l) => sameCard(l, c));
</script>

{#if !cards.length}
  <div class="fan-empty">No cards left</div>
{:else}
  <div class="fan fan-{size}" class:playable role="group" aria-label={label}>
    {#each groups as [suit, cs], gi (suit)}
      {#each cs as c, ci (c.rank + c.suit)}
        {@const ink = `var(--suit-${suit.toLowerCase()}${playable && !isLegal(c) ? '-dim' : ''})`}
        <div class="fan-slot" class:suit-start={gi > 0 && ci === 0}>
          {#if playable}
            <button class="fcard" class:legal={isLegal(c)} disabled={!isLegal(c)} style:color={ink}
              aria-label="{c.rank} of {SUIT_NAMES[suit]}" onclick={() => onplay?.(c)}>
              <span class="fcard-rank" class:ten={c.rank === '10'}>{c.rank}</span><span class="fcard-suit" aria-hidden="true">{SUIT_SYMBOLS[suit]}</span>
            </button>
          {:else}
            <div class="fcard" style:color={ink}>
              <span class="fcard-rank" class:ten={c.rank === '10'}>{c.rank}</span><span class="fcard-suit" aria-hidden="true">{SUIT_SYMBOLS[suit]}</span><span class="sr-only"> of {SUIT_NAMES[suit]}</span>
            </div>
          {/if}
        </div>
      {/each}
    {/each}
  </div>
{/if}
