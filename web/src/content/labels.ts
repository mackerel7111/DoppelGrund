// UI microcopy (exact strings agreed with the orchestrator).
// 2026-11-07 panel redesign: plain words first, technical names only in GLOSSARY and About.
// Pending orchestrator sign-off (logged in docs/STATUS.md).
import type { CardKind, ColorBy, GroupId, LensId, Manifest } from '../data/types';

export const SYNTHETIC_BANNER = 'Synthetic data — not real results';
export const PARTIAL_LABEL = 'Partial data';

/** Tooltip for the header pill when a real bundle was built from a sample or in fast mode; null when complete. */
export function partialNotice(resolution: Manifest['resolution']): string | null {
  if (!resolution) return null;
  const parts: string[] = [];
  if (resolution.mode === 'fast') parts.push('Fast mode (coarser inputs)');
  if (resolution.stride > 1) parts.push(`1 in ${resolution.stride} hexagons`);
  return parts.length ? parts.join(', ') : null;
}
export const FOOTPRINT_NOTE =
  'Matches compare the ~47 km-wide area around this point, not the landmark alone.';
export const FOOTPRINT_SHORT = 'Compares a ~47 km-wide area';
export const NOT_MEASURED = 'not measured';
export const PRESET_LABEL = 'preset';

/** One vocabulary for the panel, legend, hint and About. */
export const TERMS = {
  landmark: 'Landmark',
  customPoint: 'Custom point',
  focus: 'Mission focus',
  adjust: 'Adjust',
  results: 'Best matches on Earth',
  picks: 'Best picks',
  top: 'Top 50',
  similarity: 'Similarity',
  coverage: 'Data coverage',
  novel: 'Novel',
  knownSite: 'Known analogue site',
  compare: 'Compare in detail',
  back: 'All matches',
  definitions: 'What do these numbers mean?',
} as const;

/** Plain stability wording; `fraction` null = not among the stored top rows. */
export function stabilityText(available: boolean, fraction: number | null): string {
  if (!available) return 'Not computed';
  return fraction === null
    ? 'Rarely in the top 1%'
    : `Top 1% in ${Math.round(fraction * 100)}% of runs`;
}

export const LENS_NAMES: Record<LensId | 'custom', string> = {
  balanced: 'Balanced',
  landing_mobility: 'Landing & mobility',
  cold_volatiles: 'Cold regions & volatiles',
  geology_minerals: 'Geology & minerals',
  custom: 'Custom',
};

/** Short pill labels; the full name (LENS_NAMES) is shown next to the weights. */
export const LENS_SHORT: Record<LensId, string> = {
  balanced: 'Balanced',
  landing_mobility: 'Landing',
  cold_volatiles: 'Cold regions',
  geology_minerals: 'Geology',
};

export const GROUP_NAMES: Record<GroupId, string> = {
  terrain: 'Terrain',
  thermal: 'Thermal',
  cold_ice: 'Cold & ice',
  composition: 'Composition',
  subsurface: 'Subsurface',
};

/** Lower-case dimension names used inside sentences. */
export const DIMENSION_WORDS: Record<GroupId, string> = {
  terrain: 'terrain',
  thermal: 'thermal',
  cold_ice: 'cold & ice',
  composition: 'composition',
  subsurface: 'subsurface',
};

export const CARD_TITLES: Record<CardKind, string> = {
  overall: 'Best overall',
  terrain: 'Best terrain match',
  thermal: 'Best thermal match',
  cold_ice: 'Best cold & ice match',
  composition: 'Best composition match',
  subsurface: 'Best subsurface match',
};

export function emptyCardText(kind: CardKind): string {
  const dim = kind === 'overall' ? 'overall' : DIMENSION_WORDS[kind];
  return `No ${dim} match with enough data for this landmark`;
}

export const FEATURE_LABELS: Record<string, string> = {
  slope_p50_deg: 'Median slope',
  slope_p90_deg: '90th-percentile slope',
  relief_std_m: 'Relief (elevation std)',
  frac_slope_lt_10deg: 'Share of slope < 10°',
  lst_mean_K: 'Mean surface temperature',
  diurnal_range_K: 'Day–night range',
  annual_range_K: 'Annual range',
  frac_below_0C: 'Share of samples < 0 °C',
  permafrost_prob: 'Permafrost extent (fraction)',
  aridity_index: 'Aridity index (P/PET)',
  pit_cave_density_per_1000km2: 'Catalogued pits/caves per 1000 km²',
};

export const LITH_LABELS: Record<string, string> = {
  mafic_volcanic: 'mafic volcanic',
  felsic_feldspathic: 'felsic / feldspathic',
  carbonate: 'carbonate',
  siliciclastic: 'siliciclastic',
  evaporite: 'evaporite',
  ice: 'ice',
};

/** Plain-language help for jargon, shown via title + visually-hidden text (Term.vue). */
export const GLOSSARY = {
  S: 'Overall similarity (S), 0–100: how closely this Earth place matches the landmark under the chosen mission focus. 100 means identical on every measurement compared.',
  coverage:
    'Share of the weighted measurements that exist for both places. Places below the minimum are not ranked.',
  stability:
    'How often this place stays in the top 1% when the weights and tolerances are randomly varied.',
  novelty:
    'Distance to the nearest documented analogue site. Novel places are far from all of them.',
} as const;

export const COLOR_OPTIONS: { id: ColorBy; label: string }[] = [
  { id: 'S', label: 'Similarity' },
  { id: 'terrain', label: 'Terrain' },
  { id: 'thermal', label: 'Thermal' },
  { id: 'cold_ice', label: 'Cold & ice' },
  { id: 'composition', label: 'Composition' },
  { id: 'subsurface', label: 'Subsurface' },
  { id: 'novelty', label: 'Distance from known sites' },
];
