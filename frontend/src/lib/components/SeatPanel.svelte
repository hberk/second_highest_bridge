<!-- A seat: name, role, card count and, for a concealed hand, a fan of backs. -->
<script lang="ts">
  import CardBacks from './CardBacks.svelte';

  let { seat, role, count, note = '', backs = true }:
    { seat: string; role: string; count: number; note?: string; backs?: boolean } = $props();
  const roleCls = $derived(role === 'Declarer' ? 'is-declarer' : role === 'Dummy' ? 'is-dummy' : '');
</script>

<div class="ai-player-box">
  <div class="seat-name">{seat}</div>
  <div class="seat-role {roleCls}">{role}</div>
  {#if backs}<CardBacks {count} />{/if}
  <div class="seat-count"><strong>{count} cards</strong>{note}</div>
</div>
