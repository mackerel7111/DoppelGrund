import { describe, expect, it } from 'vitest';
import {
  MASKED_RGBA,
  HEAT_LUT,
  buildLut,
  colorize,
  hexToRgb,
  lutIndex,
  makePalette,
  metricMeta,
  sourceFor,
} from '../src/map/palette';

describe('palette', () => {
  it('builds a 256-entry heat LUT from #FFF3B0 to #E31A1C', () => {
    expect(HEAT_LUT).toHaveLength(256 * 4);
    expect(Array.from(HEAT_LUT.slice(0, 4))).toEqual([...hexToRgb('#FFF3B0'), 255]);
    expect(Array.from(HEAT_LUT.slice(255 * 4))).toEqual([...hexToRgb('#E31A1C'), 255]);
    const mid = buildLut(['#000000', '#FFFFFF'], 3);
    expect(Array.from(mid.slice(4, 8))).toEqual([128, 128, 128, 255]);
  });

  it('maps values to LUT indices with clamping; NaN → −1', () => {
    expect(lutIndex(0, [0, 100])).toBe(0);
    expect(lutIndex(100, [0, 100])).toBe(255);
    expect(lutIndex(50, [0, 100])).toBe(128);
    expect(lutIndex(-5, [0, 100])).toBe(0);
    expect(lutIndex(500, [0, 100])).toBe(255);
    expect(lutIndex(NaN, [0, 100])).toBe(-1);
  });

  it('colours ineligible, NaN and missing results grey (#9A9A9A at 60%)', () => {
    const pal = makePalette([0, 100]);
    const values = Float32Array.from([100, NaN, 0, 40]);
    const out = colorize(
      4,
      { values, stride: 1, offset: 0, eligible: Uint8Array.from([1, 1, 1, 0]) },
      pal,
    );
    expect(Array.from(out.slice(0, 4))).toEqual([...hexToRgb('#E31A1C'), 255]);
    expect(Array.from(out.slice(4, 8))).toEqual(MASKED_RGBA);
    expect(Array.from(out.slice(8, 12))).toEqual([...hexToRgb('#FFF3B0'), 255]);
    expect(Array.from(out.slice(12, 16))).toEqual(MASKED_RGBA);
    expect(Array.from(colorize(2, null, pal))).toEqual([...MASKED_RGBA, ...MASKED_RGBA]);
    expect(MASKED_RGBA[3] / 255).toBeCloseTo(0.6, 2);
  });

  it('reads group columns and novelty with the right stride', () => {
    const res = {
      S: Float32Array.from([1, 2]),
      groups: Float32Array.from([10, 20, 30, 40, 50, 60, 70, 80]),
      eligible: Uint8Array.from([1, 1]),
    };
    const nov = Float32Array.from([123, 0.1, 456, 0.2]);
    const thermal = sourceFor('thermal', res, nov, Uint8Array.from([1, 1]));
    expect(thermal?.values[1 * (thermal?.stride ?? 0) + (thermal?.offset ?? 0)]).toBe(60);
    const n = sourceFor('novelty', null, nov, Uint8Array.from([1, 0]));
    expect(n?.values[1 * 2 + 0]).toBe(456);
    expect(sourceFor('S', null, nov, Uint8Array.from([1, 1]))).toBeNull();
  });

  it('legend metadata states metric and unit', () => {
    expect(metricMeta('S')).toMatchObject({ label: 'Similarity', unit: '0–100' });
    expect(metricMeta('novelty', 2500)).toMatchObject({ unit: 'km', domain: [0, 2500] });
    expect(metricMeta('cold_ice').label).toContain('Cold & ice');
  });
});
