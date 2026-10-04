<!-- Contract text with the suit symbol in that suit's ink. `light` is for dark
     panels, where the card-face inks would be too dark to read. -->
<script lang="ts">
  import { STRAIN_NAMES, STRAIN_SYMBOLS, type Strain } from '../engine/card';

  let { level, strain, light = true }: { level: number | string; strain: Strain; light?: boolean } = $props();
  const ink = $derived(`var(--suit-${strain.toLowerCase()}${light ? '-lt' : ''})`);
</script>

{level}<span style:color={ink} aria-hidden="true">{STRAIN_SYMBOLS[strain]}</span><span class="sr-only"> {STRAIN_NAMES[strain]}</span>
