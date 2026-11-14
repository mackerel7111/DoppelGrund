<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue';
import { useSession } from '../stores/session';
import {
  CARD_TITLES,
  GLOSSARY,
  GROUP_NAMES,
  LENS_NAMES,
  LITH_LABELS,
  NOT_MEASURED,
  stabilityText,
  TERMS,
} from '../content/labels';
import { divergenceItems } from '../content/divergence';
import {
  featureComparison,
  formatLatLon,
  formatValue,
  mostAlike,
  rowInfo,
  type FeatureRow,
} from '../stores/selectors';
import { FLAG_MASKED, GROUP_IDS, LITH_CLASSES, type Card, type GroupId } from '../data/types';
import FeatureTable from './FeatureTable.vue';

const props = defineProps<{ row: number }>();
const emit = defineEmits<{ close: [] }>();

const s = useSession();

const bodyName = computed(() => (s.body === 'moon' ? 'Moon' : 'Mars'));

const targetObj = computed(() => {
  const t = s.target;
  if (!t || t.kind !== 'landmark' || !s.bundle) return null;
  return s.bundle.targets.find((x) => x.id === t.id) ?? null;
});

const targetLat = computed(() => {
  const t = s.target;
  if (!t || !s.bundle) return 0;
  if (t.kind === 'landmark') return targetObj.value?.lat ?? 0;
  return s.bundle.discs[t.body]?.latlon[t.discIndex * 2] ?? 0;
});

const targetLabel = computed(() => {
  const t = s.target;
  if (!t || !s.bundle) return '';
  if (t.kind === 'landmark') return targetObj.value?.name ?? t.id;
  const ll = s.bundle.discs[t.body]?.latlon;
  if (!ll) return TERMS.customPoint;
  return `${TERMS.customPoint} ${formatLatLon(ll[t.discIndex * 2], ll[t.discIndex * 2 + 1])}`;
});

const info = computed(() =>
  s.bundle ? rowInfo(s.bundle, s.stability, s.result !== null, props.row) : null,
);

const coords = computed(() => (info.value ? formatLatLon(info.value.lat, info.value.lng) : ''));

const h3Id = computed(() => s.bundle?.h3[props.row] ?? '');

const isMasked = computed(() => {
  if (!s.bundle) return false;
  return (s.bundle.flags[props.row] & FLAG_MASKED) === 1;
});

const isEligible = computed(() => (s.result?.eligible[props.row] ?? 0) === 1);

const coverageFloorPct = computed(() =>
  s.bundle ? Math.round(s.bundle.manifest.params.coverage_floor * 100) : 0,
);

const clusterId = computed(() => {
  const c = s.bundle?.cluster?.[props.row];
  return c !== undefined && c >= 0 ? c : null;
});

const cardMatch = computed(() => {
  const cards = s.result?.cards ?? [];
  const idx = cards.findIndex((c) => c.row === props.row);
  if (idx === -1) return null;
  return { rank: idx + 1, title: CARD_TITLES[cards[idx].kind] };
});

const idealCards = computed(() =>
  (s.result?.cards ?? []).reduce<(Card & { rank: number; row: number })[]>((acc, c, idx) => {
    if (c.row !== null) acc.push({ ...c, rank: idx + 1, row: c.row });
    return acc;
  }, []),
);

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

const overallScore = computed(() => {
  const v = s.result?.S[props.row];
  return v !== undefined && Number.isFinite(v) ? v.toFixed(1) : 'Excluded';
});

const coveragePct = computed(() => {
  const v = s.result?.coverage[props.row];
  return v !== undefined && Number.isFinite(v) ? `${Math.round(v * 100)}%` : NOT_MEASURED;
});

const noveltyText = computed(() => {
  const km = info.value?.noveltyKm ?? NaN;
  return Number.isFinite(km) ? `${Math.round(km).toLocaleString()} km` : NOT_MEASURED;
});

const featNoveltyText = computed(() => {
  const fn = info.value?.featNovelty ?? NaN;
  return Number.isFinite(fn) ? fn.toFixed(2) : null;
});

