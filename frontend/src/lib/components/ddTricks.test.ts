// The tricks table, one row per declarer (Bidding training and History).
import { describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import training from '$root/data/training_deals.json';
import { PLAYERS } from '../engine/auction';
import { STRAINS } from '../engine/card';
import DdTricks from './DdTricks.svelte';

describe('Tricks double dummy', () => {
  it('shows each declarer, boxing the contract played', () => {
    // Training deal 294: 5♣ by South takes 10, by North 11 (2026-11-21). A
    // table of the better declarer showed 11 beside a score of down one.
    const d = training.deals.find((x) => x.id === 294)!;
    const tr = d.tricks as Record<string, number>;
    const tricks = Object.fromEntries(STRAINS.map((s) => [s, Object.fromEntries(PLAYERS.map((p) => [p, tr[`${s}:${p}`]]))]));
    const html = render(DdTricks, { props: { tricks, seats: PLAYERS, contract: { strain: 'C', declarer: 'South' } } }).body;
    const rows = Object.fromEntries(html.split('bt-dd-l">').slice(1).map((chunk) =>
      [chunk.slice(0, chunk.indexOf('<')), [...chunk.matchAll(/>(\d+)</g)].map((x) => Number(x[1]))]));
    expect(rows).toEqual(Object.fromEntries(PLAYERS.map((p) => [p, STRAINS.map((s) => tr[`${s}:${p}`])])));
    expect(html.match(/bt-dd-mine[^>]*>(\d+)</)![1]).toBe('10');
    expect(html.match(/bt-dd-mine/g)).toHaveLength(1);
  });

  it('shows a strain still being solved as …', () => {
    const html = render(DdTricks, { props: { tricks: { C: { North: 9, East: 4, South: 9, West: 4 } }, seats: PLAYERS } }).body;
    expect(html.match(/…/g)).toHaveLength(16);
  });
});
