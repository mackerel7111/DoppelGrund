<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue';
import AppHeader from './components/AppHeader.vue';
import StatusBar from './components/StatusBar.vue';
import BottomMatchDock from './components/BottomMatchDock.vue';
import SiteDetailsModal from './components/SiteDetailsModal.vue';
import AboutDialog from './components/AboutDialog.vue';
import StoryIntro from './components/StoryIntro.vue';
import ExplorerTutorial from './components/ExplorerTutorial.vue';
import { useSession } from './stores/session';
import type { Body } from './data/types';

const TargetPanel = defineAsyncComponent(() => import('./components/TargetPanel.vue'));
const EarthMap = defineAsyncComponent(() => import('./components/EarthMap.vue'));
const loadGlobe = () => import('./components/GlobeView.vue');
const GlobeView = defineAsyncComponent(loadGlobe);

const s = useSession();
if (s.view === '3d') void loadGlobe(); // fetch the 3D chunk while the data loads
const nHex = computed(() => s.bundle?.manifest.n_hex ?? null);
const debug = new URLSearchParams(window.location.search).has('debug');
const detailsOpen = ref(false);
function markerGuidanceWanted(): boolean {
  try {
    return localStorage.getItem('doppelgrund.markerGuidanceSeen') !== '1';
  } catch {
    return true;
  }
}
const markerGuidance = ref(markerGuidanceWanted());
function dismissMarkerGuidance(): void {
  markerGuidance.value = false;
  try {
    localStorage.setItem('doppelgrund.markerGuidanceSeen', '1');
  } catch {
    /* remember for this visit */
  }
}
function openSelectedDetails(): void {
  dismissMarkerGuidance();
  detailsOpen.value = true;
}
function openMarkerDetails(row: number): void {
  s.selectRow(row);
  openSelectedDetails();
}
const detailsVisible = computed(
  () =>
    detailsOpen.value &&
    s.selectedRow !== null &&
    !s.introOpen &&
    !s.aboutOpen &&
    s.loading.phase === 'ready',
);

// Always begin with the welcome page, including returning visits and refreshes.
s.introOpen = true;
function tutorialWanted(): boolean {
  try {
    return localStorage.getItem('doppelgrund.tutorialSeen') !== '1';
  } catch {
    return true;
  }
}
const tutorialRequested = ref(tutorialWanted());
const tutorialVisible = computed(
  () => tutorialRequested.value && s.loading.phase === 'ready' && !s.introOpen && !s.aboutOpen,
);
function closeTutorial(): void {
  tutorialRequested.value = false;
  try {
    localStorage.setItem('doppelgrund.tutorialSeen', '1');
  } catch {
    /* The tutorial remains one-time for this visit in private mode. */
  }
}
// open on a result, not an empty globe: first landmark of the current body
function selectFirstLandmark(): void {
  const first = s.bundle?.targets.find((t) => t.body === s.body);
  if (!s.target && first) s.selectLandmark(first.id);
}

function onIntroDone(world: Body): void {
  s.introOpen = false;
  s.selectBody(world);
  selectFirstLandmark(); // no-op until the bundle is ready; the watch below covers that order
}

watch(
  () => s.loading.phase,
  (p) => {
    if (p !== 'ready') return;
    void s.ensureLayer('known_sites');
    selectFirstLandmark();
  },
);

// Auto-select the #1 predicted ideal Earth location whenever a fresh ranking arrives and nothing is selected.
watch(
  () => s.result?.version,
  () => {
    if (!s.result || s.selectedRow !== null) return;
    const best = s.result.cards.find((c) => c.row !== null);
    if (best && best.row !== null) {
      s.selectRow(best.row);
    }
  },
  { immediate: true },
);

watch([() => s.selectedRow, () => s.aboutOpen, () => s.introOpen], ([row, isAbout, isIntro]) => {
  if (row === null || isAbout || isIntro) detailsOpen.value = false;
});

watch(
  () => s.target,
  () => {
    detailsOpen.value = false;
  },
);

function onGlobeFallback(reason: string): void {
  s.setView('2d');
  s.notice = `3D view unavailable (${reason}), showing the 2D view.`;
}

const progressPct = computed(() =>
  s.loading.total > 0 ? Math.round((100 * s.loading.done) / s.loading.total) : 0,
);
</script>