const isNovel = computed(() => {
  const gate = s.bundle?.manifest.params.novelty_gate_km ?? Infinity;
  const km = info.value?.noveltyKm ?? NaN;
  return Number.isFinite(km) && km >= gate && !info.value?.knownSite;
});

function groupScore(g: GroupId): string {
  const groups = s.result?.groups;
  if (!groups) return NOT_MEASURED;
  const gi = GROUP_IDS.indexOf(g);
  if (gi < 0) return NOT_MEASURED;
  const val = groups[props.row * GROUP_IDS.length + gi];
  return Number.isFinite(val) ? val.toFixed(1) : isMasked.value ? 'masked' : NOT_MEASURED;
}

function groupWeightPct(g: GroupId): string {
  return `${Math.round(s.effective[g] * 100)}% wt`;
}

const rows = computed<FeatureRow[]>(() => {
  const rt = s.rankTarget();
  if (!s.bundle || !rt) return [];
  return featureComparison(s.bundle, rt, s.body, props.row);
});

const alikeRows = computed(() => mostAlike(rows.value, 3));

function getRow(name: string): FeatureRow | undefined {
  return rows.value.find((r) => r.name === name);
}

function pairValues(name: string, label: string) {
  const r = getRow(name);
  return {
    label,
    target: r ? (formatValue(r.target, r.unit) ?? NOT_MEASURED) : NOT_MEASURED,
    earth: r ? (formatValue(r.earth, r.unit) ?? NOT_MEASURED) : NOT_MEASURED,
    sim: r && Number.isFinite(r.similarity) ? r.similarity.toFixed(2) : null,
  };
}

const terrainPairs = computed(() => [
  pairValues('slope_p50_deg', 'Median slope'),
  pairValues('slope_p90_deg', '90th pct slope'),
  pairValues('relief_std_m', 'Relief std'),
  pairValues('frac_slope_lt_10deg', 'Slope < 10\u00b0'),
]);

const thermalPairs = computed(() => [
  pairValues('lst_mean_K', 'Mean temp'),
  pairValues('diurnal_range_K', 'Day-night range'),
  pairValues('annual_range_K', 'Annual range'),
]);

const coldSubPairs = computed(() => [
  pairValues('aridity_index', 'Aridity (P/PET)'),
  pairValues('frac_below_0C', 'Below 0 \u00b0C'),
  pairValues('permafrost_prob', 'Permafrost'),
  pairValues('pit_cave_density_per_1000km2', 'Pits / caves'),
]);

const earthLithValid = computed(() => {
  const lithRow = getRow('lith');
  const v = lithRow?.earthLith;
  return Boolean(v && v.every((x) => Number.isFinite(x)) && v.reduce((a, b) => a + b, 0) > 0);
});

const targetLithValid = computed(() => {
  const lithRow = getRow('lith');
  const v = lithRow?.targetLith;
  return Boolean(v && v.every((x) => Number.isFinite(x)) && v.reduce((a, b) => a + b, 0) > 0);
});

const lithBars = computed(() => {
  const lithRow = getRow('lith');
  if (!lithRow) return [];
  return LITH_CLASSES.map((cls, i) => ({
    id: cls,
    label: LITH_LABELS[cls],
    earth: earthLithValid.value && lithRow.earthLith ? lithRow.earthLith[i] * 100 : null,
    target: targetLithValid.value && lithRow.targetLith ? lithRow.targetLith[i] * 100 : null,
  }))
    .filter((x) => (x.earth ?? 0) >= 2 || (x.target ?? 0) >= 2)
    .sort((a, b) => Math.max(b.earth ?? 0, b.target ?? 0) - Math.max(a.earth ?? 0, a.target ?? 0));
});

const divSections = computed(() => {
  const items = divergenceItems(s.body, targetLat.value, rows.value);
  return {
    unmatchable: items.filter((i) => i.kind === 'not_replicable'),
    bodyAndWeak: items.filter((i) => i.kind === 'body' || i.kind === 'weak'),
    missing: items.filter((i) => i.kind === 'missing'),
  };
});

