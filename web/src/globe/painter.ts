// Paint the equirectangular Earth texture from the C6 index map (runs in the worker).
// Pixel value = row + 1 encoded R·65536 + G·256 + B; 0 = no hexagon.
import type { Palette } from '../data/types';

// Heat alpha ramp: alpha = A_LOW + (1 − A_LOW)·smoothstep(T0, T1, t)^GAMMA, t = normalised score.
// T1 = the result's best score, so the best place always reaches full alpha.
// T0 is data-relative: the TOP_FRACTION quantile of eligible scores, clamped to [T0_MIN, T0_MAX],
// so the best ~40 % of a result always glows and the rest stays faint (never an "empty" globe).
export const A_LOW = 0.35; // scores below T0 stay visible but quiet, so switching the colour metric always changes the globe
export const GAMMA = 0.8; // <1 makes the glowing band strong quickly
export const TOP_FRACTION = 0.4;
export const T0_MIN = 0.2;
export const T0_MAX = 0.75;

function smoothstep(e0: number, e1: number, x: number): number {
  const u = Math.max(0, Math.min(1, (x - e0) / (e1 - e0)));
  return u * u * (3 - 2 * u);
}

/** Ramp bounds [T0, T1] (normalised scores) from the score histogram of eligible rows. */
export function glowRange(
  values: Float32Array,
  eligible: Uint8Array,
  lo: number,
  span: number,
): [number, number] {
  const hist = new Uint32Array(256);
  let n = 0;
  let top = 0;
  let tMax = 0;
  for (let i = 0; i < values.length; i++) {
    if (!eligible[i] || !Number.isFinite(values[i])) continue;
    const t = Math.max(0, Math.min(1, span > 0 ? (values[i] - lo) / span : 0));
    const bin = Math.round(t * 255);
    hist[bin]++;
    if (bin > top) top = bin;
    if (t > tMax) tMax = t;
    n++;
  }
  if (n === 0) return [T0_MAX, 1];
  let above = 0;
  let bin = top;
  while (bin > 0 && above + hist[bin] < n * TOP_FRACTION) above += hist[bin--];
  const t0 = Math.max(T0_MIN, Math.min(T0_MAX, bin / 255));
  return [t0, Math.max(tMax, t0 + 0.01)];
}

/** Row index encoded in one RGB(A) pixel, or −1 for "no hexagon". */
export function decodePixel(r: number, g: number, b: number): number {
  return r * 65536 + g * 256 + b - 1;
}

/** Decode a whole RGBA index image to an Int32 row map (−1 = no hexagon). */
export function decodeIndex(indexRGBA: Uint8ClampedArray): Int32Array {
  const n = indexRGBA.length / 4;
  const out = new Int32Array(n);
  for (let p = 0; p < n; p++) {
    const o = p * 4;
    out[p] = decodePixel(indexRGBA[o], indexRGBA[o + 1], indexRGBA[o + 2]);
  }
  return out;
}

/**
 * Row map of the index image shrunk k× per axis, point-sampled at each k×k block's centre pixel
 * (x·k + k/2, y·k + k/2). The display blurs the heat far below this anyway.
 */
export function sampleIndex(
  rgba: Uint8ClampedArray,
  width: number,
  height: number,
  k = 4,
): Int32Array {
  const w = Math.floor(width / k);
  const h = Math.floor(height / k);
  const out = new Int32Array(w * h);
  const c = k >> 1;
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const o = ((y * k + c) * width + x * k + c) * 4;
      out[y * w + x] = decodePixel(rgba[o], rgba[o + 1], rgba[o + 2]);
    }
  return out;
}

/** Per-row RGBA (straight alpha); masked / ineligible / NaN rows stay fully transparent. */
function rowColors(
  values: Float32Array,
  palette: Palette,
  eligible: Uint8Array,
): Uint8ClampedArray {
  const [lo, hi] = palette.domain;
  const span = hi - lo;
  const [t0, t1] = glowRange(values, eligible, lo, span);
  const out = new Uint8ClampedArray(values.length * 4);
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (!eligible[i] || !Number.isFinite(v)) continue;
    const t = Math.max(0, Math.min(1, span > 0 ? (v - lo) / span : 0));
    const k = Math.round(t * 255) * 4;
    const o = i * 4;
    out[o] = palette.lut[k];
    out[o + 1] = palette.lut[k + 1];
    out[o + 2] = palette.lut[k + 2];
    out[o + 3] = Math.round(255 * (A_LOW + (1 - A_LOW) * Math.pow(smoothstep(t0, t1, t), GAMMA)));
  }
  return out;
}

/**
 * Display-only gap fill for sampled bundles (stride > 1): every transparent pixel within `radius`
 * pixels of a painted one takes the nearest painted pixel's colour. Without it the blur on the
 * globe averages the few painted pixels with empty ones and the heat all but disappears.
 */
export function fillGaps(
  rgba: Uint8ClampedArray,
  width: number,
  height: number,
  radius: number,
): Uint8ClampedArray {
  if (radius < 1) return rgba;
  const out = new Uint8ClampedArray(rgba);
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) {
      if (rgba[(y * width + x) * 4 + 3] !== 0) continue;
      let best = -1;
      let bestD = radius * radius + 1;
      for (let dy = -radius; dy <= radius; dy++) {
        const yy = y + dy;
        if (yy < 0 || yy >= height) continue;
        for (let dx = -radius; dx <= radius; dx++) {
          const d = dx * dx + dy * dy;
          if (d >= bestD) continue;
          const xx = (x + dx + width) % width; // wraps at the date line
          const o = (yy * width + xx) * 4;
          if (rgba[o + 3] === 0) continue;
          best = o;
          bestD = d;
        }
      }
      if (best < 0) continue;
      const o = (y * width + x) * 4;
      out[o] = rgba[best];
      out[o + 1] = rgba[best + 1];
      out[o + 2] = rgba[best + 2];
      out[o + 3] = rgba[best + 3];
    }
  return out;
}

/**
 * Paint an RGBA overlay the size of the index image. `values[row]` is the metric per Earth row.
 * Pixels without a hexagon and rows that are masked, ineligible or NaN are transparent (alpha 0).
 */
export function paint(
  indexRGB: Uint8ClampedArray | Int32Array,
  values: Float32Array,
  palette: Palette,
  eligible: Uint8Array,
  fill?: { width: number; radius: number },
): Uint8ClampedArray {
  const rows = indexRGB instanceof Int32Array ? indexRGB : decodeIndex(indexRGB);
  const colors = rowColors(values, palette, eligible);
  const n = values.length;
  const out = new Uint8ClampedArray(rows.length * 4);
  for (let p = 0; p < rows.length; p++) {
    const r = rows[p];
    if (r < 0 || r >= n) continue;
    const c = r * 4;
    const o = p * 4;
    out[o] = colors[c];
    out[o + 1] = colors[c + 1];
    out[o + 2] = colors[c + 2];
    out[o + 3] = colors[c + 3];
  }
  return fill ? fillGaps(out, fill.width, rows.length / fill.width, fill.radius) : out;
}
