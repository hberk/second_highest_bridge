<!-- The trick on the felt: each card in front of the seat that played it, the
     winner ringed once the trick is over, and a dashed space where your card
     goes when it's your turn. East and West appear only as a name and a card
     count, since their hands are hidden. -->
<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, type Card, type Seat } from '../engine/card';
  import type { Play } from '../engine/auction';
  import type { Snippet } from 'svelte';

  let { trick, winner = null, labels, counts, awaiting = null, info }: {
    trick: Play[];
    winner?: Seat | null;
    labels: Record<Seat, string>;
    counts: Record<Seat, number>;
    awaiting?: Seat | null;
    /** Text for the middle of the felt (the desktop table's trick header). */
    info?: Snippet;
  } = $props();

  const played = $derived(new Map<Seat, Card>(trick));
  const SEATS: Seat[] = ['North', 'West', 'East', 'South'];
</script>

<div class="trick-felt" role="group" aria-label="The trick">
  {#if info}<div class="tf-info">{@render info()}</div>{/if}
  {#each SEATS as p (p)}
    {@const c = played.get(p)}
    <div class="tf-seat tf-{p.toLowerCase()}">
      <span class="tf-label">{labels[p]}{#if p === 'East' || p === 'West'}<small>{counts[p]} card{counts[p] === 1 ? '' : 's'}</small>{/if}</span>
      {#if c}
        <div class="tf-card" class:tf-winner={winner === p} style:color="var(--suit-{c.suit.toLowerCase()})">
          <span class="tf-rank">{c.rank}</span><span class="tf-suit" aria-hidden="true">{SUIT_SYMBOLS[c.suit]}</span>
          <span class="sr-only"> of {SUIT_NAMES[c.suit]}{winner === p ? ', wins the trick' : ''}</span>
          {#if winner === p}<span class="tf-badge" aria-hidden="true">Wins</span>{/if}
        </div>
      {:else if awaiting === p}
        <div class="tf-slot tf-awaiting"><span class="sr-only">Your card goes here</span></div>
      {:else}
        <div class="tf-slot"></div>
      {/if}
    </div>
  {/each}
</div>
