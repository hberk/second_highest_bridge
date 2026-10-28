<!-- The session so far, from your side (N/S): every board you have played,
     free and challenge, passed-out ones included. Imported boards are not
     yours, so they are left out. Challenge boards also carry the margin
     against the robots on the same deal; the Challenge tab splits that into
     auction and card play. -->
<script lang="ts">
  import { STRAIN_SYMBOLS } from '../engine/card';
  import type { ChallengeLogEntry, HistoryRecord } from '../game.svelte';
  import { signed } from './format';

  let { history, challengeLog, passedOut, open = false }:
    { history: HistoryRecord[]; challengeLog: ChallengeLogEntry[]; passedOut: number; open?: boolean } = $props();

  // Boards from a multiplayer table are in History but not this session.
  const played = $derived(history.filter((h) => !h.imported && !h.table_id && h.contract && h.result));
  const margins = $derived(new Map(challengeLog.map((r) => [r.board_num, r.margin])));

  /** Points to N/S: positive when N/S scored, whoever declared. */
  const nsScore = (h: HistoryRecord) => (h.result!.winner === 'N/S' ? h.result!.points : -h.result!.points);

  const rows = $derived.by(() => {
    let running = 0;
    return played.map((h) => {
      const c = h.contract!, r = h.result!;
      const score = nsScore(h);
      running += score;
      return {
        num: h.board_num,
        contract: `${c.level}${STRAIN_SYMBOLS[c.strain]}${c.doubled === 'None' ? '' : c.doubled} ${c.declarer[0]}`,
        result: r.made ? (r.overtricks ? `+${r.overtricks}` : '=') : `−${r.undertricks}`,
        made: r.made,
        score,
        running,
        margin: margins.get(h.board_num) ?? null,
      };
    });
  });

  const boards = $derived(played.length + passedOut);
  const total = $derived(rows.length ? rows[rows.length - 1].running : 0);
  const declared = $derived(played.filter((h) => h.contract!.side === 'N/S'));
  const defended = $derived(played.filter((h) => h.contract!.side === 'E/W'));
  const made = $derived(declared.filter((h) => h.result!.made).length);
  const set = $derived(defended.filter((h) => !h.result!.made).length);
  const vsRobots = $derived(challengeLog.reduce((a, r) => a + r.margin, 0));
</script>

{#if boards}
  <details class="expander session-score" {open}>
    <summary>
      <span class="ss-title">Session</span>
      <span class="ss-item">{boards} board{boards === 1 ? '' : 's'}</span>
      <span class="ss-item">N/S <strong class:ss-plus={total > 0} class:ss-minus={total < 0}>{signed(total)}</strong></span>
      {#if challengeLog.length}
        <span class="ss-item">vs robots <strong class:ss-plus={vsRobots > 0} class:ss-minus={vsRobots < 0}>{signed(vsRobots)}</strong></span>
      {/if}
    </summary>
    <div class="expander-body">
      <div class="metrics">
        <div class="metric"><div class="metric-label">N/S total</div><div class="metric-value">{signed(total)}</div></div>
        <div class="metric"><div class="metric-label">Per board</div><div class="metric-value">{signed(Math.round(total / boards))}</div></div>
        <div class="metric"><div class="metric-label">Declaring</div><div class="metric-value">{made}/{declared.length} <span class="ss-unit">made</span></div></div>
        <div class="metric"><div class="metric-label">Defending</div><div class="metric-value">{set}/{defended.length} <span class="ss-unit">set</span></div></div>
      </div>
      {#if passedOut}<p class="caption">{passedOut} passed out (0 each).</p>{/if}
      {#if rows.length}
        <div class="table-scroll">
          <table class="challenge-table session-table">
            <thead><tr><th>Board</th><th>Contract</th><th>Result</th><th>N/S</th><th>Running</th>{#if challengeLog.length}<th>vs robots</th>{/if}</tr></thead>
            <tbody>
              {#each rows as row (row.num)}
                <tr>
                  <th>#{row.num}</th>
                  <td><span class="ss-contract">{row.contract}</span></td>
                  <td class:ss-plus={row.made} class:ss-minus={!row.made}>{row.result}</td>
                  <td>{signed(row.score)}</td>
                  <td>{signed(row.running)}</td>
                  {#if challengeLog.length}<td>{row.margin === null ? '—' : signed(row.margin)}</td>{/if}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
      {#if challengeLog.length}<p class="caption">"vs robots" is your score minus the robots' on the same challenge deal. The Challenge tab splits it into auction and card play.</p>{/if}
    </div>
  </details>
{/if}
