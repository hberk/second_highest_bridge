<!-- Bidding training: bid with a robot partner against robot opponents, with
     no card play. While you bid, your hand shows its judgement points; the
     moment the auction ends the bidding box gives way to the recap, all on
     this screen: your score against par, partner's hand beside yours, the
     judgement points you held together, your calls against the robot's, and
     what each strain makes double dummy. -->
<script lang="ts">
  import { rankText } from '../components/format';
  import { STRAIN_SYMBOLS, SUIT_SYMBOLS, parseBid, type Card, type Seat, type Strain as StrainT, type Suit } from '../engine/card';
  import type { Contract } from '../engine/auction';
  import { GAME, GAME_MAJOR, SLAM } from '../engine/gib';
  import { Hand } from '../engine/gib';
  import type { Trainer } from '../trainer.svelte';
  import { VUL_TEXT as VUL } from '../tableModel.svelte';
  import AuctionFelt from '../components/AuctionFelt.svelte';
  import BidPad from '../components/BidPad.svelte';
  import Fan from '../components/Fan.svelte';
  import Strain from '../components/Strain.svelte';
  import AuctionGrid from '../components/AuctionGrid.svelte';
  import Sheet from '../components/Sheet.svelte';

  let { trainer }: { trainer: Trainer } = $props();

  const JP: Record<string, number> = { K: 3, Q: 3, A: 1, J: 1, '10': 1, '9': 1 };
  const ORDER: Suit[] = ['S', 'H', 'D', 'C'];
  const COLUMNS: Seat[] = ['West', 'North', 'East', 'South'];

  const auction = $derived(trainer.auction);
  const recap = $derived(trainer.recap);
  const mine = $derived(new Hand(trainer.hands.South));
  const shape = (h: Hand) => ORDER.map((s) => h.len[s]).join('-');
  let showEW = $state(false);
  /** The whole auction, call by call: the felt shows only each seat's last few. */
  let auctionOpen = $state(false);

  const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : '0');
  const pct = (n: number) => `${(n / 40) * 100}%`;

  /** The auction under its seats, West first, with your calls looked at. */
  /** An auction under its seats, West first. */
  function gridOf(calls: [Seat, string][]) {
    const blanks = (COLUMNS.indexOf(trainer.dealer) + 4) % 4;
    return [...Array.from({ length: blanks }, () => null),
      ...calls.map(([who, call], i) => ({ who, call, i }))];
  }
  const cells = $derived(gridOf(trainer.calls));
  const robotCells = $derived(recap ? gridOf(recap.robotCalls) : []);
  /** Where the two auctions part: the seat, your table's call, the robots'. */
  const parting = $derived.by(() => {
    if (!recap || recap.parting === null) return null;
    const i = recap.parting;
    const mine = trainer.calls[i];
    const theirs = recap.robotCalls[i];
    return { i, who: (mine ?? theirs)![0], mine: mine?.[1] ?? null, theirs: theirs?.[1] ?? null,
      why: recap.robotAlerts[i] ?? null };
  });
  const checkAt = (i: number) => recap?.checks.find((c) => c.index === i) ?? null;
  const notes = $derived(recap ? recap.checks.filter((c) => c.robot !== c.call || c.misfits.length) : []);

  const verdict = $derived.by(() => {
    if (!recap) return '';
    const t = recap.judge.you + recap.judge.partner;
    if (t >= SLAM) return `slam values (${SLAM}+)`;
    if (t >= GAME) return `game in any strain (${GAME}+)`;
    if (t >= GAME_MAJOR) return `a major game, with a fit (${GAME_MAJOR}+)`;
    return `short of game (a major game needs ${GAME_MAJOR})`;
  });

  function callShort(call: string): string {
    return call === 'X' ? 'Dbl' : call === 'XX' ? 'Rdbl' : call;
  }
</script>

