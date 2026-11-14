// Colour scale: yellow → orange → red (ColorBrewer YlOrRd, higher = redder), 256-entry LUT; grey for masked / ineligible / NaN.
import { GROUP_IDS, type ColorBy, type Palette } from '../data/types';

export const HEAT_STOPS = [
  '#FFF3B0',
  '#FED976',
  '#FEB24C',
  '#FD8D3C',
  '#FC4E2A',
  '#E31A1C',
] as const;

/** #9A9A9A at 60% opacity. */
export const MASKED_RGBA: [number, number, number, number] = [154, 154, 154, 153];

export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

/** Linear RGB interpolation between equally spaced stops → n×4 RGBA (alpha 255). */
export function buildLut(stops: readonly string[] = HEAT_STOPS, n = 256): Uint8ClampedArray {
  const rgb = stops.map(hexToRgb);
  const lut = new Uint8ClampedArray(n * 4);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * (rgb.length - 1);
    const lo = Math.min(Math.floor(x), rgb.length - 2);
    const t = x - lo;
    for (let c = 0; c < 3; c++)
      lut[i * 4 + c] = Math.round(rgb[lo][c] + (rgb[lo + 1][c] - rgb[lo][c]) * t);
    lut[i * 4 + 3] = 255;
  }
  return lut;
}

export const HEAT_LUT = buildLut();

export interface MetricMeta {
  label: string;
  unit: string;
  domain: [number, number];
}

const GROUP_LABEL: Record<string, string> = {
  terrain: 'Terrain similarity',
  thermal: 'Thermal similarity',
  cold_ice: 'Cold & ice similarity',
  composition: 'Composition similarity',
};

/** Legend metadata; every legend states metric and unit. */
export function metricMeta(colorBy: ColorBy, noveltyMaxKm = 3000): MetricMeta {
  if (colorBy === 'S') return { label: 'Similarity', unit: '0–100', domain: [0, 100] };
  if (colorBy === 'novelty') {
    return { label: 'Distance to nearest known site', unit: 'km', domain: [0, noveltyMaxKm] };
  }
  return { label: GROUP_LABEL[colorBy], unit: '0–100', domain: [0, 100] };
}

export function makePalette(domain: [number, number]): Palette {
  return { lut: HEAT_LUT, domain, masked: MASKED_RGBA };
}

/** LUT index for value v over domain (clamped); −1 for NaN. */
export function lutIndex(v: number, domain: [number, number]): number {
  if (!Number.isFinite(v)) return -1;
  const span = domain[1] - domain[0];
  const t = span > 0 ? (v - domain[0]) / span : 0;
  return Math.max(0, Math.min(255, Math.round(t * 255)));
}

export interface ColorSource {
  values: Float32Array; // read at values[i * stride + offset]
  stride: number;
  offset: number;
  eligible: Uint8Array | null; // null = every row eligible
}

/** Per-row RGBA buffer (N×4) for the hex layer; grey when ineligible or NaN. */
export function colorize(n: number, src: ColorSource | null, palette: Palette): Uint8ClampedArray {
  const out = new Uint8ClampedArray(n * 4);
  const [mr, mg, mb, ma] = palette.masked;
  for (let i = 0; i < n; i++) {
    const k =
      src && (!src.eligible || src.eligible[i])
        ? lutIndex(src.values[i * src.stride + src.offset], palette.domain)
        : -1;
    const o = i * 4;
    if (k < 0) {
      out[o] = mr;
      out[o + 1] = mg;
      out[o + 2] = mb;
      out[o + 3] = ma;
    } else {
      out[o] = palette.lut[k * 4];
      out[o + 1] = palette.lut[k * 4 + 1];
      out[o + 2] = palette.lut[k * 4 + 2];
      out[o + 3] = palette.lut[k * 4 + 3];
    }
  }
  return out;
}

/** Where the active metric lives: S, a group column of `groups`, or column 0 of novelty. */
export function sourceFor(
  colorBy: ColorBy,
  result: { S: Float32Array; groups: Float32Array; eligible: Uint8Array } | null,
  novelty: Float32Array,
  notMasked: Uint8Array,
): ColorSource | null {
  if (colorBy === 'novelty') return { values: novelty, stride: 2, offset: 0, eligible: notMasked };
  if (!result) return null;
  if (colorBy === 'S') return { values: result.S, stride: 1, offset: 0, eligible: result.eligible };
  return {
    values: result.groups,
    stride: 4,
    offset: GROUP_IDS.indexOf(colorBy),
    eligible: result.eligible,
  };
}

/** 1 where flags bit0 (masked) is clear. */
export function notMaskedMask(flags: Uint8Array): Uint8Array {
  const m = new Uint8Array(flags.length);
  for (let i = 0; i < flags.length; i++) m[i] = flags[i] & 1 ? 0 : 1;
  return m;
}

/** Largest finite value of column `offset` in a strided array (0 if none). */
export function finiteMax(values: Float32Array, stride: number, offset: number): number {
  let mx = 0;
  for (let i = offset; i < values.length; i += stride) if (values[i] > mx) mx = values[i];
  return mx;
}

/** CSS colour of value v on the heat scale, so a panel bar matches that place on the globe. */
export function heatCss(v: number, domain: [number, number] = [0, 100]): string {
  const k = lutIndex(v, domain) * 4;
  return k < 0 ? 'transparent' : `rgb(${HEAT_LUT[k]} ${HEAT_LUT[k + 1]} ${HEAT_LUT[k + 2]})`;
}

/** CSS linear-gradient for the legend bar. */
export function legendGradient(stops: readonly string[] = HEAT_STOPS): string {
  return `linear-gradient(90deg, ${stops.join(', ')})`;
}
