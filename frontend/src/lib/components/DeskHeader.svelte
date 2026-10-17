<!-- The desktop header: the name (back to the home page), a tab per section,
     and the Display menu with the settings. -->
<script lang="ts">
  import type { Game } from '../game.svelte';
  import SettingsPanel from './SettingsPanel.svelte';

  type Screen = 'home' | 'table' | 'challenge' | 'history' | 'howto';
  let { screen, game, onnav }: { screen: Screen; game: Game; onnav: (s: Screen) => void } = $props();

  const tabs = $derived([
    ['table', 'Bridge Table'],
    ['challenge', `Challenge${game.challengeLog.length ? ` (${game.challengeLog.length})` : ''}`],
    ['history', `Hand History (${game.history.length})`],
    ['howto', 'How to Play'],
  ] as const);

  let open = $state(false);
  let menu = $state<HTMLElement | null>(null);
</script>

<svelte:window
  onclick={(e) => { if (open && menu && !menu.contains(e.target as Node)) open = false; }}
  onkeydown={(e) => { if (open && e.key === 'Escape') open = false; }} />

<header class="dk-header">
  <button class="dk-brand" onclick={() => onnav('home')} aria-label="Second-Highest Bridge: home">
    <span class="dk-title"><span class="accent" aria-hidden="true">♠</span> Second-Highest Bridge</span>
    <span class="dk-sub">Second-highest card takes the trick</span>
  </button>
  <nav class="dk-tabs" aria-label="Sections">
    {#each tabs as [id, label] (id)}
      <button class="dk-tab" aria-current={screen === id ? 'page' : undefined} onclick={() => onnav(id)}>{label}</button>
    {/each}
  </nav>
  <div class="dk-display" bind:this={menu}>
    <button class="dk-display-btn" aria-expanded={open} aria-haspopup="true" onclick={() => (open = !open)}>
      Display
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg>
    </button>
    {#if open}<div class="dk-display-panel"><SettingsPanel {game} /></div>{/if}
  </div>
</header>
