<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useSession } from '../stores/session';
import {
  FOOTPRINT_SHORT,
  GROUP_NAMES,
  LENS_NAMES,
  LENS_SHORT,
  PARTIAL_LABEL,
  SYNTHETIC_BANNER,
  partialNotice,
  partialShort,
  TERMS,
} from '../content/labels';
import { formatLatLon } from '../stores/selectors';
import { GROUP_IDS, LENS_IDS, type Body, type LensId } from '../data/types';
import LensControls from './LensControls.vue';
import LayerToggles from './LayerToggles.vue';

type PopoverId = 'target' | 'focus' | 'layers' | 'partial' | null;

defineProps<{ tutorialActive?: boolean }>();
const s = useSession();
const openPopover = ref<PopoverId>(null);
const navRef = ref<HTMLElement | null>(null);
const rightRef = ref<HTMLElement | null>(null);

const bodyLabel = computed(() => (s.body === 'moon' ? 'Moon' : 'Mars'));
const partial = computed(() => partialNotice(s.bundle?.manifest.resolution));
const partialReason = computed(() => partialShort(s.bundle?.manifest.resolution));

function openAbout(section: string): void {
  s.aboutSection = section;
  s.aboutOpen = true;
}

/** Disabled presets say which data they wait for (same rule as ControlPanel). */
function lensTitle(id: LensId): string {
  if (!s.lensDisabled(id)) return LENS_NAMES[id];
  const need = GROUP_IDS.filter((g) => s.presets[id][g] > 0 && !s.available[g]);
  const where = s.body === 'moon' ? 'the Moon' : 'Mars';
  return `Needs ${need.map((g) => GROUP_NAMES[g]).join(' / ')} data, not available for ${where} yet`;
}

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
  if (!openPopover.value) return;
  const t = ev.target as Node;
  if (!navRef.value?.contains(t) && !rightRef.value?.contains(t)) closePopovers();
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
  <header class="hdr hud" role="banner">
    <span class="title">DoppelGrund</span>

    <nav
      v-if="!s.aboutOpen && s.bundle"
      ref="navRef"
      class="cluster"
      aria-label="Explorer controls"
    >
      <div class="step-wrap">
        <button
          type="button"
          class="tab step"
          :class="{ 'tutorial-highlight': tutorialActive }"
          :aria-expanded="openPopover === 'target'"
          data-test="hud-step-target"
          @click="togglePopover('target')"
        >
          <span class="step-num">Target</span>
          <span class="step-val">{{ bodyLabel }} &middot; {{ targetSummary }}</span>
          <span class="chev" aria-hidden="true">&#9662;</span>
        </button>

        <div
          v-if="openPopover === 'target'"
          class="popover hud popover-target"
          role="dialog"
          aria-label="Target selection"
        >
          <div class="pop-head">
            <span class="pop-title">Target world and region</span>
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

      <span class="cluster-div" aria-hidden="true" />

      <div class="step-wrap">
        <button
          type="button"
          class="tab step"
          :aria-expanded="openPopover === 'focus'"
          data-test="hud-step-focus"
          @click="togglePopover('focus')"
        >
          <span class="step-num">Focus</span>
          <span class="step-val">{{ focusSummary }}</span>
          <span class="chev" aria-hidden="true">&#9662;</span>
        </button>

        <div
          v-if="openPopover === 'focus'"
          class="popover hud popover-focus"
          role="dialog"
          aria-label="Mission focus and weights"
        >
          <div class="pop-head">
            <span class="pop-title">{{ TERMS.focus }}</span>
            <button type="button" class="pop-close" aria-label="Close" @click="closePopovers">
              &times;
            </button>
          </div>
          <div class="lens-pills" role="group" aria-label="Mission focus presets">
            <button
              v-for="id in LENS_IDS"
              :key="id"
              type="button"
              class="tab"
              :disabled="s.lensDisabled(id)"
              :aria-pressed="s.lens === id"
              :title="lensTitle(id)"
              :data-test="`hud-lens-${id}`"
              @click="onSelectLens(id)"
            >
              {{ LENS_SHORT[id] }}
            </button>
          </div>
          <LensControls />
        </div>
      </div>

      <span class="cluster-div" aria-hidden="true" />

      <div class="step-wrap">
        <button
          type="button"
          class="tab step"
          :aria-expanded="openPopover === 'layers'"
          data-test="hud-step-layers"
          @click="togglePopover('layers')"
        >
          <span class="step-num">Layers</span>
          <span v-if="activeLayerCount > 0" class="step-val num">{{ activeLayerCount }} on</span>
          <span class="chev" aria-hidden="true">&#9662;</span>
        </button>

        <div
          v-if="openPopover === 'layers'"
          class="popover hud popover-layers"
          role="dialog"
          aria-label="Map overlay layers"
        >
          <div class="pop-head">
            <span class="pop-title">Overlay layers</span>
            <button type="button" class="pop-close" aria-label="Close" @click="closePopovers">
              &times;
            </button>
          </div>
          <LayerToggles />
        </div>
      </div>
    </nav>

    <div ref="rightRef" class="right-controls">
      <span v-if="s.synthetic === true" class="tag warn" :title="SYNTHETIC_BANNER">
        Synthetic data
      </span>
      <div v-else-if="partial" class="step-wrap">
        <button
          type="button"
          class="tag warn"
          :aria-expanded="openPopover === 'partial'"
          aria-controls="partial-popover"
          data-test="partial-badge"
          @click="togglePopover('partial')"
        >
          {{ PARTIAL_LABEL
          }}<span v-if="partialReason" class="partial-reason"
            >&nbsp;&middot; {{ partialReason }}</span
          >
        </button>
        <div
          v-if="openPopover === 'partial'"
          id="partial-popover"
          class="popover hud popover-partial"
          role="dialog"
          aria-label="What partial data means"
        >
          <div class="pop-head">
            <span class="pop-title">{{ PARTIAL_LABEL }}</span>
            <button type="button" class="pop-close" aria-label="Close" @click="closePopovers">
              &times;
            </button>
          </div>
          <p class="pop-note">This build is a sample: {{ partial }}.</p>
          <p v-if="s.bundle?.manifest.resolution?.mode === 'fast'" class="pop-hint">
            Earth terrain comes from 470 m overview levels instead of 30 m elevation models.
          </p>
          <p v-if="(s.bundle?.manifest.resolution?.stride ?? 1) > 1" class="pop-hint">
            Only some land hexagons are computed, so a better match may sit in a skipped one.
          </p>
          <button
            type="button"
            class="tab pop-link"
            data-test="partial-sources"
            @click="openAbout('sources')"
          >
            Data sources &rarr;
          </button>
        </div>
      </div>

      <div v-if="!s.aboutOpen" class="seg" role="group" aria-label="View mode">
        <button type="button" :aria-pressed="s.view === '3d'" @click="s.setView('3d')">3D</button>
        <button type="button" :aria-pressed="s.view === '2d'" @click="s.setView('2d')">2D</button>
      </div>
      <button
        v-if="!s.aboutOpen"
        id="explorer-back"
        type="button"
        class="tab"
        aria-label="Back to introduction"
        :disabled="s.introOpen"
        @click="s.introOpen = true"
      >
        &larr; Intro
      </button>
      <button
        type="button"
        class="tab"
        :aria-pressed="s.aboutOpen"
        data-test="about-btn"
        @click="s.aboutOpen = !s.aboutOpen"
      >
        {{ s.aboutOpen ? '← Back to Explorer' : 'About' }}
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
  gap: var(--s4);
  margin: var(--s2) var(--s3) 0;
  padding: var(--s2) var(--s3);
}

