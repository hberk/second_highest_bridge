<!-- A multiplayer table: join with a name, take a seat, share the link, and
     play. The board itself is the ordinary table (TableView, or the desktop
     table on a wide screen) reading a RemoteTable; above it, a strip of who
     sits where, who is connected, and the buttons for a seat whose player
     has gone. -->
<script lang="ts">
  import type { Seat } from '../engine/card';
  import { viewport } from '../viewport.svelte';
  import { NAME_KEY, type RemoteTable } from '../table/remote.svelte';
  import { NAME_MAX, NOTE_MAX } from '../table/protocol';
  import { partnerOf, seatAt } from '../seats';
  import TopBar from '../components/TopBar.svelte';
  import Sheet from '../components/Sheet.svelte';
  import TableView from './TableView.svelte';
  import DesktopTableView from './DesktopTableView.svelte';

  let { table, onhome, onsettings = () => {} }:
    { table: RemoteTable; onhome: () => void; onsettings?: () => void } = $props();

  const SEATS: Seat[] = ['North', 'East', 'South', 'West'];
  const v = $derived(table.view);
  const you = $derived(v?.you ?? null);
  const board = $derived(v?.board ?? null);

  function savedName(): string {
    try { return localStorage.getItem(NAME_KEY) ?? ''; } catch { return ''; }
  }
  let name = $state(savedName());
  let copied = $state(false);

  const link = $derived(`${location.origin}${location.pathname}#/t/${table.tableId}`);

  async function share(): Promise<void> {
    const nav = navigator as Navigator & { share?: (d: ShareData) => Promise<void> };
    try {
      if (nav.share) {
        await nav.share({ title: 'Second-Highest Bridge', text: 'Join my table', url: link });
        return;
      }
    } catch { /* cancelled, or refused: fall back to copying */ }
    try {
      await navigator.clipboard.writeText(link);
      copied = true;
      setTimeout(() => (copied = false), 2500);
    } catch { /* no clipboard: the link is on screen to copy by hand */ }
  }

  // A phone that slept: reconnect as soon as it's back.
  $effect(() => {
    const wake = () => { if (document.visibilityState === 'visible') table.wake(); };
    document.addEventListener('visibilitychange', wake);
    window.addEventListener('online', wake);
    return () => {
      document.removeEventListener('visibilitychange', wake);
      window.removeEventListener('online', wake);
    };
  });

  function who(p: Seat): string {
    const s = v!.seats[p];
    if (p === you?.seat) return 'You';
    return s.name ?? 'Robot';
  }

  /** Seats in table order around you: you, left, partner, right. */
  const around = $derived(you?.seat
    ? [you.seat, seatAt(you.seat, 'left'), partnerOf(you.seat), seatAt(you.seat, 'right')]
    : SEATS);
  const myRobot = $derived(!!you?.seat && !!v?.seats[you.seat].robot);

  // ── Report a problem ───────────────────────────────────────────────────────
  // The note goes to the game log with what this page shows; the server adds
  // its own view of the moment. Nothing here is ever shown back in the app.
  const layout = $derived<'phone' | 'desktop'>(viewport.wide ? 'desktop' : 'phone');
  let reportOpen = $state(false);
  let note = $state('');
  let reportState = $state<'writing' | 'sent' | 'offline'>('writing');

  function openReport(): void {
    reportState = 'writing';
    reportOpen = true;
  }
  function sendReport(): void {
    if (table.report(note, layout)) {
      reportState = 'sent';
      note = '';
    } else reportState = 'offline';
  }

  // Errors this page hits while at the table go to the log too, so a bug
  // nobody reported still shows up there.
  $effect(() => {
    const onError = (e: ErrorEvent) =>
      table.oops(String(e.message || e.error || 'error'), `${e.filename ?? ''}:${e.lineno ?? 0} ${e.error?.stack ?? ''}`, layout);
    const onRejection = (e: PromiseRejectionEvent) =>
      table.oops(String(e.reason?.message ?? e.reason ?? 'rejection'), String(e.reason?.stack ?? ''), layout);
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => {
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onRejection);
    };
  });
</script>

