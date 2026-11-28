// Sends a finished board (shareRecord.ts) to the site's /boards, once the
// board is over: never during play, and never with Share results off (App.svelte
// decides both). One beacon per finished board carries it and any board an
// earlier send couldn't deliver. Sending never gets in the way of the game.
import { MAX_SHARE_BATCH, readQueue, writeQueue, type SharedBoard } from './shareRecord';

export function shareBoard(storage: Storage | null, board: SharedBoard): void {
  const queue = [...readQueue(storage), board];
  const batch = queue.slice(-MAX_SHARE_BATCH);
  let sent = false;
  try {
    sent = navigator.sendBeacon('/boards', JSON.stringify({ boards: batch }));
  } catch {
    // A browser without sendBeacon, or one that refuses it: kept for the next board.
  }
  writeQueue(storage, sent ? queue.slice(0, -batch.length) : queue);
}
