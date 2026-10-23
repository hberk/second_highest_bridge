<!-- Where the points went: the auction, or the cards. -->
<script lang="ts">
  import type { ChallengeResult } from '../game.svelte';
  import { contractLabel, signed } from './format';
  import { solvedDeclarer } from '../engine/challenge';
  import type { Contract } from '../engine/auction';

  let { result }: { result: ChallengeResult } = $props();
  const rows = $derived([
    ['Contract reached',
      contractLabel(result.you.passed_out ? null : result.your_contract),
      contractLabel(result.robot_contract)],
    ['Lost in the auction', signed(-result.you.bidding_loss), signed(-result.robot.bidding_loss)],
    ['Lost in the card play', signed(-result.you.play_loss), signed(-result.robot.play_loss)],
    ['Final score', signed(result.you.actual), signed(result.robot.actual)],
  ]);
  /** The library knows one partner's double dummy count per strain and side;
   *  when the other partner declared, the grade may be a trick out. */
  const mismatch = (who: string, c: Contract | null) => {
    if (!c) return null;
    const solved = solvedDeclarer(result.deal_id, c.strain, c.side);
    return solved === c.declarer ? null : `${who} declared from ${c.declarer}, but this deal was solved with ${solved} declaring, so the split may be a trick out.`;
  };
  const notes = $derived([
    result.you.passed_out ? null : mismatch('Your side', result.your_contract),
    mismatch('The robots', result.robot_contract),
  ].filter((n) => n !== null));
</script>

<div class="section-title">Where the points went</div>
<table class="challenge-table">
  <thead><tr><th></th><th>You</th><th>Robots</th></tr></thead>
  <tbody>
    {#each rows as [label, mine, theirs]}<tr><th>{label}</th><td>{mine}</td><td>{theirs}</td></tr>{/each}
  </tbody>
</table>
{#each notes as n}<p class="caption">{n}</p>{/each}
<p class="caption">A loss is points given away against par. The two add up to the whole gap exactly, so they separate bidding judgement from card play.</p>
