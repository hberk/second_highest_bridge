<!-- A seat beside the felt on the desktop table: who sits there, their part in
     the board, and their cards, face down unless X-ray shows them. -->
<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, type Card, type Seat } from '../engine/card';
  import { grouped } from './hand';

  let { seat, role, count, cards = null, trump = null }: {
    seat: Seat;
    role: string;
    count: number;
    /** Face-up cards, or null for a concealed hand. */
    cards?: Card[] | null;
    trump?: string | null;
  } = $props();
</script>

<section class="seat-card" aria-label={seat}>
  <div>
    <div class="seat-card-name">{seat}</div>
    <div class="seat-card-role">{role}</div>
  </div>
  {#if cards}
    <div class="seat-card-lines">
      {#each grouped(cards, trump) as [suit, cs] (suit)}
        <div><span style:color="var(--suit-{suit.toLowerCase()}-lt)" aria-hidden="true">{SUIT_SYMBOLS[suit]}</span><span class="sr-only">{SUIT_NAMES[suit]}: </span> {cs.map((c) => c.rank).join(' ')}</div>
      {/each}
    </div>
  {:else if count}
    <div class="seat-card-backs" aria-hidden="true">{#each { length: count } as _}<span></span>{/each}</div>
  {/if}
  <div class="seat-card-count"><strong>{count} card{count === 1 ? '' : 's'}</strong>{cards ? '' : ' · concealed'}</div>
</section>
