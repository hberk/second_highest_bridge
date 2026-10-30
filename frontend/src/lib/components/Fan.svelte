<!-- A hand as a fan of overlapping cards, grouped by suit. The cards overlap
     only as much as the width needs: each one sits in a box that may shrink,
     while the card itself keeps its size and runs under the next. When the
     hand is playable, legal cards rise and the rest are greyed and disabled. -->
<script lang="ts">
  import { rankText } from './format';
  import { SUIT_NAMES, SUIT_SYMBOLS, sameCard, type Card } from '../engine/card';
  import { grouped } from './hand';

  let { cards, trump = null, trumpLast = false, size = 'lg', playable = false, legal = [], label, onplay, jp = false }: {
    cards: Card[];
    trump?: string | null;
    /** Trump at the right-hand end instead of the left. */
    trumpLast?: boolean;
    size?: 'lg' | 'md' | 'sm';
    playable?: boolean;
    legal?: Card[];
    label: string;
    onplay?: (c: Card) => void;
    /** Tag each card that counts judgement points with its value (Bidding training). */
    jp?: boolean;
  } = $props();

  const JP: Record<string, number> = { K: 3, Q: 3, A: 1, J: 1, '10': 1, '9': 1 };

  const groups = $derived(grouped(cards, trump, trumpLast));
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
              <span class="fcard-rank">{rankText(c.rank)}</span><span class="fcard-suit" aria-hidden="true">{SUIT_SYMBOLS[suit]}</span>
            </button>
          {:else}
            <div class="fcard" style:color={ink}>
              <span class="fcard-rank">{rankText(c.rank)}</span><span class="fcard-suit" aria-hidden="true">{SUIT_SYMBOLS[suit]}</span><span class="sr-only"> of {SUIT_NAMES[suit]}</span>
              {#if jp && JP[c.rank]}<span class="fcard-jp" aria-label="{JP[c.rank]} judgement points">{JP[c.rank]}</span>{/if}
            </div>
          {/if}
        </div>
      {/each}
    {/each}
  </div>
{/if}
