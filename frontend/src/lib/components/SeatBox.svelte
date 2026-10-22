<!-- A labelled seat box holding a hand-record style diagram: one line per
     suit, ranks high to low, voids as a dash. With `marks` (the History
     replayer's double dummy values), each card carries how the contract
     would end if it were played, and the card actually played is underlined. -->
<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, cardKey, value, type Card, type Suit } from '../engine/card';
  import type { Mark } from '../dd/analysis.svelte';

  let { seat, role, hand, marks = null, played = null }:
    { seat: string; role: string; hand: Card[]; marks?: Record<string, Mark> | null; played?: string | null } = $props();
  const roleCls = $derived(role === 'Declarer' ? 'is-declarer' : role === 'Dummy' ? 'is-dummy' : '');
  const SUITS: Suit[] = ['S', 'H', 'D', 'C'];
  const cards = (s: Suit) => hand.filter((c) => c.suit === s).sort((a, b) => value(b) - value(a));
  const ranks = (s: Suit) => cards(s).map((c) => c.rank).join('') || '—';
</script>

<div class="seat-box" class:to-play={marks}>
  <div class="seat-box-head">
    <span class="seat-letter">{seat[0]}</span>
    <span class="seat-box-name">{seat}</span>
    {#if marks}<span class="seat-box-tag">To play</span>{/if}
    <span class="seat-box-role {roleCls}">{role}</span>
  </div>
  <div class="hand-diagram">
    {#each SUITS as s}
      <div class="hd-line">
        <span class="hd-suit" style:color="var(--suit-{s.toLowerCase()})" aria-hidden="true">{SUIT_SYMBOLS[s]}</span>
        <span class="sr-only">{SUIT_NAMES[s]}: </span>
        {#if marks && cards(s).length}
          <span class="hd-ranks hd-marked">
            {#each cards(s) as c (cardKey(c))}
              {@const m = marks[cardKey(c)]}
              <span class="hd-card">
                <span class:hd-played={played === cardKey(c)}>{c.rank}</span>
                {#if m}<span class="dd-mark dd-{m.tone}"><span aria-hidden="true">{m.text}</span><span class="sr-only"> ({m.label}{played === cardKey(c) ? ', played' : ''})</span></span>{/if}
              </span>
            {/each}
          </span>
        {:else}
          <span class="hd-ranks">{ranks(s)}</span>
        {/if}
      </div>
    {/each}
  </div>
</div>
