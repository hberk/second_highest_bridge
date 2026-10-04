<!-- The auction as four columns, West to South, with leading blanks so each
     call sits under the seat that made it. Alerts are keyed by a call's index
     in the auction, so they stay attached once the blanks shift things along. -->
<script lang="ts">
  import { PLAYERS, type CallRecord } from '../engine/auction';
  import type { Seat } from '../engine/card';
  import CallBadge from './CallBadge.svelte';

  let { dealer, calls, alerts = {} }:
    { dealer: Seat; calls: CallRecord[]; alerts?: Record<number, string> } = $props();

  const COLUMNS: Seat[] = ['West', 'North', 'East', 'South'];
  const blanks = $derived((PLAYERS.indexOf(dealer) - PLAYERS.indexOf('West') + 4) % 4);
  const cells = $derived([
    ...Array.from({ length: blanks }, () => null),
    ...calls.map(([, call], i) => ({ call, i })),
  ]);
</script>

<div class="auction-grid">
  {#each COLUMNS as seat}
    <div class="auction-head" class:dealer-col={seat === dealer}>{seat}{seat === dealer ? ' · dealer' : ''}</div>
  {/each}
  {#each cells as cell, k}
    <div class:col-first={k % 4 === 0} class:col-last={k % 4 === 3}>
      {#if cell === null}<span class="bid-empty">—</span>
      {:else}<CallBadge call={cell.call} alert={alerts[cell.i] ?? null} />{/if}
    </div>
  {/each}
</div>
