<!-- Challenge the robots: a board from the solved library, graded against
     the same deal played by an all-robot table. -->
<script lang="ts">
  import { dealIds } from '../engine/challenge';
  import { PLAYERS } from '../engine/auction';
  import type { Game, HistoryRecord } from '../game.svelte';
  import HistoryView from './HistoryView.svelte';
  import MatchTotal from '../components/MatchTotal.svelte';

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
    return [...(yours ? [{ ...yours, label: '🧑 Your board' }] : []), last.robot_record];
  });

  function deal() {
    if (game.dealChallenge()) ondealt();
  }
</script>

<p>A challenge board is dealt from the <strong>{ids.length} deals this project has solved exactly</strong>, so whatever contract you reach, the number of tricks it takes with perfect play on both sides is already known. You play South; the same deal is then played out by an all-robot table, and the two results are compared.</p>
<p>Because every contract can be priced against perfect play, the gap splits in two: what the <strong>auction</strong> cost and what the <strong>card play</strong> cost. Those are separate skills, and the robots are far better at one than the other.</p>

<div class="masthead-row" style="justify-content: flex-start">
  <button class="btn primary" disabled={!remaining} onclick={deal}>Deal a challenge board →</button>
  <span class="caption">{remaining} of {ids.length} solved boards unplayed. Finish the board at the table, then come back here for the comparison.</span>
</div>

{#if game.challengeId !== null && !game.boardOver}
  <div class="notice info">A challenge board is in play at the <strong>table</strong>. Finish it to see how the robots did with the same cards.</div>
{/if}

{#if records.length}
  <hr />
  <h3>Review the deal</h3>
  <p class="caption">Both boards, the same 52 cards. Switch between them to see where the auctions diverged and which card turned the play. Hover any robot call for what it was supposed to show.</p>
  <HistoryView {records} />
{/if}

<MatchTotal log={game.challengeLog} />
