<!-- Every call as a button: Pass, Double, Redouble, then 1C to 7NT. One tap
     opens a box saying what the call would mean here, in the robots' system
     (which is how partner, a robot, will read it); a second tap on the same
     button makes the call. Calls that are no longer legal stay visible,
     greyed, so the player can see how much room is left.

     The box also takes a self-alert, as on BBO: the player's own explanation,
     which goes with the call. -->
<script lang="ts">
  import { LEVELS, STRAINS, STRAIN_NAMES, STRAIN_SYMBOLS, parseBid } from '../engine/card';
  import type { AuctionState } from '../engine/auction';
  import { ALERT_MAX } from '../game.svelte';
  import { callMeanings, describeCall } from '../meanings';
  import Strain from './Strain.svelte';

  /** `docked`: the pad sits in a desktop side panel, and the box opens to its
   *  left, pointing at the button, instead of above it. */
  let { auction, oncall, docked = false }:
    { auction: AuctionState; oncall: (call: string, alert: string) => void; docked?: boolean } = $props();
  const verb = $derived(docked ? 'Click' : 'Tap');

  const legal = $derived(auction.legalCalls());
  const ACTIONS = [['Pass', 'Pass'], ['X', 'Double'], ['XX', 'Redouble']] as const;

  /** The robots' reading of every call they would make here. Worked out just
   *  after the pad appears, so the first tap rarely waits; a tap that beats it
   *  works it out on the spot. */
  let meanings = $state.raw<Map<string, string> | null>(null);
  let selected = $state<string | null>(null);
  let arrowX = $state(0);
  let arrowY = $state(0);
  let alertOpen = $state(false);
  let alert = $state('');

  $effect(() => {
    const here = auction;
    meanings = null;
    selected = null;
    const timer = setTimeout(() => { meanings = callMeanings(here); }, 60);
    return () => clearTimeout(timer);
  });

  const meaning = $derived(selected && meanings ? describeCall(selected, meanings.get(selected)) : null);

  function tap(call: string, e: MouseEvent): void {
    if (selected === call) {
      const why = alert;
      selected = null;
      alert = '';
      alertOpen = false;
      oncall(call, why);
      return;
    }
    meanings ??= callMeanings(auction);
    const btn = e.currentTarget as HTMLElement;
    arrowX = btn.offsetLeft + btn.offsetWidth / 2;
    arrowY = btn.offsetTop + btn.offsetHeight / 2;
    selected = call;
    alert = '';
    alertOpen = false;
  }

  function name(call: string): string {
    const bid = parseBid(call);
    if (bid) return `${bid[0]} ${STRAIN_NAMES[bid[1]]}`;
    return call === 'X' ? 'Double' : call === 'XX' ? 'Redouble' : 'Pass';
  }
</script>

{#snippet callLabel(call: string)}
  {@const b = parseBid(call)}
  {#if b}<Strain level={b[0]} strain={b[1]} light={false} />{:else}{name(call)}{/if}
{/snippet}

<div class="bidpad" class:docked>
  {#if selected && meaning}
    <div class="meaning" role="dialog" aria-label="What {name(selected)} means here"
      style:top={docked ? `${Math.max(0, arrowY - 64)}px` : null}>
      <div class="meaning-head">
        <div>
          <div class="meaning-eyebrow">{@render callLabel(selected)}, here, {meaning.known ? 'means' : 'has'}</div>
          <div class="meaning-title">{meaning.title}</div>
        </div>
        <button class="icon-btn light" aria-label="Cancel" onclick={() => (selected = null)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg>
        </button>
      </div>
      {#if meaning.tags.length}
        <div class="meaning-tags">{#each meaning.tags as t}<span class="meaning-tag">{t}</span>{/each}</div>
      {/if}
      {#if meaning.shows}<p class="meaning-shows">{meaning.shows}</p>{/if}
      <p class="meaning-plain">{meaning.plain}</p>
      <div class="meaning-foot">
        <span>{verb} <strong>{@render callLabel(selected)}</strong> again to {selected === 'Pass' ? 'pass' : 'make the call'}.</span>
        {#if !alertOpen}
          <button class="link-btn" onclick={() => (alertOpen = true)}>Add an alert</button>
        {/if}
      </div>
      {#if alertOpen}
        <label class="meaning-alert">
          <span>Your alert, shown with the call</span>
          <input type="text" maxlength={ALERT_MAX} autocomplete="off" spellcheck="false"
            placeholder="What your call shows" bind:value={alert} />
        </label>
      {/if}
      <span class="meaning-arrow" aria-hidden="true"
        style:left={docked ? null : `${arrowX}px`} style:top={docked ? `${arrowY - Math.max(0, arrowY - 64) - 8}px` : null}></span>
    </div>
  {/if}

  <div class="bidpad-actions">
    {#each ACTIONS as [code, label] (code)}
      <button class="bid-act bid-{code.toLowerCase()}" class:selected={selected === code}
        disabled={!legal.includes(code)} aria-pressed={selected === code} onclick={(e) => tap(code, e)}>
        <span>{label}</span>{#if selected === code}<small>{verb} again</small>{/if}
      </button>
    {/each}
  </div>
  <div class="bidpad-grid">
    {#each LEVELS as level (level)}
      {#each STRAINS as strain (strain)}
        {@const code = `${level}${strain}`}
        <button class="bid-cell" class:selected={selected === code} disabled={!legal.includes(code)}
          aria-pressed={selected === code} aria-label="{level} {STRAIN_NAMES[strain]}" onclick={(e) => tap(code, e)}>
          {level}<span class="bid-cell-sym s-{strain.toLowerCase()}" aria-hidden="true">{STRAIN_SYMBOLS[strain]}</span>
        </button>
      {/each}
    {/each}
  </div>
</div>
