import { describe, expect, it } from 'vitest';
import fc from 'fast-check';
import { mulberry32, normal, sampleDirichlet, sampleGamma } from '../src/engine/prng';
import { stabilityRun, type StabilityRunParams } from '../src/engine/stability';
import { featureWeights, groupIndex, type ScoreInputs } from '../src/engine/scoring';
import { applyTransforms } from '../src/engine/transforms';
import { FEATURE_GROUPS, type GroupWeights, type WorkerResponse } from '../src/data/types';
import { EngineHost } from '../src/workers/engine.worker';

const BAL: GroupWeights = {
  terrain: 0.25,
  thermal: 0.25,
  cold_ice: 0.25,
  composition: 0.25,
  subsurface: 0,
};
const F = FEATURE_GROUPS.length;
const FEATS = FEATURE_GROUPS.map((group) => ({ group }));

function inputs(n: number): ScoreInputs {
  const rnd = mulberry32(7);
  const raw = Float64Array.from({ length: n * F }, () => rnd() * 10);
  const { wNum, wLith } = featureWeights(BAL, FEATS);
  return {
    Xe: applyTransforms(
      raw,
      F,
      FEATURE_GROUPS.map(() => 'none'),
    ),
    Le: Float32Array.from({ length: n * 6 }, (_, i) => (i % 6 === i % 2 ? 1 : 0)),
    flags: new Uint8Array(n),
    n,
    xt: new Float64Array(F).fill(5),
    lt: Float32Array.from([1, 0, 0, 0, 0, 0]),
    median: new Float64Array(F),
    s: new Float64Array(F).fill(2),
    groupOfFeature: groupIndex(FEATS),
    wNum,
    wLith,
    C: Float64Array.from({ length: 36 }, (_, k) => (k % 7 === 0 ? 1 : 0)),
  };
}

const PARAMS: StabilityRunParams = {
  seed: 20261114,
  coverage_floor: 0.6,
  draws: 500,
  draws_interactive: 100,
  dirichlet_concentration: 50,
  tol_log_sigma: 0.25,
  top_fraction: 0.01,
  store_top_k: 2000,
};

describe('prng', () => {
  it('mulberry32 is seeded and reproducible', () => {
    const a = mulberry32(42);
    const b = mulberry32(42);
    const xs = Array.from({ length: 5 }, () => a());
    expect(Array.from({ length: 5 }, () => b())).toEqual(xs);
    expect(xs.every((x) => x >= 0 && x < 1)).toBe(true);
    expect(mulberry32(43)()).not.toBe(xs[0]);
  });

  it('gamma and normal samples have the right first moments', () => {
    const rnd = mulberry32(1);
    const n = 20000;
    let g = 0;
    let z = 0;
    for (let i = 0; i < n; i++) {
      g += sampleGamma(3.5, rnd);
      z += normal(rnd);
    }
    expect(g / n).toBeCloseTo(3.5, 1);
    expect(Math.abs(z / n)).toBeLessThan(0.03);
    expect(sampleGamma(0, rnd)).toBe(0);
  });

  it('Dirichlet samples sum to 1 and keep zero-alpha components at 0 (property)', () => {
    fc.assert(
      fc.property(
        fc.array(fc.double({ min: 0, max: 60, noNaN: true }), { minLength: 5, maxLength: 5 }),
        fc.integer(),
        (al, seed) => {
          fc.pre(al.some((a) => a > 1e-3));
          const x = sampleDirichlet(Float64Array.from(al), mulberry32(seed));
          expect(x.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 9);
          al.forEach((a, i) => {
            if (a === 0) expect(x[i]).toBe(0);
            expect(x[i]).toBeGreaterThanOrEqual(0);
          });
        },
      ),
    );
  });
});

describe('stabilityRun', () => {
  it('is reproducible for a fixed seed', () => {
    const inp = inputs(800);
    const a = stabilityRun(inp, BAL, PARAMS, 20);
    const b = stabilityRun(inp, BAL, PARAMS, 20);
    expect(a).toEqual(b);
    expect(a.length).toBeGreaterThan(0);
    expect(a.every(([, f]) => f > 0 && f <= 1)).toBe(true);
    for (let i = 1; i < a.length; i++) expect(a[i - 1][1]).toBeGreaterThanOrEqual(a[i][1]);
  });

  it('zero jitter gives stability exactly 1 for the top set and 0 (absent) elsewhere', () => {
    const inp = inputs(1000);
    const rows = stabilityRun(
      inp,
      BAL,
      { ...PARAMS, dirichlet_concentration: Infinity, tol_log_sigma: 0 },
      7,
    );
    expect(rows.length).toBe(Math.ceil(0.01 * 1000));
    expect(rows.every(([, f]) => f === 1)).toBe(true);
  });

  it('reports progress per draw', () => {
    const seen: number[] = [];
    stabilityRun(inputs(200), BAL, PARAMS, 5, (d, t) => {
      expect(t).toBe(5);
      seen.push(d);
    });
    expect(seen).toEqual([1, 2, 3, 4, 5]);
  });
});

describe('worker stability handler', () => {
  it('streams progress, returns rows, and is cancelled by a newer stability request', async () => {
    const out: WorkerResponse[] = [];
    const inp = inputs(300);
    const host = new EngineHost((m) => out.push(m));
    host.prepared = {
      bundle: {
        manifest: {
          n_hex: 300,
          features: FEATURE_GROUPS.map((group) => ({ group, transform: 'none', s: 2, median: 0 })),
          params: { seed: 1, coverage_floor: 0.6, stability: PARAMS },
        },
        lith: inp.Le,
        flags: inp.flags,
      },
      Xe: inp.Xe,
      s: inp.s,
      median: inp.median,
      groupOfFeature: inp.groupOfFeature,
      C: inp.C,
    } as unknown as NonNullable<EngineHost['prepared']>;
    const target = { features: Array(F).fill(5), lith: [1, 0, 0, 0, 0, 0] };
    const first = host.handle({ type: 'stability', reqId: 1, target, weights: BAL, draws: 50 });
    await new Promise((r) => setTimeout(r, 5));
    const second = host.handle({ type: 'stability', reqId: 2, target, weights: BAL, draws: 3 });
    await Promise.all([first, second]);
    const done1 = out.filter((m) => m.type === 'stability' && m.reqId === 1);
    const done2 = out.filter((m) => m.type === 'stability' && m.reqId === 2);
    expect(done1).toHaveLength(0);
    expect(done2).toHaveLength(1);
    const prog2 = out.filter((m) => m.type === 'progress' && m.reqId === 2);
    expect(prog2.map((m) => (m.type === 'progress' ? m.done : 0))).toEqual([1, 2, 3]);
  });
});
