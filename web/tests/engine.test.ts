import { describe, expect, it } from 'vitest';
import fc from 'fast-check';
import { applyTransforms, transformValue } from '../src/engine/transforms';
import {
  featureSimilarity,
  featureWeights,
  groupIndex,
  lithSimilarity,
  scoreAll,
  type ScoreInputs,
} from '../src/engine/scoring';
import { percentileLinear } from '../src/engine/percentile';
import { EARTH_R_KM, haversineKm } from '../src/engine/geo';
import { eligibleMask, selectCards, topRows } from '../src/engine/cards';
import { FEATURE_GROUPS, type GroupWeights, type Transform } from '../src/data/types';

const FEATS = FEATURE_GROUPS.map((group) => ({ group }));
const F = FEATURE_GROUPS.length; // 11
const TRANSFORMS: Transform[] = FEATURE_GROUPS.map((_, i) =>
  i === 2 || i === 9 || i === 10 ? 'log1p' : 'none',
);
const BAL: GroupWeights = {
  terrain: 0.25,
  thermal: 0.25,
  cold_ice: 0.25,
  composition: 0.25,
  subsurface: 0,
};
// C3 compatibility matrix (illustrative values from the contract)
const C3 = Float64Array.from(
  [
    [1.0, 0.2, 0.0, 0.1, 0.0, 0.0],
    [0.2, 1.0, 0.0, 0.2, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.2, 0.3, 0.0],
    [0.1, 0.2, 0.2, 1.0, 0.2, 0.0],
    [0.0, 0.0, 0.3, 0.2, 1.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
  ].flat(),
);
const TARGET = [2, 5, 80, 0.8, 250, 30, 20, 0.5, 0.3, 0.1, 0.6];
const LITH_T = [1, 0, 0, 0, 0, 0];

function inputs(rows: number[][], liths: number[][], flags: number[], w = BAL, s = 1): ScoreInputs {
  const { wNum, wLith } = featureWeights(w, FEATS);
  return {
    Xe: applyTransforms(rows.flat(), F, TRANSFORMS),
    Le: Float32Array.from(liths.flat()),
    flags: Uint8Array.from(flags),
    n: rows.length,
    xt: applyTransforms(TARGET, F, TRANSFORMS),
    lt: Float32Array.from(LITH_T),
    median: new Float64Array(F),
    s: new Float64Array(F).fill(s),
    groupOfFeature: groupIndex(FEATS),
    wNum,
    wLith,
    C: C3,
  };
}

describe('transforms (C4.1)', () => {
  it('applies log1p only to relief, aridity and cave density, clamped at 0, NaN preserved', () => {
    const out = applyTransforms([1, 1, 1, 1, 1, 1, 1, 1, NaN, -5, 3], F, TRANSFORMS);
    expect(out[0]).toBe(1);
    expect(out[2]).toBeCloseTo(Math.log(2), 15);
    expect(out[9]).toBe(0);
    expect(out[10]).toBeCloseTo(Math.log(4), 15);
    expect(Number.isNaN(out[8])).toBe(true);
    expect(Number.isNaN(transformValue(NaN, 'log1p'))).toBe(true);
    expect(transformValue(-3, 'none')).toBe(-3);
  });
});

describe('kernel and weights', () => {
  it('k(z) = exp(-0.5 z²) anchors', () => {
    expect(featureSimilarity(5, 5, 1)).toBe(1);
    expect(featureSimilarity(5, 6, 1)).toBeCloseTo(0.6065306597, 10);
    expect(featureSimilarity(5, 9, 2)).toBeCloseTo(0.1353352832, 10);
    expect(Number.isNaN(featureSimilarity(NaN, 1, 1))).toBe(true);
  });

  it('balanced lens weights follow the C3 rule', () => {
    const { wNum, wLith } = featureWeights(BAL, FEATS);
    for (let f = 0; f < 4; f++) expect(wNum[f]).toBe(0.0625);
    for (let f = 4; f < 10; f++) expect(wNum[f]).toBeCloseTo(0.083333, 6);
    expect(wNum[10]).toBe(0); // subsurface weight 0 in this fixture
    expect(wLith).toBe(0.25);
  });

  it('lithology: identical → 1, disjoint → 0, smoothed mixture by hand', () => {
    const I = Float64Array.from({ length: 36 }, (_, k) => (k % 7 === 0 ? 1 : 0));
    expect(lithSimilarity([0.5, 0.5, 0, 0, 0, 0], [0.5, 0.5, 0, 0, 0, 0], C3)).toBeCloseTo(1, 12);
    expect(lithSimilarity([1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], I)).toBeCloseTo(0, 12);
    // p = [1,.2,0,.1,0,0]/1.3, q = [.2,1,0,.2,0,0]/1.4 → BC = 0.767822 → k = 0.5181515
    expect(lithSimilarity([1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], C3)).toBeCloseTo(0.5181515, 6);
    expect(Number.isNaN(lithSimilarity([NaN, 0, 0, 0, 0, 0], LITH_T, C3))).toBe(true);
    expect(Number.isNaN(lithSimilarity([0, 0, 0, 0, 0, 0], LITH_T, C3))).toBe(true);
  });
});

describe('scoreAll (C4)', () => {
  it('identical target and row → S = 100, coverage = 1, every group = 100', () => {
    const r = scoreAll(inputs([TARGET], [LITH_T], [0]));
    expect(r.S[0]).toBe(100);
    expect(r.coverage[0]).toBe(1);
    expect(Array.from(r.groups)).toEqual([100, 100, 100, 100, NaN]); // zero-weight subsurface
  });

  it('all-NaN row → S = NaN, coverage = 0, groups NaN', () => {
    const r = scoreAll(inputs([Array(F).fill(NaN)], [Array(6).fill(NaN)], [0]));
    expect(Number.isNaN(r.S[0])).toBe(true);
    expect(r.coverage[0]).toBe(0);
    expect(Array.from(r.groups).every(Number.isNaN)).toBe(true);
  });

  it('masked row → S and groups NaN, coverage still computed', () => {
    const r = scoreAll(inputs([TARGET], [LITH_T], [1 | 2]));
    expect(Number.isNaN(r.S[0])).toBe(true);
    expect(Array.from(r.groups).every(Number.isNaN)).toBe(true);
    expect(r.coverage[0]).toBe(1);
  });

  it('partial NaN: missing thermal group drops coverage to 0.75, S over valid weights', () => {
    const row = [...TARGET];
    row[4] = row[5] = row[6] = NaN;
    row[0] = TARGET[0] + 1; // z = 1 on one terrain feature
    const r = scoreAll(inputs([row], [LITH_T], [0]));
    expect(r.coverage[0]).toBeCloseTo(0.75, 6);
    const k1 = Math.exp(-0.5);
    const expected = (100 * (0.0625 * (3 + k1) + 0.25 + 0.25)) / 0.75;
    expect(r.S[0]).toBeCloseTo(expected, 4);
    expect(Number.isNaN(r.groups[1])).toBe(true);
    expect(r.groups[0]).toBeCloseTo((100 * (3 + k1)) / 4, 4);
  });

  it('a zero-weight group never changes S and its group score is NaN', () => {
    const w: GroupWeights = {
      terrain: 0.5,
      thermal: 0.5,
      cold_ice: 0,
      composition: 0,
      subsurface: 0,
    };
    const a = [...TARGET];
    const b = [...TARGET];
    b[7] = 0.99;
    b[8] = NaN;
    b[9] = 7;
    const r = scoreAll(inputs([a, b], [LITH_T, [0, 0, 0, 0, 0, 1]], [0, 0], w));
    expect(r.S[0]).toBe(r.S[1]);
    expect(r.coverage[0]).toBe(r.coverage[1]);
    expect(Number.isNaN(r.groups[2])).toBe(true);
    expect(Number.isNaN(r.groups[3])).toBe(true);
  });

  it('target with unmapped lithology drops composition from coverage', () => {
    const inp = inputs([TARGET], [LITH_T], [0]);
    inp.lt = null;
    const r = scoreAll(inp);
    expect(r.coverage[0]).toBeCloseTo(0.75, 6);
    expect(Number.isNaN(r.groups[3])).toBe(true);
    expect(r.S[0]).toBe(100);
  });

  it('subsurface: scored where both sides have a value, a missing value only lowers coverage', () => {
    const w: GroupWeights = {
      terrain: 0.2,
      thermal: 0.2,
      cold_ice: 0.2,
      composition: 0.2,
      subsurface: 0.2,
    };
    const noCave = [...TARGET];
    noCave[10] = NaN; // not catalogued / not surveyed: NaN, never 0
    const far = [...TARGET];
    far[10] = 6.6;
    const r = scoreAll(inputs([TARGET, noCave, far], [LITH_T, LITH_T, LITH_T], [0, 0, 0], w));
    expect(r.groups[4]).toBe(100);
    expect(Number.isNaN(r.groups[9])).toBe(true);
    expect(r.coverage[1]).toBeCloseTo(0.8, 6);
    expect(r.S[1]).toBe(100); // the other four groups match exactly
    const z = Math.log1p(6.6) - Math.log1p(0.6);
    expect(r.groups[14]).toBeCloseTo(100 * Math.exp(-0.5 * z * z), 4);
  });

  it('S ∈ [0, 100], coverage ∈ [0, 1], NaN-only rows stay NaN (property)', () => {
    const val = fc.oneof(fc.constant(NaN), fc.double({ min: -10, max: 400, noNaN: true }));
    const row = fc.array(val, { minLength: F, maxLength: F });
    const lith = fc.array(fc.double({ min: 0, max: 1, noNaN: true }), {
      minLength: 6,
      maxLength: 6,
    });
    fc.assert(
      fc.property(fc.array(fc.tuple(row, lith), { minLength: 1, maxLength: 20 }), (rows) => {
        const r = scoreAll(
          inputs(
            rows.map((x) => x[0]),
            rows.map((x) => x[1]),
            rows.map(() => 0),
            BAL,
            3,
          ),
        );
        for (let i = 0; i < rows.length; i++) {
          expect(r.coverage[i]).toBeGreaterThanOrEqual(0);
          expect(r.coverage[i]).toBeLessThanOrEqual(1 + 1e-6);
          if (Number.isFinite(r.S[i])) {
            expect(r.S[i]).toBeGreaterThanOrEqual(0);
            expect(r.S[i]).toBeLessThanOrEqual(100 + 1e-4);
          }
          const lithOk = rows[i][1].reduce((a, b) => a + b, 0) > 0;
          if (rows[i][0].every(Number.isNaN) && !lithOk) expect(Number.isNaN(r.S[i])).toBe(true);
        }
      }),
    );
  });
});

describe('percentileLinear (numpy "linear")', () => {
  const all = (n: number) => new Uint8Array(n).fill(1);
  it('matches numpy 2.5.4 float32 outputs', () => {
    // reference values computed with np.percentile(np.float32([...]), p)
    expect(percentileLinear(Float32Array.from([1.1, 2.3, 7.7, 9.1]), all(4), 95)).toBe(
      8.890000343322754,
    );
    expect(percentileLinear(Float32Array.from([3, 1, 2, 5, 4]), all(5), 95)).toBe(
      4.800000190734863,
    );
    expect(percentileLinear(Float32Array.from([0.1, 0.2, 0.3]), all(3), 40)).toBe(
      0.18000000715255737,
    );
    expect(percentileLinear(Float32Array.from([10, 20, 30, 40, 50, 60, 70]), all(7), 33)).toBe(
      29.799999237060547,
    );
  });
  it('ignores masked and NaN values; empty → NaN', () => {
    const v = Float32Array.from([1, NaN, 100, 3]);
    expect(percentileLinear(v, Uint8Array.from([1, 1, 0, 1]), 50)).toBe(2);
    expect(Number.isNaN(percentileLinear(v, new Uint8Array(4), 50))).toBe(true);
    expect(percentileLinear(Float32Array.from([7]), all(1), 95)).toBe(7);
  });
});

describe('haversine', () => {
  it('uses R = 6371.0088 km, handles antimeridian and poles', () => {
    const deg = (EARTH_R_KM * Math.PI) / 180;
    expect(haversineKm(0, 0, 0, 1)).toBeCloseTo(deg, 9);
    expect(haversineKm(0, 179.5, 0, -179.5)).toBeCloseTo(deg, 9);
    expect(haversineKm(90, 0, -90, 0)).toBeCloseTo(Math.PI * EARTH_R_KM, 6);
    expect(haversineKm(89.9, 0, 89.9, 180)).toBeCloseTo(0.2 * deg, 6);
  });
});

describe('selectCards (C5)', () => {
  const P = { coverage_floor: 0.6, card_overall_percentile: 0, card_min_separation_km: 300 };
  // rows: lat/lng spaced 10° apart along the equator (≈ 1112 km) unless stated
  function ll(points: [number, number][]): Float32Array {
    return Float32Array.from(points.flat());
  }

  it('returns six cards in order with tie-breaks and separation', () => {
    const S = Float32Array.from([90, 95, 95, 80, 70]);
    const cov = Float32Array.from([1, 1, 1, 1, 1]);
    // groups [terrain, thermal, cold_ice, composition, subsurface]
    const groups = Float32Array.from(
      [
        [99, 50, 10, NaN, NaN],
        [10, 10, 10, NaN, NaN],
        [10, 10, 10, NaN, NaN],
        [99, 60, 10, NaN, NaN],
        [50, 60, 90, NaN, NaN],
      ].flat(),
    );
    const latlng = ll([
      [0, 0],
      [0, 10],
      [0, 20],
      [0, 0.5],
      [0, 40],
    ]);
    const cards = selectCards(S, cov, groups, latlng, P);
    expect(cards.map((c) => c.kind)).toEqual([
      'overall',
      'terrain',
      'thermal',
      'cold_ice',
      'composition',
      'subsurface',
    ]);
    expect(cards[0].row).toBe(1); // tie 95/95 → lower index
    expect(cards[1].row).toBe(0); // terrain tie 99/99 → higher S (row 0: 90 > row 3: 80)
    expect(cards[2].row).toBe(4); // thermal 60 tie: row 3 is < 300 km from row 0 → row 4
    expect(cards[3].row).toBe(2); // cold_ice: row 4 taken... ties 10 → higher S row 2 (95)
    expect(cards[4]).toMatchObject({ row: null, reason: 'no_eligible_match' });
    expect(cards[5]).toMatchObject({ row: null, reason: 'no_eligible_match' });
  });

  it('respects the overall percentile pool and coverage floor', () => {
    const S = Float32Array.from([10, 20, 30, 40, 99]);
    const cov = Float32Array.from([1, 1, 1, 1, 0.5]);
    const groups = Float32Array.from(Array.from({ length: 5 }, (_, i) => [i, i, i, i, i]).flat());
    const latlng = ll([
      [0, 0],
      [0, 10],
      [0, 20],
      [0, 30],
      [0, 40],
    ]);
    const cards = selectCards(S, cov, groups, latlng, { ...P, card_overall_percentile: 50 });
    expect(cards[0].row).toBe(3); // row 4 below coverage floor
    // pool: S >= percentile50([10,20,30,40]) = 25 → rows 2, 3; row 3 taken by overall
    expect(cards[1].row).toBe(2);
    expect(cards[2].row).toBeNull();
  });

  it('no eligible rows → all six cards empty', () => {
    const S = Float32Array.from([NaN, NaN]);
    const cards = selectCards(
      S,
      Float32Array.from([1, 1]),
      new Float32Array(10),
      ll([
        [0, 0],
        [1, 1],
      ]),
      P,
    );
    expect(cards.every((c) => c.row === null && c.reason === 'no_eligible_match')).toBe(true);
  });

  it('antimeridian neighbours count as close', () => {
    const S = Float32Array.from([90, 89]);
    const groups = Float32Array.from([1, 1, 1, 1, 1, 2, 2, 2, 2, 2]);
    const cards = selectCards(
      S,
      Float32Array.from([1, 1]),
      groups,
      ll([
        [0, 179.9],
        [0, -179.9],
      ]),
      P,
    );
    expect(cards[0].row).toBe(0);
    expect(cards[1].row).toBeNull(); // 22 km away from the overall card
  });

  it('topRows sorts by S desc with lower index on ties', () => {
    const S = Float32Array.from([5, 9, NaN, 9, 1, 7]);
    const elig = eligibleMask(S, new Float32Array(6).fill(1), 0.6);
    expect(Array.from(topRows(S, elig, 3))).toEqual([1, 3, 5]);
  });
});
