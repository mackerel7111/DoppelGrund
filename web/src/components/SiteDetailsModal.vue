<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useSession } from '../stores/session';
import { FLAG_MASKED, GROUP_IDS } from '../data/types';
import { GROUP_NAMES, LENS_NAMES, NOT_MEASURED, stabilityText } from '../content/labels';
import { divergenceItems } from '../content/divergence';
import { featureComparison, formatLatLon, rowInfo } from '../stores/selectors';
import { heatCss } from '../map/palette';
import FeatureTable from './FeatureTable.vue';

const props = defineProps<{ row: number }>();
const emit = defineEmits<{ close: [] }>();
const s = useSession();
const tab = ref<'summary' | 'measurements' | 'sources'>('summary');
const tabs = ['summary', 'measurements', 'sources'] as const;
const panel = ref<HTMLElement | null>(null);
const heading = ref<HTMLElement | null>(null);
const mobile = ref(false);
let opener: HTMLElement | null = null;
let media: MediaQueryList | null = null;
const updateMobile = () => {
  mobile.value = media?.matches ?? false;
};
const bodyName = computed(() => (s.body === 'moon' ? 'Moon' : 'Mars'));
const landmark = computed(() =>
  s.bundle?.targets.find((t) => s.target?.kind === 'landmark' && t.id === s.target.id),
);
const targetLat = computed(() =>
  s.target?.kind === 'disc'
    ? (s.bundle?.discs[s.target.body]?.latlon[s.target.discIndex * 2] ?? NaN)
    : (landmark.value?.lat ?? NaN),
);
const targetLabel = computed(() => landmark.value?.name ?? `${bodyName.value} custom point`);
const info = computed(() =>
  s.bundle ? rowInfo(s.bundle, s.stability, s.lens === 'custom', props.row) : null,
);
const coords = computed(() => (info.value ? formatLatLon(info.value.lat, info.value.lng) : ''));
const masked = computed(() => Boolean((s.bundle?.flags[props.row] ?? 0) & FLAG_MASKED));
const eligible = computed(() => s.result?.eligible[props.row] === 1 && !masked.value);
const score = computed(() => s.result?.S[props.row] ?? NaN);
const coverage = computed(() => s.result?.coverage[props.row] ?? NaN);
const floor = computed(() => Math.round((s.bundle?.manifest.params.coverage_floor ?? 0.6) * 100));
const rows = computed(() => {
  const target = s.rankTarget();
  return s.bundle && target ? featureComparison(s.bundle, target, s.body, props.row) : [];
});
const traits = computed(() =>
  GROUP_IDS.map((id, i) => ({
    id,
    label: GROUP_NAMES[id],
    value: eligible.value ? (s.result?.groups[props.row * GROUP_IDS.length + i] ?? NaN) : NaN,
    weight: Math.round(s.effective[id] * 100),
  })),
);
const strongest = computed(() =>
  traits.value
    .filter((t) => Number.isFinite(t.value))
    .sort((a, b) => b.value - a.value)
    .slice(0, 2),
);
const differences = computed(() => divergenceItems(s.body, targetLat.value, rows.value));
const sources = computed(() =>
  Array.from(
    new Set(
      rows.value
        .flatMap((r) => [r.sourceEarth, r.sourceTarget])
        .filter((v): v is string => Boolean(v)),
    ),
  ),
);
const draws = computed(() => s.bundle?.manifest.params.stability.draws_interactive ?? 100);
const chosenMatch = ref('');
const matchOptions = computed(() => (s.result?.cards ?? []).slice(0, 5));
const selectedMatch = computed(() => {
  const chosen = chosenMatch.value;
  if (chosen !== '' && matchOptions.value[Number(chosen)]?.row === props.row) return chosen;
  const index = matchOptions.value.findIndex((card) => card.row === props.row);
  return index >= 0 ? String(index) : '';
});
function chooseMatch(event: Event): void {
  const value = (event.target as HTMLSelectElement).value;
  if (!/^[0-4]$/.test(value)) return;
  const card = matchOptions.value[Number(value)];
  if (!card || card.row === null) return;
  chosenMatch.value = value;
  s.selectRow(card.row);
}
const fmt = (v: number, digits = 1): string =>
  Number.isFinite(v) ? v.toFixed(digits) : NOT_MEASURED;
function changeTabKey(event: KeyboardEvent): void {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const i = tabs.indexOf(tab.value);
  tab.value =
    tabs[
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? 2
          : (i + (event.key === 'ArrowRight' ? 1 : 2)) % 3
    ];
  nextTick(() => document.getElementById(`site-tab-${tab.value}`)?.focus());
}
function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault();
    emit('close');
  }
  if (!mobile.value || event.key !== 'Tab') return;
  const controls = Array.from(
    panel.value?.querySelectorAll<HTMLElement>(
      'button:not(:disabled):not([tabindex="-1"]), summary, a[href]',
    ) ?? [],
  ).filter((el) => el.getClientRects().length);
  const first = controls[0];
  const last = controls.at(-1);
  if (
    event.shiftKey &&
    (document.activeElement === first || document.activeElement === heading.value)
  ) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
}
watch(
  () => props.row,
  () => {
    tab.value = 'summary';
  },
);
onMounted(() => {
  opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  heading.value?.focus();
  media = typeof window.matchMedia === 'function' ? window.matchMedia('(max-width: 899px)') : null;
  updateMobile();
  media?.addEventListener('change', updateMobile);
});
onBeforeUnmount(() => {
  media?.removeEventListener('change', updateMobile);
  if (opener?.isConnected) opener.focus();
});
</script>

