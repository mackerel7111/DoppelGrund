// Contract types: mirrors data-contracts.md C1 (features), C5 (cards), C6 (bundle), C8 (worker).
// Humans change contracts; keep names and orders verbatim.

/** C1 feature names in column order. */
export const FEATURE_NAMES = [
  'slope_p50_deg',
  'slope_p90_deg',
  'relief_std_m',
  'frac_slope_lt_10deg',
  'lst_mean_K',
  'diurnal_range_K',
  'annual_range_K',
  'frac_below_0C',
  'permafrost_prob',
  'aridity_index',
  'pit_cave_density_per_1000km2',
] as const;
export type FeatureName = (typeof FEATURE_NAMES)[number];
export const N_FEATURES = FEATURE_NAMES.length; // 11

/** C1 lithology classes in vector order. */
export const LITH_CLASSES = [
  'mafic_volcanic',
  'felsic_feldspathic',
  'carbonate',
  'siliciclastic',
  'evaporite',
  'ice',
] as const;
export type LithClass = (typeof LITH_CLASSES)[number];
export const N_LITH = LITH_CLASSES.length; // 6

/** Group ids in C5 card order. */
export const GROUP_IDS = ['terrain', 'thermal', 'cold_ice', 'composition', 'subsurface'] as const;
export type GroupId = (typeof GROUP_IDS)[number];
export type NumericGroupId = Exclude<GroupId, 'composition'>;

/** C1 group of each numeric feature, in column order. */
export const FEATURE_GROUPS: readonly NumericGroupId[] = [
  'terrain',
  'terrain',
  'terrain',
  'terrain',
  'thermal',
  'thermal',
  'thermal',
  'cold_ice',
  'cold_ice',
  'cold_ice',
  'subsurface',
];

export const LENS_IDS = [
  'balanced',
  'landing_mobility',
  'cold_volatiles',
  'geology_minerals',
] as const;
export type LensId = (typeof LENS_IDS)[number];

export type Transform = 'none' | 'log1p';
export type Body = 'moon' | 'mars';
export type GroupWeights = Record<GroupId, number>;

/** One entry of manifest.features: C1 metadata plus the pooled scaler (transformed scale). */
export interface FeatureMeta {
  name: FeatureName;
  group: NumericGroupId;
  unit: string;
  transform: Transform;
  median: number;
  s: number;
}

export interface StabilityParams {
  draws: number;
  draws_interactive: number;
  dirichlet_concentration: number;
  tol_log_sigma: number;
  top_fraction: number;
  store_top_k: number;
}

/** manifest.params: the C3 params block. */
export interface BundleParams {
  seed: number;
  footprint_radius_km: number;
  land_frac_min: number;
  coverage_floor: number;
  card_overall_percentile: number;
  card_min_separation_km: number;
  novelty_gate_km: number;
  mask: { barren_plus_ice_min: number; ndvi_max: number };
  stability: StabilityParams;
}

/** Keys of manifest.files that every bundle must provide. */
export const REQUIRED_FILE_KEYS = [
  'h3',
  'features',
  'lith',
  'latlng',
  'novelty',
  'cluster',
  'flags',
  'targets',
  'index_map',
] as const;
export type RequiredFileKey = (typeof REQUIRED_FILE_KEYS)[number];
/** Optional disc-grid files (C6 "optional full disc grids for arbitrary clicks"). */
export const OPTIONAL_DISC_FILE_KEYS = [
  'moon_features',
  'moon_lith',
  'moon_latlon',
  'mars_features',
  'mars_lith',
  'mars_latlon',
] as const;
export type DiscFileKey = (typeof OPTIONAL_DISC_FILE_KEYS)[number];
export type ManifestFiles = Record<RequiredFileKey, string> & Partial<Record<DiscFileKey, string>>;

export interface SourceEntry {
  feature: string;
  body: 'earth' | Body;
  dataset: string;
  version: string;
}

/** C6 manifest.json */
export interface Manifest {
  contract: 'doppelgrund-bundle/1';
  created_utc: string;
  synthetic: boolean;
  h3_res: number;
  n_hex: number;
  features: FeatureMeta[];
  lith_classes: LithClass[];
  compat_matrix: number[][];
  lenses: Record<LensId, GroupWeights>;
  params: BundleParams;
  files: ManifestFiles;
  sources: SourceEntry[];
}

