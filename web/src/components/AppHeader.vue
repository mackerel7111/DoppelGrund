<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useSession } from '../stores/session';
import {
  FOOTPRINT_SHORT,
  LENS_NAMES,
  LENS_SHORT,
  SYNTHETIC_BANNER,
  TERMS,
} from '../content/labels';
import { formatLatLon } from '../stores/selectors';
import { LENS_IDS, type Body, type LensId } from '../data/types';
import LensControls from './LensControls.vue';
import LayerToggles from './LayerToggles.vue';

type PopoverId = 'target' | 'focus' | 'layers' | null;

const s = useSession();
const openPopover = ref<PopoverId>(null);
const navRef = ref<HTMLElement | null>(null);

const bodyLabel = computed(() => (s.body === 'moon' ? 'Moon' : 'Mars'));
const bodyTargets = computed(() => (s.bundle?.targets ?? []).filter((t) => t.body === s.body));

const selectedLandmarkObj = computed(() => {
  const t = s.target;
  if (!t || t.kind !== 'landmark' || !s.bundle) return null;
  return s.bundle.targets.find((x) => x.id === t.id) ?? null;
});

const selectedCoords = computed(() => {
  const t = s.target;
  if (!t) return null;
  if (t.kind === 'landmark') {
    const lm = selectedLandmarkObj.value;
    return lm ? formatLatLon(lm.lat, lm.lon) : null;
  }
  const ll = s.bundle?.discs[t.body]?.latlon;
  if (!ll) return null;
  return formatLatLon(ll[t.discIndex * 2], ll[t.discIndex * 2 + 1]);
});

const targetSummary = computed(() => {
  const lm = selectedLandmarkObj.value;
  if (lm) {
    return `${lm.name} (${formatLatLon(lm.lat, lm.lon)})`;
  }
  if (s.target?.kind === 'disc') {
    return selectedCoords.value
      ? `${TERMS.customPoint} (${selectedCoords.value})`
      : TERMS.customPoint;
  }
  return 'Select landmark';
});

const focusSummary = computed(() => (s.lens === 'custom' ? LENS_NAMES.custom : LENS_SHORT[s.lens]));

const activeLayerCount = computed(() => Object.values(s.layers).filter(Boolean).length);

const targetSelectValue = computed(() => {
  if (!s.target) return '';
  return s.target.kind === 'landmark' ? s.target.id : '__disc__';
});

function togglePopover(id: Exclude<PopoverId, null>): void {
  openPopover.value = openPopover.value === id ? null : id;
}

function closePopovers(): void {
  openPopover.value = null;
}

function onSelectBody(b: Body): void {
  s.selectBody(b);
}

function onSelectLandmark(ev: Event): void {
  const id = (ev.target as HTMLSelectElement).value;
  if (id && id !== '__disc__') {
    s.selectLandmark(id);
    closePopovers();
  }
}

function onSelectLens(id: LensId): void {
  if (!s.lensDisabled(id)) {
    s.setLens(id);
  }
}

function onDocPointerDown(ev: PointerEvent): void {
  if (!openPopover.value || !navRef.value) return;
  if (!navRef.value.contains(ev.target as Node)) {
    closePopovers();
  }
}

function onKeyDown(ev: KeyboardEvent): void {
  if (ev.key === 'Escape' && openPopover.value) {
    closePopovers();
  }
}

watch(
  () => s.aboutOpen,
  (isAbout) => {
    if (isAbout) closePopovers();
  },
);

onMounted(() => {
  window.addEventListener('pointerdown', onDocPointerDown);
  window.addEventListener('keydown', onKeyDown);
});

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', onDocPointerDown);
  window.removeEventListener('keydown', onKeyDown);
});
</script>

