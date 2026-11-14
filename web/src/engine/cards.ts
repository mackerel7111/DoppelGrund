// C5 match cards: best overall plus best per group, separated by ≥ card_min_separation_km.
import { GROUP_IDS, type Card } from '../data/types';
import { haversineKm } from './geo';
import { percentileLinear } from './percentile';

export interface CardParams {
  coverage_floor: number;
  card_overall_percentile: number;
  card_min_separation_km: number;
}

/** C4.7: S finite and coverage ≥ floor. */
export function eligibleMask(S: Float32Array, cov: Float32Array, floor: number): Uint8Array {
  const m = new Uint8Array(S.length);
  for (let i = 0; i < S.length; i++) m[i] = Number.isFinite(S[i]) && cov[i] >= floor ? 1 : 0;
  return m;
}

export function selectCards(
  S: Float32Array,
  cov: Float32Array,
  groups: Float32Array,
  latlng: Float32Array,
  params: CardParams,
): Card[] {
  const n = S.length;
  const eligible = eligibleMask(S, cov, params.coverage_floor);
  const thr = percentileLinear(S, eligible, params.card_overall_percentile);

  let best = -1;
  for (let i = 0; i < n; i++) {
    if (eligible[i] && (best < 0 || S[i] > S[best])) best = i; // ties → lower index
  }
  const chosen: number[] = [];
  const cards: Card[] = [];
  const empty = (kind: Card['kind']): Card => ({
    kind,
    row: null,
    S: NaN,
    S_g: NaN,
    coverage: NaN,
    reason: 'no_eligible_match',
  });
  if (best >= 0) {
    chosen.push(best);
    cards.push({ kind: 'overall', row: best, S: S[best], S_g: S[best], coverage: cov[best] });
  } else {
    cards.push(empty('overall'));
  }

  GROUP_IDS.forEach((g, gi) => {
    let pick = -1;
    if (Number.isFinite(thr)) {
      for (let i = 0; i < n; i++) {
        if (!eligible[i] || !(S[i] >= thr)) continue;
        const sg = groups[i * 4 + gi];
        if (!Number.isFinite(sg)) continue;
        if (pick >= 0) {
          const sp = groups[pick * 4 + gi];
          if (sg < sp || (sg === sp && S[i] <= S[pick])) continue; // ties → higher S, lower row
        }
        let far = true;
        for (const c of chosen) {
          const d = haversineKm(latlng[i * 2], latlng[i * 2 + 1], latlng[c * 2], latlng[c * 2 + 1]);
          if (d < params.card_min_separation_km) {
            far = false;
            break;
          }
        }
        if (far) pick = i;
      }
    }
    if (pick >= 0) {
      chosen.push(pick);
      cards.push({
        kind: g,
        row: pick,
        S: S[pick],
        S_g: groups[pick * 4 + gi],
        coverage: cov[pick],
      });
    } else {
      cards.push(empty(g));
    }
  });
  return cards;
}

/** Up to `k` eligible rows by descending S (ties → lower row index). */
export function topRows(S: Float32Array, eligible: Uint8Array, k: number): Int32Array {
  const idx: number[] = [];
  for (let i = 0; i < S.length; i++) if (eligible[i]) idx.push(i);
  if (idx.length > k * 4) {
    // threshold pre-filter: keep rows ≥ the k-th largest value
    const vals = Float32Array.from(idx, (i) => S[i]).sort();
    const cut = vals[vals.length - k];
    const kept = idx.filter((i) => S[i] >= cut);
    idx.length = 0;
    idx.push(...kept);
  }
  idx.sort((a, b) => S[b] - S[a] || a - b);
  return Int32Array.from(idx.slice(0, k));
}