const uniqueSources = computed(() => {
  const seen = new Set<string>();
  for (const r of rows.value) {
    if (r.sourceEarth) seen.add(r.sourceEarth);
    if (r.sourceTarget && !r.sourceTarget.includes('TODO')) seen.add(r.sourceTarget);
  }
  return Array.from(seen).slice(0, 6);
});

const drawsCount = computed(() => s.bundle?.manifest.params.stability.draws_interactive ?? 500);

function onKeyDown(ev: KeyboardEvent): void {
  if (ev.key === 'Escape') emit('close');
}

onMounted(() => window.addEventListener('keydown', onKeyDown));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown));
</script>

<template>
  <div
    class="modal-backdrop"
    role="dialog"
    aria-modal="true"
    aria-label="Site detail scorecard"
    data-test="site-details-modal"
  >
    <div class="modal-card">
      <header class="modal-head">
        <div class="head-left">
          <div class="rank-badge">
            <span class="rank-lbl">Rank</span>
            <span class="rank-val num">{{ exactRank ? `#${exactRank.rank}` : 'N/A' }}</span>
          </div>
          <div class="head-meta">
            <div class="head-title-row">
              <h2>
                {{
                  cardMatch
                    ? cardMatch.title
                    : exactRank
                      ? `Rank #${exactRank.rank.toLocaleString()} of ${exactRank.total.toLocaleString()} Earth matches`
                      : 'Excluded Earth cell'
                }}
              </h2>
              <span v-if="isNovel" class="tag-pill novel">{{ TERMS.novel }}</span>
              <span v-else-if="info?.knownSite" class="tag-pill known">{{ TERMS.knownSite }}</span>
              <span v-for="t in info?.tags ?? []" :key="t" class="tag-pill">{{ t }}</span>
            </div>
            <div class="sub-meta">
              <span class="num">{{ coords }}</span>
              <span class="h3-pill num">H3 {{ h3Id }}</span>
              <span>vs {{ bodyName }} &middot; {{ targetLabel }}</span>
              <span>&middot; Lens: {{ LENS_NAMES[s.lens] }}</span>
              <span v-if="clusterId !== null">&middot; Cluster #{{ clusterId }}</span>
            </div>
          </div>
        </div>

        <button type="button" class="close-x" aria-label="Close details" @click="emit('close')">
          &times;
        </button>
      </header>

      <div
        v-if="idealCards.length"
        class="ideal-switcher"
        aria-label="Switch to predicted ideal locations"
      >
        <span class="sw-lbl">Ideal locations:</span>
        <button
          v-for="c in idealCards"
          :key="c.kind"
          type="button"
          class="sw-pill"
          :class="{ active: c.row === props.row }"
          @click="s.selectRow(c.row)"
        >
          <span>{{ c.rank }}. {{ c.kind === 'overall' ? 'Overall' : GROUP_NAMES[c.kind] }}</span>
          <span class="num">{{ (c.kind === 'overall' ? c.S : c.S_g).toFixed(1) }}</span>
        </button>
      </div>

      <div v-if="!isEligible || isMasked" class="excluded-banner">
        <span>
          <template v-if="isMasked">
            Note: This Earth hexagon is masked (vegetated, urban, ice, or water), so similarity
            scores are not assigned by the model. Pick any highlighted ideal location above to
            inspect scored predictions.
          </template>
          <template v-else>
            Note: Coverage ({{ coveragePct }}) is below the {{ coverageFloorPct }}% minimum floor,
            so this cell is excluded from top predictions.
          </template>
        </span>
      </div>

      <section class="kpi-grid" aria-label="Headline predictions">
        <div class="kpi-card primary" :title="GLOSSARY.S">
          <span class="kpi-label">Overall Similarity</span>
          <div class="kpi-value num">
            <span class="big">{{ overallScore }}</span>
            <span v-if="overallScore !== 'Excluded'" class="unit">/ 100</span>
          </div>
        </div>

        <div class="kpi-card" :title="GLOSSARY.coverage">
          <span class="kpi-label">{{ TERMS.coverage }}</span>
          <div class="kpi-value num">
            <span class="big">{{ coveragePct }}</span>
            <span class="unit">floor {{ coverageFloorPct }}%</span>
          </div>
        </div>

        <div class="kpi-card" :title="GLOSSARY.novelty">
          <span class="kpi-label">Novelty Distance</span>
          <div class="kpi-value num">
            <span class="big">{{ noveltyText }}</span>
            <span class="unit">{{
              featNoveltyText ? `feat ${featNoveltyText}` : 'to known site'
            }}</span>
          </div>
        </div>

        <div class="kpi-card" :title="GLOSSARY.stability">
          <span class="kpi-label">Stability</span>
          <div class="kpi-stability">
            <span class="stab-text">{{
              info ? stabilityText(info.stabilityAvailable, info.stability) : NOT_MEASURED
            }}</span>
            <button
              v-if="s.stabilityProgress === null"
              type="button"
              class="stab-btn"
              data-test="run-stability"
              @click="s.runStability(drawsCount)"
            >
              Run stability check ({{ drawsCount }})
            </button>
            <span v-else class="stab-prog num">
              Running {{ s.stabilityProgress.done }} / {{ s.stabilityProgress.total }}...
            </span>
          </div>
        </div>
      </section>

      <div class="columns">
        <section class="col-left" aria-label="Trait comparison">
          <h3 class="sec-head">
            Trait Predictions &amp; Comparison ({{ bodyName }} Target vs Earth)
          </h3>

          <div class="trait-grid">
            <article class="trait-card">
              <header class="trait-head">
                <span>1. {{ GROUP_NAMES.terrain }}</span>
                <span class="trait-badges">
                  <span class="wt-chip num">{{ groupWeightPct('terrain') }}</span>
                  <span class="trait-score num">{{ groupScore('terrain') }}</span>
                </span>
              </header>
              <div class="pair-list">
                <div v-for="p in terrainPairs" :key="p.label" class="pair-row">
                  <span class="pair-k">{{ p.label }}</span>
                  <span class="pair-v num">{{ p.target }} vs {{ p.earth }}</span>
                </div>
              </div>
            </article>

            <article class="trait-card">
              <header class="trait-head">
                <span>2. {{ GROUP_NAMES.thermal }}</span>
                <span class="trait-badges">
                  <span class="wt-chip num">{{ groupWeightPct('thermal') }}</span>
                  <span class="trait-score num">{{ groupScore('thermal') }}</span>
                </span>
              </header>
              <div class="pair-list">
                <div v-for="p in thermalPairs" :key="p.label" class="pair-row">
                  <span class="pair-k">{{ p.label }}</span>
                  <span class="pair-v num">{{ p.target }} vs {{ p.earth }}</span>
                </div>
              </div>
            </article>

            <article class="trait-card">
              <header class="trait-head">
                <span>3. {{ GROUP_NAMES.cold_ice }} &amp; {{ GROUP_NAMES.subsurface }}</span>
                <span class="trait-badges">
                  <span class="trait-score num"
                    >{{ groupScore('cold_ice') }} / {{ groupScore('subsurface') }}</span
                  >
                </span>
              </header>
              <div class="pair-list">
                <div v-for="p in coldSubPairs" :key="p.label" class="pair-row">
                  <span class="pair-k">{{ p.label }}</span>
                  <span class="pair-v num">{{ p.target }} vs {{ p.earth }}</span>
                </div>
              </div>
            </article>

            <article class="trait-card">
              <header class="trait-head">
                <span>4. {{ GROUP_NAMES.composition }}</span>
                <span class="trait-badges">
                  <span class="wt-chip num">{{ groupWeightPct('composition') }}</span>
                  <span class="trait-score num">{{ groupScore('composition') }}</span>
                </span>
              </header>
              <div v-if="lithBars.length" class="lith-bars">
                <div v-for="b in lithBars" :key="b.id" class="lith-row">
                  <div class="lith-lbls">
                    <span>{{ b.label }}</span>
                    <span class="num">
                      {{ b.earth !== null ? `${b.earth.toFixed(0)}%` : NOT_MEASURED }} Earth /
                      {{ b.target !== null ? `${b.target.toFixed(0)}%` : NOT_MEASURED }}
                      {{ bodyName }}
                    </span>
                  </div>
                  <div class="bar-track">
                    <div
                      class="bar-fill earth"
                      :style="{ width: `${Math.min(100, b.earth ?? 0)}%` }"
                    />
                  </div>
                </div>
              </div>
              <p v-else class="empty-lith">{{ NOT_MEASURED }}</p>
            </article>
          </div>

          <div v-if="alikeRows.length" class="alike-strip">
            <span class="alike-lbl">Closest measurements:</span>
            <span v-for="r in alikeRows" :key="r.name" class="alike-chip num">
              {{ r.name }} ({{ r.similarity.toFixed(2) }})
            </span>
          </div>

          <details class="full-table-box">
            <summary>All {{ rows.length }} measurements, gaps &amp; dataset sources</summary>
            <div class="table-scroll">
              <FeatureTable :rows="rows" :target-label="targetLabel" :body-name="bodyName" />
            </div>
          </details>
        </section>

        <section class="col-right" aria-label="Honest divergence">
          <h3 class="sec-head">Honest Divergence (Where Earth Fails)</h3>

          <div class="unmatchable-box" data-test="div-not_replicable">
            <div class="div-title">Unmatchable planetary conditions</div>
            <ul>
              <li v-for="item in divSections.unmatchable" :key="item.text">{{ item.text }}</li>
            </ul>
          </div>

          <div class="div-box">
            <div class="div-title">Physical &amp; measurement divergence</div>
            <ul v-if="divSections.bodyAndWeak.length">
              <li v-for="item in divSections.bodyAndWeak" :key="item.text">{{ item.text }}</li>
            </ul>
            <p v-if="divSections.missing.length" class="missing-note">
              {{ divSections.missing[0].text }}
            </p>
          </div>

          <div v-if="targetObj?.notes" class="div-box">
            <div class="div-title">Target landmark context</div>
            <p class="note-copy">{{ targetObj.notes }}</p>
          </div>

          <div v-if="uniqueSources.length" class="sources-row">
            <span class="src-lbl">Sources:</span>
            <span v-for="src in uniqueSources" :key="src" class="src-pill">{{ src }}</span>
          </div>
        </section>
      </div>

      <footer class="modal-foot">
        <button type="button" class="back-btn" data-test="close-details" @click="emit('close')">
          &larr; Back to Globes
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 45;
  pointer-events: auto;
  background: rgba(6, 9, 14, 0.78);
  backdrop-filter: blur(10px);
  display: grid;
  place-items: center;
  padding: var(--s4);
}

