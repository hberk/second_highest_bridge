<!-- The live table on a wide screen: everything at once. A strip of board
     facts across the top; the table on the left (the dummy, the felt with West
     and East beside it, your hand); the auction, your call, the last trick and
     the session down the right. Same game, same pieces as the phone table. -->
<script lang="ts">
  import { SUIT_SYMBOLS, STRAIN_SYMBOLS, type Seat } from '../engine/card';
  import type { Snippet } from 'svelte';
  import type { Game } from '../game.svelte';
  import { settings } from '../settings.svelte';
  import { TableModel, VUL_TEXT, useFastPlay } from '../tableModel.svelte';
  import { trickTaken, winningSoFar } from '../trickText';
  import AuctionFelt from '../components/AuctionFelt.svelte';
  import AuctionGrid from '../components/AuctionGrid.svelte';
  import BidPad from '../components/BidPad.svelte';
  import TrickFelt from '../components/TrickFelt.svelte';
  import Fan from '../components/Fan.svelte';
  import SeatCard from '../components/SeatCard.svelte';
  import SideHand from '../components/SideHand.svelte';
  import Strain from '../components/Strain.svelte';
  import Scoreline from '../components/Scoreline.svelte';
  import Breakdown from '../components/Breakdown.svelte';
  import SessionScore from '../components/SessionScore.svelte';

  let { game }: { game: Game } = $props();

  const m = new TableModel(() => game);
  useFastPlay(() => game);

  const c = $derived(m.contract);
  const auction = $derived(m.auction);
  const yourCall = $derived(game.phase === 'bidding' && !auction.isComplete && auction.currentPlayer() === 'South');
  const nsVul = $derived(game.vulnerability === 'N/S' || game.vulnerability === 'Both');
  const ewVul = $derived(game.vulnerability === 'E/W' || game.vulnerability === 'Both');

  /** The trick before the one on the felt: the felt keeps a finished trick
   *  until "Next trick", so the panel shows the one before it then. */
  const prevTrick = $derived(game.phase === 'trick_done' ? game.tricksLog.at(-2) ?? null
    : game.phase === 'playing' ? game.tricksLog.at(-1) ?? null : null);

  const session = $derived.by(() => {
    const played = game.history.filter((h) => !h.imported && h.contract && h.result);
    const total = played.reduce((a, h) => a + (h.result!.winner === 'N/S' ? h.result!.points : -h.result!.points), 0);
    return { boards: played.length + game.passedOutCount, total };
  });

  function role(p: Seat): string {
    if (!c || m.bidding) return 'Opponent · robot';
    if (c.declarer === p) return 'Declarer · robot';
    if (c.dummy === p) return 'Dummy';
    return 'Defender · robot';
  }
  const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : '0');
</script>

