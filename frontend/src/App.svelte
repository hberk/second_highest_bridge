<script lang="ts">
  import { untrack } from 'svelte';
  import { Game, type HistoryRecord } from './lib/game.svelte';
  import { Trainer } from './lib/trainer.svelte';
  import { settings } from './lib/settings.svelte';
  import HomeView from './lib/views/HomeView.svelte';
  import TableView from './lib/views/TableView.svelte';
  import TrainerView from './lib/views/TrainerView.svelte';
  import DesktopTableView from './lib/views/DesktopTableView.svelte';
  import DeskHeader from './lib/components/DeskHeader.svelte';
  import { viewport } from './lib/viewport.svelte';
  import ChallengeView from './lib/views/ChallengeView.svelte';
  import HistoryView from './lib/views/HistoryView.svelte';
  import HowToPlayView from './lib/views/HowToPlayView.svelte';
  import TopBar from './lib/components/TopBar.svelte';
  import TabStrip from './lib/components/TabStrip.svelte';
  import Sheet from './lib/components/Sheet.svelte';
  import SettingsPanel from './lib/components/SettingsPanel.svelte';

  type Screen = 'home' | 'table' | 'training' | 'challenge' | 'history' | 'howto';
  const SCREENS: Screen[] = ['home', 'table', 'training', 'challenge', 'history', 'howto'];
  const TITLES: Record<string, string> = {
    challenge: 'Challenge the robots', history: 'Hand history', howto: 'How to play',
  };

  const game = new Game();
  const trainer = new Trainer();

  // The screen follows the address (#table, #history, ...), so the browser's
  // back button and the phone's back swipe move between screens.
  const fromHash = (): Screen => {
    const s = location.hash.slice(1) as Screen;
    return SCREENS.includes(s) ? s : 'home';
  };
  let screen = $state<Screen>(fromHash());
  let settingsOpen = $state(false);

  function go(s: Screen): void {
    if (s === screen) return;
    screen = s;
    // A sandboxed frame may refuse history changes; the screen changes anyway.
    try {
      if (s === 'home') history.pushState(null, '', location.pathname + location.search);
      else location.hash = s;
    } catch { /* no back-button support here */ }
    window.scrollTo(0, 0);
  }

  $effect(() => {
    settings.applyDeck();
    settings.save();
  });
  // Reacts to the setting only; switching it on mid-trick plays a card that
  // is already forced.
  $effect(() => {
    const on = settings.autoPlay;
    untrack(() => {
      game.autoPlayForced = on;
      if (on) game.resumeAutoPlay();
    });
  });
</script>

<svelte:window onpopstate={() => (screen = fromHash())} onhashchange={() => (screen = fromHash())} />

{#snippet section()}
  {#if screen === 'training'}
    <TrainerView {trainer} />
  {:else if screen === 'challenge'}
    <ChallengeView {game} ondealt={() => go('table')} />
  {:else if screen === 'howto'}
    <HowToPlayView />
  {:else}
    <HistoryView records={game.history} analysis onimport={(boards: HistoryRecord[]) => game.importBoards(boards)} />
  {/if}
{/snippet}

{#if screen === 'home'}
  <HomeView {game} onplay={() => go('table')} ontraining={() => go('training')} onchallenge={() => go('challenge')}
    onhowto={() => go('howto')} onhistory={() => go('history')} onsettings={() => (settingsOpen = true)} />
{:else if viewport.wide}
  <!-- A wide screen: the header with every section a tab away, and the
       desktop table with everything on screen. -->
  <div class="dk-app">
    <DeskHeader {screen} {game} onnav={go} />
    {#if screen === 'table'}
      <DesktopTableView {game} />
    {:else}
      <main class="page dk-page">{@render section()}</main>
    {/if}
  </div>
{:else if screen === 'table'}
  <div class="tabbed-table">
    <TabStrip {screen} {game} onnav={go} />
    <div class="tabbed"><TableView {game} onsettings={() => (settingsOpen = true)} /></div>
  </div>
{:else if screen === 'training'}
  <div class="tabbed-table">
    <TabStrip {screen} {game} onnav={go} />
    <div class="tabbed"><TrainerView {trainer} /></div>
  </div>
{:else if screen !== 'howto'}
  <div class="screen">
    <TabStrip {screen} {game} onnav={go} />
    <main class="page">{@render section()}</main>
  </div>
{:else}
  <div class="screen">
    <TopBar title={TITLES[screen]} onback={() => go('home')} />
    <main class="page">{@render section()}</main>
  </div>
{/if}

<Sheet open={settingsOpen} title="Settings" onclose={() => (settingsOpen = false)}>
  <SettingsPanel {game} />
</Sheet>
