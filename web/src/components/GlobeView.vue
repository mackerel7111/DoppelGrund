<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import { GlobeScene, webglAvailable } from '../globe/GlobeScene';
import { Arcs } from '../globe/arcs';
import { attachPicking, buildRowLookup, nearestLandmark, rowAt } from '../globe/picking';
import { nearestDisc } from '../map/targetLayers';
import { useSession } from '../stores/session';
import { cardMarkers } from '../stores/selectors';
import { finiteMax, legendGradient, makePalette, metricMeta } from '../map/palette';
import { COLOR_OPTIONS } from '../content/labels';
import type { ColorBy } from '../data/types';

const emit = defineEmits<{ fallback: [reason: string] }>();
const s = useSession();
const host = ref<HTMLDivElement | null>(null);
const scene = shallowRef<GlobeScene | null>(null);

const landmarks = computed(() => (s.bundle?.targets ?? []).filter((t) => t.body === s.body));
const selectedId = computed(() => (s.target?.kind === 'landmark' ? s.target.id : null));
const markers = computed(() =>
  s.result && s.bundle ? cardMarkers(s.result.cards, s.bundle.latlng) : [],
);
const noveltyMax = computed(() => finiteMax(s.bundle?.novelty ?? new Float32Array(), 2, 0));
const rowLookup = computed(() => buildRowLookup(s.bundle?.h3 ?? []));
const targetPoint = computed(() => {
  const t = s.target;
  if (t?.kind === 'disc') {
    const g = s.bundle?.discs[t.body];
    return g ? { lat: g.latlon[t.discIndex * 2], lng: g.latlon[t.discIndex * 2 + 1] } : null;
  }
  const lm = landmarks.value.find((x) => x.id === selectedId.value);
  return lm ? { lat: lm.lat, lng: lm.lon } : null;
});
const targetName = computed(() => {
  const t = s.target;
  if (!t) return 'none selected';
  if (t.kind === 'disc') return 'custom target';
  return landmarks.value.find((x) => x.id === t.id)?.name ?? t.id;
});
let detach: (() => void) | null = null;
let arcs: Arcs | null = null;
const hintVisible = ref(true);
const meta = computed(() => metricMeta(s.colorBy, Math.ceil(noveltyMax.value / 100) * 100));

onMounted(() => {
  if (!host.value) return;
  if (!webglAvailable()) {
    emit('fallback', 'WebGL is unavailable in this browser');
    return;
  }
  try {
    const sc = new GlobeScene(host.value, { onFallback: (r) => emit('fallback', r) });
    scene.value = sc;
    arcs = new Arcs(sc.scene);
    sc.onFrame.push(() => {
      const tp = targetPoint.value;
      const from = tp ? sc.worldPoint('body', tp.lat, tp.lng, 0.02) : null;
      const to = markers.value.map((m) => sc.worldPoint('earth', m.lat, m.lng, 0.01));
      const centre = sc.earthGlobe.position;
      arcs?.update(
        from,
        to,
        to.map((p, i) => {
          // end point facing away from the camera: faint, shown through the globe
          if (p.clone().sub(centre).dot(sc.camera.position.clone().sub(p)) < 0) return 0.15;
          return markers.value[i].row === s.selectedRow ? 1 : 0.6;
        }),
      );
    });
    detach = attachPicking(sc, {
      onEarth: (lat, lng) => {
        const row = rowAt(rowLookup.value, lat, lng);
        if (row !== null) s.selectRow(row);
      },
      onBody: (lat, lng) => {
        // same as the 2D map: a landmark dot if close, otherwise the nearest disc becomes a custom target
        const lm = nearestLandmark(landmarks.value, lat, lng);
        if (lm) return s.selectLandmark(lm.id);
        const grid = s.bundle?.discs[s.body];
        const idx = grid ? nearestDisc(grid, lat, lng, s.body) : -1;
        if (idx >= 0) s.selectDisc(s.body, idx);
      },
    });
  } catch (e) {
    emit('fallback', e instanceof Error ? e.message : String(e));
  }
});

onBeforeUnmount(() => {
  detach?.();
  arcs?.dispose();
  scene.value?.dispose();
  scene.value = null;
});

