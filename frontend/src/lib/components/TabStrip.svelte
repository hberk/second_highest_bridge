<!-- The phone's tabs: Play, Bidding training, Challenge and History one tap apart, in one slim
     row. The spade goes home; the question mark opens How to play. On
     Challenge and History it is the whole top bar, since the tab already says
     where you are; at the table it sits above the board's own bar. -->
<script lang="ts">
  import type { Game } from '../game.svelte';

  type Screen = 'home' | 'table' | 'training' | 'challenge' | 'history' | 'howto';
  let { screen, game, onnav }: { screen: Screen; game: Game; onnav: (s: Screen) => void } = $props();

  const tabs = $derived([
    ['table', 'Play', 0],
    // "Training" here: the full name (as on the home page) pushed the row
    // past a 360px phone.
    ['training', 'Training', 0],
    ['challenge', 'Challenge', game.challengeLog.length],
    ['history', 'History', game.history.length],
  ] as const);
</script>

<nav class="tabstrip" aria-label="Sections">
  <button class="ts-icon ts-brand" aria-label="Home" onclick={() => onnav('home')}>♠</button>
  <div class="ts-tabs">
    {#each tabs as [id, label, n] (id)}
      <button class="ts-tab" aria-current={screen === id ? 'page' : undefined} onclick={() => onnav(id)}>
        {label}{#if n}<span class="ts-count">{n}</span>{/if}
      </button>
    {/each}
  </div>
  <button class="ts-icon" aria-label="How to play" onclick={() => onnav('howto')}>?</button>
</nav>
