// C4.1 feature transforms. Pure TS: no DOM, Vue or deck.gl.
import type { Transform } from '../data/types';

/** x' = log1p(max(x, 0)) for log1p features, else x. NaN stays NaN. */
export function transformValue(x: number, t: Transform): number {
  if (t === 'log1p') return Number.isNaN(x) ? NaN : Math.log1p(Math.max(x, 0));
  return x;
}

/** Transform a row-major (n × nCols) raw matrix into float64. */
export function applyTransforms(
  raw: ArrayLike<number>,
  nCols: number,
  transforms: readonly Transform[],
): Float64Array {
  if (transforms.length !== nCols) throw new Error('transforms length must equal nCols');
  const out = new Float64Array(raw.length);
  const n = raw.length / nCols;
  for (let c = 0; c < nCols; c++) {
    const log = transforms[c] === 'log1p';
    for (let r = 0; r < n; r++) {
      const i = r * nCols + c;
      const x = raw[i];
      out[i] = log ? (Number.isNaN(x) ? NaN : Math.log1p(Math.max(x, 0))) : x;
    }
  }
  return out;
}
