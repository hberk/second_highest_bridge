<!-- Where the points went: the auction, or the cards. -->
<script lang="ts">
  import type { ChallengeResult } from '../game.svelte';
  import { contractLabel, signed } from './format';

  let { result }: { result: ChallengeResult } = $props();
  const rows = $derived([
    ['Contract',
      contractLabel(result.you.passed_out ? null : result.your_contract),
      contractLabel(result.robot_contract)],
    ['Auction', signed(-result.you.bidding_loss), signed(-result.robot.bidding_loss)],
    ['Card play', signed(-result.you.play_loss), signed(-result.robot.play_loss)],
  ]);
</script>

<div class="section-title">Where the points went</div>
<table class="challenge-table">
  <thead><tr><th></th><th>You</th><th>Robots</th></tr></thead>
  <tbody>
    {#each rows as [label, mine, theirs]}<tr><th>{label}</th><td>{mine}</td><td>{theirs}</td></tr>{/each}
  </tbody>
</table>
