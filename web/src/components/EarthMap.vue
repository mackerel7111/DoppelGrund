<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watchEffect } from 'vue';
import { Deck, MapView, WebMercatorViewport, type PickingInfo } from '@deck.gl/core';
import { useSession } from '../stores/session';
import { COLOR_OPTIONS, colorHelp } from '../content/labels';
import type { ColorBy } from '../data/types';
import LayerToggles from './LayerToggles.vue';
import { buildEarthLayers } from '../map/earthLayers';
import { cardMarkers, type CardMarker } from '../stores/selectors';
import { buildOverlays } from '../map/overlayLayers';
import {
  colorize,
  finiteMax,
  legendGradient,
  makePalette,
  metricMeta,
  notMaskedMask,
  sourceFor,
} from '../map/palette';

const emit = defineEmits<{ viewDetails: [row: number] }>();
const s = useSession();
const host = ref<HTMLDivElement | null>(null);
let deck: Deck<MapView> | null = null;
let resize: ResizeObserver | null = null;

const rows = computed(() => Array.from({ length: s.bundle?.manifest.n_hex ?? 0 }, (_, i) => i));
const notMasked = computed(() => notMaskedMask(s.bundle?.flags ?? new Uint8Array()));
const noveltyMax = computed(() => finiteMax(s.bundle?.novelty ?? new Float32Array(), 2, 0));
const meta = computed(() => metricMeta(s.colorBy, Math.ceil(noveltyMax.value / 100) * 100));
let colorCounter = 0;
const colors = computed(() => {
  const b = s.bundle;
  if (!b) return { buf: new Uint8ClampedArray(), version: 0 };
  const src = sourceFor(s.colorBy, s.result, b.novelty, notMasked.value);
  const buf = colorize(b.manifest.n_hex, src, makePalette(meta.value.domain));
  colorCounter += 1;
  return { buf, version: colorCounter };
});
const markers = computed<CardMarker[]>(() =>
  s.result && s.bundle ? cardMarkers(s.result.cards, s.bundle.latlng) : [],
);
const selected = computed(() => {
  const r = s.selectedRow;
  const ll = s.bundle?.latlng;
  return r === null || !ll ? null : { lat: ll[r * 2], lng: ll[r * 2 + 1] };
});

const layers = computed(() => {
  const b = s.bundle;
  if (!b) return [];
  return buildEarthLayers(
    {
      land: s.layerData.land ?? null,
      h3: b.h3,
      rows: rows.value,
      colors: colors.value.buf,
      colorVersion: colors.value.version,
      cards: markers.value,
      selected: selected.value,
    },
    // built here (not passed in) so a remounted Deck never receives another Deck's layers
    buildOverlays('earth', s.layers, s.layerData),
  );
});

function onColor(ev: Event): void {
  const v = (ev.target as HTMLSelectElement).value;
  if (COLOR_OPTIONS.some((o) => o.id === v)) s.setColorBy(v as ColorBy);
}

function onClick(info: PickingInfo): void {
  if (info.layer?.id === 'hexes' && info.index >= 0) s.selectRow(info.index);
  else if ((info.layer?.id === 'card-rings' || info.layer?.id === 'card-numbers') && info.object)
    emit('viewDetails', (info.object as CardMarker).row);
}

function tooltip(info: PickingInfo): string | null {
  if (info.layer?.id !== 'hexes' || info.index < 0 || !s.result) return null;
  const i = info.index;
  const S = s.result.S[i];
  const cov = s.result.coverage[i];
  return Number.isFinite(S)
    ? `Similarity ${S.toFixed(1)} · data coverage ${(cov * 100).toFixed(0)}%`
    : `Not compared (vegetated or too little data) · data coverage ${(cov * 100).toFixed(0)}%`;
}

function fitView(): void {
  if (!deck || !host.value) return;
  const zoom = Math.log2(host.value.clientWidth / 512) - 0.3;
  deck.setProps({
    initialViewState: { longitude: 10, latitude: 25, zoom, minZoom: zoom - 0.5, maxZoom: 9 },
  });
}

