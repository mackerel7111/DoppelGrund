<script setup lang="ts">
import type { Card } from '../data/types';
import { formatLatLon, type RowInfo } from '../stores/selectors';
import { CARD_TITLES, TERMS, emptyCardText } from '../content/labels';
import { heatCss } from '../map/palette';
import { useSession } from '../stores/session';
import Term from './Term.vue';

// Card 1 (overall) is the headline; cards 2–5 are one-button rows that open the detail.
const props = defineProps<{
  cards: Card[];
  rowInfo: (row: number) => RowInfo;
  selectedRow?: number | null;
}>();
const emit = defineEmits<{ select: [row: number] }>();
const s = useSession();

function fmt(v: number, digits = 1): string {
  return Number.isFinite(v) ? v.toFixed(digits) : '—';
}
function where(row: number): string {
  const i = props.rowInfo(row);
  return formatLatLon(i.lat, i.lng);
}
function novel(row: number): boolean {
  return props.rowInfo(row).noveltyKm >= (s.bundle?.manifest.params.novelty_gate_km ?? 300);
}
</script>

<template>
  <ol class="cards">
    <li
      v-for="(c, i) in props.cards"
      :key="c.kind"
      :class="i === 0 && c.row !== null ? 'top' : 'row'"
      :data-test="`card-${c.kind}`"
    >
      <p v-if="c.row === null" class="none">
        <span class="match-n" aria-hidden="true">{{ i + 1 }}</span>
        <span class="what">
          <span class="title" data-test="title">{{ CARD_TITLES[c.kind] }}</span>
          <span class="meta" data-test="empty">{{ emptyCardText(c.kind) }}</span>
        </span>
      </p>
      <template v-else-if="i === 0">
        <header>
          <span class="match-n" aria-hidden="true">1</span>
          <h3 data-test="title">{{ CARD_TITLES[c.kind] }}</h3>
          <span class="tags">
            <span v-if="novel(c.row)" class="tag">{{ TERMS.novel }}</span>
            <span v-if="props.rowInfo(c.row).knownSite" class="tag">{{ TERMS.knownSite }}</span>
          </span>
        </header>
        <p class="score num">
          {{ fmt(c.S_g) }}<span class="unit"> /100 <Term k="S">similarity</Term></span>
        </p>
        <span
          class="score-bar"
          :style="{ '--v': c.S_g / 100, '--c': heatCss(c.S_g) }"
          aria-hidden="true"
        ></span>
        <p class="meta num">
          {{ fmt(c.coverage * 100, 0) }}% <Term k="coverage">data coverage</Term> ·
          {{ fmt(props.rowInfo(c.row).noveltyKm, 0) }} km from known sites
        </p>
        <div class="foot">
          <span class="num">{{ where(c.row) }}</span>
          <button
            type="button"
            :aria-pressed="props.selectedRow === c.row"
            data-test="open-overall"
            @click="emit('select', c.row)"
          >
            {{ TERMS.compare }}
          </button>
        </div>
      </template>
      <button
        v-else
        type="button"
        class="line"
        :aria-pressed="props.selectedRow === c.row"
        :data-test="`open-${c.kind}`"
        @click="emit('select', c.row)"
      >
        <span class="match-n" aria-hidden="true">{{ i + 1 }}</span>
        <span class="what">
          <span class="head">
            <span class="title" data-test="title">{{ CARD_TITLES[c.kind] }}</span>
            <span v-if="novel(c.row)" class="tag">{{ TERMS.novel }}</span>
          </span>
          <span class="meta num">{{ where(c.row) }} · overall {{ fmt(c.S, 1) }}</span>
        </span>
        <span class="pts">
          <span class="num"><span class="visually-hidden">score </span>{{ fmt(c.S_g) }}</span>
          <span
            class="score-bar"
            :style="{ '--v': c.S_g / 100, '--c': heatCss(c.S_g) }"
            aria-hidden="true"
          ></span>
        </span>
      </button>
    </li>
  </ol>
</template>

<style scoped>
.cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--s2);
}
.top {
  display: grid;
  gap: var(--s2);
  padding: var(--s3) var(--s4);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
}
.top p {
  margin: 0;
}
header,
.foot,
.head {
  display: flex;
  gap: var(--s2);
  align-items: center;
}
h3 {
  font-weight: 500;
}
.tags {
  display: flex;
  gap: var(--s1);
  margin-left: auto;
}
.score {
  font-size: 28px;
  line-height: 1.1;
  font-weight: 500;
}
.unit {
  font-size: var(--fs-meta);
  font-weight: 400;
  color: var(--text-muted);
}
.foot {
  justify-content: space-between;
}
.line,
.none {
  display: flex;
  align-items: center;
  gap: var(--s3);
  width: 100%;
  min-height: 48px;
  margin: 0;
  padding: var(--s2) var(--s4);
  text-align: left;
}
.what {
  display: grid;
  flex: 1;
  min-width: 0;
}
.what .meta {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.pts {
  display: grid;
  gap: var(--s1);
  width: 48px;
  text-align: right;
  font-weight: 500;
}
.none .match-n {
  background: var(--surface-2);
  color: var(--text-muted);
}
.none .title {
  color: var(--text-muted);
}
.none .meta {
  white-space: normal;
}
</style>
