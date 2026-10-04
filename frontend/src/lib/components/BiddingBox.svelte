<!-- Every bid from 1C to 7NT as seven level rows by five strains, with Pass /
     Double / Redouble above. Bids no longer available stay visible, greyed, so
     the player can see how much room is left. -->
<script lang="ts">
  import { LEVELS, STRAINS, STRAIN_NAMES, STRAIN_SYMBOLS } from '../engine/card';

  let { legal, oncall }: { legal: string[]; oncall: (call: string) => void } = $props();
  const actions = [['Pass', 'Pass', 'pass'], ['Double', 'X', 'dbl'], ['Redouble', 'XX', 'rdbl']] as const;
</script>

<div class="bidding-box-container">
  <div class="bidding-box-title">Your call</div>
  <div class="bid-actions">
    {#each actions as [label, call, cls]}
      <button class="bid-btn {cls}" disabled={!legal.includes(call)} onclick={() => oncall(call)}>{label}</button>
    {/each}
  </div>
  <div class="bid-grid-head">
    {#each STRAINS as strain}<span class={strain.toLowerCase()} title={STRAIN_NAMES[strain]}>{STRAIN_SYMBOLS[strain]}</span>{/each}
  </div>
  <div class="bid-ladder">
    {#each LEVELS as level}
      {#each STRAINS as strain}
        {@const call = `${level}${strain}`}
        <button class="bid-btn {strain.toLowerCase()}" disabled={!legal.includes(call)} onclick={() => oncall(call)}
          aria-label="{level} {STRAIN_NAMES[strain]}">{level}{STRAIN_SYMBOLS[strain]}</button>
      {/each}
    {/each}
  </div>
</div>
