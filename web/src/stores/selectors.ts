// Per-row read-only views used by cards, shortlist and scorecard (one row at a time, never all).
import {
  FLAG_EVAPORITIC,
  FLAG_KNOWN_SITE,
  FLAG_PERIGLACIAL,
  FLAG_VOLCANIC,
  FEATURE_GROUPS,
  GROUP_IDS,
  N_FEATURES,
  type Bundle,
  type DiscGrid,
  type GroupId,
  type GroupWeights,
} from '../data/types';
import {
  HIDDEN_GROUPS,
  type Body,
  type Card,
  type FeatureMeta,
  type RankTarget,
  type SourceEntry,
} from '../data/types';
import { featureSimilarity, lithSimilarity } from '../engine/scoring';
import { transformValue } from '../engine/transforms';
import { PRESET_LABEL } from '../content/labels';
import type { StabilityState } from './session';

export interface RowInfo {
  row: number;
  lat: number;
  lng: number;
  noveltyKm: number; // geo_novelty_km
  featNovelty: number;
  tags: string[];
  knownSite: boolean;
  stability: number | null; // fraction of draws in the top set; null = not among stored rows
  stabilityAvailable: boolean; // false when no stability file or run exists for this target
  stabilityNote: string | null; // "preset" when weights are custom and no interactive run yet
}

/** Which trait groups have usable data on this body: finite values with spread (a constant is an assumption, not data). */
export function groupAvailability(grid: DiscGrid | undefined): Record<GroupId, boolean> {
  const out = { terrain: true, thermal: true, cold_ice: true, composition: true, subsurface: true };
  if (!grid) return out;
  const lo = new Array<number>(N_FEATURES).fill(Infinity);
  const hi = new Array<number>(N_FEATURES).fill(-Infinity);
  for (let i = 0; i < grid.n; i++) {
    for (let f = 0; f < N_FEATURES; f++) {
      const v = grid.features[i * N_FEATURES + f];
      if (Number.isFinite(v)) {
        lo[f] = Math.min(lo[f], v);
        hi[f] = Math.max(hi[f], v);
      }
    }
  }
  for (const g of GROUP_IDS) {
    if (g !== 'composition') out[g] = FEATURE_GROUPS.some((fg, f) => fg === g && hi[f] > lo[f]);
  }
  out.composition = false;
  for (let i = 0; i < grid.n && !out.composition; i++) {
    let sum = 0;
    let ok = true;
    for (let k = 0; k < 6; k++) {
      const v = grid.lith[i * 6 + k];
      ok = ok && Number.isFinite(v);
      sum += v;
    }
    out.composition = ok && sum > 0;
  }
  return out;
}

/** Zero unavailable groups and rescale the rest to sum 1 (unchanged if nothing is left). */
export function effectiveWeights(w: GroupWeights, avail: Record<GroupId, boolean>): GroupWeights {
  const sum = GROUP_IDS.reduce((a, g) => a + (avail[g] ? w[g] : 0), 0);
  if (!(sum > 0)) return w;
  const out = { ...w };
  for (const g of GROUP_IDS) out[g] = avail[g] ? w[g] / sum : 0;
  return out;
}

/** "89.0°S, 12.3°E" — one decimal, hemisphere letters. */
export function formatLatLon(lat: number, lon: number): string {
  const ns = lat < 0 ? 'S' : 'N';
  const ew = lon < 0 ? 'W' : 'E';
  return `${Math.abs(lat).toFixed(1)}°${ns}, ${Math.abs(lon).toFixed(1)}°${ew}`;
}

export interface CardMarker {
  n: number; // 1..6
  row: number;
  lat: number;
  lng: number;
}

/** Numbered markers for the non-empty cards (1 = overall … 6 = subsurface). */
export function cardMarkers(cards: Card[], latlng: Float32Array): CardMarker[] {
  const out: CardMarker[] = [];
  cards.forEach((c, i) => {
    if (c.row !== null && !HIDDEN_GROUPS.includes(c.kind)) {
      out.push({ n: i + 1, row: c.row, lat: latlng[c.row * 2], lng: latlng[c.row * 2 + 1] });
    }
  });
  return out;
}

