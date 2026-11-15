// C4 scoring: tolerance-kernel similarity per feature, lithology Hellinger, coverage.
// Python (doppelgrund/scoring.py) is the reference; this port computes in float64 and returns float32.
import { GROUP_IDS, type FeatureMeta, type GroupWeights } from '../data/types';

export const N_GROUPS = GROUP_IDS.length; // 5
export const COMPOSITION = GROUP_IDS.indexOf('composition'); // group index of the lithology feature

export interface ScoreInputs {
  Xe: Float64Array; // N×F transformed Earth features
  Le: Float32Array; // N×6 Earth lithology
  flags: Uint8Array; // N, bit0 = masked
  n: number;
  xt: Float64Array; // F transformed target features
  lt: Float32Array | null; // 6 target lithology (null = unmapped)
  median: Float64Array; // F (scaler median; not used by the kernel, kept for parity inputs)
  s: Float64Array; // F tolerances on the transformed scale
  groupOfFeature: Uint8Array; // F, index into GROUP_IDS
  wNum: Float64Array; // F
  wLith: number;
  C: Float64Array; // 6×6 compatibility matrix, row-major
}

export interface ScoreOutputs {
  S: Float32Array;
  coverage: Float32Array;
  groups: Float32Array; // N×N_GROUPS in GROUP_IDS order
}

/** C3 weight rule: w_f = W_group / n_group; lithology counts as one composition feature. */
export function featureWeights(
  weights: GroupWeights,
  features: readonly Pick<FeatureMeta, 'group'>[],
): { wNum: Float64Array; wLith: number } {
  const count = Object.fromEntries(GROUP_IDS.map((g) => [g, g === 'composition' ? 1 : 0]));
  for (const f of features) count[f.group] += 1;
  const wNum = Float64Array.from(features, (f) => weights[f.group] / count[f.group]);
  return { wNum, wLith: weights.composition / count.composition };
}

/** Group index (into GROUP_IDS) of each numeric feature. */
export function groupIndex(features: readonly Pick<FeatureMeta, 'group'>[]): Uint8Array {
  return Uint8Array.from(features, (f) => GROUP_IDS.indexOf(f.group));
}

/** Kernel k = exp(-0.5 z²), z = |a − b| / s on transformed values; NaN when either is missing. */
export function featureSimilarity(xt: number, xe: number, s: number): number {
  if (!Number.isFinite(xt) || !Number.isFinite(xe)) return NaN;
  const z = Math.abs(xt - xe) / s;
  return Math.exp(-0.5 * z * z);
}

/** p = normalise(v · C); null when v is not a valid lithology vector (non-finite or sum ≤ 0). */
export function smoothLith(v: ArrayLike<number>, C: Float64Array): Float64Array | null {
  let sum = 0;
  for (let i = 0; i < 6; i++) {
    if (!Number.isFinite(v[i])) return null;
    sum += v[i];
  }
  if (!(sum > 0)) return null;
  const p = new Float64Array(6);
  let tot = 0;
  for (let j = 0; j < 6; j++) {
    let acc = 0;
    for (let i = 0; i < 6; i++) acc += v[i] * C[i * 6 + j];
    p[j] = acc;
    tot += acc;
  }
  if (!(tot > 0)) return null;
  for (let j = 0; j < 6; j++) p[j] /= tot;
  return p;
}

/** k_lith = 1 − sqrt(max(0, 1 − Σ sqrt(p_i q_i))) (one minus Hellinger distance). */
export function lithSimilarity(
  le: ArrayLike<number>,
  lt: ArrayLike<number> | null,
  C: Float64Array,
): number {
  if (!lt) return NaN;
  const p = smoothLith(le, C);
  const q = smoothLith(lt, C);
  if (!p || !q) return NaN;
  let bc = 0;
  for (let i = 0; i < 6; i++) bc += Math.sqrt(p[i] * q[i]);
  return 1 - Math.sqrt(Math.max(0, 1 - bc));
}

/** Score every Earth row against one target (C4.1–C4.6). */
export function scoreAll(inp: ScoreInputs): ScoreOutputs {
  const { Xe, Le, flags, n, xt, lt, s, groupOfFeature, wNum, wLith, C } = inp;
  const F = xt.length;
  const S = new Float32Array(n);
  const coverage = new Float32Array(n);
  const groups = new Float32Array(n * N_GROUPS);

  let wAll = wLith;
  for (let f = 0; f < F; f++) wAll += wNum[f];
  const tValid = new Uint8Array(F);
  const invS = new Float64Array(F);
  for (let f = 0; f < F; f++) {
    tValid[f] = Number.isFinite(xt[f]) ? 1 : 0;
    invS[f] = 1 / s[f];
  }
  const q = lt ? smoothLith(lt, C) : null;
  const gNum = new Float64Array(N_GROUPS);
  const gDen = new Float64Array(N_GROUPS);
  const p0 = new Float64Array(6); // scratch for the smoothed Earth lithology (no per-row allocation)

  for (let r = 0; r < n; r++) {
    gNum.fill(0);
    gDen.fill(0);
    const base = r * F;
    for (let f = 0; f < F; f++) {
      if (!tValid[f]) continue;
      const xe = Xe[base + f];
      if (!Number.isFinite(xe)) continue;
      const z = Math.abs(xt[f] - xe) * invS[f];
      const w = wNum[f];
      const g = groupOfFeature[f];
      gNum[g] += w * Math.exp(-0.5 * z * z);
      gDen[g] += w;
    }
    if (q) {
      // inline smoothLith for the Earth row (hot loop: no allocation)
      const lb = r * 6;
      let sum = 0;
      let ok = true;
      for (let i = 0; i < 6; i++) {
        const v = Le[lb + i];
        if (!Number.isFinite(v)) {
          ok = false;
          break;
        }
        sum += v;
      }
      if (ok && sum > 0) {
        let tot = 0;
        let bc = 0;
        for (let j = 0; j < 6; j++) {
          let acc = 0;
          for (let i = 0; i < 6; i++) acc += Le[lb + i] * C[i * 6 + j];
          p0[j] = acc;
          tot += acc;
        }
        if (tot > 0) {
          for (let j = 0; j < 6; j++) bc += Math.sqrt((p0[j] / tot) * q[j]);
          gNum[COMPOSITION] += wLith * (1 - Math.sqrt(Math.max(0, 1 - bc)));
          gDen[COMPOSITION] += wLith;
        }
      }
    }
    let num = 0;
    let den = 0;
    for (let g = 0; g < N_GROUPS; g++) {
      num += gNum[g];
      den += gDen[g];
    }
    const masked = (flags[r] & 1) === 1;
    if (den > 0) {
      coverage[r] = wAll > 0 ? den / wAll : 0;
      S[r] = masked ? NaN : (100 * num) / den;
    } else {
      coverage[r] = 0;
      S[r] = NaN;
    }
    const gb = r * N_GROUPS;
    for (let g = 0; g < N_GROUPS; g++) {
      groups[gb + g] = !masked && gDen[g] > 0 ? (100 * gNum[g]) / gDen[g] : NaN;
    }
  }
  return { S, coverage, groups };
}
