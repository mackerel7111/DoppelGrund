import { afterEach, describe, expect, it, vi } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  BundleError,
  loadBundle,
  loadLayer,
  loadStability,
  parseTargets,
} from '../src/data/loader';

const SAMPLE = fileURLToPath(new URL('../public/data/sample/', import.meta.url));
const BASE = 'http://doppelgrund.test/data/sample/';

type Patch = (file: string, bytes: Buffer) => Buffer | null;

function stubFetch(patch: Patch = (_f, b) => b): void {
  vi.stubGlobal('fetch', async (url: string): Promise<Response> => {
    const file = url.slice(BASE.length);
    const path = SAMPLE + file;
    if (!existsSync(path)) return new Response('not found', { status: 404 });
    const bytes = patch(file, readFileSync(path));
    if (bytes === null) return new Response('not found', { status: 404 });
    return new Response(new Uint8Array(bytes));
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('loadBundle (committed sample bundle)', () => {
  it('loads every array with matching lengths and reports progress', async () => {
    stubFetch();
    const progress: [number, number][] = [];
    const b = await loadBundle(BASE, (d, t) => progress.push([d, t]));
    const n = b.manifest.n_hex;
    expect(b.manifest.synthetic).toBe(true);
    expect(n).toBeGreaterThan(0);
    expect(n).toBeLessThanOrEqual(500);
    expect(b.h3).toHaveLength(n);
    expect(b.features).toHaveLength(n * 10);
    expect(b.lith).toHaveLength(n * 6);
    expect(b.latlng).toHaveLength(n * 2);
    expect(b.novelty).toHaveLength(n * 2);
    expect(b.cluster).toHaveLength(n);
    expect(b.flags).toHaveLength(n);
    expect(b.targets.length).toBeGreaterThanOrEqual(6);
    expect(b.discs.moon?.n).toBeGreaterThan(0);
    expect(b.discs.mars?.latlon).toHaveLength((b.discs.mars?.n ?? 0) * 2);
    const last = progress[progress.length - 1];
    expect(last[0]).toBe(last[1]);
    expect(Array.from(b.features).some(Number.isNaN)).toBe(true); // NaN preserved
  });

  it('converts null target values to NaN', async () => {
    stubFetch();
    const b = await loadBundle(BASE);
    const mars = b.targets.find((t) => t.body === 'mars');
    expect(Number.isNaN(mars?.features[4])).toBe(true);
    expect(mars?.features[9]).toBe(0);
  });

  it('throws BundleError naming the file on a corrupt length', async () => {
    stubFetch((f, b) => (f === 'earth_features.f32' ? b.subarray(0, b.length - 40) : b));
    await expect(loadBundle(BASE)).rejects.toThrow(BundleError);
    await expect(loadBundle(BASE)).rejects.toThrow(/earth_features\.f32/);
  });

  it('throws BundleError naming a missing file', async () => {
    stubFetch((f, b) => (f === 'earth_flags.u8' ? null : b));
    await expect(loadBundle(BASE)).rejects.toThrow(/earth_flags\.u8: missing \(HTTP 404\)/);
  });

  it('names the contract field when the manifest is invalid', async () => {
    stubFetch((f, b) => {
      if (f !== 'manifest.json') return b;
      const m = JSON.parse(b.toString('utf-8')) as { features: { name: string }[] };
      m.features[0].name = 'slope_mean_deg';
      return Buffer.from(JSON.stringify(m));
    });
    const err = await loadBundle(BASE).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(BundleError);
    expect((err as BundleError).file).toBe('manifest.json');
    expect((err as BundleError).field).toBe('features[0].name');
  });
});

describe('auxiliary loaders', () => {
  it('loads preset stability and returns null when absent', async () => {
    stubFetch();
    const b = await loadBundle(BASE);
    const st = await loadStability(BASE, b.targets[0].id, 'balanced');
    expect(st?.rows.length).toBeGreaterThan(0);
    expect(await loadStability(BASE, 'no_such_target', 'balanced')).toBeNull();
  });

  it('loads GeoJSON layers', async () => {
    stubFetch();
    const land = await loadLayer(BASE, 'land');
    expect(land?.features.length).toBeGreaterThan(0);
    expect(await loadLayer(BASE, 'nope')).toBeNull();
  });

  it('rejects targets with wrong feature counts', () => {
    expect(() =>
      parseTargets([{ id: 'x', body: 'moon', features: [1, 2], lith: [0, 0, 0, 0, 0, 1] }]),
    ).toThrow(/features must have 10/);
  });
});