export function tagsOf(flags: number): string[] {
  const tags: string[] = [];
  if (flags & FLAG_VOLCANIC) tags.push('volcanic');
  if (flags & FLAG_PERIGLACIAL) tags.push('periglacial');
  if (flags & FLAG_EVAPORITIC) tags.push('evaporitic');
  return tags;
}

export function rowInfo(
  bundle: Bundle,
  stability: StabilityState | null,
  weightsCustom: boolean,
  row: number,
): RowInfo {
  const f = bundle.flags[row];
  const st = stability?.rows.get(row);
  return {
    row,
    lat: bundle.latlng[row * 2],
    lng: bundle.latlng[row * 2 + 1],
    noveltyKm: bundle.novelty[row * 2],
    featNovelty: bundle.novelty[row * 2 + 1],
    tags: tagsOf(f),
    knownSite: (f & FLAG_KNOWN_SITE) !== 0,
    stability: st ?? null,
    stabilityAvailable: stability !== null,
    stabilityNote: stability && stability.kind === 'preset' && weightsCustom ? PRESET_LABEL : null,
  };
}

// ---- per-feature comparison for one Earth row (scorecard + divergence) ----

export interface FeatureRow {
  name: string; // feature name or "lith"
  group: string;
  unit: string;
  target: number; // raw, NaN = not measured
  earth: number;
  gap: number; // |target − earth| in physical units; NaN when either is missing
  similarity: number; // kernel k in [0, 1]; NaN when not comparable
  sourceEarth: string;
  sourceTarget: string;
  targetLith?: number[];
  earthLith?: number[];
}

function sourceOf(sources: SourceEntry[], feature: string, body: 'earth' | Body): string {
  const s = sources.find((x) => x.feature === feature && x.body === body);
  if (!s) return 'TODO(verify): source not listed';
  return s.version ? `${s.dataset} (${s.version})` : s.dataset;
}

export function featureComparison(
  bundle: Bundle,
  target: RankTarget,
  targetBody: Body,
  row: number,
): FeatureRow[] {
  const m = bundle.manifest;
  const rows: FeatureRow[] = m.features.map((f: FeatureMeta, i) => {
    const t = target.features[i];
    const e = bundle.features[row * m.features.length + i];
    const both = Number.isFinite(t) && Number.isFinite(e);
    return {
      name: f.name,
      group: f.group,
      unit: f.unit,
      target: t,
      earth: e,
      gap: both ? Math.abs(t - e) : NaN,
      similarity: featureSimilarity(
        transformValue(t, f.transform),
        transformValue(e, f.transform),
        f.s,
      ),
      sourceEarth: sourceOf(m.sources, f.name, 'earth'),
      sourceTarget: sourceOf(m.sources, f.name, targetBody),
    };
  });
  const le = Array.from(bundle.lith.subarray(row * 6, row * 6 + 6));
  const C = Float64Array.from(m.compat_matrix.flat());
  rows.push({
    name: 'lith',
    group: 'composition',
    unit: 'class fractions',
    target: NaN,
    earth: NaN,
    gap: NaN,
    similarity: lithSimilarity(
      le,
      target.lith.some((v) => !Number.isFinite(v)) ? null : target.lith,
      C,
    ),
    sourceEarth: sourceOf(m.sources, 'lith', 'earth'),
    sourceTarget: sourceOf(m.sources, 'lith', targetBody),
    targetLith: target.lith,
    earthLith: le,
  });
  return rows;
}

/** The n measurements (not lithology) that match best; unmeasured ones are skipped. */
export function mostAlike(rows: FeatureRow[], n = 3): FeatureRow[] {
  return rows
    .filter((r) => r.name !== 'lith' && Number.isFinite(r.similarity))
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, n);
}

/** Display a physical value with unit-appropriate precision; NaN → null (caller says "not measured"). */
export function formatValue(v: number, unit: string): string | null {
  if (!Number.isFinite(v)) return null;
  switch (unit) {
    case 'deg':
      return `${v.toFixed(1)}°`;
    case 'm':
      return `${v.toFixed(0)} m`;
    case 'K':
      return `${v.toFixed(1)} K`;
    case 'fraction':
      return v.toFixed(2);
    case 'ratio':
      return v.toFixed(3);
    default:
      return `${v.toPrecision(3)} ${unit}`;
  }
}
