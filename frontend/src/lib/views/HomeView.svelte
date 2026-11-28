<!-- The front door: the name, the one rule that makes this game different, and
     a way in. The table, the challenge, the rules and the history are all one
     tap from here. -->
<script lang="ts">
  import type { Game } from '../game.svelte';
  import SessionScore from '../components/SessionScore.svelte';

  let { game, onplay, ontraining, onchallenge, onhowto, onhistory, onsettings, onfriends, shareNotice = false, onsharenoticed }: {
    game: Game;
    onplay: () => void;
    ontraining: () => void;
    onchallenge: () => void;
    onhowto: () => void;
    onhistory: () => void;
    onsettings: () => void;
    /** Multiplayer tables, on the table server. */
    onfriends: () => void;
    /** The one-time line that finished boards are shared (Settings turns it off). */
    shareNotice?: boolean;
    onsharenoticed?: () => void;
  } = $props();

  /** A board you've started is waiting for you on the table. */
  const started = $derived(game.phase !== 'bidding' || game.calls.some(([p]) => p === game.mySeat));
  const live = $derived(started && !game.boardOver);
</script>

<div class="home">
  <div class="home-top">
    <button class="icon-btn" aria-label="Settings" onclick={onsettings}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"></path></svg>
    </button>
  </div>

  {#if shareNotice}
    <div class="notice info share-notice" role="status">
      <span>Finished boards are shared anonymously to help improve the robots.</span>
      <span class="share-notice-actions">
        <button class="link-btn" onclick={onsettings}>Settings</button>
        <button class="link-btn" onclick={onsharenoticed}>OK</button>
      </span>
    </div>
  {/if}
  <div class="home-hero">
    <!-- A heart trick: A K 9 4, and the king takes it. -->
    <div class="home-felt" aria-hidden="true">
      <div class="home-card" style:transform="rotate(-12deg) translateY(10px)"><span>A</span><span class="home-pip">♥</span></div>
      <div class="home-card home-winner" style:transform="translateY(-18px)"><span>K</span><span class="home-pip">♥</span></div>
      <div class="home-card" style:transform="rotate(6deg) translateY(6px)"><span>9</span><span class="home-pip">♥</span></div>
      <div class="home-card" style:transform="rotate(14deg) translateY(16px)"><span>4</span><span class="home-pip">♥</span></div>
    </div>
    <h1 class="home-title">Second-Highest<br />Bridge</h1>
    <p class="home-tagline">Contract bridge with one twist: the <span class="accent">second-highest</span> card takes the trick.</p>
  </div>

  <nav class="home-actions" aria-label="Start">
    <button class="btn primary full huge" onclick={onplay}>{live ? `Resume board ${game.boardNum}` : 'Play'}</button>
    <button class="btn ghost full big" onclick={ontraining}>Bidding training</button>
    <button class="btn ghost full big" onclick={onchallenge}>Challenge the robots</button>
    <button class="btn ghost full big" onclick={onfriends}>Play with friends</button>
    <div class="home-links">
      <button class="link-btn" onclick={onhowto}>How to play</button>
      <button class="link-btn" onclick={onhistory}>Hand history</button>
    </div>
    <SessionScore history={game.history} challengeLog={game.challengeLog} passedOut={game.passedOutCount} />
  </nav>
</div>

<style>
  .share-notice { display: flex; align-items: center; gap: 2px 12px; flex-wrap: wrap; margin: 0 0 8px; }
  .share-notice > span:first-child { flex: 1 1 200px; }
  .share-notice-actions { display: flex; gap: 8px; margin-left: auto; }
  .share-notice .link-btn { padding: 4px; }
</style>