<template>
  <header class="hdr" role="banner">
    <div class="brand-group">
      <span class="title">DoppelGrund</span>
      <span v-if="s.synthetic === true" class="synth-pill" :title="SYNTHETIC_BANNER">
        Synthetic data
      </span>
    </div>

    <nav
      v-if="!s.aboutOpen && s.bundle"
      ref="navRef"
      class="hud-steps"
      aria-label="Explorer controls"
    >
      <div class="step-wrap">
        <button
          type="button"
          class="step-pill"
          :class="{ open: openPopover === 'target' }"
          :aria-expanded="openPopover === 'target'"
          data-test="hud-step-target"
          @click="togglePopover('target')"
        >
          <span class="step-num">1. Target:</span>
          <span class="step-val">{{ bodyLabel }} &middot; {{ targetSummary }}</span>
          <span class="chev" aria-hidden="true">&#9662;</span>
        </button>

        <div
          v-if="openPopover === 'target'"
          class="popover popover-target"
          role="dialog"
          aria-label="Target selection"
        >
          <div class="pop-head">
            <span class="pop-title">1. Target world &amp; region</span>
            <button type="button" class="pop-close" aria-label="Close" @click="closePopovers">
              &times;
            </button>
          </div>
          <div class="seg body-seg" role="group" aria-label="Target world">
            <button
              type="button"
              :aria-pressed="s.body === 'moon'"
              data-test="body-moon"
              @click="onSelectBody('moon')"
            >
              Moon
            </button>
            <button
              type="button"
              :aria-pressed="s.body === 'mars'"
              data-test="body-mars"
              @click="onSelectBody('mars')"
            >
              Mars
            </button>
          </div>

          <label class="field-label" for="hud-landmark-select">{{ TERMS.landmark }}</label>
          <select
            id="hud-landmark-select"
            data-test="hud-landmark-select"
            :value="targetSelectValue"
            @change="onSelectLandmark"
          >
            <option v-if="s.target?.kind === 'disc'" value="__disc__">
              {{ TERMS.customPoint }}{{ selectedCoords ? ` ${selectedCoords}` : '' }}
            </option>
            <option v-for="t in bodyTargets" :key="t.id" :value="t.id">
              {{ t.name }} ({{ formatLatLon(t.lat, t.lon) }})
            </option>
          </select>

          <p v-if="selectedLandmarkObj?.notes" class="pop-note">
            {{ selectedLandmarkObj.notes }}
          </p>
          <p class="pop-hint">
            {{ FOOTPRINT_SHORT }}. Click anywhere on the left globe to pick a custom disc.
          </p>
        </div>
      </div>

      <div class="step-wrap">
        <button
          type="button"
          class="step-pill"
          :class="{ open: openPopover === 'focus' }"
          :aria-expanded="openPopover === 'focus'"
          data-test="hud-step-focus"
          @click="togglePopover('focus')"
        >
          <span class="step-num">2. Focus:</span>
          <span class="step-val">{{ focusSummary }}</span>
          <span class="chev" aria-hidden="true">&#9662;</span>
        </button>

        <div
          v-if="openPopover === 'focus'"
          class="popover popover-focus"
          role="dialog"
          aria-label="Mission focus and weights"
        >
          <div class="pop-head">
            <span class="pop-title">2. {{ TERMS.focus }}</span>
            <button type="button" class="pop-close" aria-label="Close" @click="closePopovers">
              &times;
            </button>
          </div>
          <div class="lens-pills" role="group" aria-label="Mission focus presets">
            <button
              v-for="id in LENS_IDS"
              :key="id"
              type="button"
              class="pill"
              :disabled="s.lensDisabled(id)"
              :aria-pressed="s.lens === id"
              :title="LENS_NAMES[id]"
              :data-test="`hud-lens-${id}`"
              @click="onSelectLens(id)"
            >
              {{ LENS_SHORT[id] }}
            </button>
          </div>
          <LensControls />
        </div>
      </div>

      <div class="step-wrap">
        <button
          type="button"
          class="step-pill"
          :class="{ open: openPopover === 'layers' }"
          :aria-expanded="openPopover === 'layers'"
          data-test="hud-step-layers"
          @click="togglePopover('layers')"
        >
          <span class="step-num">3. Layers</span>
          <span v-if="activeLayerCount > 0" class="layer-count">{{ activeLayerCount }}</span>
          <span class="chev" aria-hidden="true">&#9662;</span>
        </button>

        <div
          v-if="openPopover === 'layers'"
          class="popover popover-layers"
          role="dialog"
          aria-label="Map overlay layers"
        >
          <div class="pop-head">
            <span class="pop-title">3. Overlay layers</span>
            <button type="button" class="pop-close" aria-label="Close" @click="closePopovers">
              &times;
            </button>
          </div>
          <LayerToggles />
        </div>
      </div>
    </nav>

    <div class="right-controls">
      <div v-if="!s.aboutOpen" class="seg" role="group" aria-label="View mode">
        <button type="button" :aria-pressed="s.view === '3d'" @click="s.setView('3d')">3D</button>
        <button type="button" :aria-pressed="s.view === '2d'" @click="s.setView('2d')">2D</button>
      </div>
      <button
        type="button"
        class="about-btn"
        :aria-pressed="s.aboutOpen"
        data-test="about-btn"
        @click="s.aboutOpen = !s.aboutOpen"
      >
        {{ s.aboutOpen ? '\u2190 Back to Explorer' : 'About' }}
      </button>
    </div>
  </header>
