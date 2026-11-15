<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useSession } from '../stores/session';
import { partialNotice } from '../content/labels';

interface WheelSection {
  id: string;
  label: string;
  shortLabel: string;
  badge: string;
}

const SECTIONS: WheelSection[] = [
  { id: 'compared', label: 'What is compared', shortLabel: 'Compared', badge: '5 Physical Traits' },
  { id: 'scoring', label: 'How scoring works', shortLabel: 'Scoring', badge: 'Similarity Math' },
  { id: 'labelling', label: 'Honest labelling', shortLabel: 'Methods', badge: 'Transparency' },
  { id: 'validation', label: 'Validation', shortLabel: 'Validation', badge: 'Rediscovery' },
  { id: 'sources', label: 'Data sources', shortLabel: 'Sources', badge: 'Traceability' },
  { id: 'limitations', label: 'Limitations', shortLabel: 'Limits', badge: 'Caveats' },
];

const s = useSession();
const activeIndex = ref(0);
const rotationDeg = ref(0);

const stepAngle = 360 / SECTIONS.length;
const activeSection = computed(() => SECTIONS[activeIndex.value]);
const partial = computed(() => partialNotice(s.bundle?.manifest.resolution));
const formattedIndex = computed(() => String(activeIndex.value + 1).padStart(2, '0'));

function selectSection(index: number): void {
  const n = SECTIONS.length;
  const normalizedIndex = ((index % n) + n) % n;
  const targetMod = (((-normalizedIndex * stepAngle) % 360) + 360) % 360;
  const currentMod = ((rotationDeg.value % 360) + 360) % 360;
  let delta = targetMod - currentMod;
  if (delta > 180) delta -= 360;
  if (delta < -180) delta += 360;
  rotationDeg.value += delta;
  activeIndex.value = normalizedIndex;
}

function spinBy(step: number): void {
  selectSection(activeIndex.value + step);
}

function nodeStyle(index: number): Record<string, string> {
  const angle = index * stepAngle;
  return {
    transform: `rotate(${angle}deg) translate(var(--orbit-r)) rotate(${-angle}deg)`,
  };
}

function onWheelScroll(ev: WheelEvent): void {
  if (Math.abs(ev.deltaY) < 8) return;
  ev.preventDefault();
  spinBy(ev.deltaY > 0 ? 1 : -1);
}

function closeAbout(): void {
  s.aboutOpen = false;
}

function replay(): void {
  s.aboutOpen = false;
  s.introOpen = true;
}

function onKey(ev: KeyboardEvent): void {
  if (ev.key === 'Escape') closeAbout();
  if (ev.key === 'ArrowRight' || ev.key === 'ArrowDown') spinBy(1);
  if (ev.key === 'ArrowLeft' || ev.key === 'ArrowUp') spinBy(-1);
}

onMounted(() => {
  window.addEventListener('keydown', onKey);
  const wanted = SECTIONS.findIndex((x) => x.id === s.aboutSection);
  if (wanted >= 0) selectSection(wanted); // e.g. the header's "Partial data" pill opens Sources
  s.aboutSection = null;
});
onBeforeUnmount(() => window.removeEventListener('keydown', onKey));
</script>

