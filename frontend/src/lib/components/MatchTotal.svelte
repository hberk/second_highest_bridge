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
  const mean = (f: (r: ChallengeLogEntry) => number) => signed(-Math.round(sum(f) / n));
</script>

{#if n}
  <section class="res-card match">
    <div class="m-head">
      <span class="eyebrow">Match · {n} {n === 1 ? 'board' : 'boards'}</span>
      <span class="caption">Won {won} · drew {drawn} · lost {n - won - drawn}</span>
    </div>
    <table class="m-table">
      <thead><tr><th></th><th>You</th><th>Robots</th></tr></thead>
      <tbody>
        <tr class="m-total"><th>Total</th><td>{signed(you)}</td><td>{signed(robot)}</td></tr>
        <tr><th>Auction / board</th><td>{mean((r) => r.your_bidding_loss)}</td><td>{mean((r) => r.robot_bidding_loss)}</td></tr>
        <tr><th>Card play / board</th><td>{mean((r) => r.your_play_loss)}</td><td>{mean((r) => r.robot_play_loss)}</td></tr>
      </tbody>
    </table>
  </section>
{/if}

<style>
  .match { padding: 12px 14px 8px; justify-items: stretch; text-align: left; gap: 0; }
  .m-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 4px; }
  .m-table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; table-layout: fixed; }
  .m-table th, .m-table td { padding: 7px 0; text-align: right; border-bottom: 1px solid rgba(231, 235, 238, 0.1); }
  .m-table th:first-child { width: 44%; text-align: left; }
  .m-table thead th {
    font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--dim);
    border-bottom: 1px solid rgba(231, 235, 238, 0.25);
  }
  .m-table tbody th { font-weight: 500; color: var(--dim); font-size: 0.9rem; }
  .m-table tbody tr:last-child th, .m-table tbody tr:last-child td { border-bottom: none; }
  .m-total td { font-size: 1.1rem; font-weight: 800; }
</style>
