<!-- A hand as one row of cards, grouped by suit. Clickable when it is this
     seat's turn; a concealed hand shows only card backs and a count. -->
<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, sameCard, type Card } from '../engine/card';
  import CardFace from './CardFace.svelte';
  import CardBacks from './CardBacks.svelte';
  import { grouped } from './hand';

  let {
    hand, trump = null, label = null, isTurn = false, legal = [], concealed = false, onplay,
  }: {
    hand: Card[];
    trump?: string | null;
    label?: string | null;
    isTurn?: boolean;
    legal?: Card[];
    concealed?: boolean;
    onplay?: (c: Card) => void;
  } = $props();

  const groups = $derived(grouped(hand, trump));
  const isLegal = (c: Card) => legal.some((l) => sameCard(l, c));
</script>

{#if label}
  {#if isTurn}
    <div class="hand-header active-header"><span><strong>{label}</strong></span><span class="turn-pill">Your turn — play a card</span></div>
  {:else}
    <div class="hand-header"><strong>{label}</strong></div>
  {/if}
{/if}

{#if !hand.length}
  <div class="pcard-empty">No cards remaining</div>
{:else if concealed && !isTurn}
  <CardBacks count={hand.length} />
  <div class="seat-count"><strong>{hand.length} cards</strong> · concealed</div>
{:else if !isTurn}
  <div class="pcard-row">
    {#each groups as [suit, cards], i (suit)}
      {#if i}<div class="pcard-gap"></div>{/if}
      {#each cards as card (card.rank + card.suit)}<CardFace {card} />{/each}
    {/each}
  </div>
{:else}
  <div class="card-btn-row" role="group" aria-label="{label ?? 'Hand'}: choose a card">
    {#each groups as [suit, cards], i (suit)}
      {#if i}<div class="card-btn-gap"></div>{/if}
      {#each cards as card (card.rank + card.suit)}
        <button class="card-btn {card.suit.toLowerCase()}" disabled={!isLegal(card)} onclick={() => onplay?.(card)}>
          <span>{card.rank}</span><span aria-hidden="true">{SUIT_SYMBOLS[card.suit]}</span><span class="sr-only"> of {SUIT_NAMES[card.suit]}</span>
        </button>
      {/each}
    {/each}
  </div>
{/if}
