<script setup lang="ts">
import { computed } from 'vue';
import { useSession } from '../stores/session';
import { GROUP_IDS, LENS_IDS, type LensId } from '../data/types';
import { FOOTPRINT_SHORT, GROUP_NAMES, LENS_NAMES, LENS_SHORT, TERMS } from '../content/labels';
import { formatLatLon } from '../stores/selectors';
import LensControls from './LensControls.vue';

defineProps<{ tutorialActive?: boolean }>();
const s = useSession();
const landmarks = computed(() => (s.bundle?.targets ?? []).filter((t) => t.body === s.body));
const selectedId = computed(() => (s.target?.kind === 'landmark' ? s.target.id : ''));
// A custom point picked on the 2D map has no landmark id: show it as one disabled option.
const customPoint = computed(() => {
  const t = s.target;
  const ll = t?.kind === 'disc' ? s.bundle?.discs[t.body]?.latlon : undefined;
  if (t?.kind !== 'disc' || !ll) return '';
  return `${TERMS.customPoint} ${formatLatLon(ll[t.discIndex * 2], ll[t.discIndex * 2 + 1])}`;
});

function lensTitle(id: LensId): string {
  if (!s.lensDisabled(id)) return LENS_NAMES[id];
  const need = GROUP_IDS.filter((g) => s.presets[id][g] > 0 && !s.available[g]);
  return `Needs ${need.map((g) => GROUP_NAMES[g]).join(' / ')} data — not available for ${s.body === 'mars' ? 'Mars' : 'the Moon'} yet`;
}

function onLandmark(ev: Event): void {
  const id = (ev.target as HTMLSelectElement).value;
  if (id) s.selectLandmark(id);
}
</script>

<template>
  <section class="controls" aria-label="Landmark and mission focus">
    <div class="group">
      <h2 class="section-title"><span class="dot moon"></span>{{ TERMS.landmark }}</h2>
      <div class="row">
        <div class="seg" role="group" aria-label="Body">
          <button type="button" :aria-pressed="s.body === 'moon'" @click="s.selectBody('moon')">
            Moon
          </button>
          <button type="button" :aria-pressed="s.body === 'mars'" @click="s.selectBody('mars')">
            Mars
          </button>
        </div>
        <select
          :value="customPoint ? 'custom' : selectedId"
          :aria-label="TERMS.landmark"
          data-test="landmark-select"
          :class="{ 'tutorial-highlight': tutorialActive }"
          @change="onLandmark"
        >
          <option v-if="customPoint" value="custom" disabled>{{ customPoint }}</option>
          <option v-for="t in landmarks" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
      </div>
      <p class="meta">
        {{ FOOTPRINT_SHORT }} · or click {{ s.view === '2d' ? 'the map' : 'a dot on the globe' }}
      </p>
    </div>
    <div class="group">
      <h2 class="section-title">{{ TERMS.focus }}</h2>
      <div class="pills" role="group" :aria-label="TERMS.focus">
        <button
          v-for="id in LENS_IDS"
          :key="id"
          type="button"
          :title="lensTitle(id)"
          :disabled="s.lensDisabled(id)"
          :aria-pressed="s.lens === id"
          :data-test="`lens-${id}`"
          @click="s.setLens(id)"
        >
          {{ LENS_SHORT[id] }}
        </button>
      </div>
      <LensControls />
    </div>
  </section>
</template>

<style scoped>
.tutorial-highlight {
  outline: 2px solid var(--accent-earth);
  outline-offset: 4px;
  box-shadow: 0 0 0 6px rgba(79, 195, 247, 0.12);
}
.controls {
  display: grid;
  gap: var(--s4);
  padding: var(--s4);
  border-bottom: 1px solid var(--border);
}
.group {
  display: grid;
  gap: var(--s2);
}
.row {
  display: flex;
  gap: var(--s2);
}
.row select {
  flex: 1;
  width: 0; /* else the longest landmark name sets the panel's width */
}
.seg {
  flex: none;
}
p {
  margin: 0;
}
.pills {
  display: flex;
  gap: var(--s1);
}
.pills button {
  flex: 1;
  min-width: 0;
  padding-inline: var(--s1);
  font-size: var(--fs-meta);
  color: var(--text-muted);
  background: none;
}
/* selection is a surface step, not accent: the accent is kept for the score */
.pills button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.pills button[aria-pressed='true'],
.seg button[aria-pressed='true'] {
  color: var(--text);
  background: var(--surface-2);
  border-color: var(--text-muted);
}
</style>
