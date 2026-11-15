import { describe, expect, it } from 'vitest';
import {
  A_LOW,
  T0_MAX,
  T0_MIN,
  decodeIndex,
  glowRange,
  decodePixel,
  fillGaps,
  paint,
  sampleIndex,
} from '../src/globe/painter';
import { HEAT_LUT, makePalette } from '../src/map/palette';
import { EngineHost, metricValues } from '../src/workers/engine.worker';
import type { WorkerResponse } from '../src/data/types';

/** 4×2 RGBA index image: rows 0, 1, 2 and 70000 (multi-byte encoding), others empty. */
function tinyIndex(): Uint8ClampedArray {
  const px = [1, 0, 2, 3, 70001, 0, 0, 1];
  const out = new Uint8ClampedArray(px.length * 4);
  px.forEach((v, i) => {
    out[i * 4] = (v >> 16) & 255;
    out[i * 4 + 1] = (v >> 8) & 255;
    out[i * 4 + 2] = v & 255;
    out[i * 4 + 3] = 255;
  });
  return out;
}

const rgb = (a: Uint8ClampedArray, p: number) => [
  a[p * 4],
  a[p * 4 + 1],
  a[p * 4 + 2],
  a[p * 4 + 3],
];

describe('painter', () => {
  it('decodes row + 1 = R·65536 + G·256 + B, 0 = no hexagon', () => {
    expect(decodePixel(0, 0, 0)).toBe(-1);
    expect(decodePixel(0, 0, 1)).toBe(0);
    expect(decodePixel(1, 17, 113)).toBe(70000);
    expect(Array.from(decodeIndex(tinyIndex()))).toEqual([0, -1, 1, 2, 70000, -1, -1, 0]);
  });

  it('point-samples the centre pixel (x·k+k/2, y·k+k/2) of each k×k block', () => {
    const w = 8;
    const rgba = new Uint8ClampedArray(w * 4 * 4); // 8×4, all "no hexagon"
    const put = (x: number, y: number, row: number) => (rgba[(y * w + x) * 4 + 2] = row + 1);
    put(2, 2, 7); // centre of block 0
    put(6, 2, 9); // centre of block 1
    put(0, 0, 5); // corner, ignored
    expect(Array.from(sampleIndex(rgba, w, 4))).toEqual([7, 9]);
  });

  it('paints eligible rows with a value-ramped alpha; everything else is transparent', () => {
    const values = Float32Array.from([100, NaN, 0]);
    const eligible = Uint8Array.from([1, 1, 0]);
    const out = paint(tinyIndex(), values, makePalette([0, 100]), eligible);
    expect(out).toHaveLength(8 * 4);
    expect(rgb(out, 0)).toEqual([...HEAT_LUT.slice(255 * 4, 255 * 4 + 3), 255]); // t = 1
    expect(rgb(out, 1)[3]).toBe(0); // no hexagon
    expect(rgb(out, 2)[3]).toBe(0); // NaN
    expect(rgb(out, 3)[3]).toBe(0); // ineligible
    expect(rgb(out, 4)[3]).toBe(0); // row 70000 is beyond N
    expect(rgb(out, 7)).toEqual(rgb(out, 0)); // same row, same colour
  });

  it('keeps low scores faint and makes the top band glow (data-relative threshold)', () => {
    const n = 100;
    const values = Float32Array.from({ length: n }, (_, i) => i); // 0..99, domain 0..100
    const eligible = new Uint8Array(n).fill(1);
    const [t0, t1] = glowRange(values, eligible, 0, 100);
    expect(t1).toBeCloseTo(0.99, 2);
    expect(t0).toBeGreaterThanOrEqual(T0_MIN);
    expect(t0).toBeLessThanOrEqual(T0_MAX);
    const out = paint(
      Int32Array.from({ length: n }, (_, i) => i),
      values,
      makePalette([0, 100]),
      eligible,
    );
    expect(out[3]).toBe(Math.round(255 * A_LOW)); // score 0
    expect(out[10 * 4 + 3]).toBe(Math.round(255 * A_LOW)); // below T0
    expect(out[99 * 4 + 3]).toBeGreaterThan(240); // best score glows
    let bright = 0;
    for (let i = 0; i < n; i++) if (out[i * 4 + 3] > 128) bright++;
    expect(bright).toBeGreaterThanOrEqual(15); // roughly the top 40 %
    expect(bright).toBeLessThanOrEqual(40);
    for (let i = 1; i < n; i++) expect(out[i * 4 + 3]).toBeGreaterThanOrEqual(out[(i - 1) * 4 + 3]);
  });

  it('stretches the ramp to the best score of a narrow result', () => {
    const values = Float32Array.from({ length: 100 }, (_, i) => 30 + i * 0.3); // 30..59.7 of 100
    const eligible = new Uint8Array(100).fill(1);
    const out = paint(
      Int32Array.from({ length: 100 }, (_, i) => i),
      values,
      makePalette([0, 100]),
      eligible,
    );
    expect(out[99 * 4 + 3]).toBe(255);
  });

  it('never leaves a uniformly poor result empty: threshold is clamped', () => {
    const values = new Float32Array(50).fill(5); // all near the bottom
    const eligible = new Uint8Array(50).fill(1);
    expect(glowRange(values, eligible, 0, 100)[0]).toBe(T0_MIN);
    expect(glowRange(new Float32Array(3).fill(NaN), new Uint8Array(3).fill(1), 0, 100)[0]).toBe(
      T0_MAX,
    );
  });

  it('paints a 4096×2048 texture within the 150 ms budget (informational)', () => {
    const n = 85_000;
    const rows = new Int32Array(4096 * 2048);
    for (let p = 0; p < rows.length; p++) rows[p] = p % 3 === 0 ? -1 : p % n;
    const values = Float32Array.from({ length: n }, (_, i) => i % 100);
    const eligible = new Uint8Array(n).fill(1);
    paint(rows, values, makePalette([0, 100]), eligible); // warm-up
    const t0 = performance.now();
    paint(rows, values, makePalette([0, 100]), eligible);
    const ms = performance.now() - t0;
    console.info(`[perf] paint 4096×2048: ${ms.toFixed(1)} ms`);
    expect(ms).toBeLessThan(600);
    const small = sampleIndex(new Uint8ClampedArray(rows.length * 4), 4096, 2048); // shape only
    for (let p = 0; p < small.length; p++) small[p] = p % 3 === 0 ? -1 : p % n;
    const t1 = performance.now();
    paint(small, values, makePalette([0, 100]), eligible);
    console.info(`[perf] paint 1024×512: ${(performance.now() - t1).toFixed(1)} ms`);
  });
});

