<!-- Every bid from 1C to 7NT as seven level rows by five strains, with Pass /
     Double / Redouble above. Bids no longer available stay visible, greyed, so
     the player can see how much room is left. The alert field is a self-alert,
     as on BBO: type the explanation, then make the call, and the two go
     together. -->
<script lang="ts">
  import { LEVELS, STRAINS, STRAIN_NAMES, STRAIN_SYMBOLS } from '../engine/card';
  import { ALERT_MAX } from '../game.svelte';

  let { legal, oncall }: { legal: string[]; oncall: (call: string, alert: string) => void } = $props();
  let alert = $state('');

  function call(c: string): void {
    const why = alert;
    alert = '';
    oncall(c, why);
  }
  const actions = [['Pass', 'Pass', 'pass'], ['Double', 'X', 'dbl'], ['Redouble', 'XX', 'rdbl']] as const;
</script>

<div class="bidding-box-container">
  <div class="bidding-box-title">Your call</div>
  <div class="bid-alert-row">
    <label for="self-alert">Alert</label>
    <input id="self-alert" type="text" maxlength={ALERT_MAX} autocomplete="off" spellcheck="false"
      placeholder="Optional: explain your next call" bind:value={alert} />
  </div>
  {#if alert.trim()}<p class="bid-alert-hint">Your next call will be alerted.</p>{/if}
  <div class="bid-actions">
    {#each actions as [label, code, cls]}
      <button class="bid-btn {cls}" class:alerting={alert.trim()} disabled={!legal.includes(code)} onclick={() => call(code)}>{label}</button>
    {/each}
  </div>
  <div class="bid-grid-head">
    {#each STRAINS as strain}<span class={strain.toLowerCase()} title={STRAIN_NAMES[strain]}>{STRAIN_SYMBOLS[strain]}</span>{/each}
  </div>
  <div class="bid-ladder">
    {#each LEVELS as level}
      {#each STRAINS as strain}
        {@const code = `${level}${strain}`}
        <button class="bid-btn {strain.toLowerCase()}" class:alerting={alert.trim()} disabled={!legal.includes(code)} onclick={() => call(code)}
          aria-label="{level} {STRAIN_NAMES[strain]}">{level}{STRAIN_SYMBOLS[strain]}</button>
      {/each}
    {/each}
  </div>
</div>
