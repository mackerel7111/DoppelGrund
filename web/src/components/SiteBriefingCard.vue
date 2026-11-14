<script setup lang="ts">
import { computed } from 'vue';
import { useSession } from '../stores/session';
import {
  CARD_TITLES,
  GLOSSARY,
  GROUP_NAMES,
  NOT_MEASURED,
  stabilityText,
  TERMS,
} from '../content/labels';
import { divergenceItems } from '../content/divergence';
import {
  featureComparison,
  formatLatLon,
  formatValue,
  rowInfo,
  type FeatureRow,
} from '../stores/selectors';
import { FLAG_MASKED, GROUP_IDS } from '../data/types';

const props = defineProps<{ row: number }>();
const emit = defineEmits<{
  viewDetails: [];
  close: [];
}>();

const s = useSession();

const info = computed(() =>
  s.bundle ? rowInfo(s.bundle, s.stability, s.result !== null, props.row) : null,
);

const matchedCard = computed(() => {
  const cards = s.result?.cards ?? [];
  const idx = cards.findIndex((c) => c.row === props.row);
  if (idx === -1) return null;
  return { rank: idx + 1, card: cards[idx] };
});

const bestOverallCard = computed(() => s.result?.cards.find((c) => c.row !== null) ?? null);

const isMasked = computed(() => {
  if (!s.bundle) return false;
  return (s.bundle.flags[props.row] & FLAG_MASKED) === 1;
});

const isEligible = computed(() => (s.result?.eligible[props.row] ?? 0) === 1);

const exactRank = computed(() => {
  const res = s.result;
  if (!res || !isEligible.value || !Number.isFinite(res.S[props.row])) return null;
  const score = res.S[props.row];
  let better = 0;
  let total = 0;
  for (let i = 0; i < res.S.length; i++) {
    if (!res.eligible[i] || !Number.isFinite(res.S[i])) continue;
    total += 1;
    if (res.S[i] > score || (res.S[i] === score && i < props.row)) better += 1;
  }
  return { rank: better + 1, total };
});

const coverageFloorPct = computed(() =>
  s.bundle ? Math.round(s.bundle.manifest.params.coverage_floor * 100) : 0,
);

const headline = computed(() => {
  if (matchedCard.value) {
    return `${matchedCard.value.rank} \u00b7 ${CARD_TITLES[matchedCard.value.card.kind]}`;
  }
  if (exactRank.value !== null) {
    return `Rank #${exactRank.value.rank.toLocaleString()} Earth match`;
  }
  return 'Selected Earth cell';
});

const overall = computed(() => {
  const v = s.result?.S[props.row];
  return v !== undefined && Number.isFinite(v) ? v.toFixed(1) : null;
});

const coveragePct = computed(() => {
  const v = s.result?.coverage[props.row];
  return v !== undefined && Number.isFinite(v) ? `${Math.round(v * 100)}% coverage` : NOT_MEASURED;
});

const noveltyLine = computed(() => {
  const km = info.value?.noveltyKm ?? NaN;
  return Number.isFinite(km) ? `${Math.round(km).toLocaleString()} km from known sites` : null;
});

const coords = computed(() => (info.value ? formatLatLon(info.value.lat, info.value.lng) : ''));

const traitPredictions = computed(() => {
  const groups = s.result?.groups;
  if (!groups) return [];
  return GROUP_IDS.map((g, idx) => {
    const val = groups[props.row * GROUP_IDS.length + idx];
    return {
      id: g,
      label: GROUP_NAMES[g],
      score: Number.isFinite(val) ? val.toFixed(0) : null,
      weight: Math.round(s.effective[g] * 100),
    };
  }).filter((t) => t.score !== null || t.weight > 0);
});

const featRows = computed<FeatureRow[]>(() => {
  const rt = s.rankTarget();
  if (!s.bundle || !rt) return [];
  return featureComparison(s.bundle, rt, s.body, props.row);
});

