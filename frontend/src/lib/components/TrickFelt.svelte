<!-- The trick on the felt: each card in front of the seat that played it, the
     winner ringed once the trick is over, and a dashed space where your card
     goes when it's your turn. -->
<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, type Card, type Seat } from '../engine/card';
  import type { Play } from '../engine/auction';
  import type { Snippet } from 'svelte';
  import { POSITION_CLASS, seatAt, type Position } from '../seats';

  let { trick, winner = null, labels, awaiting = null, info, me = 'South' }: {
    trick: Play[];
    winner?: Seat | null;
    labels: Record<Seat, string>;
    awaiting?: Seat | null;
    /** Text for the middle of the felt (the desktop table's trick header). */
    info?: Snippet;
    /** The seat at the bottom of the felt. */
    me?: Seat;
  } = $props();

  const played = $derived(new Map<Seat, Card>(trick));
  const POSITIONS: Position[] = ['top', 'left', 'right', 'bottom'];
</script>

<div class="trick-felt" role="group" aria-label="The trick">
  {#if info}<div class="tf-info">{@render info()}</div>{/if}
  {#each POSITIONS as pos (pos)}
    {@const p = seatAt(me, pos)}
    {@const c = played.get(p)}
    <div class="tf-seat tf-{POSITION_CLASS[pos]}">
      <span class="tf-label">{labels[p]}</span>
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
