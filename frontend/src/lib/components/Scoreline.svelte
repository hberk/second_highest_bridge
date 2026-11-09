<!-- The headline: you against the robots on this board. -->
<script lang="ts">
  import type { ChallengeResult } from '../game.svelte';
  import { ddTricks } from '../engine/challenge';
  import { signed } from './format';
  import Strain from './Strain.svelte';

  let { result }: { result: ChallengeResult } = $props();
  const margin = $derived(result.margin);
  const verdict = $derived(
    margin > 0 ? [`You beat the robots by ${margin}`, 'won']
      : margin < 0 ? [`The robots beat you by ${-margin}`, 'lost']
        : ['Dead level with the robots', 'level']);
  const par = $derived(result.you.par);
  // Who declares par: the partner who takes par's tricks, or the side when
  // both partners take them.
  const parBy = $derived.by(() => {
    if (!par.strain || !par.side) return '';
    const seats = par.side === 'N/S' ? ['North', 'South'] as const : ['East', 'West'] as const;
    const makers = seats.filter((s) => ddTricks(result.deal_id, par.strain!, par.side!, s) === par.tricks);
    return makers.length === 1 ? makers[0][0] : par.side;
  });
</script>

<div class="challenge-verdict is-{verdict[1]}">{verdict[0]}</div>
<div class="metrics">
  <div class="metric"><div class="metric-label">You</div><div class="metric-value">{signed(result.you.actual)}</div></div>
  <div class="metric">
    <div class="metric-label">Robots</div>
    <div class="metric-value">{signed(result.robot.actual)}</div>
  </div>
  <div class="metric">
    <div class="metric-label">Par</div>
    <div class="metric-value">{signed(par.score)}
      <span class="par-contract">({#if par.strain}<Strain level={par.level} strain={par.strain} />{par.doubled === 'X' ? 'X' : ''} by {parBy}{:else}pass{/if})</span>
    </div>
  </div>
</div>

<style>
  .par-contract { font-size: 0.85rem; font-weight: 700; color: var(--dim); }
</style>
