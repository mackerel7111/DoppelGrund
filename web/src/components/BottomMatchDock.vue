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

/** Why a tab has no match: the body has no data for that group at all, or no cell cleared the floors. */
function emptyReason(kind: CardKind): string {
  if (kind !== 'overall' && !s.available[kind]) {
    const where = s.body === 'moon' ? 'the Moon' : 'Mars';
    return `No ${GROUP_NAMES[kind]} data for ${where} yet, so there is nothing to match`;
  }
  return emptyCardText(kind);
}

function cardTooltip(kind: CardKind, row: number | null, sVal: number, sgVal: number): string {
  if (row === null || !s.bundle) return emptyReason(kind);
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
      class="shortlist-drawer hud"
      role="dialog"
      aria-label="Top 50 predicted Earth locations"
      data-test="shortlist-drawer"
    >
      <div class="drawer-head">
        <span class="drawer-title">Predicted ideal Earth locations, top 50</span>
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

    <nav class="match-dock hud" aria-label="Ideal locations predicted by model">
      <span class="dock-label">Ideal locations</span>

      <button
        v-for="(c, idx) in cards"
        :key="c.kind"
        type="button"
        class="tab"
        :aria-disabled="c.row === null ? 'true' : undefined"
        :aria-pressed="c.row !== null && c.row === s.selectedRow"
        :aria-describedby="c.row === null ? `dock-why-${c.kind}` : undefined"
        :title="cardTooltip(c.kind, c.row, c.S, c.S_g)"
        :data-test="`dock-card-${c.kind}`"
        @click="selectCard(c.row)"
      >
        <span class="match-n">{{ idx + 1 }}</span>
        <span class="tab-name">{{ SHORT_TITLES[c.kind] }}</span>
        <span v-if="c.row !== null" class="stat">
          <b>{{ cardScore(c.kind, c.S, c.S_g) }}</b>
        </span>
        <span v-else :id="`dock-why-${c.kind}`" class="visually-hidden">
          {{ emptyReason(c.kind) }}
        </span>
      </button>

      <span class="dock-divider" aria-hidden="true" />

      <button
        type="button"
        class="tab"
        :aria-expanded="shortlistOpen"
        title="Open ranked Top 50 predicted Earth analogue locations"
        data-test="toggle-shortlist"
        @click="shortlistOpen = !shortlistOpen"
      >
        {{ TERMS.top }}
      </button>
    </nav>
  </div>
</template>

<style scoped>
.dock-anchor {
  position: fixed;
  left: var(--s3);
  right: 316px; /* legend width 288 + its 12 inset + 16 gap */
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
  gap: 2px;
  padding: var(--s2); /* panel radius 16 - 8 = control radius 8 */
  overflow-x: auto;
  max-width: 100%;
  scrollbar-width: none;
}

.match-dock::-webkit-scrollbar {
  display: none;
}

.dock-label {
  padding: 0 var(--s2);
  font-size: var(--fs-meta);
  color: var(--text-muted);
  white-space: nowrap;
}

.tab-name {
  color: var(--text);
}

.tab .match-n {
  width: 18px;
  height: 18px;
  font-size: 11px;
}

.tab[aria-disabled='true'] .match-n {
  background: var(--border);
  color: var(--text-muted);
}

.dock-divider {
  flex-shrink: 0;
  width: 1px;
  height: 16px;
  margin: 0 var(--s1);
  background: var(--border);
}

.shortlist-drawer {
  pointer-events: auto;
  width: min(464px, 92vw);
  max-height: min(56vh, 464px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: color-mix(in srgb, var(--bg) 94%, transparent);
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--s2) var(--s2) var(--s2) var(--s4);
  border-bottom: 1px solid var(--border);
}

.drawer-title {
  font-size: var(--fs-meta);
  font-weight: 500;
  color: var(--text);
}

.drawer-close {
  display: inline-grid;
  place-items: center;
  width: 28px;
  min-height: 28px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  font-size: 18px;
  line-height: 1;
}

.drawer-close:hover {
  background: var(--surface-2);
  color: var(--text);
}

.drawer-body {
  padding: var(--s3) var(--s4) var(--s4);
  overflow-y: auto;
}

/* mid widths: the dock needs the full row, so the legend moves up onto it (GlobeView) */
@media (max-width: 1365px) {
  .dock-anchor {
    right: var(--s3);
  }
}

@media (max-width: 1199px) {
  .dock-anchor {
    left: 0;
    right: 0;
    bottom: 0;
  }
  .match-dock {
    width: 100%;
    border-radius: 0;
    border-width: 1px 0 0;
  }
}
</style>
