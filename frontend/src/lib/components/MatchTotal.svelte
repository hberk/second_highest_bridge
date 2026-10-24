<!-- Running totals across every challenge board this session. -->
<script lang="ts">
  import type { ChallengeLogEntry } from '../game.svelte';
  import { signed } from './format';

  let { log }: { log: ChallengeLogEntry[] } = $props();
  const n = $derived(log.length);
  const sum = (f: (r: ChallengeLogEntry) => number) => log.reduce((a, r) => a + f(r), 0);
  const you = $derived(sum((r) => r.you));
  const robot = $derived(sum((r) => r.robot));
  const won = $derived(log.filter((r) => r.margin > 0).length);
  const drawn = $derived(log.filter((r) => r.margin === 0).length);
  const mean = (f: (r: ChallengeLogEntry) => number) => (sum(f) / n).toFixed(0);
</script>

{#if n}
  <div class="section-title">Match</div>
  <div class="metrics">
    <div class="metric"><div class="metric-label">Boards</div><div class="metric-value">{n}</div></div>
    <div class="metric"><div class="metric-label">Your total</div><div class="metric-value">{signed(you)}</div></div>
    <div class="metric"><div class="metric-label">Robot total</div><div class="metric-value">{signed(robot)}</div></div>
    <div class="metric"><div class="metric-label">Margin</div><div class="metric-value">{signed(you - robot)}</div></div>
  </div>
  <p class="caption">Won {won}, drew {drawn}, lost {n - won - drawn}. Across the library the robots give away a mean of 241 points a board in the auction, and about 4 in the play — the auction is where they are beatable.</p>
  <table class="challenge-table">
    <thead><tr><th>Mean loss per board</th><th>You</th><th>Robots</th></tr></thead>
    <tbody>
      <tr><th>Auction</th><td>{mean((r) => r.your_bidding_loss)}</td><td>{mean((r) => r.robot_bidding_loss)}</td></tr>
      <tr><th>Card play</th><td>{mean((r) => r.your_play_loss)}</td><td>{mean((r) => r.robot_play_loss)}</td></tr>
    </tbody>
  </table>
{/if}