const quickChips = computed(() => {
  const findVal = (name: string, label: string) => {
    const r = featRows.value.find((x) => x.name === name);
    const val = r ? formatValue(r.earth, r.unit) : null;
    return { label, value: val ?? NOT_MEASURED };
  };
  return [
    findVal('slope_p50_deg', 'Slope'),
    findVal('lst_mean_K', 'Temp'),
    findVal('aridity_index', 'Aridity'),
  ];
});

const unmatchableSummary = computed(() =>
  s.body === 'moon'
    ? 'Not on Earth: 1.62 m/s\u00b2 gravity, vacuum, radiation'
    : 'Not on Earth: 3.71 m/s\u00b2 gravity, 0.6 kPa CO\u2082, radiation',
);

const weakCount = computed(() => {
  const targetObj = s.bundle?.targets.find(
    (t) => s.target?.kind === 'landmark' && t.id === s.target.id,
  );
  const tLat = targetObj?.lat ?? 0;
  return divergenceItems(s.body, tLat, featRows.value).filter((i) => i.kind === 'weak').length;
});
</script>

<template>
  <aside
    v-if="info"
    class="briefing-card"
    aria-label="Earth site briefing"
    data-test="site-briefing"
  >
    <div class="brief-top">
      <div class="title-block">
        <div class="title-row">
          <h2 class="site-title">{{ headline }}</h2>
          <span v-if="info.knownSite" class="badge known">{{ TERMS.knownSite }}</span>
          <span
            v-else-if="
              Number.isFinite(info.noveltyKm) &&
              s.bundle &&
              info.noveltyKm >= s.bundle.manifest.params.novelty_gate_km
            "
            class="badge novel"
          >
            {{ TERMS.novel }}
          </span>
        </div>
        <p class="meta-line">
          <span class="num">{{ coords }}</span>
          <span>&middot; {{ coveragePct }}</span>
          <span v-if="noveltyLine">&middot; {{ noveltyLine }}</span>
        </p>
      </div>

      <div class="score-pill" :title="GLOSSARY.S">
        <span class="score-num num">{{ overall ?? 'Excluded' }}</span>
        <span v-if="overall !== null" class="score-den">/ 100</span>
      </div>
    </div>

    <div v-if="!isEligible || isMasked" class="excluded-box">
      <p class="excluded-text">
        <template v-if="isMasked">
          This Earth cell is masked (vegetated, urban, ice, or water), so the model does not rank it
          as an ideal location.
        </template>
        <template v-else>
          Coverage is below the {{ coverageFloorPct }}% minimum floor, so this cell is excluded from
          ranked predictions.
        </template>
      </p>
      <button
        v-if="bestOverallCard && bestOverallCard.row !== null && bestOverallCard.row !== props.row"
        type="button"
        class="jump-best-btn"
        data-test="jump-best-overall"
        @click="s.selectRow(bestOverallCard.row)"
      >
        Jump to #1 Best overall ({{ bestOverallCard.S.toFixed(1) }}) &rarr;
      </button>
    </div>

    <div v-else class="pred-block">
      <div class="pred-head">Model trait predictions</div>
      <div class="pred-grid">
        <div v-for="tp in traitPredictions" :key="tp.id" class="pred-chip">
          <span class="pred-k">{{ tp.label }}</span>
          <span class="pred-v num">{{ tp.score ?? '--' }}</span>
        </div>
      </div>
      <p v-if="info.stability !== null" class="stab-note">
        {{ stabilityText(info.stabilityAvailable, info.stability) }}
      </p>
    </div>

    <div class="chips-row">
      <span v-for="chip in quickChips" :key="chip.label" class="metric-chip">
        <span class="chip-k">{{ chip.label }}:</span>
        <span class="chip-v num">{{ chip.value }}</span>
      </span>
    </div>

    <div class="warn-strip">
      <span class="warn-main">{{ unmatchableSummary }}</span>
      <span v-if="weakCount > 0" class="warn-weak">
        &middot; {{ weakCount }} weak feature {{ weakCount === 1 ? 'match' : 'matches' }}
      </span>
    </div>

    <div class="brief-actions">
      <button
        type="button"
        class="dismiss-btn"
        aria-label="Close site briefing"
        @click="emit('close')"
      >
        Dismiss
      </button>
      <button
        type="button"
        class="details-btn"
        data-test="open-details"
        @click="emit('viewDetails')"
      >
        View details &rarr;
      </button>
    </div>
  </aside>
