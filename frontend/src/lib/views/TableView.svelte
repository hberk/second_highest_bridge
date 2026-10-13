<!-- The live table: auction, then play, then the result. Port of the
     "Bridge Table" tab in app.py. -->
<script lang="ts">
  import { STRAIN_SYMBOLS, SUIT_SYMBOLS, type Seat } from '../engine/card';
  import { legalPlays } from '../engine/auction';
  import type { Game } from '../game.svelte';
  import { settings } from '../settings.svelte';
  import AuctionGrid from '../components/AuctionGrid.svelte';
  import BiddingBox from '../components/BiddingBox.svelte';
  import FeltTable from '../components/FeltTable.svelte';
  import Hand from '../components/Hand.svelte';
  import HandSummary from '../components/HandSummary.svelte';
  import SeatPanel from '../components/SeatPanel.svelte';
  import Strain from '../components/Strain.svelte';
  import VulPills from '../components/VulPills.svelte';
  import Scoreline from '../components/Scoreline.svelte';
  import Breakdown from '../components/Breakdown.svelte';
  import SessionScore from '../components/SessionScore.svelte';

  let { game }: { game: Game } = $props();

  const auction = $derived(game.auction);
  const c = $derived(game.contract);
  const bidding = $derived(game.phase === 'bidding' || game.phase === 'auction_done');
  const displayNum = $derived(game.phase === 'trick_done' ? game.trickNum - 1 : game.trickNum);
  const who = $derived(game.whoseTurn());
  const led = $derived(game.trick.length ? game.trick[0][1].suit : null);
  // Hands keep the fixed S-H-D-C order unless the player asked for trump first.
  const displayTrump = $derived(settings.trumpFirst ? game.trump : null);

  function role(p: Seat): string {
    if (c?.declarer === p) return 'Declarer';
    if (c?.dummy === p) return 'Dummy';
    return 'Defender';
  }
  /** South is the player's own hand and the dummy is public to the table once
   *  the opening lead is made -- the leader chooses blind. */
  // Reactive fields only: `game.played` is a plain array, so a derived that
  // read it would stay true into the next board and expose dummy before the lead.
  const dummyDown = $derived(game.trickNum > 1 || game.trick.length > 0);
  const faceUp = (p: Seat) => settings.showAll || p === 'South' || (c?.dummy === p && dummyDown);
  const layout = $derived(c?.dummy === 'West' ? 'wide-west' : c?.dummy === 'East' ? 'wide-east' : '');
  const winnerCard = $derived(
    game.trickWinner ? game.trick.find(([p]) => p === game.trickWinner)?.[1] ?? null : null);

  // ── Last trick ─────────────────────────────────────────────────────────────
  // A peek belongs to the moment it was asked for: as soon as a card is played
  // or the trick moves on, the key changes and the felt shows the live trick
  // again, with no effect needed to reset it.
  const lastTrick = $derived(game.phase === 'playing' ? game.tricksLog.at(-1) ?? null : null);
  const momentKey = $derived(`${game.boardNum}:${game.trickNum}:${game.trick.length}`);
  let peekKey = $state<string | null>(null);
  const peeking = $derived(lastTrick !== null && peekKey === momentKey);

  // ── Fast play ──────────────────────────────────────────────────────────────
  const FAST_PLAY_MS = 1200;
  $effect(() => {
    if (game.phase !== 'trick_done' || !settings.fastPlay) return;
    const timer = setTimeout(() => game.nextTrick(), FAST_PLAY_MS);
    return () => clearTimeout(timer);
  });
</script>

<SessionScore history={game.history} challengeLog={game.challengeLog} passedOut={game.passedOutCount} />