<template>
  <div class="app">
    <AppHeader :tutorial-active="tutorialVisible" />
    <div v-if="s.notice" class="notice" role="status">
      {{ s.notice }}
      <button type="button" class="tab" aria-label="Dismiss notice" @click="s.notice = null">
        ✕
      </button>
    </div>

    <AboutDialog v-if="s.aboutOpen" />
    <main v-else-if="s.loading.phase === 'error'" class="state" role="alert">
      <h2>Could not load the data bundle</h2>
      <p class="num">{{ s.loading.error }}</p>
      <p class="meta">Check the data bundle and reload.</p>
    </main>
    <main v-else-if="s.loading.phase !== 'ready'" class="state">
      <h2>Loading Earth data...</h2>
      <progress :value="s.loading.done" :max="Math.max(1, s.loading.total)" aria-label="Loading">
        {{ progressPct }}%
      </progress>
      <p class="meta num">{{ s.loading.done }} / {{ s.loading.total || '?' }} files</p>
    </main>
    <div v-else class="explorer-workspace" :class="{ inspecting: detailsVisible }">
      <div class="explorer-canvas">
        <div v-if="s.view === '3d'" class="globe-layer">
          <GlobeView
            :show-marker-hint="
              markerGuidance && !tutorialVisible && !detailsVisible && !s.introOpen && !s.aboutOpen
            "
            @dismiss-marker-hint="dismissMarkerGuidance"
            @fallback="onGlobeFallback"
            @view-details="openMarkerDetails"
          />
        </div>
        <div v-else class="maps">
          <section class="panel" aria-label="Target body map">
            <div class="panel-title">Target</div>
            <TargetPanel />
          </section>
          <section class="panel" aria-label="Earth map">
            <div class="panel-title">Earth</div>
            <EarthMap @view-details="openMarkerDetails" />
          </section>
        </div>
        <button
          v-if="!detailsVisible"
          type="button"
          class="details-launcher"
          data-test="view-details"
          :disabled="s.selectedRow === null"
          @click="openSelectedDetails"
        >
          View details →
        </button>
        <BottomMatchDock />
      </div>
      <SiteDetailsModal
        v-if="detailsVisible && s.selectedRow !== null"
        :row="s.selectedRow"
        @close="detailsOpen = false"
      />
    </div>

    <ExplorerTutorial v-if="tutorialVisible" :body="s.body" @close="closeTutorial" />
    <Transition name="intro-out">
      <StoryIntro v-if="s.introOpen" @done="onIntroDone" />
    </Transition>

    <StatusBar v-if="debug" :synthetic="s.synthetic" :n-hex="nHex" :timings="s.timings" />
  </div>
</template>

<style scoped>
.details-launcher {
  position: absolute;
  top: 12px;
  right: 16px;
  z-index: 4;
  min-height: 44px;
  padding: 10px 18px;
  border: 1px solid var(--accent-earth);
  border-radius: 12px;
  background: #101b2af5;
  color: var(--accent-earth);
  pointer-events: auto;
}

.explorer-workspace {
  grid-row: 2;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  pointer-events: none;
}
.explorer-workspace.inspecting {
  grid-template-columns: minmax(0, 1fr) 420px;
}
.explorer-canvas {
  position: relative;
  min-width: 0;
  min-height: 0;
  height: 100%;
}
@media (max-width: 899px) {
  .explorer-workspace.inspecting {
    grid-template-columns: minmax(0, 1fr);
  }
}

.app {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: auto minmax(0, 1fr);
  height: 100%;
  pointer-events: none; /* only the UI pieces below take events; the rest reaches the globe */
}
/* the header sets its own z-index (30) so its popovers sit above the briefing card */
.maps,
.state {
  position: relative;
  z-index: 1;
}
.app > footer {
  position: fixed;
  inset: auto 0 0;
  z-index: 2;
  pointer-events: auto;
}
.app > header,
.state {
  grid-column: 1 / -1;
}
.state {
  display: grid;
  place-content: center;
  gap: var(--s3);
  padding: var(--s6);
  text-align: center;
  pointer-events: auto;
}
.state progress {
  width: 320px;
  accent-color: var(--accent-earth);
}
.globe-layer {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: auto;
}
.maps {
  grid-column: 1 / -1;
  grid-row: 2;
  display: grid;
  grid-template-columns: 2fr 3fr;
  gap: var(--s3);
  margin: var(--s2) var(--s3) var(--s3);
  height: calc(100% - var(--s2) - var(--s3));
  padding-bottom: 80px;
  min-height: 0;
  pointer-events: auto;
}
.notice {
  position: fixed;
  bottom: 76px; /* above the dock: 12 inset + 50 tall + 14 */
  left: 50%;
  transform: translateX(-50%);
  z-index: 25;
  display: flex;
  gap: var(--s3);
  align-items: center;
  padding: var(--s1) var(--s3);
  background: var(--surface-2);
  border: 1px solid var(--danger);
  border-radius: var(--radius-control);
  pointer-events: auto;
}
@media (max-width: 1099px) {
  .maps {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }
  .maps .panel {
    height: 400px;
  }
}
.intro-out-leave-active {
  transition: opacity 300ms var(--ease);
}
.intro-out-leave-to {
  opacity: 0;
}
</style>
