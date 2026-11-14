<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useSession } from '../stores/session';
import { emptyCardText, GROUP_NAMES, TERMS } from '../content/labels';
import { formatLatLon } from '../stores/selectors';
import type { CardKind } from '../data/types';
import Shortlist from './Shortlist.vue';

const s = useSession();
const shortlistOpen = ref(false);

const cards = computed(() => s.result?.cards ?? []);

const SHORT_TITLES: Record<CardKind, string> = {
  overall: 'Overall',
  terrain: GROUP_NAMES.terrain,
  thermal: GROUP_NAMES.thermal,
  cold_ice: GROUP_NAMES.cold_ice,
  composition: GROUP_NAMES.composition,
  subsurface: GROUP_NAMES.subsurface,
};

function cardScore(kind: CardKind, sVal: number, sgVal: number): string {
  const v = kind === 'overall' ? sVal : sgVal;
  return Number.isFinite(v) ? v.toFixed(1) : 'N/A';
}

function cardTooltip(kind: CardKind, row: number | null, sVal: number, sgVal: number): string {
  if (row === null || !s.bundle) return emptyCardText(kind);
  const lat = s.bundle.latlng[row * 2];
  const lng = s.bundle.latlng[row * 2 + 1];
  const coords = formatLatLon(lat, lng);
  const score = cardScore(kind, sVal, sgVal);
  return `${SHORT_TITLES[kind]} prediction: ${score}/100 at ${coords} (overall ${sVal.toFixed(1)})`;
}

function selectCard(row: number | null): void {
  if (row === null) return;
  shortlistOpen.value = false;
  s.selectRow(row);
}

// Auto-close the shortlist drawer once the researcher picks a row so the Earth briefing is unobstructed.
watch(
  () => s.selectedRow,
  (row, prev) => {
    if (row !== null && row !== prev && shortlistOpen.value) {
      shortlistOpen.value = false;
    }
  },
);
</script>

<template>
  <div v-if="s.result && !s.aboutOpen" class="dock-anchor">
    <div
      v-if="shortlistOpen"
      class="shortlist-drawer"
      role="dialog"
      aria-label="Top 50 predicted Earth locations"
      data-test="shortlist-drawer"
    >
      <div class="drawer-head">
        <span class="drawer-title">Predicted ideal Earth locations (Top 50)</span>
        <button
          type="button"
          class="drawer-close"
          aria-label="Close shortlist"
          @click="shortlistOpen = false"
        >
          &times;
        </button>
      </div>
      <div class="drawer-body">
        <Shortlist />
      </div>
    </div>

    <nav class="match-dock" aria-label="Ideal locations predicted by model">
      <span class="dock-label">Ideal locations</span>

      <button
        v-for="(c, idx) in cards"
        :key="c.kind"
        type="button"
        class="match-pill"
        :class="{
          active: c.row !== null && c.row === s.selectedRow,
          empty: c.row === null,
        }"
        :disabled="c.row === null"
        :aria-pressed="c.row !== null && c.row === s.selectedRow"
        :title="cardTooltip(c.kind, c.row, c.S, c.S_g)"
        :data-test="`dock-card-${c.kind}`"
        @click="selectCard(c.row)"
      >
        <span class="pill-rank">{{ idx + 1 }} &middot;</span>
        <span class="pill-name">{{ SHORT_TITLES[c.kind] }}</span>
        <span v-if="c.row !== null" class="pill-score num">
          {{ cardScore(c.kind, c.S, c.S_g) }}
        </span>
      </button>

      <span class="dock-divider" aria-hidden="true" />

      <button
        type="button"
        class="match-pill top-btn"
        :class="{ active: shortlistOpen }"
        :aria-expanded="shortlistOpen"
        title="Open ranked Top 50 predicted Earth analogue locations"
        data-test="toggle-shortlist"
        @click="shortlistOpen = !shortlistOpen"
      >
        <span>{{ TERMS.top }}</span>
        <span aria-hidden="true">&#8599;</span>
      </button>
    </nav>
  </div>
</template>

<style scoped>
.dock-anchor {
  position: fixed;
  left: var(--s3);
  right: 296px;
  bottom: var(--s3);
  z-index: 20;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--s2);
}

.match-dock {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(11, 14, 19, 0.86);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.55);
  overflow-x: auto;
  max-width: 100%;
  scrollbar-width: none;
}

.match-dock::-webkit-scrollbar {
  display: none;
}

.dock-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--accent-earth);
  padding-left: 4px;
  padding-right: 4px;
  white-space: nowrap;
}

.match-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid transparent;
  color: var(--text);
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.match-pill:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.09);
  border-color: rgba(255, 255, 255, 0.22);
}

.match-pill.active {
  background: rgba(102, 217, 239, 0.15);
  border-color: var(--accent-earth);
  box-shadow: 0 0 14px rgba(102, 217, 239, 0.22);
}

.match-pill.empty {
  opacity: 0.42;
  cursor: not-allowed;
}

.pill-rank {
  color: var(--text-muted, #94a3b8);
}

.pill-name {
  font-weight: 500;
}

.pill-score {
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--accent-earth);
  font-size: 11px;
  font-weight: 600;
}

.dock-divider {
  width: 1px;
  height: 18px;
  background: rgba(255, 255, 255, 0.14);
  flex-shrink: 0;
}

.top-btn {
  color: var(--text);
  border-color: rgba(255, 255, 255, 0.14);
}

.top-btn:hover,
.top-btn.active {
  border-color: var(--accent-earth);
  color: var(--accent-earth);
}

.shortlist-drawer {
  pointer-events: auto;
  width: min(460px, 92vw);
  max-height: min(56vh, 460px);
  display: flex;
  flex-direction: column;
  background: rgba(12, 16, 23, 0.94);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 14px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7);
  overflow: hidden;
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.09);
}

.drawer-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.drawer-close {
  background: transparent;
  border: none;
  color: var(--text-muted, #94a3b8);
  font-size: 18px;
  line-height: 1;
  padding: 2px 6px;
  cursor: pointer;
}

.drawer-close:hover {
  color: var(--text);
}

.drawer-body {
  padding: 10px 14px 14px;
  overflow-y: auto;
}

@media (max-width: 960px) {
  .dock-anchor {
    left: var(--s3);
    right: var(--s3);
    transform: none;
    max-width: none;
    bottom: 84px;
  }
}
</style>