.modal-card {
  width: min(1060px, 100%);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  display: grid;
  gap: var(--s3);
  padding: 22px 24px;
  background: rgba(13, 17, 25, 0.96);
  border: 1px solid rgba(102, 217, 239, 0.28);
  border-radius: 16px;
  box-shadow: 0 28px 72px rgba(0, 0, 0, 0.75);
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--s3);
}

.head-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.rank-badge {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  border-radius: 12px;
  background: rgba(102, 217, 239, 0.16);
  border: 1px solid var(--accent-earth);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 18px rgba(102, 217, 239, 0.25);
}

.rank-lbl {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--accent-earth);
}

.rank-val {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.1;
}

.head-meta {
  display: grid;
  gap: 5px;
}

.head-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.head-title-row h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
}

.tag-pill {
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11.5px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: var(--text);
}

.tag-pill.novel {
  color: #5eead4;
  background: rgba(94, 234, 212, 0.12);
  border-color: rgba(94, 234, 212, 0.38);
}

.tag-pill.known {
  color: var(--accent-warn);
  background: rgba(242, 169, 59, 0.12);
  border-color: rgba(242, 169, 59, 0.35);
}

.sub-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-muted, #94a3b8);
}

.h3-pill {
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 11.5px;
  color: var(--text);
}

