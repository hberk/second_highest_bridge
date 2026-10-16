<!-- Display preferences and the saved games on this device. -->
<script lang="ts">
  import type { Game } from '../game.svelte';
  import { settings, DECK_HELP, DECK_LABELS, type DeckName } from '../settings.svelte';

  let { game }: { game: Game } = $props();

  const n = $derived(game.history.length);
  const decks: DeckName[] = ['four', 'classic'];

  function clearSaved() {
    if (confirm('Delete every saved board and challenge result in this browser? This cannot be undone.')) game.clearSaved();
  }
</script>

<div class="settings-list">
  <fieldset>
    <legend>Card deck</legend>
    {#each decks as d}
      <label class="setting"><input type="radio" name="deck" value={d} bind:group={settings.deck} /> {DECK_LABELS[d]}</label>
    {/each}
    <p class="caption">{DECK_HELP[settings.deck]}</p>
  </fieldset>
  <fieldset>
    <legend>At the table</legend>
    <label class="setting">
      <input type="checkbox" bind:checked={settings.showStrength} />
      <span>Show hand strength<small>Your points and shape, while you bid.</small></span>
    </label>
    <label class="setting">
      <input type="checkbox" bind:checked={settings.trumpFirst} />
      <span>Sort trump suit first<small>Off, hands read spades, hearts, diamonds, clubs.</small></span>
    </label>
    <label class="setting">
      <input type="checkbox" bind:checked={settings.autoPlay} />
      <span>Auto-play forced cards<small>Your only legal card is played for you.</small></span>
    </label>
    <label class="setting">
      <input type="checkbox" bind:checked={settings.fastPlay} />
      <span>Fast play<small>The next trick starts by itself.</small></span>
    </label>
    <label class="setting">
      <input type="checkbox" bind:checked={settings.showAll} />
      <span>Show all hands<small>X-ray: every hand face up.</small></span>
    </label>
  </fieldset>
  <fieldset>
    <legend>Saved on this device</legend>
    <p class="caption">
      {n} board{n === 1 ? '' : 's'}{game.challengeLog.length ? `, ${game.challengeLog.length} challenge${game.challengeLog.length === 1 ? '' : 's'}` : ''}.
      Kept in this browser only; download them from Hand history as a backup.
    </p>
    <button class="btn" disabled={!n && !game.challengeLog.length && !game.passedOutCount} onclick={clearSaved}>Clear saved games</button>
  </fieldset>
</div>
