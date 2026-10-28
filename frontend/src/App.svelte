<script lang="ts">
  import { untrack } from 'svelte';
  import { Game, type HistoryRecord } from './lib/game.svelte';
  import { settings } from './lib/settings.svelte';
  import HomeView from './lib/views/HomeView.svelte';
  import TableView from './lib/views/TableView.svelte';
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
  import RemoteView from './lib/views/RemoteView.svelte';
  import { RemoteTable } from './lib/table/remote.svelte';
  import { TABLE_ID_RE } from './lib/table/protocol';

  type Screen = 'home' | 'table' | 'challenge' | 'history' | 'howto' | 'remote';
  const SCREENS: Screen[] = ['home', 'table', 'challenge', 'history', 'howto'];
  const TITLES: Record<string, string> = {
    challenge: 'Challenge the robots', history: 'Hand history', howto: 'How to play',
  };
  /** Multiplayer tables: only the beta build (`vite --mode beta`) has a
   *  table server behind it. The Pages build never opens a socket. */
  const TABLES = import.meta.env.VITE_TABLES === '1';

  const game = new Game();

  // The screen follows the address (#table, #history, ...), so the browser's
  // back button and the phone's back swipe move between screens. A table is
  // #/t/<id>: the link friends are sent.
  const tableFromHash = (): string | null => {
    const m = /^#\/t\/(.+)$/.exec(location.hash);
    return TABLES && m && TABLE_ID_RE.test(m[1]) ? m[1] : null;
  };
  const fromHash = (): Screen => {
    if (tableFromHash()) return 'remote';
    const s = location.hash.slice(1) as Screen;
    return SCREENS.includes(s) ? s : 'home';
  };
  let screen = $state<Screen>(fromHash());
  let tableId = $state<string | null>(tableFromHash());
  let settingsOpen = $state(false);
  let creating = $state(false);
  let createError = $state<string | null>(null);

  /** The table open now; closed when you leave it. */
  let remote = $state.raw<RemoteTable | null>(null);
  $effect(() => {
    const id = screen === 'remote' ? tableId : null;
    if (!id) return;
    const t = untrack(() => new RemoteTable(id, {
      storage: (() => { try { return localStorage; } catch { return null; } })(),
      // Finished boards go into Hand history, like solo boards.
      onfinished: (record) => game.importBoards([record]),
    }));
    remote = t;
    return () => {
      t.dispose();
      remote = null;
    };
  });

  function onHash(): void {
    screen = fromHash();
    tableId = tableFromHash();
  }

  async function playWithFriends(): Promise<void> {
    if (creating) return;
    creating = true;
    createError = null;
    try {
      const res = await fetch('tables', { method: 'POST' });
      const body = await res.json() as { id?: string; error?: string };
      if (!res.ok || !body.id) throw new Error(body.error ?? 'The table server said no.');
      location.hash = `/t/${body.id}`;
    } catch (e) {
      createError = e instanceof Error ? e.message : 'Could not reach the table server.';
    } finally {
      creating = false;
    }
  }

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

<svelte:window onpopstate={onHash} onhashchange={onHash} />

{#snippet section()}
  {#if screen === 'challenge'}
    <ChallengeView {game} ondealt={() => go('table')} />
  {:else if screen === 'howto'}
    <HowToPlayView />
  {:else}
    <HistoryView records={game.history} analysis onimport={(boards: HistoryRecord[]) => game.importBoards(boards)} />
  {/if}
{/snippet}

{#if screen === 'home'}
  <HomeView {game} onplay={() => go('table')} onchallenge={() => go('challenge')}
    onhowto={() => go('howto')} onhistory={() => go('history')} onsettings={() => (settingsOpen = true)}
    onfriends={TABLES ? playWithFriends : undefined} />
  {#if createError}<div class="notice error rt-create-error" role="alert">{createError}</div>{/if}
{:else if screen === 'remote'}
  {#if remote}<RemoteView table={remote} onhome={() => go('home')} onsettings={() => (settingsOpen = true)} />{/if}
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
