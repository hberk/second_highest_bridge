<!-- A panel that slides up over the screen: settings, the full auction. Escape,
     the close button or a tap outside it closes it. -->
<script lang="ts">
  import type { Snippet } from 'svelte';

  let { open, title, onclose, children }: {
    open: boolean;
    title: string;
    onclose: () => void;
    children: Snippet;
  } = $props();

  let closeBtn = $state<HTMLButtonElement | null>(null);
  $effect(() => {
    if (open) closeBtn?.focus();
  });
</script>

<svelte:window onkeydown={(e) => { if (open && e.key === 'Escape') onclose(); }} />

{#if open}
  <button class="sheet-backdrop" aria-label="Close {title}" tabindex="-1" onclick={onclose}></button>
  <div class="sheet" role="dialog" aria-modal="true" aria-label={title}>
    <div class="sheet-head">
      <h2>{title}</h2>
      <button class="icon-btn" aria-label="Close" bind:this={closeBtn} onclick={onclose}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg>
      </button>
    </div>
    <div class="sheet-body">{@render children()}</div>
  </div>
{/if}
