<script lang="ts">
  import { SUIT_NAMES, SUIT_SYMBOLS, type Card } from '../engine/card';

  let { card }: { card: Card } = $props();
  const ink = $derived(`var(--suit-${card.suit.toLowerCase()})`);
</script>

<div class="pcard">
  <span class="pcard-rank" style:color={ink}>{card.rank}</span>
  <span class="pcard-suit" style:color={ink} aria-hidden="true">{SUIT_SYMBOLS[card.suit]}</span>
  <span class="sr-only"> of {SUIT_NAMES[card.suit]}</span>
</div>
