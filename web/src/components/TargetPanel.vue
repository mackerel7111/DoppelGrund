<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, watchEffect } from 'vue';
import { Deck, OrthographicView, type PickingInfo } from '@deck.gl/core';
import { useSession } from '../stores/session';
import {
  buildTargetLayers,
  clampLonLat,
  fitZoom,
  nearestDisc,
  type CustomPoint,
} from '../map/targetLayers';
import { FOOTPRINT_NOTE, TERMS } from '../content/labels';
import { formatLatLon } from '../stores/selectors';
import { buildOverlays } from '../map/overlayLayers';

const s = useSession();
const host = ref<HTMLDivElement | null>(null);
let deck: Deck<OrthographicView> | null = null;
let resize: ResizeObserver | null = null;

const landmarks = computed(() => (s.bundle?.targets ?? []).filter((t) => t.body === s.body));
const selectedId = computed(() => (s.target?.kind === 'landmark' ? s.target.id : null));
const custom = computed<CustomPoint | null>(() => {
  const t = s.target;
  const grid = t?.kind === 'disc' ? s.bundle?.discs[t.body] : undefined;
  if (t?.kind !== 'disc' || !grid || t.body !== s.body) return null;
  const lat = grid.latlon[t.discIndex * 2];
  const lon = grid.latlon[t.discIndex * 2 + 1];
  return { lat, lon, label: `${TERMS.customPoint} ${formatLatLon(lat, lon)}` };
});
const selected = computed(() => landmarks.value.find((t) => t.id === selectedId.value) ?? null);
const hasDiscs = computed(() => Boolean(s.bundle?.discs[s.body]));

function fitView(): void {
  if (!deck || !host.value) return;
  const { clientWidth: w, clientHeight: h } = host.value;
  const zoom = fitZoom(w, h);
  deck.setProps({
    initialViewState: { target: [0, 0, 0], zoom, minZoom: zoom - 0.5, maxZoom: zoom + 6 },
  });
}

function onClick(info: PickingInfo): void {
  const obj = info.object as { id?: string } | undefined;
  if (info.layer?.id === 'landmarks' && obj?.id) {
    s.selectLandmark(obj.id);
    return;
  }
  const grid = s.bundle?.discs[s.body];
  if (!grid || !info.coordinate) return;
  const { lon, lat } = clampLonLat(info.coordinate[0], info.coordinate[1]);
  const idx = nearestDisc(grid, lat, lon, s.body);
  if (idx >= 0) s.selectDisc(s.body, idx);
}

onMounted(() => {
  if (!host.value) return;
  deck = new Deck<OrthographicView>({
    parent: host.value,
    views: new OrthographicView({ id: 'body', flipY: false }),
    initialViewState: { target: [0, 0, 0], zoom: 0 },
    controller: { doubleClickZoom: false },
    onClick,
    getCursor: ({ isHovering }) => (isHovering ? 'pointer' : 'crosshair'),
    layers: layers.value,
  });
  fitView();
  resize = new ResizeObserver(() => fitView());
  resize.observe(host.value);
});

onBeforeUnmount(() => {
  resize?.disconnect();
  deck?.finalize();
  deck = null;
});

watch(
  () => s.body,
  (b) => {
    void s.ensureTexture(b);
    fitView();
  },
  { immediate: true },
);

const layers = computed(() =>
  buildTargetLayers(
    {
      texture: s.textures[s.body] ?? null,
      landmarks: landmarks.value,
      selectedId: selectedId.value,
      custom: custom.value,
    },
    s.body === 'moon' ? buildOverlays('body', s.layers, s.layerData) : [],
  ),
);

watchEffect(
  () => {
    const l = layers.value; // read first so the dependency is tracked even before mount
    deck?.setProps({ layers: l });
  },
  { flush: 'post' },
);
</script>

<template>
  <div class="target-panel">
    <div class="toolbar">
      <span class="meta">{{
        hasDiscs ? 'Click a landmark or anywhere on the map' : 'landmarks only'
      }}</span>
    </div>
    <div ref="host" class="map" role="img" :aria-label="`${s.body} equirectangular map`" />
    <div class="info">
      <p v-if="selected" class="name">
        <strong>{{ selected.name }}</strong>
        <span class="num meta"> · {{ formatLatLon(selected.lat, selected.lon) }}</span>
      </p>
      <p v-else-if="custom" class="name">
        <strong>{{ custom.label }}</strong>
      </p>
      <p v-else class="meta">No landmark selected</p>
      <p class="meta">{{ FOOTPRINT_NOTE }}</p>
    </div>
  </div>
</template>

<style scoped>
.target-panel {
  display: grid;
  grid-template-rows: auto 1fr auto;
  height: calc(100% - 41px);
  min-height: 0;
}
.toolbar {
  display: flex;
  gap: var(--s3);
  align-items: center;
  padding: var(--s2) var(--s3);
  flex-wrap: wrap;
}
.map {
  position: relative;
  min-height: 200px;
  background: var(--bg);
  overflow: hidden;
}
.info {
  padding: var(--s2) var(--s3);
}
.info p {
  margin: 0 0 var(--s1);
}
</style>
