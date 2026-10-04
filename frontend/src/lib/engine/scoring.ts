// Port of bridge/scoring.py: full duplicate scoring.
import type { Side, Strain, Vulnerability } from './card';
import type { Doubled } from './auction';

export interface ScoredContract {
  level: number;
  strain: Strain;
  side: Side;
  tricks_needed: number;
  doubled: Doubled;
  vulnerability: Vulnerability;
}

export interface ScoreResult {
  winner: Side;
  made: boolean;
  tricks_won: number;
  tricks_needed: number;
  overtricks: number;
  undertricks: number;
  points: number;
  detail: string;
}

const sumFirst = (table: number[], n: number) =>
  table.slice(0, n).reduce((a, b) => a + b, 0);

export function scoreContract(
  contract: ScoredContract,
  tricksTaken: Record<Side, number>,
): ScoreResult {
  const side = contract.side;
  const defenders: Side = side === 'N/S' ? 'E/W' : 'N/S';
  const vul = contract.vulnerability === 'Both' || contract.vulnerability === side;
  const won = tricksTaken[side];
  const need = contract.tricks_needed;
  const { level, strain, doubled } = contract;

  if (won >= need) {
    const overtricks = won - need;
    let unit: number;
    let base: number;
    if (strain === 'C' || strain === 'D') {
      unit = 20;
      base = level * 20;
    } else if (strain === 'H' || strain === 'S') {
      unit = 30;
      base = level * 30;
    } else {
      unit = 30;
      base = 40 + (level - 1) * 30;
    }
    const mult = doubled === 'None' ? 1 : doubled === 'X' ? 2 : 4;
    const contractPts = base * mult;
    const isGame = contractPts >= 100;
    const gameBonus = isGame ? (vul ? 500 : 300) : 50;
    const slamBonus = level === 6 ? (vul ? 750 : 500) : level === 7 ? (vul ? 1500 : 1000) : 0;
    const insult = doubled === 'X' ? 50 : doubled === 'XX' ? 100 : 0;
    let overPts = 0;
    if (overtricks > 0) {
      if (doubled === 'None') overPts = overtricks * unit;
      else if (doubled === 'X') overPts = overtricks * (vul ? 200 : 100);
      else overPts = overtricks * (vul ? 400 : 200);
    }
    const total = contractPts + gameBonus + slamBonus + insult + overPts;
    const parts = [`${contractPts} contract`];
    if (overPts) parts.push(`${overPts} overtricks`);
    parts.push(`${gameBonus} ${isGame ? 'game' : 'part-score'} bonus`);
    if (slamBonus) parts.push(`${slamBonus} slam bonus`);
    if (insult) parts.push(`${insult} insult bonus`);
    return {
      winner: side, made: true, tricks_won: won, tricks_needed: need,
      overtricks, undertricks: 0, points: total,
      detail: `${parts.join(' + ')} = ${total}`,
    };
  }

  const under = need - won;
  let penalty: number;
  if (!vul) {
    if (doubled === 'None') penalty = under * 50;
    else if (doubled === 'X') penalty = sumFirst([100, 200, 200, ...Array(10).fill(300)], under);
    else penalty = sumFirst([200, 400, 400, ...Array(10).fill(600)], under);
  } else {
    if (doubled === 'None') penalty = under * 100;
    else if (doubled === 'X') penalty = sumFirst([200, ...Array(12).fill(300)], under);
    else penalty = sumFirst([400, ...Array(12).fill(600)], under);
  }
  return {
    winner: defenders, made: false, tricks_won: won, tricks_needed: need,
    overtricks: 0, undertricks: under, points: penalty,
    detail: `${under} undertrick(s) = ${penalty} pts to ${defenders}`,
  };
}
