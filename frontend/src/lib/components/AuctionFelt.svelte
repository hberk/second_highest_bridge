<!-- The auction on the felt, laid out like a bidding box at a real table:
     every call a seat makes stays in front of that seat, each new card laid
     over the last so the earlier ones still show their edge. The newest alert
     is spelled out in the middle; tap another alerted card to read its alert
     instead. The whole auction is a tap away in the top bar. -->
<script lang="ts">
  import { parseBid, type Seat } from '../engine/card';
  import type { CallRecord } from '../engine/auction';
  import Strain from './Strain.svelte';
  import { POSITION_CLASS, partnerOf, seatAt, type Position } from '../seats';

  let { calls, alerts, dealer, turn = null, me = 'South', names = {} }: {
    calls: CallRecord[];
    alerts: Record<number, string>;
    dealer: Seat;
    turn?: Seat | null;
    /** The seat at the bottom of the felt: you. */
    me?: Seat;
    /** People's names by seat, at a multiplayer table. */
    names?: Partial<Record<Seat, string>>;
  } = $props();

  const POSITIONS: Position[] = ['top', 'left', 'right', 'bottom'];
  const SEATS: Seat[] = ['North', 'West', 'East', 'South'];

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
    const name = names[p] ?? p;
    const who = p === partnerOf(me) ? `${name} · partner` : name;
    return p === dealer ? `${who} · dealer` : who;
  }
</script>

{#snippet callText(call: string, light: boolean)}
  {@const bid = parseBid(call)}
  {#if bid}<Strain level={bid[0]} strain={bid[1]} {light} />{:else}{short(call)}{/if}
{/snippet}

<div class="auction-felt" aria-label="The auction so far">
  {#each POSITIONS as pos (pos)}
    {@const p = seatAt(me, pos)}
    {@const mine = bySeat.get(p)!}
    {@const waiting = p === me && turn === me}
    <div class="af-seat af-{POSITION_CLASS[pos]}">
      {#if p !== me}<span class="af-who">{role(p)}</span>{/if}
      <div class="bc-stack" role="group" aria-label="{p}'s calls">
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
      {#if p === me}<span class="af-who">You</span>{/if}
    </div>
  {/each}
  <div class="af-center" aria-live="polite">
    {#if shown !== null}
      {@const [who, call] = calls[shown]}
      <span class="af-center-head">{who === me ? 'Your' : `${names[who] ?? who}'s`} {@render callText(call, true)}</span>
      <span class="af-center-text">{alerts[shown]}</span>
    {/if}
  </div>
</div>
