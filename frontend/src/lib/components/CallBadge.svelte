<!-- An auction call. With `alert`, it carries a marker and an explanation on
     hover or focus: the table equivalent of alerting a bid. Svelte escapes
     text, so alert text can never become markup. -->
<script lang="ts">
  import { parseBid } from '../engine/card';
  import Strain from './Strain.svelte';

  let { call, alert = null }: { call: string; alert?: string | null } = $props();
  const parsed = $derived(parseBid(call));
</script>

{#snippet pill()}
  {#if call === 'Pass'}<span class="bid-pill bid-pass">Pass</span>
  {:else if call === 'X'}<span class="bid-pill bid-dbl">Dbl</span>
  {:else if call === 'XX'}<span class="bid-pill bid-rdbl">Rdbl</span>
  {:else if parsed}<span class="bid-pill bid-contract" style:color="var(--suit-{parsed[1].toLowerCase()})"><Strain level={parsed[0]} strain={parsed[1]} light={false} /></span>
  {:else}<span class="bid-pill">{call}</span>{/if}
{/snippet}

{#if alert}
  <!-- Focusable so keyboard users can read the alert, as at a real table. -->
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <span class="bid-alerted" tabindex="0" role="note">
    {@render pill()}<span class="bid-alert-dot" aria-hidden="true">!</span><span class="bid-alert-tip" role="tooltip">{alert}</span>
  </span>
{:else}
  {@render pill()}
{/if}