.close-x {
  background: transparent;
  border: none;
  color: var(--text-muted, #94a3b8);
  font-size: 24px;
  line-height: 1;
  padding: 2px 8px;
  cursor: pointer;
}

.close-x:hover {
  color: var(--text);
}

.ideal-switcher {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.sw-lbl {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-muted, #94a3b8);
  margin-right: 4px;
}

.sw-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: var(--text);
  font-size: 12px;
  cursor: pointer;
}

.sw-pill:hover {
  border-color: rgba(102, 217, 239, 0.45);
}

.sw-pill.active {
  background: rgba(102, 217, 239, 0.16);
  border-color: var(--accent-earth);
  color: var(--accent-earth);
  font-weight: 600;
}

.excluded-banner {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(242, 169, 59, 0.1);
  border: 1px solid rgba(242, 169, 59, 0.4);
  color: #ffd38a;
  font-size: 12.5px;
  line-height: 1.45;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.kpi-card {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.12);
  display: grid;
  gap: 4px;
}

.kpi-card.primary {
  background: rgba(102, 217, 239, 0.08);
  border-color: var(--accent-earth);
}

.kpi-label {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}

.kpi-value {
  display: flex;
  align-items: baseline;
  gap: 5px;
}

.kpi-value .big {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
}

.kpi-card.primary .big {
  color: var(--accent-earth);
}

.kpi-value .unit {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}

.kpi-stability {
  display: grid;
  gap: 6px;
}

.stab-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.stab-btn {
  justify-self: start;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: var(--text);
  font-size: 11px;
  cursor: pointer;
}

.stab-btn:hover {
  border-color: var(--accent-earth);
}

.stab-prog {
  font-size: 11.5px;
  color: var(--accent-earth);
}

.columns {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 18px;
  align-items: start;
}

.col-left,
.col-right {
  display: grid;
  gap: 12px;
}

.sec-head {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.trait-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.trait-card {
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.11);
  display: grid;
  gap: 8px;
}

.trait-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
}

