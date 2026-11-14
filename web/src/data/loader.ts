// Bundle loader (03/R1): the only module that fetches files. Same-origin static files only.
import { ManifestError, checkArrayLength, validateManifest } from './config';
import {
  N_FEATURES,
  N_LITH,
  type Body,
  type Bundle,
  type DiscGrid,
  type LensId,
  type Manifest,
  type StabilityFile,
  type Target,
  type TargetJson,
} from './types';

/** Thrown when a bundle file is missing or does not match the contract; names the file. */
export class BundleError extends Error {
  readonly file: string;
  readonly field: string | null;
  constructor(file: string, message: string, field: string | null = null) {
    super(`${file}: ${message}`);
    this.name = 'BundleError';
    this.file = file;
    this.field = field;
  }
}

export interface GeoJsonFeature {
  type: 'Feature';
  properties: Record<string, unknown>;
  geometry: { type: string; coordinates: unknown };
}
export interface GeoJsonFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJsonFeature[];
}

const LITTLE_ENDIAN = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

function join(baseUrl: string, file: string): string {
  return baseUrl.endsWith('/') ? baseUrl + file : `${baseUrl}/${file}`;
}

async function fetchOk(baseUrl: string, file: string): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(join(baseUrl, file));
  } catch (e) {
    throw new BundleError(file, `network error (${(e as Error).message})`);
  }
  if (!res.ok) throw new BundleError(file, `missing (HTTP ${res.status})`);
  return res;
}

async function fetchJson(baseUrl: string, file: string): Promise<unknown> {
  const res = await fetchOk(baseUrl, file);
  try {
    return (await res.json()) as unknown;
  } catch {
    throw new BundleError(file, 'invalid JSON');
  }
}

type TypedCtor = Float32ArrayConstructor | Int16ArrayConstructor | Uint8ArrayConstructor;

/** View an ArrayBuffer as a little-endian typed array (byte-swaps on big-endian hosts). */
function view<T extends TypedCtor>(file: string, buf: ArrayBuffer, ctor: T): InstanceType<T> {
  const size = ctor.BYTES_PER_ELEMENT;
  if (buf.byteLength % size !== 0) {
    throw new BundleError(file, `byte length ${buf.byteLength} is not a multiple of ${size}`);
  }
  if (LITTLE_ENDIAN || size === 1) return new ctor(buf) as InstanceType<T>;
  const dv = new DataView(buf);
  const out = new ctor(buf.byteLength / size);
  for (let i = 0; i < out.length; i++) {
    out[i] = size === 4 ? dv.getFloat32(i * 4, true) : dv.getInt16(i * 2, true);
  }
  return out as InstanceType<T>;
}

async function fetchArray<T extends TypedCtor>(
  baseUrl: string,
  file: string,
  ctor: T,
): Promise<InstanceType<T>> {
  const res = await fetchOk(baseUrl, file);
  return view(file, await res.arrayBuffer(), ctor);
}

function toNaN(values: unknown, n: number, file: string, field: string): Float64Array {
  if (!Array.isArray(values) || values.length !== n) {
    throw new BundleError(file, `${field} must have ${n} entries`, field);
  }
  return Float64Array.from(values, (v: unknown) => (typeof v === 'number' ? v : NaN));
}

/** Parse targets.json (null → NaN). */
export function parseTargets(raw: unknown, file = 'targets.json'): Target[] {
  if (!Array.isArray(raw)) throw new BundleError(file, 'must be a JSON array');
  return raw.map((r: unknown, i): Target => {
    const t = r as Partial<TargetJson>;
    if (typeof t.id !== 'string' || (t.body !== 'moon' && t.body !== 'mars')) {
      throw new BundleError(file, `entry ${i} needs id and body (moon|mars)`, `[${i}]`);
    }
    return {
      id: t.id,
      name: typeof t.name === 'string' ? t.name : t.id,
      body: t.body,
      lat: Number(t.lat),
      lon: Number(t.lon),
      features: toNaN(t.features, N_FEATURES, file, `[${i}].features`),
      lith: toNaN(t.lith, N_LITH, file, `[${i}].lith`),
      cluster: typeof t.cluster === 'number' ? t.cluster : null,
      notes: typeof t.notes === 'string' ? t.notes : '',
      coverage_notes: Array.isArray(t.coverage_notes) ? t.coverage_notes.map(String) : [],
    };
  });
}

function checked(manifest: Manifest, key: string, file: string, length: number): void {
  try {
    checkArrayLength(manifest, key, length);
  } catch (e) {
    if (e instanceof ManifestError) throw new BundleError(file, e.message, e.field);
    throw e;
  }
}

async function loadDiscs(baseUrl: string, m: Manifest, body: Body): Promise<DiscGrid | null> {
  const f = m.files[`${body}_features`];
  const l = m.files[`${body}_lith`];
  const ll = m.files[`${body}_latlon`];
  if (!f || !l || !ll) return null;
  const [features, lith, latlon] = await Promise.all([
    fetchArray(baseUrl, f, Float32Array),
    fetchArray(baseUrl, l, Float32Array),
    fetchArray(baseUrl, ll, Float32Array),
  ]);
  const n = features.length / N_FEATURES;
  if (!Number.isInteger(n))
    throw new BundleError(f, `length ${features.length} not M×${N_FEATURES}`);
  if (lith.length !== n * N_LITH) throw new BundleError(l, `expected ${n * N_LITH} values`);
  if (latlon.length !== n * 2) throw new BundleError(ll, `expected ${n * 2} values`);
  return { n, features, lith, latlon };
}

