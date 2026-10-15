// Drives the table's state machine the way a player would -- free boards and
// challenge boards, start to finish -- and renders every view at every step,
// so a template error or a stuck phase fails here rather than in the browser.
// The counterpart of tests/test_app_flow.py.
import { describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import { Game } from './game.svelte';
import { legalPlays } from './engine/auction';
import TableView from './views/TableView.svelte';
import HistoryView from './views/HistoryView.svelte';
import ChallengeView from './views/ChallengeView.svelte';

let openingLeads = 0;

function renderAll(game: Game): string {
  const html = render(TableView, { props: { game } }).body;
  render(HistoryView, { props: { records: game.history } });
  render(ChallengeView, { props: { game, ondealt: () => {} } });
  return html;
}

/** South passes unless it can open or raise cheaply, and plays its first
 *  legal card: crude, but it walks every phase. */
function playBoard(game: Game): void {
  for (let guard = 0; guard < 500; guard++) {
    const html = renderAll(game);
    const auction = game.auction;
    if (game.phase === 'bidding') {
      if (auction.passedOut) return;
      expect(html).toContain('Your call');
      const legal = auction.legalCalls();
      const bid = legal.find((c) => c === '2C' || c === '2S' || c === '3H');
      game.humanBids(guard % 3 === 0 && bid ? bid : 'Pass');
    } else if (game.phase === 'auction_done') {
      expect(html).toContain('Start play');
      game.startPlay();
    } else if (game.phase === 'playing') {
      const who = game.whoseTurn();
      expect(who, 'playing phase must wait on the human').not.toBeNull();
      const led = game.trick.length ? game.trick[0][1].suit : null;
      expect(html).toContain('Your turn');
      if (!game.played.length && !game.trick.length) {
        // South is on opening lead, and leads blind: dummy is not down yet.
        // South's own hand is buttons, so no face-up card row may appear.
        expect(html, 'dummy face-up before the opening lead').not.toContain('pcard-row');
        openingLeads++;
      }
      game.humanPlays(who!, legalPlays(game.hands[who!], led)[0]);
    } else if (game.phase === 'trick_done') {
      expect(html).toContain('second-highest');
      game.nextTrick();
    } else {
      expect(html).toContain('Hand Complete');
      return;
    }
  }
  throw new Error('board did not finish');
}

describe('table flow', () => {
  it('plays free boards to the end and records them', () => {
    const game = new Game();
    let finished = 0;
    for (let i = 0; i < 40; i++) {
      playBoard(game);
      if (game.phase === 'done') {
        finished++;
        const r = game.result!;
        expect(game.tricksTaken['N/S'] + game.tricksTaken['E/W']).toBe(13);
        expect(Object.values(game.hands).every((h) => h.length === 0)).toBe(true);
        expect(r.tricks_needed).toBe(game.contract!.tricks_needed);
      }
      game.newBoard();
    }
    expect(finished).toBeGreaterThan(10);
    expect(openingLeads, 'no blind opening lead was exercised').toBeGreaterThan(0);
    expect(game.history.length).toBe(finished);
    expect(game.history.every((h) => h.tricks_log.length === 13)).toBe(true);
  });

  it('grades challenge boards against the robot table', () => {
    const game = new Game();
    let graded = 0;
    for (let i = 0; i < 25; i++) {
      expect(game.dealChallenge()).toBe(true);
      expect(game.challengeId).not.toBeNull();
      playBoard(game);
      if (game.phase !== 'done') continue;
      graded++;
      const ch = game.challenge!;
      // par - actual = bidding_loss + play_loss, exactly.
      for (const g of [ch.you, ch.robot]) {
        expect(g.par.score - g.actual).toBe(g.bidding_loss + g.play_loss);
      }
      expect(ch.margin).toBe(ch.you.actual - ch.robot.actual);
      const html = render(ChallengeView, { props: { game, ondealt: () => {} } }).body;
      expect(html).toContain('Review the deal');
      expect(render(TableView, { props: { game } }).body).toContain('Where the points went');
    }
    expect(graded).toBeGreaterThan(5);
    // Every board is logged, passed-out ones included, each deal once.
    expect(game.challengeLog.length).toBe(25);
    expect(new Set(game.challengeLog.map((r) => r.deal_id)).size).toBe(25);
  });

  it('grades a challenge board that passes out', () => {
    // Find a library deal the robots pass out when South passes too.
    const game = new Game();
    let found = false;
    for (let id = 0; id < 400 && !found; id++) {
      game.newBoard(id);
      while (!game.auction.isComplete) game.humanBids('Pass');
      found = game.auction.passedOut;
    }
    expect(found, 'no library deal passes out').toBe(true);
    const ch = game.challenge!;
    expect(ch, 'a passed-out challenge board was not graded').not.toBeNull();
    expect(ch.you.passed_out).toBe(true);
    expect(ch.you.actual).toBe(0);
    expect(ch.margin).toBe(-ch.robot.actual);
    expect(game.challengeLog.at(-1)!.deal_id).toBe(ch.deal_id);
    expect(game.boardOver).toBe(true);
    const table = render(TableView, { props: { game } }).body;
    expect(table).toContain('Passed Out');
    expect(table).toContain('Where the points went');
    const review = render(ChallengeView, { props: { game, ondealt: () => {} } }).body;
    expect(review, 'still claims the board is in play').not.toContain('Finish it');
    expect(review).toContain('Your board');
    expect(review).toContain("Robots' board");
  });

  it('refuses illegal or out-of-turn actions', () => {
    const game = new Game();
    const before = game.calls.length;
    game.humanBids('8NT');
    expect(game.calls.length).toBe(before);
    if (game.auction.currentPlayer() === 'South') {
      game.humanBids('Pass');
      expect(game.calls.length).toBeGreaterThan(before);
    }
  });
});