{#snippet banner()}
  {#if table.status === 'reconnecting' || (table.status === 'connecting' && v)}
    <div class="rt-banner" role="status">Reconnecting…</div>
  {/if}
  {#if table.error}<div class="rt-banner rt-error" role="alert">{table.error}</div>{/if}
  {#if board?.phase === 'done' && you?.seat && v?.seats[you.seat].ready}
    <div class="rt-banner rt-info" role="status">You're ready. The next board deals when everyone is, or when the host deals.</div>
  {/if}
{/snippet}

{#snippet seatStrip()}
  <div class="rt-strip" aria-label="Who is at the table">
    {#each around as p (p)}
      {@const s = v!.seats[p]}
      <div class="rt-seat" class:rt-you={p === you?.seat}>
        <span class="rt-line">
          <span class="rt-dot" class:on={s.connected || s.robot} aria-hidden="true"></span>
          <span class="rt-name">{who(p)}</span>
        </span>
        <span class="rt-compass">{p[0]}{s.robot && s.name ? ' · robot' : ''}{board?.phase === 'done' && s.ready ? ' · ready' : ''}</span>
        {#if s.away && !s.robot && p !== you?.seat}
          <button class="chip-btn rt-chip" onclick={() => table.robot(p)}>Let a robot play</button>
        {/if}
      </div>
    {/each}
    <button class="icon-btn rt-flag" aria-label="Report a problem" title="Report a problem" onclick={openReport}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 21V4M5 4h11l-2 4 2 4H5"></path></svg>
    </button>
  </div>
  {#if myRobot}
    <button class="btn primary full" onclick={() => table.reclaim()}>A robot is playing your seat: take it back</button>
  {/if}
{/snippet}

{#if table.status === 'gone' || table.status === 'outdated' || table.status === 'removed'}
  <div class="screen">
    <TopBar title="Table" onback={onhome} />
    <main class="page rt-page">
      <section class="res-card">
        {#if table.status === 'gone'}
          <div class="res-verdict">This table no longer exists</div>
          <p class="res-detail">Tables close a week after anyone last played at them. Your finished boards are in Hand history.</p>
        {:else if table.status === 'outdated'}
          <div class="res-verdict">This page is out of date</div>
          <p class="res-detail">The table server has been updated. Reload the page to carry on.</p>
          <button class="btn primary full big" onclick={() => location.reload()}>Reload</button>
        {:else}
          <div class="res-verdict">You were removed from this table</div>
          <p class="res-detail">The host took you off the table.</p>
        {/if}
      </section>
    </main>
  </div>

{:else if !v || !you}
  <div class="screen">
    <TopBar title="Table" onback={onhome} />
    <main class="page rt-page"><p class="caption">Connecting to the table…</p></main>
  </div>

{:else if !you.playerId}
  <!-- ── Join ─────────────────────────────────────────────────────────────── -->
  <div class="screen">
    <TopBar title="Join the table" onback={onhome} />
    <main class="page rt-page">
      {@render banner()}
      <form class="rt-form" onsubmit={(e) => { e.preventDefault(); if (name.trim()) table.join(name.trim()); }}>
        <label class="eyebrow" for="rt-name">Your name at the table</label>
        <input id="rt-name" class="rt-input" bind:value={name} maxlength={NAME_MAX} autocomplete="nickname"
          placeholder="Name" />
        <button class="btn primary full big" type="submit" disabled={!name.trim() || v.locked}>Join</button>
        {#if v.locked}<p class="caption">The host has locked this table.</p>{/if}
      </form>
      <p class="caption">At the table: {SEATS.filter((p) => v.seats[p].name).map((p) => `${v.seats[p].name} (${p})`).join(', ') || 'nobody yet'}.</p>
    </main>
  </div>

{:else if !you.seat || !board}
  <!-- ── Seats and the lobby ──────────────────────────────────────────────── -->
  <div class="screen">
    <TopBar title="Your table" sub={v.locked ? 'Locked' : 'Open to anyone with the link'} onback={onhome} />
    <main class="page rt-page">
      {@render banner()}
      <section class="rt-seats" aria-label="Seats">
        {#each SEATS as p (p)}
          {@const s = v.seats[p]}
          <div class="rt-seatbox rt-{p.toLowerCase()}">
            <div class="eyebrow">{p}</div>
            {#if s.name}
              <div class="rt-occupant">{p === you.seat ? 'You' : s.name}<span class="rt-dot" class:on={s.connected} aria-hidden="true"></span></div>
            {:else if !board || board.phase === 'done'}
              <button class="chip-btn" onclick={() => table.sit(p)}>{you.seat ? 'Move here' : 'Sit here'}</button>
              <div class="caption">A robot if empty</div>
            {:else}
              <div class="caption">Robot</div>
            {/if}
          </div>
        {/each}
      </section>

      {#if you.seat}
        <section class="rt-share">
          <div class="eyebrow">Invite friends</div>
          <p class="caption">Anyone with this link can take an empty seat.</p>
          <div class="rt-link">{link}</div>
          <button class="btn ghost full" onclick={share}>{copied ? 'Link copied' : 'Share the link'}</button>
          {#if you.isHost}
            <button class="chip-btn" aria-pressed={v.locked} onclick={() => table.lock(!v.locked)}>
              {v.locked ? 'Locked: nobody new can join' : 'Lock the table'}
            </button>
          {/if}
        </section>
        {#if you.isHost}
          <button class="btn primary full big" onclick={() => table.newBoard()}>Deal the first board</button>
          <p class="caption">Empty seats are played by robots.</p>
        {:else}
          <p class="caption">Waiting for the host to deal.</p>
        {/if}
        <button class="link-btn" onclick={() => table.stand()}>Stand up</button>
        <button class="link-btn" onclick={openReport}>Report a problem</button>
      {:else}
        <p class="caption">Pick a seat. You can play alone with three robots, or with up to three friends.</p>
      {/if}
      {#if v.watching.length}<p class="caption">Watching: {v.watching.join(', ')}</p>{/if}
    </main>
  </div>

{:else}
  <!-- ── The board ────────────────────────────────────────────────────────── -->
  {#if viewport.wide}
    <div class="dk-app">
      <div class="rt-top">{@render banner()}{@render seatStrip()}</div>
      <DesktopTableView game={table} />
    </div>
  {:else}
    <!-- The solo table's frame, with the seat strip where its tabs go. -->
    <div class="tabbed-table">
      <div class="rt-top">{@render banner()}{@render seatStrip()}</div>
      <div class="tabbed"><TableView game={table} {onhome} {onsettings} /></div>
    </div>
  {/if}
{/if}

<Sheet open={reportOpen} title="Report a problem" onclose={() => (reportOpen = false)}>
  {#if reportState === 'sent'}
    <p class="caption">Sent, thanks. It's in the game log with this board, so it can be looked at later.</p>
    <button class="btn primary full" onclick={() => (reportOpen = false)}>Back to the table</button>
  {:else}
    <p class="caption">What looked wrong? It's saved with this exact moment of the board: what your screen shows and what the server had.</p>
    <textarea class="rt-input rt-note" bind:value={note} maxlength={NOTE_MAX} rows="4"
      placeholder="For example: East's cards showed on the wrong side" aria-label="What looked wrong"></textarea>
    {#if reportState === 'offline'}<p class="caption rt-warn">Not connected to the table right now. Try again in a moment.</p>{/if}
    <button class="btn primary full" disabled={!note.trim()} onclick={sendReport}>Send</button>
  {/if}
</Sheet>

<style>
  .rt-page { display: flex; flex-direction: column; gap: 14px; }
  .rt-banner {
    margin: 6px 12px 0; padding: 8px 12px; border-radius: 10px; font-size: 14px;
    background: rgba(220, 170, 60, 0.14); border: 1px solid rgba(220, 170, 60, 0.45); color: var(--text);
  }
  .rt-error { background: rgba(200, 40, 50, 0.14); border-color: rgba(220, 70, 80, 0.45); }
  .rt-info { background: rgba(52, 131, 90, 0.16); border-color: rgba(82, 177, 120, 0.45); }
  .rt-top { padding: calc(var(--safe-top) + 4px) 0 0; }
  .rt-strip {
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)) auto; gap: 5px;
    padding: 4px 12px 0; max-width: 520px; margin: 0 auto; box-sizing: border-box; width: 100%;
  }
  .rt-seat {
    display: flex; flex-direction: column; align-items: flex-start; min-width: 0;
    padding: 3px 8px; border: 1px solid var(--line); border-radius: 8px; font-size: 13px; line-height: 1.25;
  }
  .rt-you { border-color: var(--line-2); }
  .rt-line { display: flex; align-items: center; gap: 5px; min-width: 0; max-width: 100%; }
  .rt-name { color: var(--text); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .rt-compass { color: var(--dim); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
  .rt-chip { min-height: 28px; padding: 0 8px; font-size: 12px; margin: 2px 0; }
  .rt-dot { display: inline-block; flex-shrink: 0; width: 7px; height: 7px; border-radius: 4px; background: #6f857a; margin-left: 6px; }
  .rt-seat .rt-dot { margin-left: 0; }
  .rt-dot.on { background: var(--good); }
  /* Narrow, so the four seats keep their room for names. */
  .rt-flag { align-self: stretch; width: 28px; height: auto; min-height: 40px; border: 0; border-radius: 8px; padding: 0; color: var(--dim); }
  .rt-note { min-height: 96px; padding: 10px 14px; font-size: 16px; resize: vertical; }
  .rt-warn { color: var(--text); }
  .rt-form { display: flex; flex-direction: column; gap: 10px; }
  .rt-input {
    min-height: 48px; padding: 0 14px; border-radius: 12px; border: 1px solid var(--line-2);
    background: var(--panel); color: var(--text); font: inherit; font-size: 17px;
  }
  .rt-seats {
    display: grid; gap: 8px;
    grid-template-areas: ". north ." "west . east" ". south .";
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .rt-seatbox {
    display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 10px 6px;
    border: 1px solid var(--felt-line); border-radius: 12px; background: var(--felt); text-align: center; min-width: 0;
  }
  .rt-north { grid-area: north; } .rt-south { grid-area: south; }
  .rt-west { grid-area: west; } .rt-east { grid-area: east; }
  .rt-occupant { color: var(--text); font-weight: 600; overflow-wrap: anywhere; }
  .rt-share { display: flex; flex-direction: column; gap: 8px; }
  .rt-link {
    font-size: 13px; color: var(--dim-2); padding: 10px 12px; border: 1px dashed var(--line-2);
    border-radius: 10px; overflow-wrap: anywhere; user-select: all;
  }
</style>