watch(
  [scene, () => s.textures.earth],
  ([sc, tex]) => {
    void s.ensureTexture('earth');
    sc?.setEarthBasemap(tex ?? null);
  },
  { immediate: true },
);
watch(
  [scene, () => s.body, () => s.textures[s.body]],
  ([sc, body, tex]) => {
    void s.ensureTexture(body);
    sc?.setBodyTexture(tex ?? null, body);
  },
  { immediate: true },
);
watch(
  [scene, landmarks, selectedId, targetPoint],
  ([sc, l, id, tp]) => sc?.setLandmarks(l, id, id ? null : tp && { lat: tp.lat, lon: tp.lng }),
  { immediate: true },
);
watch([scene, markers], ([sc, m]) => sc?.setCards(m), { immediate: true });
// face the selected landmark and the best overall match when they change
watch(
  [scene, () => landmarks.value.find((t) => t.id === selectedId.value)],
  ([sc, t]) => {
    if (sc && t) sc.facePoint('body', t.lat, t.lon);
  },
  { immediate: true },
);
watch(
  [scene, () => markers.value[0]],
  ([sc, m]) => {
    if (sc && m) sc.facePoint('earth', m.lat, m.lng);
  },
  { immediate: true },
);
// clicking a card (or a hex) turns Earth to that place and marks it while the briefing is open
watch([scene, () => s.selectedRow], ([sc, row]) => {
  const ll = s.bundle?.latlng;
  const p = ll && row !== null ? { lat: ll[row * 2], lng: ll[row * 2 + 1] } : null;
  sc?.setSelected(p);
  if (sc && p) sc.facePoint('earth', p.lat, p.lng);
});
function onColor(ev: Event): void {
  const v = (ev.target as HTMLSelectElement).value;
  if (COLOR_OPTIONS.some((o) => o.id === v)) s.setColorBy(v as ColorBy);
}
watch(
  [scene, () => s.result?.version, () => s.colorBy],
  ([sc]) => {
    if (sc) void s.requestPaint(makePalette(meta.value.domain));
  },
  { immediate: true },
);
watch([scene, () => s.painted], ([sc, p]) => {
  if (sc && p) sc.setEarthTexture(p.rgba, p.width, p.height);
});

defineExpose({ scene });
</script>

<template>
  <div class="globe-view" @pointerdown="hintVisible = false">
    <div
      ref="host"
      class="canvas"
      role="img"
      :aria-label="`3D view: ${s.body === 'moon' ? 'Moon' : 'Mars'} (left) and Earth (right); target ${targetName}`"
    />
    <p class="hint meta" :class="{ gone: !hintVisible }">
      Drag to turn · scroll to zoom · click left globe for target · click Earth for details
    </p>
    <div class="legend" data-test="globe-legend">
      <div class="row">
        <select
          :value="s.colorBy"
          aria-label="Colour metric"
          data-test="color-by"
          @change="onColor"
        >
          <option v-for="o in COLOR_OPTIONS" :key="o.id" :value="o.id">{{ o.label }}</option>
        </select>
        <span class="num meta">{{ meta.domain[0] }}</span>
        <span class="bar" :style="{ background: legendGradient() }" />
        <span class="num meta">{{ meta.domain[1] }}{{ meta.unit === 'km' ? ' km' : '' }}</span>
      </div>
      <span class="meta">
        {{
          s.colorBy === 'novelty'
            ? 'Brighter = farther from known sites'
            : 'Brighter = more similar'
        }}
        · smoothed for display
      </span>
    </div>
  </div>
</template>

<style scoped>
.globe-view {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #000;
}
.canvas {
  position: absolute;
  inset: 0;
}
.hint {
  position: absolute;
  top: 66px;
  left: 50%;
  transform: translateX(-50%);
  margin: 0;
  padding: var(--s1) var(--s3);
  border-radius: 999px;
  background: rgba(4, 6, 11, 0.65);
  color: var(--text-muted);
  white-space: nowrap;
  pointer-events: none;
  transition: opacity 600ms var(--ease);
}
.hint.gone {
  opacity: 0;
}
.legend {
  position: absolute;
  bottom: var(--s3);
  right: var(--s3);
  left: auto;
  width: 260px;
  max-width: 260px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  padding: 6px 10px;
  border-radius: var(--radius-card);
  background: rgba(11, 14, 19, 0.82);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  text-align: right;
  pointer-events: none;
}
.row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  width: 100%;
}
.row select {
  pointer-events: auto;
  max-width: 118px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 11px;
  padding: 2px 5px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text);
  border: 1px solid rgba(255, 255, 255, 0.14);
}
.bar {
  width: 64px;
  flex-shrink: 0;
  height: 8px;
  border-radius: 3px;
}
@media (max-width: 960px) {
  .hint {
    top: 106px;
    max-width: calc(100vw - 24px);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .legend {
    right: var(--s3);
    bottom: var(--s2);
  }
}
</style>
