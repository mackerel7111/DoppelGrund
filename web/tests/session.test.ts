import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import fc from 'fast-check';
import { DEFAULT_LENSES, renormalise, useSession, type EngineLike } from '../src/stores/session';
import { GROUP_IDS, type Bundle, type GroupWeights, type RankedResponse } from '../src/data/types';

function sum(w: GroupWeights): number {
  return GROUP_IDS.reduce((a, g) => a + w[g], 0);
}

function fakeBundle(): Bundle {
  const t = {
    id: 'synthetic_t',
    name: 'T',
    body: 'moon' as const,
    lat: -89,
    lon: 0,
    features: new Float64Array(10).fill(1),
    lith: new Float64Array([1, 0, 0, 0, 0, 0]),
    cluster: null,
    notes: '',
    coverage_notes: [],
  };
  const manifest = { lenses: DEFAULT_LENSES, params: { coverage_floor: 0.6 } };
  return { targets: [t], discs: {}, manifest } as unknown as Bundle;
}

function fakeEngine(): EngineLike & { calls: number } {
  const eng = {
    calls: 0,
    rank: vi.fn(async (): Promise<RankedResponse> => {
      eng.calls += 1;
      return {
        type: 'ranked',
        reqId: eng.calls,
        S: new Float32Array(1),
        coverage: new Float32Array(1),
        groups: new Float32Array(4),
        cards: [],
        top: new Int32Array(0),
      };
    }),
    stability: vi.fn(async () => [[0, 1]] as [number, number][]),
  };
  return eng;
}

describe('renormalise', () => {
  const balanced = DEFAULT_LENSES.balanced;

  it('scales the other weights proportionally', () => {
    const w = renormalise(balanced, 'terrain', 0.4);
    expect(w.terrain).toBeCloseTo(0.4);
    expect(w.thermal).toBeCloseTo((0.6 * 0.225) / 0.775); // others keep their ratios
    expect(w.subsurface).toBeCloseTo((0.6 * 0.1) / 0.775);
    expect(sum(w)).toBeCloseTo(1, 12);
  });

  it('setting one weight to 1 zeroes the others', () => {
    const w = renormalise(balanced, 'cold_ice', 1);
    expect(w).toEqual({ terrain: 0, thermal: 0, cold_ice: 1, composition: 0, subsurface: 0 });
  });

  it('setting one weight to 0 spreads its share over the others', () => {
    const w = renormalise(DEFAULT_LENSES.landing_mobility, 'terrain', 0);
    expect(w.terrain).toBe(0);
    expect(w.thermal).toBeCloseTo(0.5);
    expect(w.cold_ice).toBe(0);
    expect(w.composition).toBeCloseTo(0.5);
  });

  it('recovers from all-other-zero weights by splitting equally', () => {
    const w = renormalise(
      { terrain: 1, thermal: 0, cold_ice: 0, composition: 0, subsurface: 0 },
      'terrain',
      0.4,
    );
    expect(w.thermal).toBeCloseTo(0.15); // 0.6 split equally over the other four groups
    expect(sum(w)).toBeCloseTo(1, 12);
  });

  it('always sums to 1 with non-negative weights (property)', () => {
    const wArb = fc
      .tuple(fc.double({ min: 0, max: 1, noNaN: true }), fc.double({ min: 0, max: 1, noNaN: true }))
      .map(([a, b]) => ({
        terrain: a / 2,
        thermal: (1 - a) / 2,
        cold_ice: b / 2,
        composition: (1 - b) / 2,
        subsurface: 0,
      }));
    fc.assert(
      fc.property(
        wArb,
        fc.constantFrom(...GROUP_IDS),
        fc.double({ min: -1, max: 2, noNaN: true }),
        (w, g, v) => {
          const out = renormalise(w, g, v);
          expect(sum(out)).toBeCloseTo(1, 9);
          for (const k of GROUP_IDS) expect(out[k]).toBeGreaterThanOrEqual(0);
        },
      ),
    );
  });
});

describe('session store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useRealTimers();
  });

  it('starts on the balanced lens', () => {
    const s = useSession();
    expect(s.lens).toBe('balanced');
    expect(s.weights).toEqual(DEFAULT_LENSES.balanced);
  });

  it('setWeight switches the label to custom and renormalises', () => {
    const s = useSession();
    s.setWeight('thermal', 0.7);
    expect(s.lens).toBe('custom');
    expect(sum(s.weights)).toBeCloseTo(1, 12);
    expect(s.weights.thermal).toBeCloseTo(0.7);
  });

  it('lens switch resets weights to the preset', () => {
    const s = useSession();
    s.setWeight('terrain', 0.9);
    s.setLens('cold_volatiles');
    expect(s.lens).toBe('cold_volatiles');
    expect(s.weights).toEqual(DEFAULT_LENSES.cold_volatiles);
  });

  it('selecting a landmark ranks immediately; sliders are debounced to 50 ms', async () => {
    vi.useFakeTimers();
    const s = useSession();
    const eng = fakeEngine();
    s.attach({ engine: eng });
    s.setBundle(fakeBundle());
    s.selectLandmark('synthetic_t');
    await vi.waitFor(() => expect(eng.calls).toBe(1));
    s.setWeight('terrain', 0.3);
    s.setWeight('terrain', 0.35);
    s.setWeight('terrain', 0.4);
    expect(eng.calls).toBe(1);
    await vi.advanceTimersByTimeAsync(49);
    expect(eng.calls).toBe(1);
    await vi.advanceTimersByTimeAsync(2);
    expect(eng.calls).toBe(2);
    expect(s.result?.version).toBe(2);
  });

  it('switching body clears a target on the other body', () => {
    const s = useSession();
    s.setBundle(fakeBundle());
    s.selectLandmark('synthetic_t');
    s.selectBody('mars');
    expect(s.target).toBeNull();
    expect(s.result).toBeNull();
  });

  it("switching body opens that body's first landmark", () => {
    const s = useSession();
    const b = fakeBundle();
    b.targets.push({ ...b.targets[0], id: 'synthetic_mars', body: 'mars' });
    s.setBundle(b);
    s.selectLandmark('synthetic_t');
    s.selectBody('mars');
    expect(s.target).toEqual({ kind: 'landmark', id: 'synthetic_mars' });
  });

  it('interactive stability replaces preset and returns to preset when weights change', async () => {
    const s = useSession();
    const eng = fakeEngine();
    const fetchStability = vi.fn(async () => ({
      target: 'synthetic_t',
      lens: 'balanced' as const,
      draws: 500,
      rows: [[3, 0.5]] as [number, number][],
    }));
    s.attach({ engine: eng, fetchStability });
    s.setBundle(fakeBundle());
    s.selectLandmark('synthetic_t');
    await vi.waitFor(() => expect(s.stability?.kind).toBe('preset'));
    await s.runStability(100);
    expect(s.stability?.kind).toBe('interactive');
    s.setWeight('terrain', 0.5);
    await vi.waitFor(() => expect(s.stability?.kind).toBe('preset'));
  });
});
