// Stability: how often a hexagon stays in the top set when lens weights and tolerances are
// perturbed (Dirichlet weights around the lens, log-normal jitter on s_f). A statistic, not ML.
import { GROUP_IDS, type GroupWeights, type StabilityParams } from '../data/types';
import { mulberry32, normal, sampleDirichlet } from './prng';
import { COMPOSITION, N_GROUPS, scoreAll, type ScoreInputs } from './scoring';

export interface StabilityRunParams extends StabilityParams {
  seed: number;
  coverage_floor: number;
}

/** Per-feature group index used to rebuild weights from sampled group weights. */
function weightsFor(inp: ScoreInputs, groups: Float64Array): { wNum: Float64Array; wLith: number } {
  const count = new Float64Array(N_GROUPS);
  for (let f = 0; f < inp.groupOfFeature.length; f++) count[inp.groupOfFeature[f]] += 1;
  count[COMPOSITION] += 1; // lithology
  const wNum = Float64Array.from(inp.groupOfFeature, (g) => groups[g] / count[g]);
  return { wNum, wLith: groups[COMPOSITION] / count[COMPOSITION] };
}

/** Incremental runner so the worker can yield between draws (progress + cancellation). */
export class StabilityAccumulator {
  readonly counts: Uint16Array;
  done = 0;
  private readonly rnd: () => number;
  private readonly alpha: Float64Array;
  private readonly base: Float64Array;
  private readonly inp: ScoreInputs;
  private readonly params: StabilityRunParams;

  constructor(inp: ScoreInputs, base: GroupWeights, params: StabilityRunParams) {
    this.inp = inp;
    this.params = params;
    this.counts = new Uint16Array(inp.n);
    this.rnd = mulberry32(params.seed);
    this.base = Float64Array.from(GROUP_IDS, (g) => base[g]);
    this.alpha = Float64Array.from(this.base, (w) => w * params.dirichlet_concentration);
  }

  /** One perturbed draw: score all rows and count the top `top_fraction` of eligible rows. */
  step(): void {
    const p = this.params;
    const groups = Number.isFinite(p.dirichlet_concentration)
      ? sampleDirichlet(this.alpha, this.rnd)
      : this.base;
    const { wNum, wLith } = weightsFor(this.inp, groups);
    const s = Float64Array.from(this.inp.s, (v) =>
      p.tol_log_sigma > 0 ? v * Math.exp(p.tol_log_sigma * normal(this.rnd)) : v,
    );
    const { S, coverage } = scoreAll({ ...this.inp, s, wNum, wLith });
    let nElig = 0;
    for (let i = 0; i < S.length; i++)
      if (Number.isFinite(S[i]) && coverage[i] >= p.coverage_floor) nElig++;
    const k = Math.max(1, Math.ceil(p.top_fraction * nElig));
    if (nElig > 0) {
      const vals = new Float32Array(nElig);
      let j = 0;
      for (let i = 0; i < S.length; i++)
        if (Number.isFinite(S[i]) && coverage[i] >= p.coverage_floor) vals[j++] = S[i];
      vals.sort();
      const cut = vals[nElig - Math.min(k, nElig)];
      for (let i = 0; i < S.length; i++) {
        if (Number.isFinite(S[i]) && coverage[i] >= p.coverage_floor && S[i] >= cut)
          this.counts[i]++;
      }
    }
    this.done++;
  }

  /** [row, fraction of draws in the top set], descending fraction then row; at most store_top_k. */
  result(): [number, number][] {
    const rows: [number, number][] = [];
    if (this.done === 0) return rows;
    for (let i = 0; i < this.counts.length; i++)
      if (this.counts[i] > 0) rows.push([i, this.counts[i] / this.done]);
    rows.sort((a, b) => b[1] - a[1] || a[0] - b[0]);
    return rows.slice(0, this.params.store_top_k);
  }
}

export function stabilityRun(
  inp: ScoreInputs,
  base: GroupWeights,
  params: StabilityRunParams,
  draws: number,
  onProgress?: (done: number, total: number) => void,
): Array<[number, number]> {
  const acc = new StabilityAccumulator(inp, base, params);
  for (let d = 0; d < draws; d++) {
    acc.step();
    onProgress?.(acc.done, draws);
  }
  return acc.result();
}
