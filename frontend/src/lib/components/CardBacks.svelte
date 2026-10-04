<!-- Decorative: the card count beside it carries the information. -->
<script lang="ts">
  let { count }: { count: number } = $props();
</script>

<div class="card-backs" aria-hidden="true">
  {#each { length: Math.max(0, count) } as _}<div class="cb"></div>{/each}
</div>
