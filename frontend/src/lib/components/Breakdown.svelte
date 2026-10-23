<!-- Where the points went: the auction, or the cards. -->
<script lang="ts">
  import type { ChallengeResult } from '../game.svelte';
  import { contractLabel, signed } from './format';

  let { result }: { result: ChallengeResult } = $props();
  const rows = $derived([
    ['Contract reached',
      contractLabel(result.you.passed_out ? null : result.your_contract),
      contractLabel(result.robot_contract)],
    ['Lost in the auction', signed(-result.you.bidding_loss), signed(-result.robot.bidding_loss)],
    ['Lost in the card play', signed(-result.you.play_loss), signed(-result.robot.play_loss)],
    ['Final score', signed(result.you.actual), signed(result.robot.actual)],
  ]);
</script>

<div class="section-title">Where the points went</div>
<table class="challenge-table">
  <thead><tr><th></th><th>You</th><th>Robots</th></tr></thead>
  <tbody>
    {#each rows as [label, mine, theirs]}<tr><th>{label}</th><td>{mine}</td><td>{theirs}</td></tr>{/each}
  </tbody>
</table>
<p class="caption">A loss is points given away against par. The two add up to the whole gap exactly, so they separate bidding judgement from card play.</p>
