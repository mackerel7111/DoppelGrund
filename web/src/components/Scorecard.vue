<script setup lang="ts">
import { computed } from 'vue';
import FeatureTable from './FeatureTable.vue';
import DivergencePanel from './DivergencePanel.vue';
import Term from './Term.vue';
import { useSession } from '../stores/session';
import {
  featureComparison,
  formatLatLon,
  formatValue,
  mostAlike,
  rowInfo,
} from '../stores/selectors';
import { GROUP_IDS, HIDDEN_GROUPS } from '../data/types';
import { N_GROUPS } from '../engine/scoring';
import { heatCss } from '../map/palette';
import {
  CARD_TITLES,
  FEATURE_LABELS,
  GROUP_NAMES,
  LENS_NAMES,
  NOT_MEASURED,
  TERMS,
  stabilityText,
} from '../content/labels';

const props = defineProps<{ row: number }>();
const s = useSession();

const target = computed(() => s.rankTarget());
const targetBody = computed(() => {
  const t = s.target;
  if (t?.kind === 'disc') return t.body;
  return s.bundle?.targets.find((x) => x.id === t?.id)?.body ?? s.body;
});
const bodyName = computed(() => (targetBody.value === 'mars' ? 'Mars' : 'Moon'));
const targetLabel = computed(() => {
  const t = s.target;
  if (t?.kind === 'landmark') return s.bundle?.targets.find((x) => x.id === t.id)?.name ?? t.id;
  return TERMS.customPoint;
});
const targetLat = computed(() => {
  const t = s.target;
  if (t?.kind === 'disc') return s.bundle?.discs[t.body]?.latlon[t.discIndex * 2] ?? NaN;
  return s.bundle?.targets.find((x) => x.id === t?.id)?.lat ?? NaN;
});
const info = computed(() =>
  s.bundle ? rowInfo(s.bundle, s.stability, s.lens === 'custom', props.row) : null,
);
const groupScores = computed(() =>
  GROUP_IDS.map((_, g) => {
    const v = s.result?.groups[props.row * N_GROUPS + g];
    return v !== undefined && Number.isFinite(v) ? v : null;
  }),
);
const overall = computed(() => s.result?.S[props.row] ?? NaN);
const coverage = computed(() => s.result?.coverage[props.row] ?? NaN);
const rows = computed(() =>
  s.bundle && target.value
    ? featureComparison(s.bundle, target.value, targetBody.value, props.row)
    : [],
);
const alike = computed(() => mostAlike(rows.value));
const cardIndex = computed(() => s.result?.cards.findIndex((c) => c.row === props.row) ?? -1);
const title = computed(() =>
  cardIndex.value >= 0 && s.result
    ? CARD_TITLES[s.result.cards[cardIndex.value].kind]
    : 'Selected place',
);
const isNovel = computed(
  () => (info.value?.noveltyKm ?? NaN) >= (s.bundle?.manifest.params.novelty_gate_km ?? Infinity),
);
const draws = computed(() => s.bundle?.manifest.params.stability.draws_interactive ?? 0);

function fmt(v: number | null, d = 1): string {
  return v !== null && Number.isFinite(v) ? v.toFixed(d) : NOT_MEASURED;
}
</script>

