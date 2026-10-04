<!-- A labelled seat box holding a hand-record style diagram: one line per
     suit, ranks high to low, voids as a dash. -->
<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, value, type Card, type Suit } from '../engine/card';

  let { seat, role, hand }: { seat: string; role: string; hand: Card[] } = $props();
  const roleCls = $derived(role === 'Declarer' ? 'is-declarer' : role === 'Dummy' ? 'is-dummy' : '');
  const SUITS: Suit[] = ['S', 'H', 'D', 'C'];
  const ranks = (s: Suit) =>
    hand.filter((c) => c.suit === s).sort((a, b) => value(b) - value(a)).map((c) => c.rank).join('') || '—';
</script>

<div class="seat-box">
  <div class="seat-box-head">
    <span class="seat-letter">{seat[0]}</span>
    <span class="seat-box-name">{seat}</span>
    <span class="seat-box-role {roleCls}">{role}</span>
  </div>
  <div class="hand-diagram">
    {#each SUITS as s}
      <div class="hd-line">
        <span class="hd-suit" style:color="var(--suit-{s.toLowerCase()})" aria-hidden="true">{SUIT_SYMBOLS[s]}</span>
        <span class="sr-only">{SUIT_NAMES[s]}: </span>
        <span class="hd-ranks">{ranks(s)}</span>
      </div>
    {/each}
  </div>
</div>