<template>
  <aside
    ref="panel"
    class="site-details"
    :role="mobile ? 'dialog' : 'region'"
    :aria-modal="mobile ? true : undefined"
    aria-labelledby="site-heading"
    data-test="site-details-modal"
    @keydown="onKey"
  >
    <header class="detail-header">
      <div>
        <div class="match-heading">
          <h2 id="site-heading" ref="heading" tabindex="-1">Earth match</h2>
          <select
            aria-label="Choose Earth match number"
            data-test="match-number"
            :value="selectedMatch"
            @change="chooseMatch"
          >
            <option v-if="selectedMatch === ''" value="" disabled>Selected location</option>
            <option
              v-for="(card, index) in matchOptions"
              :key="card.kind"
              :value="String(index)"
              :disabled="card.row === null"
            >
              {{ index + 1 }} · {{ card.kind === 'overall' ? 'Overall' : GROUP_NAMES[card.kind]
              }}{{ card.row === null ? ' — unavailable' : '' }}
            </option>
          </select>
        </div>
        <p class="meta num">{{ coords }} · compared with {{ bodyName }}</p>
      </div>
      <button
        type="button"
        aria-label="Close details"
        data-test="close-details"
        @click="emit('close')"
      >
        ×
      </button>
    </header>
    <div class="detail-tabs" role="tablist" aria-label="Match information" @keydown="changeTabKey">
      <button
        v-for="name in tabs"
        :id="`site-tab-${name}`"
        :key="name"
        type="button"
        role="tab"
        :aria-selected="tab === name"
        :aria-controls="`site-panel-${name}`"
        :tabindex="tab === name ? 0 : -1"
        @click="tab = name"
      >
        {{ name === 'summary' ? 'Summary' : name === 'measurements' ? 'Measurements' : 'Sources' }}
      </button>
    </div>
    <div
      :id="`site-panel-${tab}`"
      class="detail-body"
      role="tabpanel"
      :aria-labelledby="`site-tab-${tab}`"
      tabindex="0"
    >
      <template v-if="tab === 'summary'">
        <p v-if="s.synthetic" class="warning">Synthetic data — not real results</p>
        <p v-if="!eligible" class="warning">
          {{
            masked
              ? 'This place is masked and has no comparison score.'
              : `Not ranked: this place needs at least ${floor}% data coverage.`
          }}
        </p>
        <div class="headline">
          <div>
            <span class="meta">Overall similarity</span>
            <p class="figure">
              {{ eligible ? fmt(score) : 'Not scored' }}<small v-if="eligible"> / 100</small>
            </p>
          </div>
          <div>
            <strong>{{
              Number.isFinite(coverage) ? `${fmt(coverage * 100, 0)}%` : 'No data'
            }}</strong
            ><span class="meta">data coverage</span>
          </div>
        </div>
        <p class="plain">
          How closely this Earth place resembles the selected {{ bodyName }} target across the
          available measurements.
        </p>
        <section v-if="strongest.length">
          <h3>Strongest similarities</h3>
          <div v-for="t in strongest" :key="t.id" class="trait">
            <span>{{ t.label }}</span
            ><span class="score-bar" :style="{ '--v': t.value / 100, '--c': heatCss(t.value) }" /><b
              class="num"
              >{{ fmt(t.value, 0) }}</b
            >
          </div>
        </section>
        <details>
          <summary>All traits &amp; missing data</summary>
          <div v-for="t in traits" :key="t.id" class="trait all-trait">
            <span>{{ t.label }}</span
            ><span>{{ Number.isFinite(t.value) ? `${fmt(t.value)} / 100` : 'No data' }}</span>
          </div>
          <p class="meta">
            No data means no comparison is available; it does not mean a zero match.
          </p>
        </details>
        <section class="caution">
          <h3>What Earth cannot reproduce</h3>
          <p class="chips"><span>Gravity</span><span>Atmosphere</span><span>Radiation</span></p>
          <p>Similar terrain does not mean identical conditions.</p>
          <details>
            <summary>Limits of this comparison</summary>
            <ul>
              <li v-for="item in differences" :key="item.text">{{ item.text }}</li>
            </ul>
          </details>
        </section>
        <details>
          <summary>Distance from known sites</summary>
          <p>{{ fmt(info?.noveltyKm ?? NaN, 0) }} km to the nearest documented analogue site.</p>
          <p class="meta">
            Distance alone does not establish that a place is suitable for a mission.
          </p>
        </details>
        <details>
          <summary>Check result stability</summary>
          <p>See how often this place stays near the top when comparison settings vary.</p>
          <p>{{ info ? stabilityText(info.stabilityAvailable, info.stability) : NOT_MEASURED }}</p>
          <button
            v-if="eligible && s.stabilityProgress === null"
            type="button"
            data-test="run-stability"
            @click="s.runStability(draws)"
          >
            Run stability check ({{ draws }})
          </button>
          <p v-if="s.stabilityProgress" role="status">
            Running {{ s.stabilityProgress.done }} / {{ s.stabilityProgress.total }}
          </p>
        </details>
      </template>
      <template v-else-if="tab === 'measurements'">
        <h3>Target vs Earth</h3>
        <p>{{ targetLabel }} · {{ s.lens === 'custom' ? 'Custom focus' : LENS_NAMES[s.lens] }}</p>
        <div class="table-scroll">
          <FeatureTable :rows="rows" :target-label="targetLabel" :body-name="bodyName" />
        </div>
        <h3>Comparison weights</h3>
        <div v-for="t in traits" :key="t.id" class="all-trait">
          <span>{{ t.label }}</span
          ><span>{{ t.weight }}%</span>
        </div>
        <h3>Where this analogy falls short</h3>
        <ul>
          <li v-for="item in differences" :key="item.text">{{ item.text }}</li>
        </ul>
        <p v-if="landmark?.notes">{{ landmark.notes }}</p>
        <details>
          <summary>Cell identifiers &amp; context</summary>
          <p class="num">H3 {{ s.bundle?.h3[row] }}</p>
          <p>Cluster: {{ s.bundle?.cluster?.[row] ?? NOT_MEASURED }}</p>
          <p>Feature novelty: {{ fmt(info?.featNovelty ?? NaN, 2) }}</p>
          <p>{{ info?.tags.join(' · ') }}</p>
        </details>
      </template>
      <template v-else
        ><h3>Data sources</h3>
        <p>Datasets used for the measurements in this comparison.</p>
        <ul v-if="sources.length" class="sources">
          <li v-for="source in sources" :key="source">{{ source }}</li>
        </ul>
        <p v-else>No dataset sources are available for this comparison.</p>
        <p class="meta">
          Missing or unverified measurements are not evidence of a match.
        </p></template
      >
    </div>
  </aside>