<!-- ── Scoreboard ─────────────────────────────────────────────────────────── -->
<div class="scoreboard">
  {#if bidding}
    <div class="score-cell"><div class="score-label">Board</div><div class="score-value">#{game.boardNum}</div></div>
    <div class="score-cell"><div class="score-label">Dealer</div><div class="score-value">{game.dealer}</div></div>
    <div class="score-cell"><div class="score-label">Vulnerable</div><div class="score-value"><VulPills vul={game.vulnerability} /></div></div>
    <div class="score-cell"><div class="score-label">High bid</div><div class="score-value">
      {#if auction.highestBid}
        <Strain level={auction.highestBid[0]} strain={auction.highestBid[1]} />
        <span class="muted">by {auction.highestBid[2]}</span>
        {#if auction.doubled !== 'None'}<span class="accent">{auction.doubled}</span>{/if}
      {:else}<span class="muted">—</span>{/if}
    </div></div>
  {:else if c}
    <div class="score-cell"><div class="score-label">Board</div><div class="score-value">#{game.boardNum}</div></div>
    <div class="score-cell"><div class="score-label">Vulnerable</div><div class="score-value"><VulPills vul={game.vulnerability} /></div></div>
    <div class="score-cell"><div class="score-label">Contract</div><div class="score-value">
      <Strain level={c.level} strain={c.strain} /><span class="muted"> by {c.declarer}</span>
      {#if c.doubled !== 'None'}<span class="accent">{c.doubled}</span>{/if}
    </div></div>
    <div class="score-cell"><div class="score-label">Trick</div><div class="score-value">
      {Math.min(displayNum, 13)} <span class="muted">/ 13 · need {c.tricks_needed}</span></div></div>
    <div class="score-cell"><div class="score-label">Tricks won</div><div class="score-value">
      <span class="accent">N/S {game.tricksTaken['N/S']}</span><span class="muted">  ·  E/W {game.tricksTaken['E/W']}</span></div></div>
  {/if}
</div>

{#if game.phase === 'done' && c && game.result}
  <!-- ── Result ──────────────────────────────────────────────────────────── -->
  {@const r = game.result}
  <div class="split">
    <div>
      <h2>🏁 Hand Complete!</h2>
      <p><strong>Contract:</strong> {c.level}{STRAIN_SYMBOLS[c.strain]} by {c.declarer} ({c.doubled}) | <strong>Vul:</strong> {c.vulnerability}</p>
      <p><strong>Tricks Won:</strong> N/S {game.tricksTaken['N/S']} — E/W {game.tricksTaken['E/W']} (Target: {r.tricks_needed})</p>
      <div class="notice {r.made ? 'success' : 'error'}">{r.made ? '✅ Contract Made! ' : '❌ Contract Down. '}{r.detail}</div>
      <button class="btn primary" onclick={() => game.newBoard()}>Deal Next Board ➔</button>
      {#if game.challenge}
        <hr />
        <Scoreline result={game.challenge} />
        <Breakdown result={game.challenge} />
      {/if}
    </div>
    <div>
      <div class="result-panel">
        <div class="result-eyebrow">Board #{game.boardNum} result</div>
        <div class="result-contract"><Strain level={c.level} strain={c.strain} /> by {c.declarer}</div>
        <div class="result-verdict {r.made ? 'made' : 'down'}">{r.made ? 'Contract made' : 'Contract down'}</div>
        <div class="result-points">{r.winner === c.side ? '+' : '−'}{r.points}</div>
        <div class="result-to">points to {r.winner}</div>
      </div>
    </div>
  </div>
  <details class="expander">
    <summary>Auction</summary>
    <div class="expander-body"><AuctionGrid dealer={game.dealer} calls={game.calls} alerts={game.alerts} /></div>
  </details>

{:else if bidding && auction.passedOut}
  <div class="notice warning">🛑 <strong>Auction Passed Out (4 Passes)</strong> — No contract reached (0 points).</div>
  <button class="btn primary" onclick={() => game.newBoard()}>Deal Next Board ➔</button>

{:else if bidding}
  <!-- ── Auction ─────────────────────────────────────────────────────────── -->
  <div class="table-layout">
    <div class="center">
      {#if settings.showAll}
        <div class="hand-header"><strong>North (Partner)</strong></div>
        <Hand hand={game.hands.North} />
      {:else}
        <SeatPanel seat="North" role="Partner · AI" count={game.hands.North.length} note=" · concealed until play starts" />
      {/if}

      <div class="section-title">Auction</div>
      <AuctionGrid dealer={game.dealer} calls={game.calls} alerts={game.liveAlerts} />

      {#if !auction.isComplete && auction.currentPlayer() === 'South'}
        <BiddingBox legal={auction.legalCalls()} oncall={(call, alert) => game.humanBids(call, alert)} />
      {/if}

      {#if game.phase === 'auction_done' && c}
        <div class="contract-ready">
          <span class="cr-label">Contract</span>
          <span class="cr-contract"><Strain level={c.level} strain={c.strain} />{#if c.doubled !== 'None'} <span class="cr-gold">{c.doubled}</span>{/if}</span>
          <span class="cr-detail">by <strong>{c.declarer}</strong> · dummy {c.dummy} · <span class="cr-gold">{c.leader}</span> leads · needs {c.tricks_needed} tricks</span>
        </div>
        <button class="btn primary full" onclick={() => game.startPlay()}>Start play →</button>
      {/if}

      <div class="section-title">Your hand</div>
      {#if settings.showStrength}<HandSummary hand={game.hands.South} />{/if}
      <Hand hand={game.hands.South} />
    </div>
    {#each ['West', 'East'] as const as seat}
      <div class={seat.toLowerCase()}>
        <SeatPanel {seat} role="Opponent · AI" count={game.hands[seat].length} />
        {#if settings.showAll}<Hand hand={game.hands[seat]} />{/if}
      </div>
    {/each}
  </div>

{:else if c}
  <!-- ── Play ────────────────────────────────────────────────────────────── -->
  <div class="table-layout centered {layout}">
    <div class="center">
      <Hand label="North ({role('North')})" hand={game.hands.North} trump={displayTrump}
        isTurn={who === 'North'} legal={who === 'North' ? legalPlays(game.hands.North, led) : []}
        concealed={!faceUp('North')} onplay={(card) => game.humanPlays('North', card)} />

      {#if peeking && lastTrick}
        <FeltTable trick={lastTrick.plays} winner={lastTrick.winner}
          displayNum={lastTrick.trick_num} contract={c} tricksTaken={game.tricksTaken} />
      {:else}
        <FeltTable trick={game.trick} winner={game.phase === 'trick_done' ? game.trickWinner : null}
          displayNum={displayNum} contract={c} tricksTaken={game.tricksTaken} />
      {/if}
      {#if lastTrick}
        <div class="last-trick-row">
          <button class="btn" aria-pressed={peeking} onclick={() => (peekKey = peeking ? null : momentKey)}>
            {peeking ? '↩ Back to this trick' : '👁 Last trick'}
          </button>
          {#if peeking}
            {@const w = lastTrick.winning_card}
            <span class="caption">Trick {lastTrick.trick_num}: <strong>{lastTrick.winner}</strong> won with
              <span style:color="var(--suit-{w.suit.toLowerCase()}-lt)">{w.rank}{SUIT_SYMBOLS[w.suit]}</span></span>
          {/if}
        </div>
      {/if}

      {#if game.phase === 'trick_done' && game.trickWinner && winnerCard}
        <div class="trick-result">
          <span class="tr-winner">{game.trickWinner}</span>
          <span class="tr-text">({game.trickWinner === 'North' || game.trickWinner === 'South' ? 'N/S' : 'E/W'}) takes trick {displayNum} with</span>
          <span class="tr-card" style:color="var(--suit-{winnerCard.suit.toLowerCase()})">{winnerCard.rank}{SUIT_SYMBOLS[winnerCard.suit]}</span>
          <span class="tr-text">— second-highest</span>
        </div>
        <button class="btn primary full" onclick={() => game.nextTrick()}>
          {game.gameOver ? 'See final score →' : 'Next trick →'}{settings.fastPlay ? ' (automatic)' : ''}
        </button>
      {/if}

      <Hand label={c.dummy === 'South' ? 'South (Dummy · North plays this hand)' : `South (${role('South')})`}
        hand={game.hands.South} trump={displayTrump}
        isTurn={who === 'South'} legal={who === 'South' ? legalPlays(game.hands.South, led) : []}
        concealed={!faceUp('South')} onplay={(card) => game.humanPlays('South', card)} />
      {#if settings.showStrength}<HandSummary hand={game.hands.South} />{/if}

      <details class="expander">
        <summary>Auction</summary>
        <div class="expander-body">
          <div class="auction-recap-note">Board #{game.boardNum} · dealer {game.dealer} · {c.declarer} declares</div>
          <AuctionGrid dealer={game.dealer} calls={game.calls} alerts={game.liveAlerts} />
        </div>
      </details>
    </div>
    {#each ['West', 'East'] as const as seat}
      <div class={seat.toLowerCase()}>
        <SeatPanel {seat} role={role(seat)} count={game.hands[seat].length} backs={!faceUp(seat)} />
        {#if faceUp(seat)}<Hand hand={game.hands[seat]} trump={displayTrump} />{/if}
      </div>
    {/each}
  </div>
{/if}