.trait-badges {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.wt-chip {
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-muted, #94a3b8);
  font-size: 10.5px;
  font-weight: 500;
}

.trait-score {
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(102, 217, 239, 0.12);
  color: var(--accent-earth);
  font-size: 11px;
}

.pair-list {
  display: grid;
  gap: 5px;
}

.pair-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
}

.pair-k {
  color: var(--text-muted, #94a3b8);
}

.pair-v {
  color: var(--text);
  text-align: right;
}

.lith-bars {
  display: grid;
  gap: 7px;
}

.lith-row {
  display: grid;
  gap: 3px;
}

.lith-lbls {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  font-size: 11.5px;
  color: var(--text);
}

.bar-track {
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.bar-fill.earth {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #22d3ee, #66d9ef);
}

.empty-lith {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}

.alike-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.alike-lbl {
  color: var(--text-muted, #94a3b8);
}

.alike-chip {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text);
}

.full-table-box {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.12);
  padding: 10px 12px;
}

.full-table-box summary {
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--accent-earth);
}

.table-scroll {
  margin-top: 10px;
  overflow-x: auto;
}

.unmatchable-box {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(242, 169, 59, 0.12);
  border: 1px solid rgba(242, 169, 59, 0.5);
  display: grid;
  gap: 6px;
}

.div-box {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.12);
  display: grid;
  gap: 6px;
}

.div-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
}

.unmatchable-box .div-title {
  color: #ffd38a;
}

.unmatchable-box ul,
.div-box ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 4px;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--text);
}

.missing-note,
.note-copy {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
  line-height: 1.45;
}

.sources-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.src-lbl {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}

.src-pill {
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}

.back-btn {
  padding: 8px 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.back-btn:hover {
  border-color: var(--accent-earth);
  color: var(--accent-earth);
}

@media (max-width: 860px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .columns,
  .trait-grid {
    grid-template-columns: 1fr;
  }
}
</style>
