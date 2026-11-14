// Divergence content (03 design §5). Static strings are standard physical constants; humans proof-read.
// Nothing here is ever scored (science-invariants §8): it is shown next to every match.
import type { Body } from '../data/types';
import type { FeatureRow } from '../stores/selectors';
import { formatValue } from '../stores/selectors';
import { FEATURE_LABELS } from './labels';

export interface DivergenceItem {
  kind: 'not_replicable' | 'body' | 'weak' | 'missing';
  text: string;
}

export const WEAK_SIMILARITY = 0.2; // R8.2: "similarity < 0.2" → weak match
// TODO(verify): latitude cut-off for showing the permanent-shadow note (display only, not scored)
export const POLAR_NOTE_MIN_ABS_LAT = 80;

const GRAVITY: Record<Body, string> = {
  moon: 'Gravity: Earth 9.81 m/s² vs Moon 1.62 m/s² — not replicable on Earth',
  mars: 'Gravity: Earth 9.81 m/s² vs Mars 3.71 m/s² — not replicable on Earth',
};
const ATMOSPHERE: Record<Body, string> = {
  moon: 'Atmosphere: vacuum on the Moon — not replicable on Earth',
  mars: 'Atmosphere: ~0.6 kPa CO₂ on Mars — not replicable on Earth',
};
const RADIATION = 'Radiation environment — not replicable on Earth';
const PERMANENT_SHADOW = 'Permanent-shadow illumination and cold traps — no Earth analogue';
const MOON_THERMAL =
  'Lunar day–night range is hundreds of kelvin; no Earth surface reaches it (gap shown in K)';
const DUST = 'Dust: electrostatic regolith behaviour not captured by Earth proxies';

function label(r: FeatureRow): string {
  return r.name === 'lith' ? 'lithology' : (FEATURE_LABELS[r.name] ?? r.name).toLowerCase();
}

/** Static + body-specific + dynamic divergence items for one target/Earth-row comparison. */
export function divergenceItems(
  body: Body,
  targetLat: number,
  rows: FeatureRow[],
): DivergenceItem[] {
  const items: DivergenceItem[] = [
    { kind: 'not_replicable', text: GRAVITY[body] },
    { kind: 'not_replicable', text: ATMOSPHERE[body] },
    { kind: 'not_replicable', text: RADIATION },
  ];
  if (body === 'moon' && Math.abs(targetLat) >= POLAR_NOTE_MIN_ABS_LAT) {
    items.push({ kind: 'body', text: PERMANENT_SHADOW });
  }
  if (body === 'moon') {
    const d = rows.find((r) => r.name === 'diurnal_range_K');
    const gap = d && Number.isFinite(d.gap) ? ` — here Δ ${formatValue(d.gap, 'K')}` : '';
    items.push({ kind: 'body', text: MOON_THERMAL + gap });
  }
  items.push({ kind: 'body', text: DUST });
  for (const r of rows) {
    if (!(r.similarity < WEAK_SIMILARITY)) continue; // NaN is "missing", not weak
    const gap =
      r.name === 'lith'
        ? `similarity ${r.similarity.toFixed(2)}`
        : `gap Δ ${formatValue(r.gap, r.unit) ?? 'not measured'}`;
    items.push({ kind: 'weak', text: `Weak match: ${label(r)} ${gap}` });
  }
  const missing = rows.filter((r) => !Number.isFinite(r.similarity)).map(label);
  if (missing.length) {
    items.push({
      kind: 'missing',
      text: `Not compared (not measured on one side): ${missing.join(', ')}`,
    });
  }
  return items;
}