/** Fly to the bounding box of the match cards (Mercator clips beyond ~85°). */
function fitCards(): void {
  if (!deck || !host.value || markers.value.length === 0) return;
  const lats = markers.value.map((m) => Math.max(-84, Math.min(84, m.lat)));
  const lngs = markers.value.map((m) => m.lng);
  const { clientWidth: width, clientHeight: height } = host.value;
  const vp = new WebMercatorViewport({ width, height });
  const { longitude, latitude, zoom } = vp.fitBounds(
    [
      [Math.min(...lngs), Math.min(...lats)],
      [Math.max(...lngs), Math.max(...lats)],
    ],
    { padding: Math.min(60, height / 4), maxZoom: 5 },
  );
  deck.setProps({
    initialViewState: {
      longitude,
      latitude,
      zoom,
      minZoom: 0,
      maxZoom: 9,
      transitionDuration: 300,
    },
  });
}

onMounted(() => {
  if (!host.value) return;
  void s.ensureLayer('land');
  deck = new Deck<MapView>({
    parent: host.value,
    views: new MapView({ id: 'earth', repeat: false }),
    initialViewState: { longitude: 10, latitude: 20, zoom: 1.2 },
    controller: { doubleClickZoom: false },
    onClick,
    getTooltip: tooltip,
    getCursor: ({ isHovering }) => (isHovering ? 'pointer' : 'grab'),
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

watchEffect(
  () => {
    const l = layers.value;
    deck?.setProps({ layers: l });
  },
  { flush: 'post' },
);
</script>

<template>
  <div class="earth-map">
    <div class="toolbar">
      <button
        type="button"
        :disabled="markers.length === 0"
        data-test="fit-cards"
        @click="fitCards"
      >
        Zoom to matches
      </button>
      <label class="color"
        ><span class="meta">Colour the Earth by</span>
        <select data-test="color-by" :value="s.colorBy" @change="onColor">
          <option v-for="o in COLOR_OPTIONS" :key="o.id" :value="o.id">{{ o.label }}</option>
        </select></label
      >
      <span v-if="!s.result" class="meta">Pick a landmark to compare every Earth place</span>
    </div>
    <div
      ref="host"
      class="map"
      role="img"
      aria-label="Earth map of H3 hexagons coloured by the active metric"
    />
    <div class="legend" aria-label="Legend">
      <span class="meta" data-test="color-help">{{ colorHelp(s.colorBy) }}</span>
      <span class="meta">{{ meta.label }} ({{ meta.unit }})</span>
      <span class="num meta">{{ meta.domain[0] }}</span>
      <span class="bar" :style="{ background: legendGradient() }" />
      <span class="num meta">{{ meta.domain[1] }}{{ meta.unit === 'km' ? ' km' : '' }}</span>
      <span class="swatch" /><span class="meta">not compared (vegetated or too little data)</span>
      <span class="ring" /><span class="meta">matches 1–6</span>
    </div>
    <div class="layers-row">
      <LayerToggles />
    </div>
  </div>
</template>

<style scoped>
.earth-map {
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
.color {
  display: inline-flex;
  gap: var(--s2);
  align-items: center;
}
.layers-row {
  padding: 0 var(--s3) var(--s2);
}
.map {
  position: relative;
  min-height: 220px;
  background: var(--bg);
  overflow: hidden;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s2);
  align-items: center;
  padding: var(--s2) var(--s3);
}
.bar {
  width: 160px;
  height: 10px;
  border-radius: 3px;
}
.swatch {
  width: 14px;
  height: 10px;
  background: var(--masked);
  border-radius: 2px;
  margin-left: var(--s3);
}
.ring {
  width: 12px;
  height: 12px;
  border: 2px solid var(--accent-earth);
  border-radius: 50%;
  margin-left: var(--s3);
}
</style>