<template>
  <section class="about-page" aria-labelledby="about-title">
    <div class="hero">
      <div class="hero-copy">
        <h2 id="about-title">Find Earth's Closest Matches to the Moon &amp; Mars</h2>
        <p class="hero-sub">
          Pick any landing site on the Moon or Mars. DoppelGrund scans the entire Earth to compare
          terrain, temperatures, ice, and rock, highlighting places nobody has studied and stating
          plainly where each match falls short.
        </p>
      </div>
      <div class="hero-actions">
        <button type="button" class="btn-replay" @click="replay">Replay intro</button>
      </div>
    </div>

    <div class="wheel-layout">
      <div class="wheel-stage" @wheel="onWheelScroll">
        <div class="wheel-ring outer" aria-hidden="true" />
        <div class="wheel-ring inner" aria-hidden="true" />
        <div class="pointer" aria-hidden="true" />

        <div
          class="wheel-rotor"
          :style="{ transform: `rotate(${rotationDeg}deg)` }"
          role="tablist"
          aria-label="About sections"
        >
          <button
            v-for="(sec, i) in SECTIONS"
            :key="sec.id"
            type="button"
            role="tab"
            :aria-selected="activeIndex === i"
            class="orbit-node"
            :class="{ active: activeIndex === i }"
            :style="nodeStyle(i)"
            @click="selectSection(i)"
          >
            <span class="node-inner" :style="{ transform: `rotate(${-rotationDeg}deg)` }">
              <span class="node-dot" />
              <span class="node-label">{{ sec.label }}</span>
            </span>
          </button>
        </div>

        <div class="wheel-hub">
          <div class="hub-count num">{{ formattedIndex }} / 0{{ SECTIONS.length }}</div>
          <div class="hub-title">{{ activeSection.shortLabel }}</div>
          <div class="hub-controls">
            <button type="button" aria-label="Previous section" @click="spinBy(-1)">&#8634;</button>
            <span class="hub-hint">Spin</span>
            <button type="button" aria-label="Next section" @click="spinBy(1)">&#8635;</button>
          </div>
        </div>
      </div>

      <div class="detail-panel" role="tabpanel">
        <div class="detail-head">
          <h3>{{ activeSection.label }}</h3>
          <span class="detail-badge">{{ activeSection.badge }}</span>
        </div>

        <div v-show="activeIndex === 0" class="section-body">
          <p class="lead">
            We divide Earth into hexagons (about 1,770 km&sup2; each) and compare them against 47
            km-wide circular zones (23.7 km radius) around Moon or Mars landmarks across five
            physical traits:
          </p>
          <div class="trait-grid">
            <article class="trait-card">
              <h4>Terrain</h4>
              <p>
                Median and 90th-percentile slope (degrees), elevation spread (m), and share of
                ground with slope below 10&deg;.
              </p>
            </article>
            <article class="trait-card">
              <h4>Thermal</h4>
              <p>
                Mean surface temperature, day-night swing, and annual range (K) using MODIS Terra
                and Diviner bins. Mars thermal is not measured yet.
              </p>
            </article>
            <article class="trait-card">
              <h4>Cold &amp; ice</h4>
              <p>
                Share of samples below 0 &deg;C, Northern Hemisphere permafrost extent, and aridity
                index (P/PET, 0 by definition on Moon and Mars).
              </p>
            </article>
            <article class="trait-card">
              <h4>Composition</h4>
              <p>
                Six-class rock and ice vector (mafic volcanic, felsic/feldspathic, carbonate,
                siliciclastic, evaporite, ice) mapped through a geologic crosswalk.
              </p>
            </article>
            <article class="trait-card">
              <h4>Subsurface</h4>
              <p>
                Catalogued pits and lava tubes per 1,000 km&sup2; (log scale). This is a prior taken
                from catalogues, not a detection: places outside a catalogued area are "not
                measured", never zero, and Mars has no catalogue yet.
              </p>
            </article>
          </div>
          <p class="callout">
            Missing data stays marked "not measured" and lowers data coverage. It is never filled
            with zero or an average. Barren-ground filtering on Earth is a mask applied before
            ranking, never a scored feature.
          </p>
        </div>

        <div v-show="activeIndex === 1" class="section-body">
          <p class="lead">
            Every ranking is computed transparently from unit-bearing measurements right inside your
            browser.
          </p>
          <div class="trait-grid">
            <article class="trait-card">
              <h4>Tolerance Kernel</h4>
              <p>
                Each feature is compared using similarity = exp(-0.5 &middot; z&sup2;), where z is
                the gap divided by a pooled tolerance fitted across Earth, Moon, and Mars.
              </p>
            </article>
            <article class="trait-card">
              <h4>Rock &amp; Ice Distance</h4>
              <p>
                Lithology is scored as one minus the Hellinger distance between smoothed six-class
                composition vectors.
              </p>
            </article>
            <article class="trait-card">
              <h4>Coverage &amp; Focus Presets</h4>
              <p>
                Overall score S (0 to 100) averages features measured on both sides when coverage
                meets the floor. Presets (Balanced, Landing &amp; mobility, Cold regions &amp;
                volatiles, Geology &amp; minerals) adjust trait weights live.
              </p>
            </article>
            <article class="trait-card">
              <h4>Stability &amp; Novelty</h4>
              <p>
                Stability is how often a hexagon stays in the top 1% across perturbed runs. Novelty
                is the distance in km to the nearest documented analogue site.
              </p>
            </article>
          </div>
        </div>

        <div v-show="activeIndex === 2" class="section-body">
          <p class="lead">
            Here is exactly what each component in DoppelGrund uses under the hood:
          </p>
          <table class="data-table">
            <thead>
              <tr>
                <th scope="col">Component</th>
                <th scope="col">What it is</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Tolerance-kernel scoring, match cards, shortlist</td>
                <td>Numerical method, not a trained model</td>
              </tr>
              <tr>
                <td>PCA, GMM, HDBSCAN clustering</td>
                <td>Unsupervised machine learning</td>
              </tr>
              <tr>
                <td>Weight calibration on known site pairs</td>
                <td>Weakly supervised learning on a very small set</td>
              </tr>
              <tr>
                <td>Novelty, stability</td>
                <td>Statistical analysis built on the scores</td>
              </tr>
              <tr>
                <td>Neural networks</td>
                <td>None are used anywhere in DoppelGrund</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-show="activeIndex === 3" class="section-body">
          <p class="lead">
            Validation by rediscovery tests whether documented analogue sites rank highly for the
            Moon and Mars targets they are known for. Results update here once the real pipeline
            runs.
          </p>
          <table class="data-table">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">Result</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Recall of known sites in the top 100 / 500 / 1,000 vs random</td>
                <td class="pending">Pending validation</td>
              </tr>
              <tr>
                <td>Median percentile rank of known sites</td>
                <td class="pending">Pending validation</td>
              </tr>
              <tr>
                <td>Novel candidates (stable, well covered, &ge; 300 km from any known site)</td>
                <td class="pending">Pending validation</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-show="activeIndex === 4" class="section-body">
          <p class="lead">
            Every number on screen traces directly to a physical feature, a dataset, and a version.
          </p>
          <div class="info-list">
            <div class="info-item">
              <h4>Feature Scorecard Traceability</h4>
              <p>
                Open the detailed scorecard on any Earth match to inspect the exact dataset source
                used for each measurement.
              </p>
            </div>
            <div class="info-item">
              <h4>Dataset Registry &amp; Licences</h4>
              <p>
                Full dataset identifiers and licences live in <code>config/datasets.yaml</code> and
                <code>docs/submission/data-sources.md</code>.
              </p>
            </div>
            <div v-if="partial" class="info-item">
              <h4>Partial real data</h4>
              <p>
                This build is a fast-mode sample ({{ partial }}). Earth terrain is read from Earth
                Engine overview levels at 470 m instead of the 30 m elevation models, Earth
                temperature comes from MODIS MOD11A2 only, and only some of the land hexagons are
                computed. The scorecard source lines say the same.
              </p>
            </div>
            <div class="info-item">
              <h4>Synthetic Test Mode</h4>
              <p>
                While the top banner reads "Synthetic data", values come from a seeded fake-data
                generator and do not represent real places.
              </p>
            </div>
          </div>
        </div>

        <div v-show="activeIndex === 5" class="section-body">
          <p class="lead">
            A high similarity score is a starting point for research, not a guarantee of mission
            readiness.
          </p>
          <ul class="limits-list">
            <li>
              Gravity, atmosphere or vacuum, radiation, and permanent-shadow illumination cannot be
              reproduced on Earth. They are never scored and always appear in the divergence panel.
            </li>
            <li>
              The 2D Earth map uses Web Mercator, which clips latitudes beyond about 85&deg;.
              Antarctic matches remain in the cards and shortlist, and the 3D globe shows the poles.
            </li>
            <li>
              A 1,770 km&sup2; hexagon can hide small, strong local matches. Finer stage-2
              refinement is future work.
            </li>
            <li>
              Permafrost data covers the Northern Hemisphere only, Mars thermal data is an open
              item, and the lithology crosswalk is the weakest harmonised dimension.
            </li>
            <li>
              Subsurface data is thin: only a few Earth lava tubes and 266 lunar pits are
              catalogued, so most places show it as not measured. Karst caves are never treated as
              lava-tube analogues.
            </li>
            <li>
              A high score means model-defined similarity on the listed features. It is not a claim
              that a site is suitable for any mission.
            </li>
          </ul>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.about-page {
  grid-column: 1 / -1;
  grid-row: 2;
  overflow-y: auto;
  scrollbar-gutter: stable;
  padding: var(--s5) clamp(16px, 4vw, 48px) var(--s6);
  background:
    radial-gradient(circle at 22% 45%, rgba(79, 195, 247, 0.08), transparent 55%), var(--bg);
  color: var(--text);
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  gap: var(--s5);
}

