<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import MatchCards from './MatchCards.vue';
import Scorecard from './Scorecard.vue';
import Shortlist from './Shortlist.vue';
import { rowInfo, type RowInfo } from '../stores/selectors';
import { useSession } from '../stores/session';
import { GLOSSARY, LENS_NAMES, LENS_SHORT, TERMS } from '../content/labels';
import { LENS_IDS } from '../data/types';

const s = useSession();
const scorecard = ref<HTMLElement | null>(null);
const TABS = ['matches', 'shortlist'] as const;
const tab = ref<(typeof TABS)[number]>('matches');
function onTabKey(ev: KeyboardEvent): void {
  if (ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight') return;
  tab.value = tab.value === 'matches' ? 'shortlist' : 'matches';
  document.getElementById(`tab-${tab.value}`)?.focus();
}
const gate = computed(() => s.bundle?.manifest.params.novelty_gate_km ?? 300);
const floorPct = computed(() =>
  Math.round((s.bundle?.manifest.params.coverage_floor ?? 0.6) * 100),
);
const allEmpty = computed(() => !!s.result && s.result.cards.every((c) => c.row === null));
let opener: HTMLElement | null = null;

function info(row: number): RowInfo {
  if (!s.bundle) throw new Error('bundle not loaded');
  return rowInfo(s.bundle, s.stability, s.lens === 'custom', row);
}

// Focus the scorecard heading on open; return focus to the opener on close.
// The results stay mounted (v-show) so the opener still exists.
watch(
  () => s.selectedRow,
  async (row, prev) => {
    if (row !== null && prev === null) {
      opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      await nextTick();
      scorecard.value?.querySelector<HTMLElement>('h2')?.focus();
    } else if (row === null && prev !== null) {
      await nextTick();
      opener?.focus();
      opener = null;
    }
  },
);
</script>

<template>
  <section class="results" aria-label="Results">
    <div v-if="s.selectedRow !== null" ref="scorecard" @keydown.esc="s.selectRow(null)">
      <button type="button" class="back" @click="s.selectRow(null)">← {{ TERMS.back }}</button>
      <Scorecard :row="s.selectedRow" />
    </div>
    <div v-show="s.selectedRow === null" class="list">
      <h2 class="section-title"><span class="dot earth"></span>{{ TERMS.results }}</h2>
      <div class="seg" role="tablist" aria-label="Results" @keydown="onTabKey">
        <button
          v-for="n in TABS"
          :id="`tab-${n}`"
          :key="n"
          type="button"
          role="tab"
          :aria-selected="tab === n"
          :aria-controls="`panel-${n}`"
          :tabindex="tab === n ? 0 : -1"
          :data-test="`tab-${n}`"
          @click="tab = n"
        >
          {{ n === 'matches' ? TERMS.picks : TERMS.top }}
        </button>
      </div>
      <div
        v-show="tab === 'matches'"
        id="panel-matches"
        class="list"
        role="tabpanel"
        aria-labelledby="tab-matches"
      >
        <p v-if="!s.result" class="meta">Pick a landmark to see its best matches on Earth</p>
        <div v-else-if="allEmpty" class="none" role="status">
          <p class="meta">
            No Earth place has enough data to compare under
            {{ s.lens === 'custom' ? 'these weights' : LENS_NAMES[s.lens] }}: at least
            {{ floorPct }}% data coverage is needed
          </p>
          <div class="try">
            <button
              v-for="id in LENS_IDS.filter((l) => l !== s.lens)"
              :key="id"
              type="button"
              @click="s.setLens(id)"
            >
              Try {{ LENS_SHORT[id] }}
            </button>
          </div>
        </div>
        <MatchCards
          v-else
          :cards="s.result.cards"
          :row-info="info"
          :selected-row="s.selectedRow"
          @select="s.selectRow"
        />
      </div>
      <div
        v-show="tab === 'shortlist'"
        id="panel-shortlist"
        role="tabpanel"
        aria-labelledby="tab-shortlist"
      >
        <Shortlist />
      </div>
      <details class="more">
        <summary>{{ TERMS.definitions }}</summary>
        <dl>
          <dt>{{ TERMS.similarity }}</dt>
          <dd>{{ GLOSSARY.S }}</dd>
          <dt>{{ TERMS.coverage }}</dt>
          <dd>{{ GLOSSARY.coverage }}</dd>
          <dt>{{ TERMS.novel }}</dt>
          <dd>{{ gate }} km or more from every documented analogue site</dd>
          <dt>Stability</dt>
          <dd>{{ GLOSSARY.stability }}</dd>
        </dl>
      </details>
    </div>
  </section>
</template>

<style scoped>
.results {
  padding: var(--s4);
}
.list {
  display: grid;
  gap: var(--s3);
}
.try {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s2);
}
dl {
  display: grid;
  gap: var(--s1);
  margin: 0;
  font-size: var(--fs-meta);
  color: var(--text-muted);
}
dt {
  color: var(--text);
}
dd {
  margin: 0 0 var(--s2);
}
.seg {
  gap: 0;
  padding: 2px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
}
[role='tab'] {
  min-height: 28px;
  background: none;
  border-color: transparent;
  border-radius: 4px;
  color: var(--text-muted);
  transition:
    color var(--dur) var(--ease),
    background-color var(--dur) var(--ease);
}
[role='tab']:hover:not(:disabled) {
  border-color: transparent;
  color: var(--text);
}
[role='tab'][aria-selected='true'] {
  background: var(--surface-2);
  color: var(--text);
}
.back {
  margin-bottom: var(--s3);
  padding-left: 0;
  background: none;
  border-color: transparent;
  color: var(--text-muted);
}
.back:hover:not(:disabled) {
  border-color: transparent;
  color: var(--text);
}
</style>
