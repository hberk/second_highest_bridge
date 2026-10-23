<!-- The bar across the top of every screen but home: back on the left, what
     this screen is in the middle, and room on the right for a screen's own
     controls. -->
<script lang="ts">
  import type { Snippet } from 'svelte';

  let { onback, title = '', sub = '', center, right }: {
    onback?: () => void;
    title?: string;
    sub?: string;
    center?: Snippet;
    right?: Snippet;
  } = $props();
</script>

<header class="topbar">
  {#if onback}
    <button class="icon-btn plain" aria-label="Back to home" onclick={onback}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"></path></svg>
    </button>
  {:else}<span></span>{/if}
  <div class="topbar-center">
    {#if center}{@render center()}
    {:else}
      <div class="topbar-title">{title}</div>
      {#if sub}<div class="topbar-sub">{sub}</div>{/if}
    {/if}
  </div>
  <div class="topbar-right">{#if right}{@render right()}{/if}</div>
</header>