/** C6 targets.json entry as stored (NaN written as null). */
export interface TargetJson {
  id: string;
  name: string;
  body: Body;
  lat: number;
  lon: number;
  features: (number | null)[];
  lith: (number | null)[];
  cluster: number | null;
  notes: string;
  coverage_notes: string[];
}

/** Target after loading: null converted to NaN. */
export interface Target {
  id: string;
  name: string;
  body: Body;
  lat: number;
  lon: number;
  features: Float64Array; // 11, raw (untransformed)
  lith: Float64Array; // 6
  cluster: number | null;
  notes: string;
  coverage_notes: string[];
}

/** Optional per-body disc grid (M discs). */
export interface DiscGrid {
  n: number;
  features: Float32Array; // M×11 raw
  lith: Float32Array; // M×6
  latlon: Float32Array; // M×2 [lat, lon]
}

/** Earth flags bits (C6 earth_flags.u8). */
export const FLAG_MASKED = 1;
export const FLAG_VOLCANIC = 2;
export const FLAG_PERIGLACIAL = 4;
export const FLAG_EVAPORITIC = 8;
export const FLAG_KNOWN_SITE = 16;

/** Loaded bundle arrays (C6). Earth arrays share row order with `h3`. */
export interface Bundle {
  manifest: Manifest;
  h3: string[];
  features: Float32Array; // N×11 raw
  lith: Float32Array; // N×6
  latlng: Float32Array; // N×2 [lat, lng]
  novelty: Float32Array; // N×2 [geo_novelty_km, feat_novelty]
  cluster: Int16Array; // N
  flags: Uint8Array; // N
  targets: Target[];
  discs: Partial<Record<Body, DiscGrid>>;
}

/** C6 stability/<target>__<lens>.json */
export interface StabilityFile {
  target: string;
  lens: LensId;
  draws: number;
  rows: [number, number][];
}

// ---- C5 match cards ----
export type CardKind = 'overall' | GroupId;
export const CARD_KINDS: readonly CardKind[] = ['overall', ...GROUP_IDS];

export interface Card {
  kind: CardKind;
  row: number | null;
  S: number;
  S_g: number;
  coverage: number;
  reason?: 'no_eligible_match';
}

// ---- C8 worker protocol ----
export type ColorBy = 'S' | 'novelty' | GroupId;

/** Colour mapping used by the painter: a 256-entry RGBA LUT over [domain[0], domain[1]]. */
export interface Palette {
  lut: Uint8ClampedArray; // 256×4
  domain: [number, number];
  masked: [number, number, number, number]; // RGBA for masked / ineligible / no data
}

export interface RankTarget {
  features: number[]; // 11 raw values, NaN = missing
  lith: number[]; // 6
}

export interface InitRequest {
  type: 'init';
  baseUrl: string;
}
export interface RankRequest {
  type: 'rank';
  reqId: number;
  target: RankTarget;
  weights: GroupWeights;
}
export interface StabilityRequest {
  type: 'stability';
  reqId: number;
  target: RankTarget;
  weights: GroupWeights;
  draws: number;
}
export interface PaintRequest {
  type: 'paint';
  reqId: number;
  colorBy: ColorBy;
  palette: Palette;
}
export type WorkerRequest = InitRequest | RankRequest | StabilityRequest | PaintRequest;

export interface ReadyResponse {
  type: 'ready';
  nHex: number;
  synthetic: boolean;
}
export interface ErrorResponse {
  type: 'error';
  message: string;
  reqId?: number;
}
export interface RankedResponse {
  type: 'ranked';
  reqId: number;
  S: Float32Array;
  coverage: Float32Array;
  groups: Float32Array; // N×4
  cards: Card[];
  top: Int32Array; // best 200 rows
}
export interface ProgressResponse {
  type: 'progress';
  reqId: number;
  done: number;
  total: number;
}
export interface StabilityResponse {
  type: 'stability';
  reqId: number;
  rows: [number, number][];
}
export interface PaintedResponse {
  type: 'painted';
  reqId: number;
  width: number;
  height: number;
  rgba: Uint8ClampedArray;
}
export type WorkerResponse =
  | ReadyResponse
  | ErrorResponse
  | RankedResponse
  | ProgressResponse
  | StabilityResponse
  | PaintedResponse;
