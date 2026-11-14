<script setup lang="ts">
import { computed } from 'vue';
import { useSession } from '../stores/session';
import { formatLatLon, rowInfo, type RowInfo } from '../stores/selectors';
import { heatCss } from '../map/palette';

const SHORTLIST_N = 50; // R9.1: top 50 eligible
const s = useSession();

const gateKm = computed(() => s.bundle?.manifest.params.novelty_gate_km ?? NaN);
const entries = computed<(RowInfo & { S: number; coverage: number })[]>(() => {
  const b = s.bundle;
  const r = s.result;
  if (!b || !r) return [];
  const out: (RowInfo & { S: number; coverage: number })[] = [];
  for (const row of r.top) {
    const info = rowInfo(b, s.stability, s.lens === 'custom', row);
    if (s.novelOnly && !(info.noveltyKm >= gateKm.value)) continue;
    out.push({ ...info, S: r.S[row], coverage: r.coverage[row] });
    if (out.length >= SHORTLIST_N) break;
  }
  return out;
});
const pool = computed(() => s.result?.top.length ?? 0);

function stab(e: RowInfo): string {
  if (!e.stabilityAvailable || e.stability === null || e.stabilityNote) return '';
  return `${Math.round(e.stability * 100)}% stable`;
}
</script>

<template>
  <div class="shortlist">
    <div class="bar">
      <label class="toggle">
        <input
          type="checkbox"
          :checked="s.novelOnly"
          data-test="novel-only"
          @change="s.setNovelOnly(($event.target as HTMLInputElement).checked)"
        />
        <span>Only novel places (≥ {{ gateKm }} km from known sites)</span>
      </label>
      <span class="meta num" data-test="shortlist-count"
        >{{ entries.length }} shown<template v-if="s.novelOnly">
          · from the best {{ pool }}</template
        ></span
      >
    </div>
    <p v-if="!s.result" class="meta pad">Pick a landmark to see the top 50</p>
    <p v-else-if="entries.length === 0" class="meta pad">
      No place among the best {{ pool }} is {{ gateKm }} km or more from a known site
    </p>
    <ol v-else class="list">
      <li v-for="(e, i) in entries" :key="e.row">
        <button
          type="button"
          class="row"
          :aria-pressed="s.selectedRow === e.row"
          @click="s.selectRow(e.row)"
        >
          <span class="top">
            <span class="rank meta num">{{ i + 1 }}</span>
            <span class="num">{{ formatLatLon(e.lat, e.lng) }}</span>
            <span v-if="e.noveltyKm >= gateKm" class="tag">Novel</span>
            <span class="score num">{{ e.S.toFixed(1) }}</span>
          </span>
          <span
            class="score-bar"
            :style="{ '--v': e.S / 100, '--c': heatCss(e.S) }"
            aria-hidden="true"
          ></span>
          <span class="meta num"
            >{{ (e.coverage * 100).toFixed(0) }}% data · {{ e.noveltyKm.toFixed(0) }} km from known
            sites<template v-if="stab(e)"> · {{ stab(e) }}</template></span
          >
        </button>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  justify-content: space-between;
  gap: var(--s3);
  padding-bottom: var(--s3);
  flex-wrap: wrap;
}
.toggle {
  display: inline-flex;
  gap: var(--s2);
  align-items: center;
}
.pad {
  margin: 0;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--s1);
}
.row {
  width: 100%;
  display: grid;
  gap: var(--s1);
  padding: var(--s2) var(--s3);
  text-align: left;
  background: none;
  border-color: transparent;
}
.row:hover:not(:disabled) {
  background: var(--surface-2);
  border-color: transparent;
}
.row[aria-pressed='true'] {
  background: var(--surface-2);
  border-color: var(--border);
  color: inherit;
}
.top {
  display: flex;
  align-items: center;
  gap: var(--s2);
}
.rank {
  width: 24px;
  flex: none;
}
.score {
  margin-left: auto;
  font-weight: 500;
}
</style>
