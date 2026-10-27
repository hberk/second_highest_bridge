import { STRAIN_SYMBOLS } from '../engine/card';
import type { Contract } from '../engine/auction';

/** Python's f"{n:+d}". */
export const signed = (n: number): string => (n >= 0 ? `+${n}` : `${n}`);

export function contractLabel(c: Contract | null): string {
  return c ? `${c.level}${STRAIN_SYMBOLS[c.strain]}${c.doubled === 'None' ? '' : c.doubled} by ${c.declarer}` : 'passed out';
}
