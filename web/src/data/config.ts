// Manifest validation (00/R5.2): checks a loaded manifest.json against contract C6/C1/C3.
import {
  FEATURE_GROUPS,
  FEATURE_NAMES,
  GROUP_IDS,
  LENS_IDS,
  LITH_CLASSES,
  N_FEATURES,
  N_LITH,
  REQUIRED_FILE_KEYS,
  type Manifest,
} from './types';

/** Thrown when manifest.json (or an array it describes) does not match the contract. */
export class ManifestError extends Error {
  readonly field: string;
  constructor(field: string, message: string) {
    super(`manifest.${field}: ${message}`);
    this.name = 'ManifestError';
    this.field = field;
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function finite(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

const REQUIRED_PARAMS = [
  'seed',
  'footprint_radius_km',
  'land_frac_min',
  'coverage_floor',
  'card_overall_percentile',
  'card_min_separation_km',
  'novelty_gate_km',
] as const;
const REQUIRED_STABILITY = [
  'draws',
  'draws_interactive',
  'dirichlet_concentration',
  'tol_log_sigma',
  'top_fraction',
  'store_top_k',
] as const;

function checkFeatures(raw: unknown): void {
  if (!Array.isArray(raw) || raw.length !== N_FEATURES) {
    throw new ManifestError('features', `expected ${N_FEATURES} entries`);
  }
  raw.forEach((f: unknown, i) => {
    if (!isRecord(f)) throw new ManifestError(`features[${i}]`, 'not an object');
    if (f.name !== FEATURE_NAMES[i]) {
      throw new ManifestError(
        `features[${i}].name`,
        `'${String(f.name)}' but C1 order requires '${FEATURE_NAMES[i]}'`,
      );
    }
    if (f.group !== FEATURE_GROUPS[i]) {
      throw new ManifestError(`features[${i}].group`, `expected '${FEATURE_GROUPS[i]}'`);
    }
    if (f.transform !== 'none' && f.transform !== 'log1p') {
      throw new ManifestError(`features[${i}].transform`, 'must be none or log1p');
    }
    if (typeof f.unit !== 'string') throw new ManifestError(`features[${i}].unit`, 'missing');
    if (!finite(f.median)) throw new ManifestError(`features[${i}].median`, 'must be finite');
    if (!finite(f.s) || f.s <= 0) throw new ManifestError(`features[${i}].s`, 'must be > 0');
  });
}

function checkMatrix(raw: unknown): void {
  const ok =
    Array.isArray(raw) &&
    raw.length === N_LITH &&
    raw.every((r: unknown) => Array.isArray(r) && r.length === N_LITH && r.every(finite));
  if (!ok) throw new ManifestError('compat_matrix', `expected ${N_LITH}×${N_LITH} numbers`);
}

function checkLenses(raw: unknown): void {
  if (!isRecord(raw)) throw new ManifestError('lenses', 'not an object');
  for (const id of LENS_IDS) {
    const lens = raw[id];
    if (!isRecord(lens)) throw new ManifestError(`lenses.${id}`, 'missing');
    let sum = 0;
    for (const g of GROUP_IDS) {
      const w = lens[g];
      if (!finite(w) || w < 0) throw new ManifestError(`lenses.${id}.${g}`, 'must be ≥ 0');
      sum += w;
    }
    if (Math.abs(sum - 1) > 1e-6) throw new ManifestError(`lenses.${id}`, `sums to ${sum}`);
  }
}

function checkParams(raw: unknown): void {
  if (!isRecord(raw)) throw new ManifestError('params', 'not an object');
  for (const k of REQUIRED_PARAMS) {
    if (!finite(raw[k])) throw new ManifestError(`params.${k}`, 'missing or not a number');
  }
  const st = raw.stability;
  if (!isRecord(st)) throw new ManifestError('params.stability', 'missing');
  for (const k of REQUIRED_STABILITY) {
    if (!finite(st[k])) throw new ManifestError(`params.stability.${k}`, 'missing');
  }
}

/** Validate a parsed manifest.json; returns it typed or throws ManifestError naming the field. */
export function validateManifest(raw: unknown): Manifest {
  if (!isRecord(raw)) throw new ManifestError('(root)', 'not an object');
  if (raw.contract !== 'doppelgrund-bundle/1') {
    throw new ManifestError('contract', `'${String(raw.contract)}' is not 'doppelgrund-bundle/1'`);
  }
  if (typeof raw.synthetic !== 'boolean') throw new ManifestError('synthetic', 'must be boolean');
  if (raw.h3_res !== 4) throw new ManifestError('h3_res', 'must be 4');
  if (!Number.isInteger(raw.n_hex) || (raw.n_hex as number) <= 0) {
    throw new ManifestError('n_hex', 'must be a positive integer');
  }
  checkFeatures(raw.features);
  const lith = raw.lith_classes;
  if (
    !Array.isArray(lith) ||
    lith.length !== N_LITH ||
    lith.some((c, i) => c !== LITH_CLASSES[i])
  ) {
    throw new ManifestError('lith_classes', `must equal [${LITH_CLASSES.join(', ')}]`);
  }
  checkMatrix(raw.compat_matrix);
  checkLenses(raw.lenses);
  checkParams(raw.params);
  if (!isRecord(raw.files)) throw new ManifestError('files', 'not an object');
  const files = raw.files;
  for (const k of REQUIRED_FILE_KEYS) {
    if (typeof files[k] !== 'string') throw new ManifestError(`files.${k}`, 'missing');
  }
  if (!Array.isArray(raw.sources)) throw new ManifestError('sources', 'must be an array');
  return raw as unknown as Manifest;
}

/** Element counts each Earth array must have for a manifest with n_hex rows. */
export function expectedLengths(nHex: number): Record<string, number> {
  return {
    h3: nHex,
    features: nHex * N_FEATURES,
    lith: nHex * N_LITH,
    latlng: nHex * 2,
    novelty: nHex * 2,
    cluster: nHex,
    flags: nHex,
  };
}

/** Throw ManifestError if an Earth array's element count does not match manifest.n_hex. */
export function checkArrayLength(manifest: Manifest, key: string, length: number): void {
  const expected = expectedLengths(manifest.n_hex)[key];
  if (expected !== undefined && expected !== length) {
    throw new ManifestError(
      'n_hex',
      `${manifest.files[key as keyof typeof manifest.files] ?? key} has ${length} elements, ` +
        `expected ${expected} for n_hex=${manifest.n_hex}`,
    );
  }
}
