// numpy.percentile(method="linear") on a float32 array, including numpy's float32 lerp
// (diff·t for t < 0.5, b − diff·(1 − t) otherwise), so card thresholds match Python exactly.

const f32 = Math.fround;

/** Percentile `p` (0–100) of the finite `values[i]` where `mask[i]` is non-zero; NaN if none. */
export function percentileLinear(values: Float32Array, mask: Uint8Array, p: number): number {
  let n = 0;
  for (let i = 0; i < values.length; i++) if (mask[i] && Number.isFinite(values[i])) n++;
  if (n === 0) return NaN;
  const v = new Float32Array(n);
  let k = 0;
  for (let i = 0; i < values.length; i++)
    if (mask[i] && Number.isFinite(values[i])) v[k++] = values[i];
  v.sort();
  const r = (n - 1) * (p / 100);
  const lo = Math.floor(r);
  const hi = Math.min(Math.ceil(r), n - 1);
  const t = r - lo;
  if (lo === hi || t === 0) return v[lo];
  const a = v[lo];
  const b = v[hi];
  const diff = f32(b - a);
  return t >= 0.5 ? f32(b - f32(diff * f32(1 - t))) : f32(a + f32(diff * f32(t)));
}