{#snippet contractText()}
  {#if c}<Strain level={c.level} strain={c.strain} />{#if c.doubled !== 'None'}<span class="accent"> {c.doubled}</span>{/if}{/if}
{/snippet}

{#snippet cell(label: string, body: Snippet)}
  <div class="dk-cell"><span class="dk-lab">{label}</span><span class="dk-val">{@render body()}</span></div>
{/snippet}

{#snippet sessionCell()}
  {#snippet body()}{session.boards} board{session.boards === 1 ? '' : 's'} · N/S <span class:good={session.total > 0} class:bad={session.total < 0}>{signed(session.total)}</span>{/snippet}
  <div class="dk-cell dk-grow"><span class="dk-lab">Session</span><span class="dk-val dk-soft">{@render body()}</span></div>
{/snippet}

{#snippet seatPanel(p: Seat)}
  {#if m.sideDummy === p}
    <!-- An East or West dummy shows its cards on its own side of the table. -->
    <div class="seat-card dk-side-dummy"><SideHand cards={game.hands[p]} trump={m.displayTrump} title={m.labels[p]} /></div>
  {:else}
    <SeatCard seat={p} role={role(p)} count={m.counts[p]} />
  {/if}
{/snippet}

{#snippet seats(felt: Snippet)}
  <div class="dk-row">
    {@render seatPanel('West')}
    {@render felt()}
    {@render seatPanel('East')}
  </div>
{/snippet}

{#snippet challengeResult()}
  {#if game.challenge}
    <section class="dk-panel challenge-result">
      <Scoreline result={game.challenge} />
      <Breakdown result={game.challenge} />
    </section>
  {/if}
{/snippet}

<div class="dk-table">
  <!-- ── Board facts ─────────────────────────────────────────────────────── -->
  <div class="dk-strip">
    {#snippet board()}#{game.boardNum}{#if game.challengeId !== null}<span class="dk-soft"> · challenge</span>{/if}{/snippet}
    {@render cell('Board', board)}
    {#if m.bidding || !c}
      {#snippet dealer()}{game.dealer}{/snippet}
      {#snippet vul()}
        <span class="dk-pill" class:on={nsVul}>N-S</span><span class="dk-pill" class:on={ewVul}>E-W</span>
        <span class="sr-only">{VUL_TEXT[game.vulnerability]}</span>
      {/snippet}
      {#snippet high()}
        {#if auction.highestBid}<Strain level={auction.highestBid[0]} strain={auction.highestBid[1]} /> <span class="dk-soft">by {m.by(auction.highestBid[2])}</span>{#if auction.doubled !== 'None'} <span class="accent">{auction.doubled}</span>{/if}
        {:else}<span class="dk-soft">—</span>{/if}
      {/snippet}
      {@render cell('Dealer', dealer)}
      {@render cell('Vulnerable', vul)}
      {@render cell(game.phase === 'auction_done' ? 'Contract' : 'High bid', high)}
    {:else}
      {#snippet contract()}{@render contractText()} <span class="dk-soft">by {m.by(c.declarer)}</span>{/snippet}
      {#snippet trick()}{Math.min(m.displayNum, 13)} <span class="dk-soft">/ 13{#if m.led}{' · '}led <span style:color="var(--suit-{m.led.toLowerCase()}-lt)">{SUIT_SYMBOLS[m.led]}</span>{/if}</span>{/snippet}
      {#snippet won()}<span class="accent">N/S {game.tricksTaken['N/S']}</span> <span class="dk-soft">· E/W {game.tricksTaken['E/W']} · {c.side === 'N/S' ? 'you need' : 'they need'} {c.tricks_needed}</span>{/snippet}
      {@render cell('Contract', contract)}
      {#if game.phase !== 'done'}{@render cell('Trick', trick)}{/if}
      {@render cell('Tricks won', won)}
    {/if}
    {@render sessionCell()}
  </div>

  <div class="dk-grid">
    <div class="dk-main">
      {#if game.phase === 'done' && c && game.result}
        <!-- ── Result ──────────────────────────────────────────────────────── -->
        {@const r = game.result}
        {@const ns = r.winner === 'N/S' ? r.points : -r.points}
        <section class="res-card dk-result">
          <div class="eyebrow">Hand complete · board {game.boardNum}</div>
          <div class="res-contract">{@render contractText()} <span class="dim">by {m.by(c.declarer)}</span></div>
          <div class="res-verdict" class:made={r.made} class:down={!r.made}>{r.made ? 'Contract made' : 'Contract down'}</div>
          <div class="res-points" class:plus={ns > 0} class:minus={ns < 0}>{signed(ns)}</div>
          <div class="res-to">to your side, North-South</div>
          <p class="res-detail">{r.detail}</p>
          <p class="res-detail">Tricks: N/S {game.tricksTaken['N/S']}, E/W {game.tricksTaken['E/W']}. {c.side === 'N/S' ? 'You' : 'They'} needed {r.tricks_needed}.</p>
          <button class="btn primary big dk-cta" onclick={() => game.newBoard()}>Deal the next board</button>
        </section>
        {@render challengeResult()}

      {:else if m.bidding && auction.passedOut}
        {#snippet passedFelt()}<div class="dk-felt"><AuctionFelt calls={game.calls} alerts={game.liveAlerts} dealer={game.dealer} /></div>{/snippet}
        {@render seats(passedFelt)}
        <section class="res-card dk-result">
          <div class="res-verdict">Passed out</div>
          <p class="res-detail">All four players passed: no contract, and no score on this board.</p>
          <button class="btn primary big dk-cta" onclick={() => game.newBoard()}>Deal the next board</button>
        </section>
        {@render challengeResult()}

      {:else if m.bidding}
        <!-- ── Auction ─────────────────────────────────────────────────────── -->
        {#snippet auctionFelt()}
          <div class="dk-felt">
            <AuctionFelt calls={game.calls} alerts={game.liveAlerts} dealer={game.dealer}
              turn={auction.isComplete ? null : auction.currentPlayer()} />
          </div>
        {/snippet}
        {@render seats(auctionFelt)}
        <section class="dk-panel dk-hand">
          <div class="dk-hand-head">
            <span class="eyebrow">Your hand · South</span>
            {#if settings.showStrength && m.strength}
              <span class="dk-strength">HCP <strong>{m.strength.hcp}</strong> <span class="dk-sep">|</span> 2nd-highest value <strong>{m.strength.value}</strong> <span class="dk-sep">|</span> Shape <strong>{m.strength.shape}</strong></span>
            {/if}
          </div>
          <Fan cards={game.hands.South} size="lg" label="Your hand" />
        </section>

      {:else if c}
        <!-- ── Play ────────────────────────────────────────────────────────── -->
        {#if m.topSeat}
          <section class="dk-panel dk-hand dummy-zone">
            <div class="eyebrow" class:accent={m.who === m.topSeat}>
              {m.labels[m.topSeat]}{c.declarer === 'South' ? ' · you play this hand' : ''}{m.who === m.topSeat ? ' · your turn' : ''}
            </div>
            <Fan cards={game.hands[m.topSeat]} trump={m.displayTrump} size="lg"
              playable={m.who === m.topSeat} legal={m.legalFor(m.topSeat)}
              label="{m.topSeat}'s hand" onplay={(card) => game.humanPlays(m.topSeat!, card)} />
          </section>
        {/if}

        {#snippet trickFelt()}
          {#snippet info()}
            <span><span class="dk-trick-title">Trick {Math.min(m.displayNum, 13)} / 13</span>{#if m.led} · led <span style:color="var(--suit-{m.led.toLowerCase()}-lt)">{SUIT_SYMBOLS[m.led]}</span>{/if}</span>
            <span class="dk-rule">2nd-highest in the winning suit wins</span>
          {/snippet}
          <div class="dk-felt">
            <TrickFelt trick={game.trick} winner={game.phase === 'trick_done' ? game.trickWinner : null}
              labels={m.labels} awaiting={m.who} {info} />
          </div>
        {/snippet}
        {@render seats(trickFelt)}

        {#if game.phase === 'trick_done' && game.trickWinner}
          <p class="trick-line trick-won">{trickTaken(game.trick, game.trump, game.trickWinner, m.displayNum)}</p>
        {:else if game.trick.length}
          <p class="trick-line">{winningSoFar(game.trick, game.trump)}</p>
        {:else}
          <p class="trick-line dim">{m.who === 'South' ? 'Your lead.' : m.who ? `Lead from ${m.who}'s hand.` : ''}</p>
        {/if}

        <section class="dk-panel dk-hand" class:dk-turn={m.who === 'South'}>
          <div class="dk-hand-head">
            <span class="eyebrow" class:accent={m.who !== null}>
              {#if m.who === 'South'}Your turn · South{m.led && game.hands.South.some((x) => x.suit === m.led) ? ` · follow in ${STRAIN_SYMBOLS[m.led]}` : ''}
              {:else if m.who}Your turn · play from {m.who}'s hand
              {:else}{m.labels.South} · South{/if}
            </span>
            {#if game.phase === 'trick_done'}
              <button class="btn primary dk-next" onclick={() => game.nextTrick()}>
                {game.gameOver ? 'See the result' : 'Next trick'}{settings.fastPlay ? ' (automatic)' : ''}
              </button>
            {/if}
          </div>
          <Fan cards={game.hands.South} trump={m.displayTrump} size="lg"
            playable={m.who === 'South'} legal={m.legalFor('South')}
            label="Your hand" onplay={(card) => game.humanPlays('South', card)} />
        </section>
      {/if}
    </div>

    <aside class="dk-side">
      <section class="dk-panel">
        <div class="dk-panel-head">
          <h2>Auction</h2>
          {#if c}<span class="dk-soft">{@render contractText()} by {m.by(c.declarer)} · {m.by(c.leader) === 'you' ? 'you lead' : `${c.leader} leads`}</span>
          {:else}<span class="dk-soft">{game.dealer} deals · {VUL_TEXT[game.vulnerability]}</span>{/if}
        </div>
        <AuctionGrid dealer={game.dealer} calls={game.calls} alerts={game.boardOver ? game.alerts : game.liveAlerts} />
      </section>

      {#if yourCall}
        <section class="dk-panel">
          <div class="dk-panel-head"><h2>Your call</h2><span class="dk-soft">Click a call to see what it means</span></div>
          <BidPad {auction} docked oncall={(call, alert) => game.humanBids(call, alert)} />
        </section>
      {:else if game.phase === 'auction_done' && c}
        <section class="dk-panel ready-card">
          <div class="eyebrow">The contract</div>
          <div class="ready-contract">{@render contractText()} <span class="dim">by {m.by(c.declarer)}</span></div>
          <p class="ready-detail">
            {c.dummy === 'South' ? 'You are dummy' : `${c.dummy} is dummy`} ·
            {c.leader === 'South' ? 'you lead' : `${c.leader} leads`} ·
            {c.side === 'N/S' ? 'your side needs' : 'they need'} {c.tricks_needed} tricks
          </p>
          <button class="btn primary full big" onclick={() => game.startPlay()}>Start play</button>
        </section>
      {/if}

      {#if !m.bidding && game.phase !== 'done'}
        <section class="dk-panel">
          <div class="dk-panel-head">
            <h2>Last trick</h2>
            {#if prevTrick}<span class="dk-soft">Trick {prevTrick.trick_num}</span>{/if}
          </div>
          {#if prevTrick}
            <div class="dk-last">
              {#each prevTrick.plays as [p, card] (p)}
                <div class="dk-last-seat">
                  <span class="dk-lab">{p === 'South' ? 'You' : p}</span>
                  <span class="dk-mini" class:tf-winner={p === prevTrick.winner} style:color="var(--suit-{card.suit.toLowerCase()})">{card.rank}<span aria-hidden="true">{SUIT_SYMBOLS[card.suit]}</span></span>
                </div>
              {/each}
            </div>
            <p class="dk-note">{trickTaken(prevTrick.plays, game.trump, prevTrick.winner, prevTrick.trick_num)}</p>
          {:else}
            <p class="dk-note">The first trick is still being played.</p>
          {/if}
        </section>
      {/if}

      <SessionScore history={game.history} challengeLog={game.challengeLog} passedOut={game.passedOutCount} open />
    </aside>
  </div>
</div>
