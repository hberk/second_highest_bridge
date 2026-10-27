<!-- The auction on the felt, laid out like a bidding box at a real table:
     every call a seat makes stays in front of that seat, each new card laid
     over the last so the earlier ones still show their edge. The newest alert
     is spelled out in the middle; tap another alerted card to read its alert
     instead. The whole auction is a tap away in the top bar. -->
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
  /** The most calls a seat shows on the felt; earlier ones fold into a "+n"
   *  card. West and East stand on the felt's short side. Without a cap a long
   *  auction ran off the felt, over the alert and the title (the whole
   *  auction is a tap away). */
  const SHOWN: Record<Seat, number> = { North: 4, South: 3, West: 2, East: 2 };

  /** Each seat's calls in order, with where each sits in the auction. */
  const bySeat = $derived.by(() => {
    const out = new Map<Seat, { call: string; i: number }[]>(SEATS.map((p) => [p, []]));
    calls.forEach(([p, call], i) => out.get(p)!.push({ call, i }));
    return out;
  });

  /** The alert to spell out: the one tapped, else the newest. */
  let picked = $state<number | null>(null);
  const shown = $derived.by(() => {
    const alerted = calls.map((_, i) => i).filter((i) => alerts[i]);
    if (picked !== null && alerted.includes(picked)) return picked;
    return alerted.length ? Math.max(...alerted) : null;
  });

  function short(call: string): string {
    return call === 'X' ? 'Dbl' : call === 'XX' ? 'Rdbl' : call;
  }
  /** The bidding-box colours: white bids, green Pass, red X, blue XX. */
  function kind(call: string): string {
    return call === 'Pass' ? 'bc-pass' : call === 'X' ? 'bc-dbl' : call === 'XX' ? 'bc-rdbl' : 'bc-bid';
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
    {@const all = bySeat.get(p)!}
    {@const waiting = p === 'South' && turn === 'South'}
    <!-- "Your call" takes a card's room in your row. -->
    {@const mine = all.slice(-(SHOWN[p] - (waiting ? 1 : 0)))}
    {@const folded = all.length - mine.length}
    <div class="af-seat af-{p.toLowerCase()}">
      {#if p !== 'South'}<span class="af-who">{role(p)}</span>{/if}
      <div class="bc-stack" role="group" aria-label="{p}'s calls">
        {#if folded}<span class="bc bc-more" aria-label="{folded} earlier call{folded === 1 ? '' : 's'}"><span class="bc-label">+{folded}</span></span>{/if}
        {#each mine as c, k (c.i)}
          {@const top = k === mine.length - 1 && !waiting}
          {#if alerts[c.i]}
            <button class="bc {kind(c.call)} bc-alerted" class:bc-top={top} class:bc-shown={shown === c.i}
              aria-label="{p}: {c.call}, alerted. Show the alert" onclick={() => (picked = c.i)}>
              <span class="bc-label">{@render callText(c.call, false)}</span>
            </button>
          {:else}
            <span class="bc {kind(c.call)}" class:bc-top={top}>
              <span class="bc-label">{@render callText(c.call, false)}</span>
            </span>
          {/if}
        {/each}
        {#if waiting}
          <span class="bc bc-yours bc-top"><span class="bc-label">Your call</span></span>
        {:else if !mine.length}
          <span class="bc bc-none bc-top" aria-label="{p} has not bid"><span class="bc-label">—</span></span>
        {/if}
      </div>
      {#if p === 'South'}<span class="af-who">You</span>{/if}
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
