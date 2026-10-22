<!-- Hand history: pick a board, review the auction, step through the play
     card by card, with double dummy values and the cards that lost tricks
     (`analysis`). Renders any record of the history shape, which is how
     challenge mode shows your board and the robots' side by side. -->
<script lang="ts">
  import { STRAIN_SYMBOLS, SUIT_NAMES, SUIT_SYMBOLS, cardKey as key, parseCard, sameCard, type Card, type Seat } from '../engine/card';
  import { PARTNERSHIP, PLAYERS, type Contract, type Play } from '../engine/auction';
  import type { HistoryRecord } from '../game.svelte';
  import AuctionGrid from '../components/AuctionGrid.svelte';
  import FeltTable from '../components/FeltTable.svelte';
  import SeatBox from '../components/SeatBox.svelte';
  import Strain from '../components/Strain.svelte';
  import { MAX_LIN_BYTES, fromLinFile, toLin, toLinFile } from '../lin';
  import { MAX_SAVED_BOARDS } from '../saves';
  import { AUTO_CARDS, DdAnalysis } from '../dd/analysis.svelte';

  /** `onimport` adds the boards it hasn't already got and says how many.
   *  `analysis` shows double dummy values on the replayer (History and Challenge). */
  let { records, onimport, analysis = false }:
    { records: HistoryRecord[]; onimport?: (boards: HistoryRecord[]) => number; analysis?: boolean } = $props();

  // ── LIN in and out ──────────────────────────────────────────────────────────
  let linText = $state('');
  let linError = $state('');
  let linNote = $state('');
  let copied = $state(false);

  function download(name: string, text: string): void {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  async function copy(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      // Clipboard blocked: the text is still selectable in the box.
    }
  }

  function importLin(text: string): void {
    linError = '';
    linNote = '';
    try {
      const boards = fromLinFile(text).map((b) => ({ ...b, label: `Imported #${b.board_num}`, imported: true }));
      const added = onimport?.(boards) ?? 0;
      const total = records.length + added;
      linNote = `Imported ${added} board${added === 1 ? '' : 's'}.`;
      if (added < boards.length) linNote += ` ${boards.length - added} already imported, skipped.`;
      if (total > MAX_SAVED_BOARDS) {
        linNote += ` This device keeps ${MAX_SAVED_BOARDS} boards, so the oldest imported ones won't be kept after a reload; your own boards are kept first.`;
      }
      linText = '';
      selected = null;
    } catch (e) {
      linError = (e as Error).message;
    }
  }

  async function importFile(e: Event & { currentTarget: HTMLInputElement }): Promise<void> {
    const file = e.currentTarget.files?.[0];
    e.currentTarget.value = '';
    if (file && file.size > MAX_LIN_BYTES) {
      linNote = '';
      linError = `The file is ${file.size.toLocaleString()} bytes; at most ${MAX_LIN_BYTES.toLocaleString()} are read`;
    } else if (file) importLin(await file.text());
  }

  // Newest first.
  const options = $derived([...records.keys()].reverse());
  let selected = $state<number | null>(null);
  const sel = $derived(selected !== null && selected < records.length ? selected : records.length - 1);
  const hb = $derived(records[sel]);
  const lin = $derived(hb ? toLin(hb) : '');
  let step = $state(0);
  $effect(() => {
    sel; // a different board starts from the opening lead
    step = 0;
  });

  /** 'X' or 'XX' after the contract, as in 3♦X; nothing when undoubled. */
  const dbl = (d: string) => (d === 'None' ? '' : d);

  function label(h: HistoryRecord): string {
    const prefix = h.label || `Board #${h.board_num}`;
    if (h.passed_out || !h.contract || !h.result) return `${prefix} — Passed Out`;
    const c = h.contract, r = h.result;
    const pts = r.winner === c.side ? `+${r.points}` : `-${r.points}`;
    return `${prefix}: ${c.level}${STRAIN_SYMBOLS[c.strain]}${dbl(c.doubled)} by ${c.declarer} — ${r.made ? 'Made' : 'Down'} ${pts}pts`;
  }

  const role = (c: Contract, s: Seat) =>
    c.declarer === s ? 'Declarer' : c.dummy === s ? 'Dummy' : 'Defender';

  const flat = $derived(hb ? hb.tricks_log.flatMap((t) =>
    t.plays.map(([p, card]) => ({ p, card }))) : []);
  const total = $derived(flat.length);

  const view = $derived.by(() => {
    if (!hb?.contract) return null;
    const remaining = Object.fromEntries(
      PLAYERS.map((p) => [p, [...hb.initial_hands[p]]])) as Record<Seat, Card[]>;
    for (const { p, card } of flat.slice(0, step)) {
      const i = remaining[p].findIndex((c) => sameCard(c, card));
      if (i >= 0) remaining[p].splice(i, 1);
    }
    let trickNum = step < total ? Math.floor(step / 4) + 1 : 13;
    let trick: Play[] = flat.slice(Math.floor(step / 4) * 4, step).map(({ p, card }) => [p, card]);
    const justCompleted = step > 0 && step % 4 === 0;
    let winner: Seat | null = null;
    if (justCompleted && step / 4 - 1 < hb.tricks_log.length) {
      const t = hb.tricks_log[step / 4 - 1];
      trick = t.plays;
      trickNum = t.trick_num;
      winner = t.winner;
    }
    const tally = { 'N/S': 0, 'E/W': 0 };
    for (const t of hb.tricks_log.slice(0, Math.floor(step / 4))) tally[PARTNERSHIP[t.winner]]++;
    return { remaining, trickNum, trick, winner, tally };
  });

  // ── Double dummy ────────────────────────────────────────────────────────────
  // One analysis per board shown, started when the board is, stopped (and its
  // worker's memory freed) when another board is picked or the view closes.
  let dd = $state<DdAnalysis | null>(null);
  $effect(() => {
    if (!analysis || !hb?.contract || hb.passed_out) return;
    const a = new DdAnalysis(hb);
    dd = a;
    a.start();
    return () => a.stop();
  });
  /** The seat to play next at this step, with its marks (null while pending). */
  const toPlay = $derived(dd && step < total ? { seat: flat[step].p, marks: dd.marks(step), played: dd.played(step) } : null);
  const firstTrick = $derived(Math.ceil(total / 4));
  const losses = $derived(dd ? dd.losses : []);

  function boxProps(seat: Seat) {
    return toPlay && toPlay.seat === seat ? { marks: toPlay.marks, played: toPlay.played } : {};
  }

  function cardOf(plays: Play[], p: Seat) {
    return plays.find(([s]) => s === p)?.[1];
  }
