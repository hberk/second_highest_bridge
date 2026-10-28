<!-- The live table, phone first: the auction, then play, then the result. The
     felt holds what is happening now; your hand sits at the bottom, within
     reach of your thumb; everything else is a tap away. -->
<script lang="ts">
  import { STRAIN_SYMBOLS, type Seat } from '../engine/card';
  import { settings } from '../settings.svelte';
  import { TableModel, useFastPlay, type TableSource } from '../tableModel.svelte';
  import { SIDE_NAME } from '../seats';
  import { trickTaken, winningSoFar } from '../trickText';
  import TopBar from '../components/TopBar.svelte';
  import Sheet from '../components/Sheet.svelte';
  import AuctionFelt from '../components/AuctionFelt.svelte';
  import AuctionGrid from '../components/AuctionGrid.svelte';
  import BidPad from '../components/BidPad.svelte';
  import TrickFelt from '../components/TrickFelt.svelte';
  import Fan from '../components/Fan.svelte';
  import SideHand from '../components/SideHand.svelte';
  import Strain from '../components/Strain.svelte';
  import Scoreline from '../components/Scoreline.svelte';
  import Breakdown from '../components/Breakdown.svelte';

  let { game, onhome, onsettings = () => {} }:
    { game: TableSource; onhome?: () => void; onsettings?: () => void } = $props();

  const m = new TableModel(() => game);
  useFastPlay(() => game);

  const me = $derived(m.me);
  const mySide = $derived(m.mySide);
  const theirSide = $derived(m.theirSide);
  const names = $derived(Object.fromEntries((['North', 'East', 'South', 'West'] as Seat[])
    .map((p) => [p, m.name(p)])) as Record<Seat, string>);

  const auction = $derived(m.auction);
  const c = $derived(m.contract);
  const bidding = $derived(m.bidding);
  const displayNum = $derived(m.displayNum);
  const who = $derived(m.who);
  const led = $derived(m.led);
  const displayTrump = $derived(m.displayTrump);
  const usVul = $derived(m.usVul);
  const topSeat = $derived(m.topSeat);
  const labels = $derived(m.labels);
  const lastTrick = $derived(m.lastTrick);
  const peeking = $derived(m.peeking);
  const strength = $derived(m.strength ? `${m.strength.hcp} HCP · ${m.strength.shape}` : '');

  let auctionOpen = $state(false);

  const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : '0');
  const by = (p: Parameters<TableModel['by']>[0]) => m.by(p);
</script>