/** Load and validate the whole C6 bundle; files are fetched in parallel. */
export async function loadBundle(
  baseUrl: string,
  onProgress?: (done: number, total: number) => void,
): Promise<Bundle> {
  const rawManifest = await fetchJson(baseUrl, 'manifest.json');
  let manifest: Manifest;
  try {
    manifest = validateManifest(rawManifest);
  } catch (e) {
    if (e instanceof ManifestError) throw new BundleError('manifest.json', e.message, e.field);
    throw e;
  }
  const fl = manifest.files;
  const hasDiscs = (b: Body): boolean => Boolean(fl[`${b}_features`]);
  const total = 9 + (hasDiscs('moon') ? 1 : 0) + (hasDiscs('mars') ? 1 : 0);
  let done = 1;
  onProgress?.(done, total);
  const tick = <T>(p: Promise<T>): Promise<T> =>
    p.then((v) => {
      done += 1;
      onProgress?.(done, total);
      return v;
    });

  const [h3Text, features, lith, latlng, novelty, cluster, flags, targetsRaw, moon, mars] =
    await Promise.all([
      tick(fetchOk(baseUrl, fl.h3).then((r) => r.text())),
      tick(fetchArray(baseUrl, fl.features, Float32Array)),
      tick(fetchArray(baseUrl, fl.lith, Float32Array)),
      tick(fetchArray(baseUrl, fl.latlng, Float32Array)),
      tick(fetchArray(baseUrl, fl.novelty, Float32Array)),
      tick(fetchArray(baseUrl, fl.cluster, Int16Array)),
      tick(fetchArray(baseUrl, fl.flags, Uint8Array)),
      tick(fetchJson(baseUrl, fl.targets)),
      hasDiscs('moon') ? tick(loadDiscs(baseUrl, manifest, 'moon')) : Promise.resolve(null),
      hasDiscs('mars') ? tick(loadDiscs(baseUrl, manifest, 'mars')) : Promise.resolve(null),
    ]);

  const h3 = h3Text.split('\n').filter((s) => s.length > 0);
  checked(manifest, 'h3', fl.h3, h3.length);
  checked(manifest, 'features', fl.features, features.length);
  checked(manifest, 'lith', fl.lith, lith.length);
  checked(manifest, 'latlng', fl.latlng, latlng.length);
  checked(manifest, 'novelty', fl.novelty, novelty.length);
  checked(manifest, 'cluster', fl.cluster, cluster.length);
  checked(manifest, 'flags', fl.flags, flags.length);
  const discs: Bundle['discs'] = {};
  if (moon) discs.moon = moon;
  if (mars) discs.mars = mars;
  return {
    manifest,
    h3,
    features,
    lith,
    latlng,
    novelty,
    cluster,
    flags,
    targets: parseTargets(targetsRaw, fl.targets),
    discs,
  };
}

/** Preset stability for one target and lens; null when the file does not exist. */
export async function loadStability(
  baseUrl: string,
  targetId: string,
  lens: LensId,
): Promise<StabilityFile | null> {
  const file = `stability/${targetId}__${lens}.json`;
  try {
    const raw = (await fetchJson(baseUrl, file)) as Partial<StabilityFile>;
    if (!Array.isArray(raw.rows)) throw new BundleError(file, 'rows must be an array', 'rows');
    return raw as StabilityFile;
  } catch (e) {
    if (e instanceof BundleError && e.message.includes('HTTP 404')) return null;
    throw e;
  }
}

/** One overlay layer (layers/<id>.geojson); null when absent. */
export async function loadLayer(
  baseUrl: string,
  id: string,
): Promise<GeoJsonFeatureCollection | null> {
  const file = `layers/${id}.geojson`;
  try {
    const raw = (await fetchJson(baseUrl, file)) as Partial<GeoJsonFeatureCollection>;
    if (raw.type !== 'FeatureCollection' || !Array.isArray(raw.features)) {
      throw new BundleError(file, 'not a GeoJSON FeatureCollection');
    }
    return raw as GeoJsonFeatureCollection;
  } catch (e) {
    if (e instanceof BundleError && e.message.includes('HTTP 404')) return null;
    throw e;
  }
}

/** Decode an image file (texture or index map) to an ImageBitmap. */
export async function loadImageBitmap(baseUrl: string, file: string): Promise<ImageBitmap> {
  const res = await fetchOk(baseUrl, file);
  try {
    return await createImageBitmap(await res.blob(), {
      premultiplyAlpha: 'none',
      colorSpaceConversion: 'none',
    });
  } catch {
    throw new BundleError(file, 'could not decode image');
  }
}

/** Decode earth_index_4096x2048.png to raw RGBA pixels (needs OffscreenCanvas; worker-safe). */
export async function loadIndexMap(
  baseUrl: string,
  manifest: Manifest,
): Promise<{ width: number; height: number; rgba: Uint8ClampedArray }> {
  const bmp = await loadImageBitmap(baseUrl, manifest.files.index_map);
  const canvas = new OffscreenCanvas(bmp.width, bmp.height);
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new BundleError(manifest.files.index_map, '2D canvas unavailable');
  ctx.drawImage(bmp, 0, 0);
  const img = ctx.getImageData(0, 0, bmp.width, bmp.height);
  bmp.close();
  return { width: img.width, height: img.height, rgba: img.data };
}
