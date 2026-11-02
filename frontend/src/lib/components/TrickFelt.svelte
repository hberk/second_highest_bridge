<!-- The trick on the felt: each card in front of the seat that played it, the
     winner ringed once the trick is over, and a dashed space where your card
     goes when it's your turn. -->
<script lang="ts">
  import { rankText } from './format';
  import { SUIT_NAMES, SUIT_SYMBOLS, type Card, type Seat } from '../engine/card';
  import type { Play } from '../engine/auction';
  import type { Snippet } from 'svelte';
  import { POSITION_CLASS, seatAt, type Position } from '../seats';

  let { trick, winner = null, labels, awaiting = null, info, me = 'South', onadvance }: {
    trick: Play[];
    winner?: Seat | null;
    labels: Record<Seat, string>;
    awaiting?: Seat | null;
    /** Text for the middle of the felt (the desktop table's trick header). */
    info?: Snippet;
    /** The seat at the bottom of the felt. */
    me?: Seat;
    /** A finished trick: a tap anywhere on the felt moves on to the next. */
    onadvance?: () => void;
  } = $props();

  const played = $derived(new Map<Seat, Card>(trick));
  const POSITIONS: Position[] = ['top', 'left', 'right', 'bottom'];
</script>

<!-- The "Next trick" button is the keyboard way on; the felt is a bigger target for a thumb. -->
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<div class="trick-felt" class:tf-tap={onadvance} role="group" aria-label="The trick" onclick={onadvance}>
  {#if info}<div class="tf-info">{@render info()}</div>{/if}
  {#each POSITIONS as pos (pos)}
    {@const p = seatAt(me, pos)}
    {@const c = played.get(p)}
    <div class="tf-seat tf-{POSITION_CLASS[pos]}">
      <span class="tf-label">{labels[p]}</span>
      {#if c}
        <div class="tf-card" class:tf-winner={winner === p} style:color="var(--suit-{c.suit.toLowerCase()})">
          <span class="tf-rank">{rankText(c.rank)}</span><span class="tf-suit" aria-hidden="true">{SUIT_SYMBOLS[c.suit]}</span>
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
  {#if onadvance}<span class="tf-hint" aria-hidden="true">Tap for the next trick</span>{/if}
</div>