{#snippet contractText()}
  {#if c}<Strain level={c.level} strain={c.strain} />{#if c.doubled !== 'None'}<span class="accent"> {c.doubled}</span>{/if}{/if}
{/snippet}

{#snippet gear()}
  <button class="icon-btn" aria-label="Settings" onclick={onsettings}>
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"></path></svg>
  </button>
{/snippet}

{#snippet auctionBtn()}
  <button class="icon-btn" aria-label="Show the whole auction" onclick={() => (auctionOpen = true)}>
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10"></path></svg>
  </button>
{/snippet}

{#snippet challengeResult()}
  {#if game.challenge}
    <section class="challenge-result">
      <Scoreline result={game.challenge} />
      <Breakdown result={game.challenge} />
    </section>
  {/if}
{/snippet}

<div class="table-screen">
  {#if game.phase === 'done' && c && game.result}
    <!-- ── Result ──────────────────────────────────────────────────────────── -->
    {@const r = game.result}
    {@const ns = r.winner === mySide ? r.points : -r.points}
    <TopBar onback={onhome} title="Board {game.boardNum}" sub="Hand complete">
      {#snippet right()}{@render auctionBtn()}{/snippet}
    </TopBar>
    <div class="table-body scroll">
      <section class="res-card">
        <div class="res-contract">{@render contractText()} <span class="dim">by {by(c.declarer)}</span></div>
        <div class="res-verdict" class:made={r.made} class:down={!r.made}>{r.made ? 'Contract made' : 'Contract down'}</div>
        <div class="res-points" class:plus={ns > 0} class:minus={ns < 0}>{signed(ns)}</div>
        <div class="res-to">to your side, {SIDE_NAME[mySide]}</div>
        <p class="res-detail">{r.detail}</p>
        <p class="res-detail">Tricks: N/S {game.tricksTaken['N/S']}, E/W {game.tricksTaken['E/W']}. {c.side === mySide ? 'You' : 'They'} needed {r.tricks_needed}.</p>
      </section>
      <button class="btn primary full big" onclick={() => game.newBoard()}>Deal the next board</button>
      {@render challengeResult()}
    </div>

  {:else if bidding && auction.passedOut}
    <TopBar onback={onhome} title="Board {game.boardNum}" sub="Passed out">
      {#snippet right()}{@render auctionBtn()}{/snippet}
    </TopBar>
    <div class="table-body scroll">
      <AuctionFelt calls={game.calls} alerts={game.liveAlerts} dealer={game.dealer} {me} {names} />
      <section class="res-card">
        <div class="res-verdict">Passed out</div>
        <p class="res-detail">All four players passed: no contract, and no score on this board.</p>
      </section>
      <button class="btn primary full big" onclick={() => game.newBoard()}>Deal the next board</button>
      {@render challengeResult()}
    </div>

  {:else if bidding}
    <!-- ── Auction ─────────────────────────────────────────────────────────── -->
    <TopBar onback={onhome}>
      {#snippet center()}
        <div class="topbar-title">Board {game.boardNum}{game.challengeId !== null ? ' · challenge' : ''}</div>
        <div class="topbar-sub">{m.dealsText} · <span class:vul={usVul}>{m.vul}</span></div>
      {/snippet}
      {#snippet right()}{@render gear()}{/snippet}
    </TopBar>
    <div class="table-body">
      <AuctionFelt calls={game.calls} alerts={game.liveAlerts} dealer={game.dealer}
        turn={auction.isComplete ? null : auction.currentPlayer()} {me} {names} />

      <section class="hand-zone">
        <div class="hand-head">
          <span class="eyebrow">Your hand</span>
          <span class="hand-tools">
            {#if settings.showStrength && strength}<span class="hand-strength">{strength}</span>{/if}
            {@render auctionBtn()}
          </span>
        </div>
        <Fan cards={game.hands[me]} size="md" label="Your hand" />
      </section>

      {#if game.phase === 'auction_done' && c}
        <section class="ready-card">
          <div class="eyebrow">The contract</div>
          <div class="ready-contract">{@render contractText()} <span class="dim">by {by(c.declarer)}</span></div>
          <p class="ready-detail">
            {c.dummy === me ? 'You are dummy' : `${m.name(c.dummy)} is dummy`} ·
            {c.leader === me ? 'you lead' : `${m.name(c.leader)} leads`} ·
            {c.side === mySide ? 'your side needs' : 'they need'} {c.tricks_needed} tricks
          </p>
          <button class="btn primary full big" onclick={() => game.startPlay()}>Start play</button>
        </section>
      {:else if !auction.isComplete && auction.currentPlayer() === me}
        <BidPad {auction} oncall={(call, alert) => game.humanBids(call, alert)} />
      {/if}
    </div>

  {:else if c}
    <!-- ── Play ────────────────────────────────────────────────────────────── -->
    <TopBar onback={onhome}>
      {#snippet center()}
        <div class="topbar-title">{@render contractText()} <span class="dim">by {by(c.declarer)}</span></div>
        <div class="topbar-sub">Trick {Math.min(displayNum, 13)} of 13 · {c.side === mySide ? 'you need' : 'they need'} {c.tricks_needed}</div>
      {/snippet}
      {#snippet right()}
        <div class="tally" role="img" aria-label="Tricks won: your side {game.tricksTaken[mySide]}, theirs {game.tricksTaken[theirSide]}">
          <span><strong class="accent">{game.tricksTaken[mySide]}</strong> us</span>
          <span><strong>{game.tricksTaken[theirSide]}</strong> them</span>
        </div>
      {/snippet}
    </TopBar>
    <div class="table-body">
      {#if topSeat}
        <section class="dummy-zone">
          <div class="eyebrow" class:accent={who === topSeat}>{labels[topSeat]}{who === topSeat ? ' · your turn' : ''}</div>
          <Fan cards={game.hands[topSeat]} trump={displayTrump} size={who === topSeat ? 'md' : 'sm'}
            playable={who === topSeat} legal={m.legalFor(topSeat)}
            label="{topSeat}'s hand" onplay={(card) => game.humanPlays(topSeat, card)} />
        </section>
      {/if}

      {#snippet felt()}
        {#if peeking && lastTrick}
          <TrickFelt trick={lastTrick.plays} winner={lastTrick.winner} {labels} {me} />
        {:else}
          <TrickFelt trick={game.trick} winner={game.phase === 'trick_done' ? game.trickWinner : null}
            {labels} awaiting={who} {me} />
        {/if}
      {/snippet}
      {#if m.sideDummy}
        <!-- An East or West dummy on its own side; the felt moves over. -->
        <div class="play-row" class:dummy-east={m.sideDummy === 'East'}>
          <SideHand cards={game.hands[m.sideDummy]} trump={displayTrump} title={labels[m.sideDummy]} />
          <div class="play-felt">{@render felt()}</div>
        </div>
      {:else}
        {@render felt()}
      {/if}

      {#if peeking && lastTrick}
        <p class="trick-line">Previous trick. {trickTaken(lastTrick.plays, game.trump, lastTrick.winner, lastTrick.trick_num, me)}</p>
      {:else}
        {#if game.phase === 'trick_done' && game.trickWinner}
          <p class="trick-line trick-won">{trickTaken(game.trick, game.trump, game.trickWinner, displayNum, me)}</p>
        {:else if game.trick.length}
          <p class="trick-line">{winningSoFar(game.trick, game.trump, me)}</p>
        {:else}
          <p class="trick-line dim">{who === me ? 'Your lead.' : who ? `Lead from ${m.name(who)}'s hand.` : ''}</p>
        {/if}
      {/if}

      <section class="hand-zone">
        {#if game.phase === 'trick_done'}
          <button class="btn primary full big" onclick={() => game.nextTrick()}>
            {game.gameOver ? 'See the result' : 'Next trick'}{settings.fastPlay ? ' (automatic)' : ''}
          </button>
        {:else}
          <div class="hand-head">
            <span class="eyebrow" class:accent={who !== null}>
              {#if who === me}Your turn{led && game.hands[me].some((x) => x.suit === led) ? ` · follow in ${STRAIN_SYMBOLS[led]}` : ''}
              {:else if who}Your turn · play from {m.name(who)}'s hand
              {:else}{labels[me]}{/if}
            </span>
            <span class="hand-tools">
              {#if lastTrick}
                <button class="chip-btn" aria-pressed={peeking} onclick={() => m.togglePeek()}>
                  {peeking ? 'Back to this trick' : 'Last trick'}
                </button>
              {/if}
              {@render auctionBtn()}
              {@render gear()}
            </span>
          </div>
        {/if}
        <Fan cards={game.hands[me]} trump={displayTrump} size="lg"
          playable={who === me} legal={m.legalFor(me)}
          label="Your hand" onplay={(card) => game.humanPlays(me, card)} />
      </section>
    </div>
  {/if}
</div>

<Sheet open={auctionOpen} title="Auction · board {game.boardNum}" onclose={() => (auctionOpen = false)}>
  <p class="caption">{m.name(game.dealer)} dealt · {m.vul}. Calls marked ! were alerted: tap one to read it.</p>
  <AuctionGrid dealer={game.dealer} calls={game.calls} alerts={game.boardOver ? game.alerts : game.liveAlerts} />
</Sheet>
