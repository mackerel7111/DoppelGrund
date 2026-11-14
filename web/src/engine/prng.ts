// Seeded randomness for stability draws (science-invariants §11: every stochastic step is seeded).

/** mulberry32: small, fast 32-bit PRNG returning floats in [0, 1). */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Standard normal via Box–Muller (one value per call; the pair's second value is discarded). */
export function normal(rnd: () => number): number {
  let u = 0;
  while (u === 0) u = rnd();
  const v = rnd();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

/** Gamma(shape, 1) by Marsaglia–Tsang; shape < 1 uses the u^(1/shape) boost. */
export function sampleGamma(shape: number, rnd: () => number): number {
  if (!(shape > 0)) return 0;
  if (shape < 1) {
    let u = 0;
    while (u === 0) u = rnd();
    return sampleGamma(shape + 1, rnd) * Math.pow(u, 1 / shape);
  }
  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);
  for (;;) {
    const x = normal(rnd);
    const v0 = 1 + c * x;
    if (v0 <= 0) continue;
    const v = v0 * v0 * v0;
    const u = rnd();
    if (u < 1 - 0.0331 * x * x * x * x) return d * v;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
  }
}

/** Dirichlet(alpha) sample; components with alpha = 0 stay exactly 0. */
export function sampleDirichlet(alpha: Float64Array, rnd: () => number): Float64Array {
  const out = new Float64Array(alpha.length);
  let sum = 0;
  for (let i = 0; i < alpha.length; i++) {
    out[i] = alpha[i] > 0 ? sampleGamma(alpha[i], rnd) : 0;
    sum += out[i];
  }
  if (sum > 0) {
    for (let i = 0; i < out.length; i++) out[i] /= sum;
    return out;
  }
  // every gamma draw underflowed (only possible for tiny alphas): fall back to the mean
  let aSum = 0;
  for (let i = 0; i < alpha.length; i++) aSum += Math.max(0, alpha[i]);
  for (let i = 0; i < alpha.length; i++) out[i] = aSum > 0 ? Math.max(0, alpha[i]) / aSum : 0;
  return out;
}
