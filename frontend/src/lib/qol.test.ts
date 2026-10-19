// Table conveniences: auto-played forced cards, the last-trick button, and
// the session scoreboard.
import { describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import { Game } from './game.svelte';
import { prng } from './meanings';
import { legalPlays } from './engine/auction';
import TableView from './views/TableView.svelte';
import SessionScore from './components/SessionScore.svelte';

/** South opens or raises now and then, and plays its first legal card. */
function playBoard(game: Game, onPlaying?: (game: Game) => void): void {
  for (let guard = 0; guard < 500; guard++) {
    if (game.phase === 'bidding') {
      if (game.auction.passedOut) return;
      const bid = game.auction.legalCalls().find((c) => c === '2C' || c === '2S' || c === '3H');
      game.humanBids(guard % 3 === 0 && bid ? bid : 'Pass');
    } else if (game.phase === 'auction_done') game.startPlay();
    else if (game.phase === 'playing') {
      onPlaying?.(game);
      const who = game.whoseTurn()!;
      const led = game.trick.length ? game.trick[0][1].suit : null;
      game.humanPlays(who, legalPlays(game.hands[who], led)[0]);
    } else if (game.phase === 'trick_done') game.nextTrick();
    else return;
  }
  throw new Error('board did not finish');
}

describe('auto-play forced cards', () => {
  it('never waits on the human with only one legal card', () => {
    const game = new Game(null, prng(1));
    game.autoPlayForced = true;
    let waits = 0;
    let finished = 0;
    for (let i = 0; i < 25; i++) {
      playBoard(game, (g) => {
        const who = g.whoseTurn();
        expect(who, 'playing phase must wait on the human').not.toBeNull();
        const led = g.trick.length ? g.trick[0][1].suit : null;
        expect(legalPlays(g.hands[who!], led).length, 'a forced card was left to the human').toBeGreaterThan(1);
        waits++;
      });
      if (game.phase === 'done') {
        finished++;
        expect(game.tricksTaken['N/S'] + game.tricksTaken['E/W']).toBe(13);
        expect(Object.values(game.hands).every((h) => h.length === 0)).toBe(true);
      }
      game.newBoard();
    }
    expect(finished).toBeGreaterThan(5);
    expect(waits).toBeGreaterThan(0);
  });

  it('is off by default: the human plays the last trick themselves', () => {
    const game = new Game(null, prng(2));
    let lastTrickWaits = 0;
    for (let i = 0; i < 15; i++) {
      playBoard(game, (g) => { if (g.trickNum === 13) lastTrickWaits++; });
      game.newBoard();
    }
    expect(lastTrickWaits).toBeGreaterThan(0);
  });
});

describe('last trick', () => {
  it('is offered from trick 2 on, never during trick 1', () => {
    const game = new Game(null, prng(3));
    let offered = 0;
    for (let i = 0; i < 10; i++) {
      playBoard(game, (g) => {
        const html = render(TableView, { props: { game: g } }).body;
        if (g.tricksLog.length === 0) expect(html).not.toContain('Last trick');
        else {
          expect(html).toContain('Last trick');
          offered++;
        }
      });
      game.newBoard();
    }
    expect(offered).toBeGreaterThan(0);
  });
});

describe('session scoreboard', () => {
  it('counts passed-out boards', () => {
    const game = new Game(null, prng(4));
    let seen = 0;
    for (let i = 0; i < 60; i++) {
      while (game.phase === 'bidding' && !game.auction.isComplete) game.humanBids('Pass');
      if (game.auction.passedOut) seen++;
      game.newBoard();
    }
    expect(seen).toBeGreaterThan(0);
    expect(game.passedOutCount).toBe(seen);
  });

  it('totals N/S scores and leaves imported boards out', () => {
    const game = new Game(null, prng(5));
    for (let i = 0; i < 12; i++) {
      playBoard(game);
      game.newBoard();
    }
    const total = game.history.reduce((a, h) => a + (h.result!.winner === 'N/S' ? h.result!.points : -h.result!.points), 0);
    const props = { history: game.history, challengeLog: game.challengeLog, passedOut: game.passedOutCount };
    const html = render(SessionScore, { props }).body;
    const boards = game.history.length + game.passedOutCount;
    expect(html).toContain(`${boards} board${boards === 1 ? '' : 's'}`);
    expect(html).toContain(total >= 0 ? `+${total}` : `${total}`);

    const imported = { ...game.history[0], board_num: 999, imported: true };
    const withImport = render(SessionScore, { props: { ...props, history: [...game.history, imported] } }).body;
    expect(withImport).not.toContain('#999');
    expect(withImport).toContain(`${boards} board${boards === 1 ? '' : 's'}`);
  });

  it('shows the margin against the robots on challenge boards', () => {
    const game = new Game(null, prng(6));
    for (let i = 0; i < 8; i++) {
      game.dealChallenge();
      playBoard(game);
    }
    if (!game.challengeLog.length) return;
    const margin = game.challengeLog.reduce((a, r) => a + r.margin, 0);
    const html = render(SessionScore, {
      props: { history: game.history, challengeLog: game.challengeLog, passedOut: game.passedOutCount },
    }).body;
    expect(html).toContain('vs robots');
    expect(html).toContain(margin >= 0 ? `+${margin}` : `${margin}`);
  });
});
