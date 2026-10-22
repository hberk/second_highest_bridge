<!-- A seat beside the felt on the desktop table: who sits there, their part in
     the board, and their cards, face down. -->
<script lang="ts">
  import type { Seat } from '../engine/card';

  let { seat, role, count }: { seat: Seat; role: string; count: number } = $props();
</script>

<section class="seat-card" aria-label={seat}>
  <div>
    <div class="seat-card-name">{seat}</div>
    <div class="seat-card-role">{role}</div>
  </div>
  {#if count}
    <div class="seat-card-backs" aria-hidden="true">{#each { length: count } as _}<span></span>{/each}</div>
  {/if}
  <div class="seat-card-count"><strong>{count} card{count === 1 ? '' : 's'}</strong> · concealed</div>
</section>
