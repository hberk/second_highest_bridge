// Drives the table's state machine the way a player would -- free boards and
// challenge boards, start to finish -- and renders every view at every step,
// so a template error or a stuck phase fails here rather than in the browser.
import { describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import { Game } from './game.svelte';
import { prng } from './meanings';
import { legalPlays } from './engine/auction';
import { SUIT_SYMBOLS, type Seat, type Suit } from './engine/card';
import { seatAt } from './seats';
import TableView from './views/TableView.svelte';
import DesktopTableView from './views/DesktopTableView.svelte';
import HistoryView from './views/HistoryView.svelte';
import ChallengeView from './views/ChallengeView.svelte';

let openingLeads = 0;
let sideDummies = 0;

/** The table in both layouts, phone and desktop; every check below must hold
 *  for each. */
function renderAll(game: Game): string[] {
  const tables = [render(TableView, { props: { game } }).body, render(DesktopTableView, { props: { game } }).body];
  render(HistoryView, { props: { records: game.history } });
  render(ChallengeView, { props: { game, ondealt: () => {} } });
  return tables;
}

/** Each layout's markup contains `text`. */
function expectBoth(htmls: string[], text: string, why?: string): void {
  for (const [i, html] of htmls.entries()) expect(html, `${['phone', 'desktop'][i]}: ${why ?? text}`).toContain(text);
}

/** South passes unless it can open or raise cheaply, and plays its first
 *  legal card: crude, but it walks every phase. */
function playBoard(game: Game): void {
  for (let guard = 0; guard < 500; guard++) {
    const htmls = renderAll(game);
    const auction = game.auction;
    if (game.phase === 'bidding') {
      if (auction.passedOut) return;
      expectBoth(htmls, 'Your call');
      // Your calls sit at the bottom of the felt, whatever seat you're in.
      const bottom = /af-seat af-south">(?:<!--[^>]*-->|\s)*<div class="bc-stack" role="group" aria-label="(\w+)'s calls"/;
      expect(htmls[0], 'phone: no auction seat at the bottom').toMatch(bottom);
      expect(htmls[0].match(bottom)![1], 'phone: someone else at the bottom of the auction').toBe(game.mySeat);
      const legal = auction.legalCalls();
      const bid = legal.find((c) => c === '2C' || c === '2S' || c === '3H');
      game.humanBids(guard % 3 === 0 && bid ? bid : 'Pass');
    } else if (game.phase === 'auction_done') {
      expectBoth(htmls, 'Start play');
      game.startPlay();
    } else if (game.phase === 'playing') {
      const who = game.whoseTurn();
      expect(who, 'playing phase must wait on the human').not.toBeNull();
      const led = game.trick.length ? game.trick[0][1].suit : null;
      expectBoth(htmls, 'Your turn');
      if (!game.played.length && !game.trick.length) {
        // South is on opening lead, and leads blind: dummy is not down yet.
        // Dummy's hand goes above the felt only once the lead is made.
        for (const html of htmls) expect(html, 'dummy face-up before the opening lead').not.toContain('dummy-zone');
        openingLeads++;
      }
      // You sit at the bottom of the trick, in both layouts.
      expectBoth(htmls, 'tf-seat tf-south"><span class="tf-label">You', 'you at the bottom of the felt');
      // An opponent's dummy sits on its own side of the table, not on top.
      const c = game.contract!;
      const me = game.mySeat;
      if ((game.trickNum > 1 || game.trick.length > 0) && (c.dummy === seatAt(me, 'left') || c.dummy === seatAt(me, 'right'))) {
        expect(htmls[0], 'phone: dummy beside the felt').toContain('side-hand');
        expect(htmls[1], 'desktop: dummy in its seat panel').toContain('dk-side-dummy');
        // On the side its cards land on the felt: right of you is right,
        // whatever the compass says.
        const onRight = c.dummy === seatAt(me, 'right');
        expect(htmls[0].includes('class="play-row dummy-east"'),
          `phone: ${me} sees ${c.dummy}'s dummy on the ${onRight ? 'left' : 'right'}; its cards land on the ${onRight ? 'right' : 'left'}`)
          .toBe(onRight);
        // Dummy's trumps on declarer's left: the top row when declarer
        // sits on your left, the bottom row when declarer sits on your right.
        if (c.trump !== 'NT') {
          for (const [i, html] of htmls.entries()) {
            const hand = html.slice(html.indexOf('side-hand'));
            const rows = [...hand.matchAll(/class="side-sym"[^>]*>([♠♥♦♣])</g)].slice(0, 4).map((r) => r[1]);
            expect(rows[onRight ? 0 : 3], `${['phone', 'desktop'][i]}: ${c.declarer} declares ${c.trump}; dummy's trumps on declarer's left`)
              .toBe(SUIT_SYMBOLS[c.trump as Suit]);
          }
        }
        sideDummies++;
      }
      game.humanPlays(who!, legalPlays(game.hands[who!], led)[0]);
    } else if (game.phase === 'trick_done') {
      expectBoth(htmls, 'trick-won');
      game.nextTrick();
    } else {
      expectBoth(htmls, 'Hand complete', 'the result');
      return;
    }
  }
  throw new Error('board did not finish');
}

describe('table flow', () => {
  it('plays free boards to the end and records them', () => {
    const game = new Game(null, prng(1));
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
    expect(sideDummies, 'no East or West dummy was exercised').toBeGreaterThan(0);
    expect(game.history.length).toBe(finished);
    expect(game.history.every((h) => h.tricks_log.length === 13)).toBe(true);
  });

  it('seats the player anywhere: you are always at the bottom, partner across', () => {
    for (const seat of ['North', 'East', 'West'] as Seat[]) {
      const game = new Game(null, prng(30), seat);
      let finished = 0;
      for (let i = 0; i < 10; i++) {
        playBoard(game);
        if (game.phase === 'done') {
          finished++;
          expect(game.tricksTaken['N/S'] + game.tricksTaken['E/W']).toBe(13);
          // The result is told from your side.
          const side = seat === 'North' ? 'N/S' : 'E/W';
          expectBoth(renderAll(game), `<div class="res-to">to ${side}</div>`);
        }
        game.newBoard();
      }
      expect(finished, `${seat}: no board finished`).toBeGreaterThan(2);
    }
  });

  it('grades challenge boards against the robot table', () => {
    const game = new Game(null, prng(2));
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
      expectBoth(renderAll(game), 'Where the points went');
    }
    expect(graded).toBeGreaterThan(5);
    // Every board is logged, passed-out ones included, each deal once.
    expect(game.challengeLog.length).toBe(25);
    expect(new Set(game.challengeLog.map((r) => r.deal_id)).size).toBe(25);
  });

  it('grades a challenge board that passes out', () => {
    // Find a library deal the robots pass out when South passes too.
    const game = new Game(null, prng(3));
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
    const tables = renderAll(game);
    expectBoth(tables, 'Passed out');
    expectBoth(tables, 'Where the points went');
    const review = render(ChallengeView, { props: { game, ondealt: () => {} } }).body;
    expect(review, 'still claims the board is in play').not.toContain('Finish it');
    expect(review).toContain('Your board');
    expect(review).toContain("Robots' board");
  });

  it('refuses illegal or out-of-turn actions', () => {
    const game = new Game(null, prng(4));
    const before = game.calls.length;
    game.humanBids('8NT');
    expect(game.calls.length).toBe(before);
    if (game.auction.currentPlayer() === 'South') {
      game.humanBids('Pass');
      expect(game.calls.length).toBeGreaterThan(before);
    }
  });
});
