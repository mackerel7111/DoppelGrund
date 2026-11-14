import { describe, expect, it } from 'vitest';
import { ManifestError, checkArrayLength, validateManifest } from '../src/data/config';
import { FEATURE_GROUPS, FEATURE_NAMES } from '../src/data/types';

export function validManifest(): Record<string, unknown> {
  return {
    contract: 'doppelgrund-bundle/1',
    created_utc: '2026-11-14T00:00:00Z',
    synthetic: true,
    h3_res: 4,
    n_hex: 3,
    features: FEATURE_NAMES.map((name, i) => ({
      name,
      group: FEATURE_GROUPS[i],
      unit: 'u',
      transform: name === 'relief_std_m' || name === 'aridity_index' ? 'log1p' : 'none',
      median: 0,
      s: 1,
    })),
    lith_classes: [
      'mafic_volcanic',
      'felsic_feldspathic',
      'carbonate',
      'siliciclastic',
      'evaporite',
      'ice',
    ],
    compat_matrix: Array.from({ length: 6 }, (_, i) =>
      Array.from({ length: 6 }, (_, j) => (i === j ? 1 : 0)),
    ),
    lenses: {
      balanced: { terrain: 0.25, thermal: 0.25, cold_ice: 0.25, composition: 0.25 },
      landing_mobility: { terrain: 0.7, thermal: 0.15, cold_ice: 0, composition: 0.15 },
      cold_volatiles: { terrain: 0.15, thermal: 0.3, cold_ice: 0.45, composition: 0.1 },
      geology_minerals: { terrain: 0.2, thermal: 0.1, cold_ice: 0.1, composition: 0.6 },
    },
    params: {
      seed: 1,
      footprint_radius_km: 23.7,
      land_frac_min: 0.3,
      coverage_floor: 0.6,
      card_overall_percentile: 95,
      card_min_separation_km: 300,
      novelty_gate_km: 300,
      mask: { barren_plus_ice_min: 0.5, ndvi_max: 0.2 },
      stability: {
        draws: 500,
        draws_interactive: 100,
        dirichlet_concentration: 50,
        tol_log_sigma: 0.25,
        top_fraction: 0.01,
        store_top_k: 2000,
      },
    },
    files: {
      h3: 'earth_h3.txt',
      features: 'earth_features.f32',
      lith: 'earth_lith.f32',
      latlng: 'earth_latlng.f32',
      novelty: 'earth_novelty.f32',
      cluster: 'earth_cluster.i16',
      flags: 'earth_flags.u8',
      targets: 'targets.json',
      index_map: 'earth_index_4096x2048.png',
    },
    sources: [],
  };
}

describe('validateManifest', () => {
  it('accepts a valid manifest', () => {
    const m = validateManifest(validManifest());
    expect(m.n_hex).toBe(3);
    expect(m.features[2].transform).toBe('log1p');
  });

  it('rejects wrong feature order with ManifestError naming the field', () => {
    const raw = validManifest();
    const feats = raw.features as Record<string, unknown>[];
    [feats[0], feats[1]] = [feats[1], feats[0]];
    expect(() => validateManifest(raw)).toThrow(ManifestError);
    try {
      validateManifest(raw);
    } catch (e) {
      expect((e as ManifestError).field).toBe('features[0].name');
    }
  });

  it('rejects a wrong contract id', () => {
    const raw = { ...validManifest(), contract: 'doppelgrund-bundle/2' };
    expect(() => validateManifest(raw)).toThrow(/contract/);
  });

  it('rejects a lens that does not sum to 1', () => {
    const raw = validManifest();
    (raw.lenses as Record<string, Record<string, number>>).balanced.terrain = 0.5;
    expect(() => validateManifest(raw)).toThrow(/lenses\.balanced/);
  });

  it('rejects a missing required file key', () => {
    const raw = validManifest();
    delete (raw.files as Record<string, string>).flags;
    expect(() => validateManifest(raw)).toThrow(/files\.flags/);
  });

  it('rejects non-positive scaler s', () => {
    const raw = validManifest();
    (raw.features as Record<string, unknown>[])[4].s = 0;
    expect(() => validateManifest(raw)).toThrow(/features\[4\]\.s/);
  });
});

describe('checkArrayLength', () => {
  it('accepts matching lengths and rejects wrong n_hex vs array length', () => {
    const m = validateManifest(validManifest());
    expect(() => checkArrayLength(m, 'features', 30)).not.toThrow();
    expect(() => checkArrayLength(m, 'flags', 3)).not.toThrow();
    expect(() => checkArrayLength(m, 'features', 29)).toThrow(ManifestError);
    expect(() => checkArrayLength(m, 'h3', 4)).toThrow(/earth_h3\.txt has 4 elements/);
  });
});