describe('worker paint handler', () => {
  it('decodes the index once and returns a transferred painted texture', async () => {
    const out: [WorkerResponse, Transferable[]][] = [];
    let loads = 0;
    const host = new EngineHost(
      (m, t) => out.push([m, t]),
      undefined,
      async () => {
        loads++;
        return { width: 8, height: 4, rgba: new Uint8ClampedArray(8 * 4 * 4) };
      },
    );
    host.prepared = {
      bundle: {
        manifest: { n_hex: 3 },
        novelty: Float32Array.from([10, 0, 500, 0, 2000, 0]),
        flags: Uint8Array.from([0, 1, 0]),
      },
    } as unknown as NonNullable<EngineHost['prepared']>;
    const palette = makePalette([0, 2000]);
    await host.handle({ type: 'paint', reqId: 1, colorBy: 'novelty', palette });
    await host.handle({ type: 'paint', reqId: 2, colorBy: 'S', palette });
    expect(loads).toBe(1);
    const [res, transfer] = out[0];
    if (res.type !== 'painted') throw new Error(res.type);
    expect([res.width, res.height, res.rgba.length]).toEqual([2, 1, 8]); // 4× down-sampled
    expect(transfer).toHaveLength(1);
    if (!host.prepared) throw new Error('not prepared');
    const v = metricValues(host.prepared, null, 'novelty');
    expect(Array.from(v.values)).toEqual([10, 500, 2000]);
    expect(Array.from(v.eligible)).toEqual([1, 0, 1]);
  });
});

describe('fillGaps', () => {
  // one painted pixel (red, alpha 200) in a 6x1 strip
  const strip = (): Uint8ClampedArray => {
    const a = new Uint8ClampedArray(6 * 4);
    a.set([255, 0, 0, 200], 2 * 4);
    return a;
  };

  it('copies the nearest painted pixel into gaps within the radius and no further', () => {
    const out = fillGaps(strip(), 6, 1, 2);
    for (const x of [0, 1, 2, 3, 4])
      expect(Array.from(out.slice(x * 4, x * 4 + 4))).toEqual([255, 0, 0, 200]);
    expect(out[5 * 4 + 3]).toBe(0); // 3 px away
  });

  it('wraps at the date line and is a no-op for radius 0', () => {
    const a = new Uint8ClampedArray(6 * 4);
    a.set([0, 255, 0, 255], 5 * 4);
    expect(fillGaps(a, 6, 1, 1)[3]).toBe(255); // pixel 0 is next to pixel 5
    const s = strip();
    expect(fillGaps(s, 6, 1, 0)).toBe(s);
  });
});