{#snippet callText(call: string)}
  {@const b = parseBid(call)}
  {#if b}<Strain level={b[0]} strain={b[1]} />{:else}{callShort(call)}{/if}
{/snippet}

{#snippet contractText(c: Contract | null)}
  {#if c}<Strain level={c.level} strain={c.strain} />{#if c.doubled !== 'None'}<span class="accent"> {c.doubled}</span>{/if}{:else}Passed out{/if}
{/snippet}

{#snippet handPanel(seat: Seat, title: string, cards: Card[])}
  {@const h = new Hand(cards)}
  <div class="bt-hand" aria-label="{title}'s hand">
    <div class="bt-hand-head"><span>{title}</span><b>{h.judge} JP</b></div>
    <div class="bt-hand-sub">{h.hcp} HCP · {shape(h)}</div>
    {#each ORDER as s (s)}
      {@const cs = cards.filter((c) => c.suit === s)}
      <div class="bt-suit"><span class="bt-pip s-{s.toLowerCase()}">{SUIT_SYMBOLS[s]}</span>
        {#if cs.length}{#each cs as c (c.rank)}<span class:bt-jp={JP[c.rank]}>{rankText(c.rank)}</span>{/each}{:else}<span class="dim">—</span>{/if}
      </div>
    {/each}
  </div>
{/snippet}

<div class="table-screen bt">
  {#if !recap}
    <!-- ── Bidding ─────────────────────────────────────────────────────────── -->
    <header class="topbar bt-top">
      <span></span>
      <div class="topbar-center">
        <div class="topbar-title">Bidding training · board {trainer.boardNum}</div>
        <div class="topbar-sub">{trainer.dealer} deals · {VUL[trainer.vulnerability]} · bid only, no play</div>
      </div>
      <button class="icon-btn" aria-label="Show the whole auction" onclick={() => (auctionOpen = true)}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10"></path></svg>
      </button>
    </header>
    <div class="table-body">
      <AuctionFelt calls={trainer.calls} alerts={trainer.liveAlerts} dealer={trainer.dealer}
        turn={auction.isComplete ? null : auction.currentPlayer()} />
      <section class="hand-zone bt-hand-zone">
        <div class="hand-head">
          <span class="eyebrow">Your hand</span>
          <span class="hand-strength"><b class="accent">{mine.judge} JP</b> · {mine.hcp} HCP · {shape(mine)}</span>
        </div>
        <Fan cards={trainer.hands.South} size="md" label="Your hand" jp />
        <p class="bt-strip">Judgement points: <b>K, Q = 3 · A, J, 10, 9 = 1</b>. Bids show HCP; game is judged on JP.</p>
      </section>
      {#if !auction.isComplete && auction.currentPlayer() === 'South'}
        <BidPad {auction} oncall={(call, alert) => trainer.humanBids(call, alert)} />
      {/if}
    </div>

  {:else}
    <!-- ── Recap: the same screen, the auction over ────────────────────────── -->
    <div class="table-body scroll bt-recap">
      <section class="bt-card bt-result">
        <div>
          <div class="bt-contract">
            {@render contractText(recap.contract)}{#if recap.contract}{" "}<span class="dim">by {recap.contract.declarer}</span>{/if}
            · {signed(recap.score)}
          </div>
          <div class="bt-sub">
            {#if recap.contract}{recap.contract.side === 'N/S' ? recap.tricks : 13 - recap.tricks} tricks double dummy · {/if}
            <b>par {#if recap.par.strain}<Strain level={recap.par.level} strain={recap.par.strain} />{:else}pass{/if} {signed(recap.par.score)}</b>
          </div>
          <div class="bt-sub">
            Robots bid {@render contractText(recap.robotContract)} ({signed(recap.robotScore)})
            {#if trainer.average !== null} · average {signed(trainer.average)} over {trainer.log.length}{/if}
          </div>
        </div>
        <div class="bt-diff" class:zero={recap.diff >= 0}>{signed(recap.diff)}<small>against par</small></div>
      </section>

      <div class="bt-hands">
        {@render handPanel('North', 'North · partner', trainer.hands.North)}
        {@render handPanel('South', 'South · you', trainer.hands.South)}
      </div>
      {#if showEW}
        <div class="bt-hands">
          {@render handPanel('West', 'West', trainer.hands.West)}
          {@render handPanel('East', 'East', trainer.hands.East)}
        </div>
      {/if}
      <div class="bt-links">
        <span>Underlined cards count judgement points</span>
        <button class="link-btn" onclick={() => (showEW = !showEW)}>{showEW ? 'Hide' : 'Show'} East–West</button>
      </div>

      <section class="bt-card">
        <div class="eyebrow">Was there a game?</div>
        <div class="bt-meter" role="img"
          aria-label="You {recap.judge.you} plus North {recap.judge.partner} judgement points, against {GAME_MAJOR} for a major game, {GAME} for 3NT and {SLAM} for slam">
          <span class="bt-bar you" style:left="0" style:width={pct(recap.judge.you)}></span>
          <span class="bt-bar partner" style:left={pct(recap.judge.you)} style:width={pct(recap.judge.partner)}></span>
          <span class="bt-tick up" class:hit={recap.judge.you + recap.judge.partner >= GAME_MAJOR} style:left={pct(GAME_MAJOR)}><i class="left">{GAME_MAJOR} ♥♠ game</i></span>
          <span class="bt-tick down" class:hit={recap.judge.you + recap.judge.partner >= GAME} style:left={pct(GAME)}><i>{GAME} 3NT</i></span>
          <span class="bt-tick up" class:hit={recap.judge.you + recap.judge.partner >= SLAM} style:left={pct(SLAM)}><i>{SLAM} slam</i></span>
        </div>
        <p class="bt-note">
          You {recap.judge.you} + North {recap.judge.partner} = <b>{recap.judge.you + recap.judge.partner} JP</b>: {verdict}.
          Best fit: {recap.fit.length} {SUIT_SYMBOLS[recap.fit.suit]}.
          {#if recap.hcp.you - recap.judge.you >= 3}Your {recap.hcp.you} HCP are only {recap.judge.you} JP.{:else if recap.judge.you - recap.hcp.you >= 3}Your {recap.hcp.you} HCP are worth {recap.judge.you} JP.{/if}
        </p>
      </section>

      <section class="bt-card">
        <div class="bt-auction-title"><span class="eyebrow">Your auction</span>
          <span>{@render contractText(recap.contract)} {signed(recap.score)}</span></div>
        <div class="bt-auction">
          {#each COLUMNS as seat (seat)}<span class="bt-head">{seat}</span>{/each}
          {#each cells as cell, k (k)}
            {#if cell === null}<span></span>
            {:else}
              {@const check = checkAt(cell.i)}
              <span class:bt-me={cell.who === 'South'} class:bt-bad={check && check.robot !== cell.call}
                class:bt-part={parting?.i === cell.i}>
                {@render callText(cell.call)}{#if check}{check.robot === cell.call ? ' ✓' : ' ✗'}{/if}
                {#if check && check.robot !== cell.call}<small class="bt-robot">robot: {@render callText(check.robot)}</small>{/if}
              </span>
            {/if}
          {/each}
        </div>
        {#each notes as n (n.index)}
          <p class="bt-note">
            <b>{@render callText(n.call)}</b>{#if n.meaning}{" "}showed: {n.meaning}{:else if n.call !== 'Pass'} has no agreed meaning here.{:else}.{/if}
            {#if n.misfits.length}You hold {n.misfits.join(' and ')}.{/if}
            {#if n.robot !== n.call}The robot would bid {@render callText(n.robot)}.{/if}
          </p>
        {/each}

        <div class="bt-auction-title bt-robots-title"><span class="eyebrow">Robots' auction, same deal</span>
          <span>{@render contractText(recap.robotContract)} {signed(recap.robotScore)}</span></div>
        <div class="bt-auction">
          {#each COLUMNS as seat (seat)}<span class="bt-head">{seat}</span>{/each}
          {#each robotCells as cell, k (k)}
            {#if cell === null}<span></span>
            {:else}
              <span class:bt-me={cell.who === 'South'} class:bt-part={parting?.i === cell.i}>{@render callText(cell.call)}</span>
            {/if}
          {/each}
        </div>
        <p class="bt-note">
          {#if parting === null}The robots bid it exactly as you did.
          {:else}
            The auctions part at {parting.who === 'South' ? 'your' : `${parting.who}'s`} call:
            {#if parting.mine}{@render callText(parting.mine)}{:else}the auction over{/if} at your table,
            {#if parting.theirs}{@render callText(parting.theirs)}{:else}the auction over{/if} at the robots'.
            {#if parting.theirs && parting.why}The robots' {@render callText(parting.theirs)}: {parting.why}{/if}
          {/if}
        </p>
      </section>

      <section class="bt-card">
        <div class="bt-dd">
          <span class="bt-dd-l">makes</span>
          {#each ['C', 'D', 'H', 'S', 'NT'] as s (s)}
            {@const n = recap.dd[s as StrainT]}
            <span class:best={recap.par.strain === s}>{#if n >= 7}<Strain level={n - 6} strain={s as StrainT} />{:else}—{/if}</span>
          {/each}
          <span class="bt-dd-l">tricks</span>
          {#each ['C', 'D', 'H', 'S', 'NT'] as s (s)}
            <span class:best={recap.par.strain === s}>{recap.dd[s as StrainT]}</span>
          {/each}
        </div>
        <p class="bt-note">N/S tricks double dummy, the better declarer.</p>
      </section>

      <button class="btn primary full big bt-next" onclick={() => { showEW = false; trainer.newBoard(); }}>Next board</button>
    </div>
  {/if}
</div>

<Sheet open={auctionOpen && !recap} title="Auction · board {trainer.boardNum}" onclose={() => (auctionOpen = false)}>
  <p class="caption">{trainer.dealer} dealt · {VUL[trainer.vulnerability]}. Calls marked ! were alerted: tap one to read it.</p>
  <AuctionGrid dealer={trainer.dealer} calls={trainer.calls} alerts={trainer.liveAlerts} />
</Sheet>
