<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import { GlobeScene, webglAvailable } from '../globe/GlobeScene';
import { Arcs } from '../globe/arcs';
import {
  attachPicking,
  buildRowLookup,
  nearestLandmark,
  pickMatchMarker,
  rowAt,
} from '../globe/picking';
import { nearestDisc } from '../map/targetLayers';
import { useSession } from '../stores/session';
import { cardMarkers } from '../stores/selectors';
import { finiteMax, makePalette, metricMeta } from '../map/palette';

const props = defineProps<{ showMarkerHint?: boolean }>();
const emit = defineEmits<{
  fallback: [reason: string];
  viewDetails: [row: number];
  dismissMarkerHint: [];
}>();
const markerHint = ref<{ x: number; y: number; n: number } | null>(null);
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
      if (props.showMarkerHint && host.value) {
        const width = host.value.clientWidth;
        const height = host.value.clientHeight;
        let visible = false;
        for (const marker of markers.value) {
          const point = sc.worldPoint('earth', marker.lat, marker.lng, 0.015);
          if (
            point.clone().sub(sc.earthGlobe.position).dot(sc.camera.position.clone().sub(point)) <=
            0
          )
            continue;
          const p = point.project(sc.camera);
          if (p.z < -1 || p.z > 1 || Math.abs(p.x) > 1 || Math.abs(p.y) > 1) continue;
          const x = Math.round(Math.max(12, Math.min(width - 280, ((p.x + 1) * width) / 2 + 24)));
          const y = Math.round(Math.max(12, Math.min(height - 180, ((1 - p.y) * height) / 2 - 90)));
          if (
            markerHint.value?.x !== x ||
            markerHint.value.y !== y ||
            markerHint.value.n !== marker.n
          )
            markerHint.value = { x, y, n: marker.n };
          visible = true;
          break;
        }
        if (!visible) markerHint.value = null;
      }
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
      onMatch: (x, y) => {
        const bounds = sc.renderer.domElement.getBoundingClientRect();
        const row = pickMatchMarker(sc, markers.value, x, y, bounds.width, bounds.height);
        if (row === null) return false;
        emit('viewDetails', row);
        return true;
      },
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
      Drag to turn · scroll to zoom · click left globe to choose a target · click a numbered Earth
      location for details
    </p>
    <div
      v-if="showMarkerHint && markerHint"
      class="marker-hint"
      :style="{ left: `${markerHint.x}px`, top: `${markerHint.y}px` }"
      role="status"
      data-test="marker-guidance"
    >
      <span class="number" aria-hidden="true">{{ markerHint.n }}</span>
      <p>Click a numbered Earth location to see its details.</p>
      <button type="button" aria-label="Dismiss location tip" @click="$emit('dismissMarkerHint')">
        ×
      </button>
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
  top: 76px; /* under the header */
  left: 50%;
  transform: translateX(-50%);
  margin: 0;
  padding: var(--s1) var(--s3);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--bg) 70%, transparent);
  color: var(--text-muted);
  white-space: nowrap;
  pointer-events: none;
  transition: opacity 600ms var(--ease);
}
.hint.gone {
  opacity: 0;
}
.marker-hint {
  position: absolute;
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: min(268px, calc(100% - 24px));
  padding: 10px 8px 10px 12px;
  background: #101b2a;
  border: 1px solid #52778e;
  border-radius: 12px;
  pointer-events: auto;
  box-shadow: 0 6px 20px #0005;
}
.marker-hint p {
  margin: 0;
  font-size: 15px;
  line-height: 1.45;
}
.marker-hint .number {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid var(--accent-earth);
  border-radius: 50%;
  color: var(--accent-earth);
  flex-shrink: 0;
}
.marker-hint button {
  min-width: 44px;
  min-height: 44px;
  padding: 0;
  background: transparent;
  border: 0;
  font-size: 22px;
}
@media (max-width: 640px) {
  .hint {
    display: none;
  }
}
</style>