.hero {
  max-width: 1180px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--s4);
  flex-wrap: wrap;
  padding-bottom: var(--s4);
  border-bottom: 1px solid var(--border);
}

.hero-copy {
  max-width: 740px;
}

.hero-copy h2 {
  font-size: clamp(22px, 2.6vw, 30px);
  font-weight: 600;
  margin-bottom: var(--s2);
  color: var(--text);
}

.hero-sub {
  margin: 0;
  font-size: 15px;
  line-height: 1.55;
  color: var(--text-muted);
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: var(--s3);
}

.btn-back {
  background: rgba(79, 195, 247, 0.14);
  border: 1px solid var(--accent-earth);
  color: var(--accent-earth);
  font-weight: 600;
  padding: var(--s2) var(--s4);
  border-radius: 999px;
}

.btn-back:hover {
  background: rgba(79, 195, 247, 0.24);
}

.btn-replay {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: var(--s2) var(--s3);
  border-radius: 999px;
}

.btn-replay:hover {
  color: var(--text);
}

.wheel-layout {
  max-width: 1180px;
  width: 100%;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(340px, 430px) 1fr;
  gap: var(--s6);
  align-items: start;
}

.wheel-stage {
  --orbit-r: 158px;
  position: relative;
  width: 380px;
  height: 380px;
  margin: 0 auto;
  display: grid;
  place-items: center;
  user-select: none;
  flex-shrink: 0;
}

