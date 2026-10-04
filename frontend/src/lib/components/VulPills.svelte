<!-- Filled vs outlined carries the state as well as the red does, so it
     survives colour blindness. -->
<script lang="ts">
  import type { Vulnerability } from '../engine/card';

  let { vul }: { vul: Vulnerability } = $props();
  const pills = $derived([
    ['N-S', vul === 'N/S' || vul === 'Both'],
    ['E-W', vul === 'E/W' || vul === 'Both'],
  ] as const);
</script>

<div class="vul-pills">
  {#each pills as [label, on]}
    <span class="vul-pill {on ? 'vul-on' : 'vul-off'}"><span aria-hidden="true">{label}</span><span class="sr-only">{label} {on ? 'vulnerable' : 'not vulnerable'}. </span></span>
  {/each}
</div>