.title {
  flex-shrink: 0;
  font-size: var(--fs-card);
  font-weight: 500;
  color: var(--text);
}

/* Target / Focus / Layers read as one instrument: shared frame, hairline dividers */
.cluster {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--border);
  border-radius: calc(var(--radius-control) + 2px);
  background: color-mix(in srgb, var(--surface) 60%, transparent);
}

.cluster-div {
  flex: none;
  width: 1px;
  height: 16px;
  background: var(--border);
}

.step-wrap {
  position: relative;
}

.step-num {
  color: var(--text-muted);
}

.step-val {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text);
  font-weight: 500;
}

.chev {
  font-size: 10px;
  color: var(--text-muted);
}

.tutorial-highlight {
  outline: 2px solid var(--accent-earth);
  outline-offset: 4px;
  box-shadow: 0 0 0 6px color-mix(in srgb, var(--accent-earth) 12%, transparent);
}

.popover {
  position: absolute;
  top: calc(100% + var(--s4)); /* clears the header's bottom edge */
  left: 0;
  z-index: 35;
  display: grid;
  gap: var(--s2);
  padding: var(--s3);
  background: color-mix(in srgb, var(--bg) 94%, transparent);
}

.popover-target {
  width: min(336px, 88vw);
}

.popover-focus {
  width: min(344px, 90vw);
}

.popover-layers {
  width: min(288px, 88vw);
  left: auto;
  right: 0;
}

.popover-partial {
  width: min(320px, 88vw);
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
  font-size: var(--fs-meta);
  font-weight: 500;
  color: var(--text-muted);
}

.pop-close {
  display: inline-grid;
  place-items: center;
  width: 24px;
  min-height: 24px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  font-size: 16px;
  line-height: 1;
}

.pop-close:hover {
  background: var(--surface-2);
  color: var(--text);
}

.field-label {
  font-size: var(--fs-meta);
  color: var(--text-muted);
}

select {
  width: 100%;
  font-size: var(--fs-meta);
  color: var(--text);
}

.pop-note {
  margin: 0;
  font-size: var(--fs-meta);
  color: var(--text);
}

.pop-hint {
  margin: 0;
  font-size: var(--fs-meta);
  color: var(--text-muted);
}

.pop-link {
  justify-self: start;
  border-color: var(--border);
  color: var(--accent-earth);
}

.lens-pills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s1);
}

.right-controls {
  display: flex;
  align-items: center;
  gap: var(--s2);
  flex-shrink: 0;
}

.seg {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--border);
  border-radius: calc(var(--radius-control) + 2px);
  background: color-mix(in srgb, var(--surface) 60%, transparent);
}

.seg button {
  min-height: 28px;
  padding: 0 var(--s3);
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: var(--fs-meta);
}

.seg button:hover {
  color: var(--text);
  background: var(--surface-2);
}

.seg button[aria-pressed='true'] {
  background: var(--surface-2);
  color: var(--text);
  box-shadow: inset 0 -2px 0 var(--accent-earth);
}

@media (max-width: 1199px) {
  .hdr {
    flex-wrap: wrap;
    row-gap: var(--s2);
  }
  .cluster {
    order: 3;
    max-width: 100%;
    flex-wrap: wrap; /* not overflow: that would clip the popovers */
  }
  .step-val {
    max-width: 160px;
  }
}

@media (max-width: 900px) {
  .partial-reason {
    display: none;
  }
}
</style>
