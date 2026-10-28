<!-- The headline: you against the robots on this board. -->
<script lang="ts">
  import type { ChallengeResult } from '../game.svelte';
  import { signed } from './format';

  let { result }: { result: ChallengeResult } = $props();
  const margin = $derived(result.margin);
  const verdict = $derived(
    margin > 0 ? [`You beat the robots by ${margin}`, 'won']
      : margin < 0 ? [`The robots beat you by ${-margin}`, 'lost']
        : ['Dead level with the robots', 'level']);
</script>

<div class="challenge-verdict is-{verdict[1]}">{verdict[0]}</div>
<div class="metrics">
  <div class="metric"><div class="metric-label">You</div><div class="metric-value">{signed(result.you.actual)}</div></div>
  <div class="metric">
    <div class="metric-label">Robots</div>
    <div class="metric-value">{signed(result.robot.actual)}</div>
  </div>
  <div class="metric" title="The most this deal offered your side with perfect bidding and perfect play. It ignores whether the opponents would have competed over it, so treat it as a ceiling rather than a score anyone could guarantee.">
    <div class="metric-label">Par ⓘ</div>
    <div class="metric-value">{signed(result.you.par.score)}</div>
  </div>
</div>
