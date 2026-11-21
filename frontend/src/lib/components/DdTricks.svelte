<script lang="ts">
  // Tricks double dummy, one row per declarer: a contract's score counts its
  // own declarer's tricks, which can be a trick short of partner's (opening
  // lead from the other side), so the table never shows only the better one.
  import { STRAINS, type Seat, type Side, type Strain as StrainT } from '../engine/card';
  import Strain from './Strain.svelte';

  let { tricks, seats, par = null, contract = null }: {
    /** Strain -> declarer -> the declaring side's tricks; a missing strain shows '…'. */
    tricks: Partial<Record<StrainT, Partial<Record<Seat, number>>>>;
    seats: readonly Seat[];
    par?: { side: Side | null; strain: StrainT | null; tricks: number } | null;
    /** The contract played: its cell is boxed. */
    contract?: { strain: StrainT; declarer: Seat } | null;
  } = $props();

  const SIDE_OF: Record<Seat, Side> = { North: 'N/S', South: 'N/S', East: 'E/W', West: 'E/W' };
</script>

<div class="bt-dd">
  <span></span>
  {#each STRAINS as s (s)}<span><Strain level="" strain={s} /></span>{/each}
  {#each seats as seat (seat)}
    <span class="bt-dd-l">{seat}</span>
    {#each STRAINS as s (s)}
      {@const n = tricks[s]?.[seat]}
      <span class:best={par?.side === SIDE_OF[seat] && par.strain === s && n === par.tricks}
        class:bt-dd-mine={contract?.declarer === seat && contract.strain === s}>{n ?? '…'}</span>
    {/each}
  {/each}
</div>
