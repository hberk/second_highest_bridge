<!-- A challenge board's result on one card: the verdict, then you, the robots
     and par side by side (score, contract, and where the points went). -->
<script lang="ts">
  import type { ChallengeResult } from '../game.svelte';
  import type { Contract } from '../engine/auction';
  import { ddTricks } from '../engine/challenge';
  import { STRAIN_SYMBOLS } from '../engine/card';
  import { signed } from './format';

  let { result }: { result: ChallengeResult } = $props();
  const margin = $derived(result.margin);
  const verdict = $derived(
    margin > 0 ? [`You beat the robots by ${margin}`, 'won']
      : margin < 0 ? [`The robots beat you by ${-margin}`, 'lost']
        : ['Dead level with the robots', 'level']);
  const par = $derived(result.you.par);

  const short = (c: Contract | null) =>
    c ? `${c.level}${STRAIN_SYMBOLS[c.strain]}${c.doubled === 'None' ? '' : c.doubled} ${c.declarer[0]}` : 'Pass';
  // Who declares par: the partner who takes par's tricks, or the side when
  // both partners take them.
  const parContract = $derived.by(() => {
    if (!par.strain || !par.side) return 'Pass';
    const seats = par.side === 'N/S' ? ['North', 'South'] as const : ['East', 'West'] as const;
    const makers = seats.filter((s) => ddTricks(result.deal_id, par.strain!, par.side!, s) === par.tricks);
    const by = makers.length === 1 ? makers[0][0] : par.side;
    return `${par.level}${STRAIN_SYMBOLS[par.strain]}${par.doubled === 'X' ? 'X' : ''} ${by}`;
  });
</script>

<section class="res-card scorecard">
  <div class="challenge-verdict is-{verdict[1]}">{verdict[0]}</div>
  <table class="sc-table">
    <thead><tr><th></th><th>You</th><th>Robots</th><th>Par</th></tr></thead>
    <tbody>
      <tr class="sc-score">
        <th>Score</th>
        <td>{signed(result.you.actual)}</td><td>{signed(result.robot.actual)}</td><td>{signed(par.score)}</td>
      </tr>
      <tr>
        <th>Contract</th>
        <td>{short(result.you.passed_out ? null : result.your_contract)}</td>
        <td>{short(result.robot_contract)}</td>
        <td>{parContract}</td>
      </tr>
      <tr><th>Auction</th><td>{signed(-result.you.bidding_loss)}</td><td>{signed(-result.robot.bidding_loss)}</td><td></td></tr>
      <tr><th>Card play</th><td>{signed(-result.you.play_loss)}</td><td>{signed(-result.robot.play_loss)}</td><td></td></tr>
    </tbody>
  </table>
</section>

<style>
  .scorecard { padding: 12px 14px 8px; justify-items: stretch; text-align: left; gap: 0; }
  .scorecard .challenge-verdict { margin: 0 0 6px; }
  .sc-table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; table-layout: fixed; }
  .sc-table th, .sc-table td { padding: 7px 0; text-align: right; border-bottom: 1px solid rgba(231, 235, 238, 0.1); }
  .sc-table th:first-child { width: 26%; text-align: left; }
  .sc-table thead th {
    font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--dim);
    border-bottom: 1px solid rgba(231, 235, 238, 0.25);
  }
  .sc-table tbody th { font-weight: 500; color: var(--dim); font-size: 0.9rem; }
  .sc-table tbody tr:last-child th, .sc-table tbody tr:last-child td { border-bottom: none; }
  .sc-score td { font-size: 1.35rem; font-weight: 800; }
  .sc-table thead th:last-child, .sc-table tbody td:last-child { color: var(--dim); }
</style>
