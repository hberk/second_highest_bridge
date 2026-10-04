<script lang="ts">
  import { Game } from './lib/game.svelte';
  import { settings, DECK_HELP, DECK_LABELS, type DeckName } from './lib/settings.svelte';
  import TableView from './lib/views/TableView.svelte';
  import ChallengeView from './lib/views/ChallengeView.svelte';
  import HistoryView from './lib/views/HistoryView.svelte';

  const game = new Game();
  let tab = $state<'table' | 'challenge' | 'history'>('table');

  $effect(() => {
    settings.applyDeck();
    settings.save();
  });

  const n = $derived(game.history.length);
  const tabs = $derived([
    ['table', '🎮 Bridge Table'],
    ['challenge', `⚔️ Challenge${game.challengeLog.length ? ` (${game.challengeLog.length})` : ''}`],
    ['history', `📜 Hand History (${n} board${n === 1 ? '' : 's'})`],
  ] as const);
  const decks: DeckName[] = ['four', 'classic'];
</script>

<div class="page">
  <div class="masthead-row">
    <div class="masthead">
      <span class="masthead-title"><span class="pip">♠</span> Second-Highest Bridge</span>
      <span class="masthead-sub">Second-highest card takes the trick</span>
    </div>
    <details class="settings">
      <summary>Display ▾</summary>
      <div class="settings-panel">
        <fieldset>
          <legend>Card deck</legend>
          {#each decks as d}
            <label><input type="radio" name="deck" value={d} bind:group={settings.deck} /> {DECK_LABELS[d]}</label>
          {/each}
          <p class="caption">{DECK_HELP[settings.deck]}</p>
        </fieldset>
        <label title="Off: hands always read spades, hearts, diamonds, clubs, as in a printed hand record. On: the trump suit moves to the left once play starts.">
          <input type="checkbox" bind:checked={settings.trumpFirst} /> Sort trump suit first
        </label>
        <label title="High-card points, this variant's own valuation, and your shape.">
          <input type="checkbox" bind:checked={settings.showStrength} /> Show hand strength
        </label>
        <label><input type="checkbox" bind:checked={settings.showAll} /> Show all hands (X-ray)</label>
      </div>
    </details>
  </div>

  <div class="tabs" role="tablist">
    {#each tabs as [id, label]}
      <button class="tab" role="tab" aria-selected={tab === id} onclick={() => (tab = id)}>{label}</button>
    {/each}
  </div>

  <div role="tabpanel">
    {#if tab === 'table'}
      <TableView {game} />
    {:else if tab === 'challenge'}
      <ChallengeView {game} ondealt={() => (tab = 'table')} />
    {:else}
      <HistoryView records={game.history} />
    {/if}
  </div>
</div>
