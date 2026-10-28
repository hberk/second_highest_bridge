<!-- Challenge the robots: a board from the solved library, graded against
     the same deal played by an all-robot table. -->
<script lang="ts">
  import { dealIds } from '../engine/challenge';
  import { PLAYERS } from '../engine/auction';
  import type { Game, HistoryRecord } from '../game.svelte';
  import HistoryView from './HistoryView.svelte';
  import MatchTotal from '../components/MatchTotal.svelte';
  import Scoreline from '../components/Scoreline.svelte';
  import Breakdown from '../components/Breakdown.svelte';

  let { game, ondealt }: { game: Game; ondealt: () => void } = $props();

  const ids = dealIds();
  const remaining = $derived(ids.length - new Set(game.challengeLog.map((r) => r.deal_id)).size);
  const last = $derived(game.challenge);
  const records = $derived.by((): HistoryRecord[] => {
    if (!last) return [];
    // The board number alone is not enough: an imported LIN takes its number
    // from the file, so match the deal and skip imports.
    const deal = last.robot_record.initial_hands;
    const sameDeal = (h: HistoryRecord) =>
      PLAYERS.every((p) => JSON.stringify(h.initial_hands[p]) === JSON.stringify(deal[p]));
    const yours = game.history.findLast((h) => !h.imported && h.board_num === last.board_num && sameDeal(h))
      ?? last.your_record;
    return [...(yours ? [{ ...yours, label: 'Your board' }] : []), last.robot_record];
  });

  function deal() {
    // The board in play isn't saved half-played, so ask before dropping it.
    if (game.inProgress && !confirm('Leave the board in play? It won\'t be saved or scored, and a challenge deal goes back in the pool.')) return;
    if (game.dealChallenge()) ondealt();
  }
</script>

<div class="hv">
  <section class="res-card">
    <div class="eyebrow accent">Challenge the robots</div>
    <p class="res-detail">Play a solved deal, then compare with four robots on the same cards.</p>
    {#if game.challengeId !== null && !game.boardOver}
      <p class="res-detail hv-note">A challenge board is in play at the table.</p>
    {/if}
    <button class="btn primary full big" disabled={!remaining} onclick={deal}>Deal a challenge board</button>
    <p class="caption hv-center">{remaining} of {ids.length} unplayed</p>
  </section>

  {#if last}
    <div class="eyebrow hv-h">Last board</div>
    <Scoreline result={last} />
    <Breakdown result={last} />
  {/if}

  {#if records.length}
    <div class="eyebrow hv-h" id="challenge-review">Review the deal</div>
    <HistoryView {records} analysis />
  {/if}

  <MatchTotal log={game.challengeLog} />
</div>
