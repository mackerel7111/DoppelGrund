// Parity with the Python reference scorer (contract C7). The vectors are produced by
// `make parity` from doppelgrund/scoring.py (spec 02/2.4); never edit them by hand.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { applyTransforms } from '../src/engine/transforms';
import { featureWeights, groupIndex, scoreAll } from '../src/engine/scoring';
import { selectCards } from '../src/engine/cards';
import { FEATURE_GROUPS, GROUP_IDS, type GroupWeights, type Transform } from '../src/data/types';

const VECTORS = fileURLToPath(new URL('../../tests/parity/vectors.json', import.meta.url));

type Num = number | null;
interface ParityCase {
  name: string;
  earth_features: Num[][];
  earth_lith: Num[][];
  latlng: number[][];
  flags: number[];
  target_features: Num[];
  target_lith: Num[];
  median: number[];
  s: number[];
  transforms: Transform[];
  compat_matrix: number[][];
  lens_weights: GroupWeights;
  params: {
    coverage_floor: number;
    card_overall_percentile: number;
    card_min_separation_km: number;
  };
  expected: {
    S: Num[];
    coverage: Num[];
    group: Num[][];
    cards: { kind: string; row: number | null }[];
  };
}

const nan = (v: Num): number => (v === null ? NaN : v);

function close(actual: number, expected: Num, label: string): void {
  if (expected === null) {
    expect(Number.isNaN(actual), `${label}: expected NaN, got ${actual}`).toBe(true);
  } else {
    expect(Math.abs(actual - expected), `${label}: ${actual} vs ${expected}`).toBeLessThanOrEqual(
      1e-5,
    );
  }
}

if (!existsSync(VECTORS)) {
  describe.skip('parity: tests/parity/vectors.json not found — skipped until spec 02/2.4 generates it with `make parity` (override O3)', () => {
    it('runs every C7 case', () => {});
  });
} else {
  const doc = JSON.parse(readFileSync(VECTORS, 'utf-8')) as {
    contract: string;
    cases: ParityCase[];
  };
  describe('parity with doppelgrund/scoring.py (C7)', () => {
    it('has the doppelgrund-parity/1 contract', () => {
      expect(doc.contract).toBe('doppelgrund-parity/1');
    });
    for (const c of doc.cases) {
      it(c.name, () => {
        const n = c.earth_features.length;
        const feats = FEATURE_GROUPS.map((group) => ({ group }));
        const { wNum, wLith } = featureWeights(c.lens_weights, feats);
        const lt = c.target_lith.map(nan);
        const r = scoreAll({
          Xe: applyTransforms(c.earth_features.flat().map(nan), c.transforms.length, c.transforms),
          Le: Float32Array.from(c.earth_lith.flat().map(nan)),
          flags: Uint8Array.from(c.flags),
          n,
          xt: applyTransforms(c.target_features.map(nan), c.transforms.length, c.transforms),
          lt: lt.every(Number.isNaN) ? null : Float32Array.from(lt),
          median: Float64Array.from(c.median),
          s: Float64Array.from(c.s),
          groupOfFeature: groupIndex(feats),
          wNum,
          wLith,
          C: Float64Array.from(c.compat_matrix.flat()),
        });
        for (let i = 0; i < n; i++) {
          close(r.S[i], c.expected.S[i], `S[${i}]`);
          close(r.coverage[i], c.expected.coverage[i], `coverage[${i}]`);
          for (let g = 0; g < GROUP_IDS.length; g++)
            close(r.groups[i * GROUP_IDS.length + g], c.expected.group[i][g], `group[${i}][${g}]`);
        }
        const cards = selectCards(
          r.S,
          r.coverage,
          r.groups,
          Float32Array.from(c.latlng.flat()),
          c.params,
        );
        expect(cards.map((x) => [x.kind, x.row])).toEqual(
          c.expected.cards.map((x) => [x.kind, x.row]),
        );
      });
    }
  });
}