</template>

<style scoped>
.match-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
.match-heading select {
  width: 140px;
  max-width: 100%;
  min-height: 44px;
  font-size: 14px;
  padding-inline: 8px;
}

.site-details {
  min-height: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0c121d;
  border-left: 1px solid var(--border);
  pointer-events: auto;
  color: var(--text);
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 20px;
}
h2 {
  font-size: 22px;
  outline: none;
}
h3 {
  font-size: 17px;
  margin: 0 0 16px;
}
p {
  margin: 8px 0;
  line-height: 1.55;
}
button {
  min-height: 44px;
}
.detail-header button {
  min-width: 44px;
  font-size: 24px;
}
.detail-tabs {
  display: flex;
  padding: 0 16px 16px;
  gap: 6px;
  border-bottom: 1px solid var(--border);
}
.detail-tabs button {
  flex: 1;
  font-size: 14px;
  padding: 8px;
}
[aria-selected='true'] {
  border-color: var(--accent-earth);
  color: var(--accent-earth);
}
.detail-body {
  padding: 20px;
  overflow-y: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.headline {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}
.headline > div:last-child {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.figure {
  color: var(--accent-earth);
  font-size: 36px;
  font-weight: 650;
  line-height: 1.2;
}
.figure small {
  font-size: 16px;
  color: var(--text-muted);
  font-weight: 400;
}
.plain {
  color: var(--text-muted);
  margin: 0;
}
.trait {
  display: grid;
  grid-template-columns: 1fr 90px 30px;
  gap: 12px;
  align-items: center;
  margin: 16px 0;
}
.all-trait {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 8px 0;
}
details {
  border-bottom: 1px solid var(--border);
  padding-bottom: 16px;
}
summary {
  cursor: pointer;
  min-height: 32px;
  color: #9eddf8;
  line-height: 1.6;
}
.caution {
  border: 1px solid #77602b;
  border-radius: 12px;
  padding: 16px;
  background: #f2b5440c;
}
.caution h3 {
  color: #f5c66f;
}
.caution details {
  border: 0;
  padding: 0;
  margin-top: 12px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chips span {
  border: 1px solid #77602b;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 13px;
}
.warning {
  padding: 12px;
  border: 1px solid var(--warn);
  border-radius: 8px;
  color: #f5c66f;
}
ul {
  padding-left: 20px;
}
li {
  margin-block: 12px;
  line-height: 1.6;
}
.table-scroll {
  overflow-x: auto;
}
.sources {
  overflow-wrap: anywhere;
}
@media (max-width: 899px) {
  .site-details {
    position: fixed;
    inset: 0;
    z-index: 45;
    height: 100dvh;
    padding-bottom: env(safe-area-inset-bottom);
    border: 0;
  }
}
</style>
