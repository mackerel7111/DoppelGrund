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
import { FLAG_MASKED, GROUP_IDS, HIDDEN_GROUPS } from '../data/types';
import { heatCss } from '../map/palette';

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
      bar: Number.isFinite(val) ? { '--v': val / 100, '--c': heatCss(val) } : undefined,
      weight: Math.round(s.effective[g] * 100),
    };
  }).filter((t) => !HIDDEN_GROUPS.includes(t.id) && (t.score !== null || t.weight > 0));
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
    class="briefing-card hud"
    aria-label="Earth site briefing"
    data-test="site-briefing"
  >
    <header class="brief-top">
      <div class="title-block">
        <div class="title-row">
          <h2 class="site-title">{{ headline }}</h2>
          <span v-if="info.knownSite" class="tag">{{ TERMS.knownSite }}</span>
          <span
            v-else-if="
              Number.isFinite(info.noveltyKm) &&
              s.bundle &&
              info.noveltyKm >= s.bundle.manifest.params.novelty_gate_km
            "
            class="tag earth"
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

      <div v-if="overall !== null" class="score" :title="GLOSSARY.S">
        <span class="score-num num">{{ overall }}</span>
        <span class="score-den">/ 100</span>
      </div>
      <span v-else class="tag" :title="GLOSSARY.S">Excluded</span>
    </header>

    <div class="brief-body">
      <div v-if="!isEligible || isMasked" class="excluded-box">
        <p class="excluded-text">
          <template v-if="isMasked">
            This Earth cell is masked (vegetated, urban, ice, or water), so the model does not rank
            it as an ideal location.
          </template>
          <template v-else>
            Coverage is below the {{ coverageFloorPct }}% minimum floor, so this cell is excluded
            from ranked predictions.
          </template>
        </p>
        <button
          v-if="
            bestOverallCard && bestOverallCard.row !== null && bestOverallCard.row !== props.row
          "
          type="button"
          class="tab jump-best-btn"
          data-test="jump-best-overall"
          @click="s.selectRow(bestOverallCard.row)"
        >
          Jump to #1 Best overall ({{ bestOverallCard.S.toFixed(1) }}) &rarr;
        </button>
      </div>

      <section v-else class="pred-block" aria-label="Model trait predictions">
        <h3 class="pred-head">Model trait predictions</h3>
        <ul class="traits">
          <li v-for="tp in traitPredictions" :key="tp.id">
            <span class="trait-k">{{ tp.label }}</span>
            <span class="score-bar" :class="{ none: !tp.bar }" :style="tp.bar" />
            <span class="trait-v num">{{ tp.score ?? '--' }}</span>
          </li>
        </ul>
        <p v-if="info.stability !== null" class="stab-note">
          {{ stabilityText(info.stabilityAvailable, info.stability) }}
        </p>
      </section>

      <div class="stats-row">
        <span v-for="chip in quickChips" :key="chip.label" class="stat">
          {{ chip.label }} <b>{{ chip.value }}</b>
        </span>
      </div>

      <p class="warn-strip" role="note">
        <span class="warn-main">{{ unmatchableSummary }}</span>
        <span v-if="weakCount > 0" class="warn-weak">
          &middot; {{ weakCount }} weak feature {{ weakCount === 1 ? 'match' : 'matches' }}
        </span>
      </p>
    </div>

    <footer class="brief-actions">
      <button
        type="button"
        class="tab"
        aria-label="Close site briefing"
        data-test="dismiss-briefing"
        @click="emit('close')"
      >
        Dismiss
      </button>
      <button
        type="button"
        class="tab details-btn"
        data-test="open-details"
        @click="emit('viewDetails')"
      >
        View details &rarr;
      </button>
    </footer>
  </aside>
</template>

<style scoped>
/*
 * facePoint yaws the selected Earth site toward the camera, then pitches it about the world x-axis:
 * its sideways offset grows with latitude (up to ~130px at the pole at 1920), but it rests within
 * ~25px of the canvas's vertical centre line (measured at 89°S). Ending the card at 50vh - 48px keeps
 * it off the site at every width and latitude; the Moon target is at 26.5% of the width.
 * ponytail: holds at rest only; the idle spin (15 s after the last input) and drags move the site.
 * Upgrade: project the site with GlobeScene.worldPoint each frame and flip the card to the left.
 */
