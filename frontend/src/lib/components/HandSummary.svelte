<!-- HCP for orientation beside this variant's own valuation, which is the
     better guide here. -->
<script lang="ts">
  import type { Card } from '../engine/card';
  import { evalHandSh, hcp } from '../engine/ai';

  let { hand }: { hand: Card[] } = $props();
  const ev = $derived(evalHandSh(hand));
  // Python's {:g}: six significant digits, trailing zeros dropped.
  const g = (x: number) => String(Number(x.toPrecision(6)));
</script>

<div class="hand-summary">
  <span>HCP <strong>{hcp(hand)}</strong></span>
  <span class="hs-sep">|</span>
  <span>2nd-highest value <strong>{g(ev.total_pts)}</strong></span>
  <span class="hs-sep">|</span>
  <span>Shape <strong>{ev.lengths.join('-')}</strong></span>
</div>
