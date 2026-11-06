<!-- The headline: you against the robots on this board. -->
<script lang="ts">
  import type { ChallengeResult } from '../game.svelte';
  import { signed } from './format';
  import Strain from './Strain.svelte';

  let { result }: { result: ChallengeResult } = $props();
  const margin = $derived(result.margin);
  const verdict = $derived(
    margin > 0 ? [`You beat the robots by ${margin}`, 'won']
      : margin < 0 ? [`The robots beat you by ${-margin}`, 'lost']
        : ['Dead level with the robots', 'level']);
  const par = $derived(result.you.par);
  // A tap, not a hover title: phones have no hover.
  let showPar = $state(false);
</script>

<div class="challenge-verdict is-{verdict[1]}">{verdict[0]}</div>
<div class="metrics">
  <div class="metric"><div class="metric-label">You</div><div class="metric-value">{signed(result.you.actual)}</div></div>
  <div class="metric">
    <div class="metric-label">Robots</div>
    <div class="metric-value">{signed(result.robot.actual)}</div>
  </div>
  <button class="metric par-button" type="button" aria-expanded={showPar} aria-controls="par-note"
    onclick={() => (showPar = !showPar)}>
    <div class="metric-label">Par <span aria-hidden="true">ⓘ</span></div>
    <div class="metric-value">{signed(par.score)}</div>
  </button>
</div>
{#if showPar}
  <p class="par-note" id="par-note">
    Both sides bid and play perfectly:
    {#if par.strain}<Strain level={par.level} strain={par.strain} />{par.doubled === 'X' ? 'X' : ''} by {par.side}.{:else}passed out.{/if}
  </p>
{/if}

<style>
  .par-button {
    background: none; border: 0; color: inherit; font: inherit; text-align: left;
    cursor: pointer; -webkit-tap-highlight-color: transparent;
  }
  .par-note { margin: 4px 0 0; font-size: 0.9rem; color: var(--dim); }
</style>
