import { describe, expect, it } from 'vitest';
import { divergenceItems } from '../src/content/divergence';
import type { FeatureRow } from '../src/stores/selectors';

function row(name: string, unit: string, gap: number, similarity: number): FeatureRow {
  return {
    name,
    group: 'thermal',
    unit,
    target: NaN,
    earth: NaN,
    gap,
    similarity,
    sourceEarth: '',
    sourceTarget: '',
  };
}

describe('divergenceItems', () => {
  it('always lists gravity, atmosphere/vacuum and radiation as not replicable on Earth', () => {
    for (const body of ['moon', 'mars'] as const) {
      const nr = divergenceItems(body, 0, []).filter((i) => i.kind === 'not_replicable');
      expect(nr).toHaveLength(3);
      expect(nr.every((i) => i.text.endsWith('not replicable on Earth'))).toBe(true);
    }
    expect(divergenceItems('mars', 0, [])[1].text).toContain('0.6 kPa CO₂');
    expect(divergenceItems('moon', 0, [])[1].text).toContain('vacuum');
  });

  it('adds the permanent-shadow note only for polar Moon targets', () => {
    const has = (b: 'moon' | 'mars', lat: number) =>
      divergenceItems(b, lat, []).some((i) => i.text.startsWith('Permanent-shadow'));
    expect(has('moon', -88.5)).toBe(true);
    expect(has('moon', 10)).toBe(false);
    expect(has('mars', 85)).toBe(false);
  });

  it('lists weak matches with their physical gap and keeps missing features separate', () => {
    const items = divergenceItems('moon', 0, [
      row('diurnal_range_K', 'K', 212, 0.01),
      row('slope_p50_deg', 'deg', 0.5, 0.9),
      row('annual_range_K', 'K', NaN, NaN),
      row('lst_mean_K', 'K', NaN, NaN),
      { ...row('lith', 'class fractions', NaN, 0.12) },
    ]);
    const weak = items.filter((i) => i.kind === 'weak').map((i) => i.text);
    expect(weak).toEqual([
      'Weak match: day–night range gap Δ 212.0 K',
      'Weak match: lithology similarity 0.12',
    ]);
    expect(items.some((i) => i.text.includes('here Δ 212.0 K'))).toBe(true);
    expect(items.filter((i) => i.kind === 'missing').map((i) => i.text)).toEqual([
      'Not compared (not measured on one side): annual range, mean surface temperature',
    ]);
  });
});