</script>

{#snippet card(x: Card)}<span style:color="var(--suit-{x.suit.toLowerCase()}-lt)">{x.rank}<span aria-hidden="true">{SUIT_SYMBOLS[x.suit]}</span><span class="sr-only"> of {SUIT_NAMES[x.suit]}</span></span>{/snippet}

{#if onimport}
  <details class="expander">
    <summary>📥 Import LIN</summary>
    <div class="expander-body lin-box">
      <p class="caption">Paste LIN text or open a .lin file. Each board is replayed under second-highest rules; one played under ordinary rules will usually be refused, because its tricks go to different hands.</p>
      <textarea rows="4" spellcheck="false" maxlength={MAX_LIN_BYTES} placeholder="pn|...|md|3SAKQ...|sv|o|mb|1S|..." bind:value={linText}></textarea>
      <div class="lin-actions">
        <button class="btn" disabled={!linText.trim()} onclick={() => importLin(linText)}>Import</button>
        <label class="btn">Open .lin file<input class="sr-only" type="file" accept=".lin,.txt,text/plain" onchange={importFile} /></label>
      </div>
      {#if linError}<div class="notice error">Not imported: {linError}</div>{/if}
      {#if linNote}<div class="notice success">{linNote}</div>{/if}
    </div>
  </details>
{/if}

{#if records.length}
  <button class="btn" onclick={() => download('second-highest-session.lin', toLinFile(records))}>⬇ Download all boards (.lin)</button>
{/if}

{#if !records.length}
  <div class="notice info">📭 No completed hands yet. Play a board and then return here to review it!</div>
{:else}
  <label class="caption" for="board-select">📋 Select a board to review:</label>
  <select id="board-select" value={sel} onchange={(e) => (selected = Number(e.currentTarget.value))}>
    {#each options as i}<option value={i}>{label(records[i])}</option>{/each}
  </select>

  {#if hb.passed_out || !hb.contract || !hb.result || !view}
    <div class="notice warning">🛑 <strong>Board #{hb.board_num}</strong> — Passed Out (4 passes, no contract)</div>
  {:else}
    {@const c = hb.contract}
    {@const r = hb.result}
    <hr />
    <div class="split">
      <div>
        <h3>Board #{hb.board_num}  |  Dealer: {hb.dealer}  |  Vul: {hb.vulnerability}</h3>
        <p><strong>Contract:</strong> <Strain level={c.level} strain={c.strain} />{dbl(c.doubled)} by {c.declarer} &nbsp;|&nbsp;
          <strong>Target:</strong> {c.tricks_needed} tricks &nbsp;|&nbsp;
          <strong>Tricks Won:</strong> N/S {hb.tricks_taken['N/S']} — E/W {hb.tricks_taken['E/W']}</p>
        <div class="notice {r.made ? 'success' : 'error'}">{r.made ? '✅ Made! ' : '❌ Down. '}{r.detail}</div>
      </div>
      <div class="result-panel">
        <div class="result-eyebrow">Score</div>
        <div class="result-points">{r.winner === c.side ? '+' : '−'}{r.points}</div>
        <div class="result-to">points to {r.winner}</div>
      </div>
    </div>

    <details class="expander" open>
      <summary>📋 Auction Sequence</summary>
      <div class="expander-body"><AuctionGrid dealer={hb.dealer} calls={hb.auction_calls} alerts={hb.bid_alerts} /></div>
    </details>

    <hr />
    <h3>🎬 Card-by-Card Replayer</h3>
    <div class="replay-controls">
      <button class="btn" disabled={step === 0} onclick={() => (step = Math.max(0, step - 1))}>◀ Back</button>
      <button class="btn" disabled={step >= total} onclick={() => (step = Math.min(total, step + 1))}>Next card ▶</button>
      <button class="btn" disabled={step >= total} onclick={() => (step = Math.min(total, (Math.floor(step / 4) + 1) * 4))}>Next trick ⏭</button>
    </div>

    {#if dd}
      <div class="dd-status" aria-live="polite">
        <strong>Double dummy</strong>
        {#if dd.error}
          <span class="dd-error">{dd.error}</span>
        {:else}
          <span>{dd.doneFrom > firstTrick ? 'Starting…' : dd.doneFrom === firstTrick ? `Trick ${firstTrick} analysed` : `Tricks ${dd.doneFrom}–${firstTrick} analysed`}</span>
          {#if dd.running}<span class="dd-dim">· working on trick {dd.doneFrom - 1}…</span>{/if}
          {#if !dd.deep && firstTrick > AUTO_CARDS && !dd.running}
            <button class="btn" onclick={() => dd?.deeper()}>Analyse tricks 1–{13 - AUTO_CARDS} (can take minutes)</button>
          {/if}
        {/if}
      </div>
      <div class="dd-legend">
        <span><span class="dd-mark dd-down">−1</span> down 1 if played</span>
        <span><span class="dd-mark dd-even">=</span> makes exactly</span>
        <span><span class="dd-mark dd-over">+2</span> 2 overtricks</span>
        <span><span class="hd-played">Underlined</span>: the card played</span>
      </div>
    {/if}

    <div class="replay-grid">
      <div class="north"><SeatBox seat="North" role={role(c, 'North')} hand={view.remaining.North} {...boxProps('North')} /></div>
      <div class="west"><SeatBox seat="West" role={role(c, 'West')} hand={view.remaining.West} {...boxProps('West')} /></div>
      <div class="felt">
        <FeltTable trick={view.trick} winner={view.winner} displayNum={view.trickNum} contract={c} tricksTaken={view.tally} />
      </div>
      <div class="east"><SeatBox seat="East" role={role(c, 'East')} hand={view.remaining.East} {...boxProps('East')} /></div>
      <div class="south"><SeatBox seat="South" role={role(c, 'South')} hand={view.remaining.South} {...boxProps('South')} /></div>
    </div>

    {#if dd && !dd.error && dd.doneFrom <= firstTrick}
      <div class="dd-losses">
        <h4>Where tricks were lost</h4>
        {#if losses.length}
          <ul>
            {#each losses as l (l.i)}
              {@const m = dd.marks(l.i)}
              <li>
                <button class="dd-loss" class:dd-loss-here={step === l.i} onclick={() => (step = l.i)}>
                  <span class="dd-loss-trick">Trick {Math.floor(l.i / 4) + 1}</span>
                  <span>{l.seat} ({role(c, l.seat).toLowerCase()}) played {@render card(l.card)}, giving away {l.cost} trick{l.cost === 1 ? '' : 's'}</span>
                  {#if m}<span class="dd-loss-swing"><span class="dd-mark dd-{m[l.best[0]].tone}">{m[l.best[0]].text}</span> → <span class="dd-mark dd-{m[key(l.card)].tone}">{m[key(l.card)].text}</span></span>{/if}
                  <span class="dd-dim">Best: {#each l.best as b, k}{k ? ', ' : ''}{@render card(parseCard(b))}{/each}</span>
                </button>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="caption">No card cost a trick{dd.doneFrom > 1 ? ` from trick ${dd.doneFrom} on` : ''}.</p>
        {/if}
        {#if dd.doneFrom > 1}
          <p class="caption">{dd.running ? 'Still analysing: earlier tricks are added as they finish.' : `Tricks 1–${dd.doneFrom - 1} aren't analysed yet.`}</p>
        {/if}
      </div>
    {/if}

    <details class="expander">
      <summary>📊 Full Trick Log</summary>
      <div class="expander-body table-scroll">
        <table class="log-table">
          <thead><tr><th>#</th><th>Leader</th><th>West</th><th>North</th><th>East</th><th>South</th><th>Winner</th></tr></thead>
          <tbody>
            {#each hb.tricks_log as t}
              <tr>
                <td>{t.trick_num}</td><td>{t.leader}</td>
                {#each ['West', 'North', 'East', 'South'] as const as p}
                  {@const c = cardOf(t.plays, p)}
                  <td>{#if c}<span style:color="var(--suit-{c.suit.toLowerCase()}-lt)">{c.rank}<span aria-hidden="true">{SUIT_SYMBOLS[c.suit]}</span><span class="sr-only"> of {SUIT_NAMES[c.suit]}</span></span>{p === t.winner ? ' ⭐' : ''}{:else}—{/if}</td>
                {/each}
                <td>{t.winner}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </details>
  {/if}
  <details class="expander">
    <summary>📄 LIN record</summary>
    <div class="expander-body lin-box">
      <textarea rows="4" readonly spellcheck="false" value={lin}></textarea>
      <div class="lin-actions">
        <button class="btn" onclick={() => copy(lin)}>{copied ? 'Copied ✓' : 'Copy'}</button>
        <button class="btn" onclick={() => download(`board-${hb.board_num}.lin`, toLinFile([hb]))}>⬇ Download .lin</button>
      </div>
      <p class="caption">BBO's format. BBO's own hand viewer plays by ordinary rules, so it would show these tricks going to the wrong hands.</p>
    </div>
  </details>
{/if}
