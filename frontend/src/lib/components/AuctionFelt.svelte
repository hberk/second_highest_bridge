<!-- The auction at a glance: each seat's latest call on the felt, where that
     player sits, and the newest alert spelled out in the middle. Tap another
     alerted call to read its alert instead; the whole auction is a tap away
     in the top bar. -->
<script lang="ts">
  import { parseBid, type Seat } from '../engine/card';
  import type { CallRecord } from '../engine/auction';
  import Strain from './Strain.svelte';

  let { calls, alerts, dealer, turn = null }: {
    calls: CallRecord[];
    alerts: Record<number, string>;
    dealer: Seat;
    turn?: Seat | null;
  } = $props();

  const SEATS: Seat[] = ['North', 'West', 'East', 'South'];

  /** Each seat's latest call and where it sits in the auction. */
  const latest = $derived.by(() => {
    const out = new Map<Seat, { call: string; i: number }>();
    calls.forEach(([p, call], i) => out.set(p, { call, i }));
    return out;
  });

  /** The alert to spell out: the one tapped, else the newest on the felt. */
  let picked = $state<number | null>(null);
  const shown = $derived.by(() => {
    const onFelt = [...latest.values()].map((l) => l.i).filter((i) => alerts[i]);
    if (picked !== null && onFelt.includes(picked)) return picked;
    return onFelt.length ? Math.max(...onFelt) : null;
  });

  function short(call: string): string {
    return call === 'X' ? 'Dbl' : call === 'XX' ? 'Rdbl' : call;
  }
  function role(p: Seat): string {
    const who = p === 'North' ? 'North · partner' : p;
    return p === dealer ? `${who} · dealer` : who;
  }
</script>

{#snippet callText(call: string, light: boolean)}
  {@const bid = parseBid(call)}
  {#if bid}<Strain level={bid[0]} strain={bid[1]} {light} />{:else}{short(call)}{/if}
{/snippet}

<div class="auction-felt" aria-label="The auction so far">
  {#each SEATS as p (p)}
    {@const l = latest.get(p)}
    <div class="af-seat af-{p.toLowerCase()}">
      {#if p !== 'South'}<span class="af-who">{role(p)}</span>{/if}
      {#if p === 'South' && turn === 'South'}
        <span class="af-call af-yours">Your call</span>
      {:else if !l}
        <span class="af-call af-none" aria-label="{p} has not bid">—</span>
      {:else if alerts[l.i]}
        <button class="af-call af-alerted" class:af-shown={shown === l.i} aria-label="{p}: {l.call}, alerted. Show the alert" onclick={() => (picked = l.i)}>
          {@render callText(l.call, false)}
        </button>
      {:else}
        <span class="af-call">{@render callText(l.call, false)}</span>
      {/if}
      {#if p === 'South' && turn !== 'South'}<span class="af-who">You</span>{/if}
    </div>
  {/each}
  <div class="af-center" aria-live="polite">
    {#if shown !== null}
      {@const [who, call] = calls[shown]}
      <span class="af-center-head">{who === 'South' ? 'Your' : `${who}'s`} {@render callText(call, true)}</span>
      <span class="af-center-text">{alerts[shown]}</span>
    {/if}
  </div>
</div>