</template>

<style scoped>
.hdr {
  grid-column: 1 / -1;
  grid-row: 1;
  position: relative;
  z-index: 30;
  pointer-events: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s3);
  margin: var(--s2) var(--s3) 0;
  padding: 6px var(--s3);
  background: rgba(11, 14, 19, 0.84);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
}

.brand-group {
  display: flex;
  align-items: center;
  gap: var(--s2);
  flex-shrink: 0;
}

.title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text);
}

.synth-pill {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  color: var(--accent-warn);
  background: rgba(242, 169, 59, 0.12);
  border: 1px solid rgba(242, 169, 59, 0.35);
}

.hud-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--s2);
  flex-wrap: wrap;
}

.step-wrap {
  position: relative;
}

.step-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: var(--text);
  font-size: 12.5px;
  line-height: 1.3;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.step-pill:hover,
.step-pill.open {
  background: rgba(102, 217, 239, 0.12);
  border-color: rgba(102, 217, 239, 0.55);
}

.step-num {
  color: var(--text-muted, #94a3b8);
  font-weight: 500;
}

.step-val {
  color: var(--text);
  font-weight: 500;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.layer-count {
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(102, 217, 239, 0.2);
  color: var(--accent-earth);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.chev {
  font-size: 10px;
  color: var(--text-muted, #94a3b8);
}

.popover {
  position: absolute;
  top: calc(100% + 10px);
  left: 0;
  z-index: 35;
  background: rgba(12, 16, 23, 0.96);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 12px;
  padding: var(--s3);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.65);
  display: grid;
  gap: var(--s2);
}

.popover-target {
  width: min(330px, 88vw);
}

.popover-focus {
  width: min(340px, 90vw);
}

.popover-layers {
  width: min(290px, 88vw);
  left: auto;
  right: 0;
}

.pop-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s2);
}

.pop-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--text-muted, #94a3b8);
}

.pop-close {
  background: transparent;
  border: none;
  color: var(--text-muted, #94a3b8);
  font-size: 16px;
  line-height: 1;
  padding: 2px 6px;
  cursor: pointer;
}

.pop-close:hover {
  color: var(--text);
}

.field-label {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}

select {
  width: 100%;
  padding: 6px 8px;
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text);
  border: 1px solid var(--border);
  font-size: 13px;
}

.pop-note {
  margin: 0;
  font-size: 12px;
  color: var(--text);
  line-height: 1.45;
}

.pop-hint {
  margin: 0;
  font-size: 11.5px;
  color: var(--text-muted, #94a3b8);
  line-height: 1.4;
}

.lens-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pill {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: var(--text);
  cursor: pointer;
}

.pill[aria-pressed='true'] {
  background: rgba(102, 217, 239, 0.16);
  border-color: var(--accent-earth);
  color: var(--accent-earth);
}

.pill:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.right-controls {
  display: flex;
  align-items: center;
  gap: var(--s2);
  flex-shrink: 0;
}

.seg {
  display: inline-flex;
  border-radius: 999px;
  padding: 2px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.seg button {
  padding: 3px 10px;
  border-radius: 999px;
  border: none;
  background: transparent;
  color: var(--text-muted, #94a3b8);
  font-size: 12px;
  cursor: pointer;
}

.seg button[aria-pressed='true'] {
  background: rgba(255, 255, 255, 0.14);
  color: var(--text);
  font-weight: 500;
}

.about-btn {
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: var(--text);
  font-size: 12.5px;
  cursor: pointer;
}

.about-btn:hover,
.about-btn[aria-pressed='true'] {
  border-color: var(--accent-earth);
  background: rgba(102, 217, 239, 0.12);
}

@media (max-width: 960px) {
  .hdr {
    flex-wrap: wrap;
    row-gap: var(--s2);
  }
  .hud-steps {
    order: 3;
    width: 100%;
    justify-content: flex-start;
  }
  .step-val {
    max-width: 180px;
  }
}
</style>
