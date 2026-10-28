<!-- The green felt: the four cards of the current trick, the led suit and the
     running trick count. -->
<script lang="ts">
  import { rankText } from './format';
  import { SUIT_NAMES, SUIT_SYMBOLS, type Card, type Seat, type Side } from '../engine/card';
  import type { Contract, Play } from '../engine/auction';

  let { trick, winner = null, displayNum = 1, contract = null, tricksTaken = null }: {
    trick: Play[];
    winner?: Seat | null;
    displayNum?: number;
    contract?: Contract | null;
    tricksTaken?: Record<Side, number> | null;
  } = $props();

  const played = $derived(new Map<Seat, Card>(trick));
  const led = $derived(trick.length ? trick[0][1].suit : null);

  function seatRole(p: Seat): string {
    if (!contract) return p.toUpperCase();
    if (contract.dummy === p) return `${p.toUpperCase()} (Dummy)`;
    if (contract.declarer === p) return `${p.toUpperCase()} (Declarer)`;
    return `${p.toUpperCase()} (Defender)`;
  }
</script>

{#snippet slot(p: Seat)}
  {@const c = played.get(p)}
  {#if c}
    {@const ink = `var(--suit-${c.suit.toLowerCase()})`}
    <div class="felt-card" class:winner-card={winner === p}>
      <div class="felt-card-rank" style:color={ink}>{rankText(c.rank)}</div>
      <div class="felt-card-suit" style:color={ink} aria-hidden="true">{SUIT_SYMBOLS[c.suit]}</div>
      <span class="sr-only">{c.rank} of {SUIT_NAMES[c.suit]}{winner === p ? ', wins the trick' : ''}</span>
      {#if winner === p}<div class="winner-badge">★ 2nd Highest</div>{/if}
    </div>
  {:else}
    <div class="empty-felt-slot"><span class="slot-letter" aria-hidden="true">{p[0]}</span><span class="sr-only">{p} has not played yet</span></div>
  {/if}
{/snippet}

<div class="bridge-felt-container">
  <div class="felt-top"><div class="seat-label">{seatRole('North')}</div>{@render slot('North')}</div>
  <div class="felt-middle">
    <div class="felt-west-side"><div class="seat-label">{seatRole('West')}</div>{@render slot('West')}</div>
    <div class="felt-center-info">
      <div class="trick-title">TRICK {displayNum} / 13</div>
      <div class="trick-sub">
        {#if led}
          <span class="led-tag"><span aria-hidden="true">Led: <span style:color="var(--suit-{led.toLowerCase()}-lt)">{SUIT_SYMBOLS[led]}</span></span><span class="sr-only">Led: {SUIT_NAMES[led]}</span></span>
        {/if}
      </div>
      <div class="felt-rule">2nd-Highest in winning suit wins</div>
      {#if tricksTaken}
        <div class="felt-tally"><span class="us">N/S {tricksTaken['N/S']}</span><span>E/W {tricksTaken['E/W']}</span></div>
      {/if}
    </div>
    <div class="felt-east-side"><div class="seat-label">{seatRole('East')}</div>{@render slot('East')}</div>
  </div>
  <div class="felt-bottom">{@render slot('South')}<div class="seat-label">{seatRole('South')}</div></div>
</div>