<template>
  <section class="scorecard" :aria-label="title">
    <header>
      <h2 tabindex="-1">
        <span v-if="cardIndex >= 0" class="match-n">{{ cardIndex + 1 }}</span>
        {{ title }}
      </h2>
      <p v-if="info" class="tags">
        <span v-if="isNovel" class="tag">{{ TERMS.novel }}</span>
        <span v-if="info.knownSite" class="tag">{{ TERMS.knownSite }}</span>
        <span v-for="t in info.tags" :key="t" class="tag">{{ t }}</span>
      </p>
      <p v-if="info" class="num meta">
        {{ formatLatLon(info.lat, info.lng) }} vs {{ targetLabel }}
      </p>
      <p class="num figure">
        {{ fmt(overall) }}
        <span class="meta"
          >/100 <Term k="S">similarity</Term> · {{ fmt(coverage * 100, 0) }}%
          <Term k="coverage">data coverage</Term></span
        >
      </p>
    </header>

    <section class="block" aria-labelledby="sc-traits">
      <div class="row-head">
        <h3 id="sc-traits">How each trait compares</h3>
        <span class="meta">weight</span>
      </div>
      <ul class="traits">
        <template v-for="(g, i) in GROUP_IDS" :key="g">
          <li v-if="!HIDDEN_GROUPS.includes(g)">
            <span>{{ GROUP_NAMES[g] }}</span>
            <span
              class="score-bar"
              :class="{ none: groupScores[i] === null }"
              :style="
                groupScores[i] === null
                  ? undefined
                  : { '--v': groupScores[i]! / 100, '--c': heatCss(groupScores[i]!) }
              "
            />
            <span class="num" :class="{ meta: groupScores[i] === null }">{{
              fmt(groupScores[i])
            }}</span>
            <span class="num meta">{{ Math.round(s.weights[g] * 100) }}%</span>
          </li>
        </template>
      </ul>
    </section>

    <section v-if="alike.length" class="block" aria-labelledby="sc-alike">
      <h3 id="sc-alike">Most alike</h3>
      <ul class="alike">
        <li v-for="r in alike" :key="r.name">
          <span>{{ FEATURE_LABELS[r.name] ?? r.name }}</span>
          <span class="num meta"
            >{{ bodyName }} {{ formatValue(r.target, r.unit) ?? NOT_MEASURED }} · Earth
            {{ formatValue(r.earth, r.unit) ?? NOT_MEASURED }}</span
          >
        </li>
      </ul>
    </section>

    <DivergencePanel :body="targetBody" :target-lat="targetLat" :rows="rows" />

    <details class="more">
      <summary>All measurements and sources ({{ rows.length }})</summary>
      <FeatureTable :rows="rows" :target-label="targetLabel" :body-name="bodyName" />
    </details>

    <details class="more">
      <summary>More</summary>
      <dl v-if="info" class="facts">
        <dt><Term k="stability">Stability</Term></dt>
        <dd>
          {{ stabilityText(info.stabilityAvailable, info.stability)
          }}<template v-if="info.stabilityNote">
            (for {{ LENS_NAMES[s.lastPreset] }} weights)</template
          >
          <template v-if="!info.stabilityAvailable || info.stabilityNote">
            <button
              type="button"
              data-test="run-stability"
              :disabled="s.stabilityProgress !== null"
              @click="s.runStability(draws)"
            >
              Run check ({{ draws }} runs)
            </button>
            <template v-if="s.stabilityProgress">
              <progress
                :value="s.stabilityProgress.done"
                :max="s.stabilityProgress.total"
                aria-label="Stability progress"
              />
              <span class="num meta">
                {{ s.stabilityProgress.done }} / {{ s.stabilityProgress.total }}
              </span>
            </template>
          </template>
        </dd>
        <dt>Distance from known sites</dt>
        <dd class="num">{{ fmt(info.noveltyKm, 0) }} km</dd>
        <dt>Feature novelty</dt>
        <dd class="num">{{ fmt(info.featNovelty, 2) }}</dd>
        <dt>Cell id</dt>
        <dd class="num id">{{ s.bundle?.h3[props.row] }}</dd>
        <dt>Scale</dt>
        <dd>Stage 1 · ~1,770 km² area</dd>
      </dl>
    </details>
  </section>
</template>

<style scoped>
.scorecard {
  display: grid;
  gap: var(--s4);
  min-width: 0;
}
header {
  display: grid;
  gap: var(--s2);
  min-width: 0;
}
header p,
h2 {
  margin: 0;
}
h2 {
  display: flex;
  align-items: center;
  gap: var(--s2);
}
h2:focus {
  outline: none;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s1);
}
.figure {
  font-size: 20px;
  font-weight: 500;
}
.figure .meta {
  font-size: var(--fs-meta);
  font-weight: 400;
}
.block {
  display: grid;
  gap: var(--s2);
  min-width: 0;
}
.row-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: var(--s2);
}
.traits li {
  display: grid;
  grid-template-columns: 5.5rem minmax(0, 1fr) 5rem 2.5rem;
  gap: var(--s2);
  align-items: center;
}
.traits .num {
  text-align: right;
}
.alike li {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0 var(--s2);
}
.facts {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--s1) var(--s3);
  margin: 0;
  font-size: var(--fs-meta);
}
dt {
  color: var(--text-muted);
}
dd {
  margin: 0;
  min-width: 0;
}
.id {
  overflow-wrap: anywhere;
}
dd button {
  display: block;
  margin-top: var(--s1);
}
dd progress {
  width: 100%;
  accent-color: var(--accent-earth);
}
</style>