.wheel-ring {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.wheel-ring.outer {
  inset: 32px;
  border: 1px dashed rgba(79, 195, 247, 0.38);
}

.wheel-ring.inner {
  inset: 68px;
  border: 1px solid var(--border);
  box-shadow: inset 0 0 36px rgba(79, 195, 247, 0.08);
}

.pointer {
  position: absolute;
  right: 8px;
  top: 50%;
  width: 34px;
  height: 2px;
  transform: translateY(-50%);
  background: linear-gradient(90deg, transparent, var(--accent-earth));
  pointer-events: none;
}

.pointer::after {
  content: '';
  position: absolute;
  right: -2px;
  top: -4px;
  border-left: 8px solid var(--accent-earth);
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
}

.wheel-rotor {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  transform-origin: center center;
  display: grid;
  place-items: center;
  transition: transform 480ms var(--ease);
}

.orbit-node {
  position: absolute;
  width: 16px;
  height: 16px;
  background: none;
  border: 0;
  padding: 0;
  min-height: 0;
  cursor: pointer;
}

.node-inner {
  position: relative;
  width: 16px;
  height: 16px;
  display: block;
  transform-origin: center center;
  transition: transform 480ms var(--ease);
}

.node-dot {
  display: block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--surface-2);
  border: 2px solid var(--border);
  transition:
    border-color var(--dur) var(--ease),
    background var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.orbit-node:hover .node-dot {
  border-color: var(--accent-earth);
}

.orbit-node.active .node-dot {
  background: var(--accent-earth);
  border-color: var(--text);
  box-shadow: 0 0 14px rgba(79, 195, 247, 0.7);
}

.node-label {
  position: absolute;
  top: 22px;
  left: 50%;
  transform: translateX(-50%);
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(18, 24, 38, 0.92);
  border: 1px solid var(--border);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  white-space: nowrap;
}

.orbit-node.active .node-label {
  border-color: var(--accent-earth);
  color: var(--accent-earth);
  font-weight: 600;
}

.wheel-hub {
  position: relative;
  z-index: 2;
  width: 148px;
  height: 148px;
  border-radius: 50%;
  background: var(--surface);
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
  box-shadow: 0 0 32px rgba(4, 6, 11, 0.9);
}

.hub-count {
  font-size: 20px;
  font-weight: 600;
  color: var(--accent-earth);
}

.hub-title {
  font-size: 13px;
  color: var(--text);
  font-weight: 500;
}

.hub-controls {
  display: flex;
  align-items: center;
  gap: var(--s2);
  margin-top: 2px;
}

.hub-controls button {
  padding: 2px 8px;
  min-height: 26px;
  font-size: 14px;
  border-radius: 999px;
}

.hub-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.detail-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-panel);
  padding: var(--s5);
  min-height: 440px;
  display: flex;
  flex-direction: column;
  gap: var(--s4);
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s3);
  border-bottom: 1px solid var(--border);
  padding-bottom: var(--s3);
}

.detail-head h3 {
  font-size: 20px;
  font-weight: 600;
}

.detail-badge {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(242, 181, 68, 0.14);
  border: 1px solid var(--accent-moon);
  color: var(--accent-moon);
  font-size: 12px;
  font-weight: 600;
}

.section-body {
  display: flex;
  flex-direction: column;
  gap: var(--s4);
}

.lead {
  margin: 0;
  font-size: 15px;
  line-height: 1.55;
  color: var(--text);
}

.trait-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--s3);
}

.trait-card,
.info-item {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--s3) var(--s4);
}

.trait-card h4,
.info-item h4 {
  font-size: 15px;
  font-weight: 600;
  color: var(--accent-earth);
  margin-bottom: var(--s1);
}

.trait-card p,
.info-item p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.5;
  color: var(--text-muted);
}

.callout {
  margin: 0;
  padding: var(--s3) var(--s4);
  border-radius: var(--radius-card);
  background: rgba(242, 181, 68, 0.08);
  border: 1px solid rgba(242, 181, 68, 0.4);
  color: var(--text);
  font-size: 13.5px;
  line-height: 1.5;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: var(--s3);
}

.limits-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: var(--s3);
}

.limits-list li {
  line-height: 1.55;
  color: var(--text-muted);
}

.data-table td,
.data-table th {
  padding: var(--s2) var(--s3);
}

.pending {
  color: var(--warn);
  font-weight: 600;
}

@media (max-width: 960px) {
  .wheel-layout {
    grid-template-columns: 1fr;
  }
  .pointer {
    display: none;
  }
  .trait-grid {
    grid-template-columns: 1fr;
  }
}
</style>