.briefing-card {
  position: fixed;
  top: 72px; /* header bottom (64) + 8 */
  right: var(--s4);
  z-index: 16;
  pointer-events: auto;
  width: min(364px, calc(100vw - 32px));
  max-height: calc(50vh - 120px); /* top 72, bottom 50vh - 48: above the site's row */
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.brief-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--s3);
  padding: var(--s4) var(--s4) var(--s2);
}

.title-block {
  display: grid;
  gap: var(--s1);
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--s2);
}

.site-title {
  margin: 0;
  font-size: var(--fs-card);
  font-weight: 500;
  color: var(--text);
}

.meta-line {
  display: flex;
  flex-wrap: wrap;
  column-gap: var(--s1); /* Vue drops the spaces between these spans */
  margin: 0;
  font-size: var(--fs-meta);
  color: var(--text-muted);
}

.score {
  flex-shrink: 0;
  display: inline-flex;
  align-items: baseline;
  gap: var(--s1);
}

.score-num {
  font-size: var(--fs-section);
  font-weight: 500;
  color: var(--text);
}

.score-den {
  font-size: var(--fs-meta);
  color: var(--text-muted);
}

.brief-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  align-content: start;
  gap: var(--s3);
  padding: 0 var(--s4) var(--s2);
}

.excluded-box {
  display: grid;
  gap: var(--s2);
  padding: var(--s3);
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface);
}

.excluded-text {
  margin: 0;
  font-size: var(--fs-meta);
  color: var(--text-muted);
}

.jump-best-btn {
  justify-self: start;
  border-color: var(--border);
  color: var(--accent-earth);
}

.pred-block {
  display: grid;
  gap: var(--s2);
}

.pred-head {
  font-size: var(--fs-meta);
  font-weight: 500;
  color: var(--text-muted);
}

.traits {
  display: grid;
  gap: var(--s1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.traits li {
  display: grid;
  grid-template-columns: 112px 1fr 28px;
  align-items: center;
  gap: var(--s3);
  font-size: var(--fs-meta);
}

.trait-k {
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trait-v {
  text-align: right;
  color: var(--text);
}

.stab-note {
  margin: 0;
  font-size: var(--fs-meta);
  color: var(--text-muted);
}

.stats-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s1) var(--s4);
  padding-top: var(--s3);
  border-top: 1px solid var(--border);
}

/* the one amber block on the card: what Earth can never reproduce */
.warn-strip {
  margin: 0;
  padding: var(--s2) var(--s3);
  border-left: 3px solid var(--warn);
  border-radius: 0 var(--radius-control) var(--radius-control) 0;
  background: color-mix(in srgb, var(--warn) 10%, transparent);
  font-size: var(--fs-meta);
  color: var(--warn);
}

.warn-weak {
  color: var(--text-muted);
}

.brief-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s2);
  padding: var(--s3) var(--s4);
  border-top: 1px solid var(--border);
}

.details-btn {
  border-color: var(--accent-earth);
  background: var(--surface-2);
  color: var(--accent-earth);
}

.details-btn:hover:not(:disabled) {
  border-color: var(--accent-earth);
  background: color-mix(in srgb, var(--accent-earth) 14%, var(--surface-2));
  color: var(--text);
}

/* narrow: a bottom sheet sitting on the dock, capped so it ends below the globes (centre 50vh, radius 17.5vw) */
@media (max-width: 1199px) {
  .briefing-card {
    top: auto;
    left: 0;
    right: 0;
    bottom: 49px; /* dock: 32 tab + 2 x 8 padding + 1 hairline */
    width: auto;
    max-height: max(160px, calc(50vh - 17.5vw - 57px));
    border-bottom: none;
    border-radius: var(--radius-panel) var(--radius-panel) 0 0;
  }
  .brief-top {
    padding-top: var(--s3);
  }
}
</style>
