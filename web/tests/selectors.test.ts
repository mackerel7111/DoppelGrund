import { describe, expect, it } from 'vitest';
import {
  featureComparison,
  formatValue,
  mostAlike,
  rowInfo,
  tagsOf,
} from '../src/stores/selectors';
import type { Bundle } from '../src/data/types';

function bundle(): Bundle {
  const feats = new Float32Array(20).fill(NaN);
  feats.set([2, 5, 80, 0.8, 250, 30, 20, 0.5, NaN, 0.1], 0); // row 0
  feats.set([3, 5, 80, 0.8, 300, 30, 20, 0.5, 0.2, 0.1], 10); // row 1
  return {
    manifest: {
      features: [
        ['slope_p50_deg', 'terrain', 'deg', 'none'],
        ['slope_p90_deg', 'terrain', 'deg', 'none'],
        ['relief_std_m', 'terrain', 'm', 'log1p'],
        ['frac_slope_lt_10deg', 'terrain', 'fraction', 'none'],
        ['lst_mean_K', 'thermal', 'K', 'none'],
        ['diurnal_range_K', 'thermal', 'K', 'none'],
        ['annual_range_K', 'thermal', 'K', 'none'],
        ['frac_below_0C', 'cold_ice', 'fraction', 'none'],
        ['permafrost_prob', 'cold_ice', 'fraction', 'none'],
        ['aridity_index', 'cold_ice', 'ratio', 'log1p'],
      ].map(([name, group, unit, transform]) => ({
        name,
        group,
        unit,
        transform,
        median: 0,
        s: 1,
      })),
      compat_matrix: Array.from({ length: 6 }, (_, i) =>
        Array.from({ length: 6 }, (_, j) => (i === j ? 1 : 0)),
      ),
      sources: [{ feature: 'lst_mean_K', body: 'earth', dataset: 'synthetic', version: 'seed 1' }],
    },
    features: feats,
    lith: Float32Array.from([1, 0, 0, 0, 0, 0, NaN, NaN, NaN, NaN, NaN, NaN]),
    latlng: Float32Array.from([10, 20, -30, 40]),
    novelty: Float32Array.from([123, 0.4, 900, 0.1]),
    flags: Uint8Array.from([2 | 4, 16]),
  } as unknown as Bundle;
}

const target = { features: [2, 5, 80, 0.8, 250, 280, NaN, 0.5, NaN, 0], lith: [1, 0, 0, 0, 0, 0] };

describe('featureComparison', () => {
  it('reports physical gaps, kernel similarity and "not measured" as NaN', () => {
    const rows = featureComparison(bundle(), target, 'moon', 1);
    const slope = rows[0];
    expect(slope.gap).toBe(1);
    expect(slope.similarity).toBeCloseTo(Math.exp(-0.5), 10);
    expect(rows[4].gap).toBe(50); // lst Δ 50 K
    expect(Number.isNaN(rows[6].similarity)).toBe(true); // target annual range missing
    expect(Number.isNaN(rows[8].gap)).toBe(true);
    // Earth value is float32(0.1) in the bundle
    expect(rows[9].similarity).toBeCloseTo(Math.exp(-0.5 * Math.log1p(0.1) ** 2), 7);
    const lith = rows[10];
    expect(lith.name).toBe('lith');
    expect(Number.isNaN(lith.similarity)).toBe(true); // Earth row 1 lithology unmapped
    expect(featureComparison(bundle(), target, 'moon', 0)[10].similarity).toBeCloseTo(1, 12);
    expect(rows[4].sourceEarth).toBe('synthetic (seed 1)');
    expect(rows[4].sourceTarget).toContain('TODO(verify)');
  });
});

describe('mostAlike', () => {
  it('ranks measured non-lithology rows by similarity and skips missing ones', () => {
    const rows = featureComparison(bundle(), target, 'moon', 0);
    const top = mostAlike(rows, 3);
    expect(top).toHaveLength(3);
    expect(top.every((r) => r.name !== 'lith' && Number.isFinite(r.similarity))).toBe(true);
    expect(top[0].similarity).toBeGreaterThanOrEqual(top[1].similarity);
    expect(top[1].similarity).toBeGreaterThanOrEqual(top[2].similarity);
  });
});

describe('row helpers', () => {
  it('decodes process tags and known-site flags', () => {
    expect(tagsOf(2 | 4 | 8)).toEqual(['volcanic', 'periglacial', 'evaporitic']);
    const info = rowInfo(bundle(), { rows: new Map([[1, 0.42]]), kind: 'preset' }, true, 1);
    expect(info).toMatchObject({
      lat: -30,
      lng: 40,
      noveltyKm: 900,
      knownSite: true,
      stability: 0.42,
      stabilityNote: 'preset',
    });
    expect(rowInfo(bundle(), null, false, 0)).toMatchObject({
      stabilityAvailable: false,
      stability: null,
      tags: ['volcanic', 'periglacial'],
    });
  });

  it('formats values with units and never turns NaN into a number', () => {
    expect(formatValue(212.04, 'K')).toBe('212.0 K');
    expect(formatValue(3.25, 'deg')).toBe('3.3°');
    expect(formatValue(80.4, 'm')).toBe('80 m');
    expect(formatValue(NaN, 'K')).toBeNull();
  });
});