</template>

<style scoped>
.briefing-card {
  position: fixed;
  right: var(--s4);
  top: 50%;
  transform: translateY(-50%);
  z-index: 16;
  pointer-events: auto;
  width: min(364px, calc(100vw - 32px));
  max-height: calc(100vh - 196px);
  overflow-y: auto;
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  background: rgba(11, 14, 19, 0.88);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(102, 217, 239, 0.28);
  border-radius: 14px;
  box-shadow: 0 18px 42px rgba(0, 0, 0, 0.65);
}

.brief-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.title-block {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.site-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.badge {
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
}

.badge.novel {
  color: var(--accent-earth);
  background: rgba(102, 217, 239, 0.14);
  border: 1px solid rgba(102, 217, 239, 0.35);
}

.badge.known {
  color: var(--text);
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.meta-line {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
  line-height: 1.4;
}

.score-pill {
  flex-shrink: 0;
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(242, 169, 59, 0.1);
  border: 1px solid rgba(242, 169, 59, 0.35);
}

.score-num {
  font-size: 14px;
  font-weight: 700;
  color: var(--accent-warn);
}

.score-den {
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
}

.excluded-box {
  padding: 9px 11px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.14);
  display: grid;
  gap: 8px;
}

.excluded-text {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-muted, #94a3b8);
}

.jump-best-btn {
  justify-self: start;
  padding: 5px 11px;
  border-radius: 999px;
  background: rgba(102, 217, 239, 0.16);
  border: 1px solid var(--accent-earth);
  color: var(--accent-earth);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.jump-best-btn:hover {
  background: rgba(102, 217, 239, 0.26);
}

.pred-block {
  display: grid;
  gap: 6px;
}

.pred-head {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #94a3b8);
}

.pred-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.pred-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 8px;
  background: rgba(102, 217, 239, 0.08);
  border: 1px solid rgba(102, 217, 239, 0.22);
  font-size: 11.5px;
}

.pred-k {
  color: var(--text-muted, #94a3b8);
}

.pred-v {
  color: var(--accent-earth);
  font-weight: 600;
}

.stab-note {
  margin: 0;
  font-size: 11.5px;
  color: var(--text-muted, #94a3b8);
}

.chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.metric-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.11);
  font-size: 12px;
}

.chip-k {
  color: var(--text-muted, #94a3b8);
}

.chip-v {
  color: var(--text);
  font-weight: 500;
}

.warn-strip {
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(242, 169, 59, 0.1);
  border: 1px solid rgba(242, 169, 59, 0.38);
  font-size: 12px;
  line-height: 1.4;
  color: #ffd38a;
}

.warn-weak {
  color: var(--text-muted, #94a3b8);
}

.brief-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s2);
  padding-top: 2px;
}

.dismiss-btn {
  padding: 5px 10px;
  border-radius: 999px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: var(--text-muted, #94a3b8);
  font-size: 12px;
  cursor: pointer;
}

.dismiss-btn:hover {
  color: var(--text);
  border-color: rgba(255, 255, 255, 0.3);
}

.details-btn {
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(102, 217, 239, 0.18);
  border: 1px solid var(--accent-earth);
  color: var(--accent-earth);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.details-btn:hover {
  background: rgba(102, 217, 239, 0.28);
  box-shadow: 0 0 16px rgba(102, 217, 239, 0.28);
}

@media (max-width: 960px) {
  .briefing-card {
    right: var(--s3);
    left: var(--s3);
    width: auto;
    top: auto;
    bottom: 132px;
    transform: none;
  }
}
</style>
