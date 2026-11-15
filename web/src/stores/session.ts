// Session store (03 design §3): the single source of UI state.
import { defineStore } from 'pinia';
import { computed, reactive, ref, shallowRef } from 'vue';
import {
  GROUP_IDS,
  N_FEATURES,
  type Body,
  type Bundle,
  type Card,
  type ColorBy,
  type GroupId,
  type GroupWeights,
  type LensId,
  type RankTarget,
  type PaintedResponse,
  type Palette,
  type RankedResponse,
  type StabilityFile,
} from '../data/types';
import type { GeoJsonFeatureCollection } from '../data/loader';
import { eligibleMask } from '../engine/cards';
import { effectiveWeights, groupAvailability } from './selectors';

export type TargetRef =
  { kind: 'landmark'; id: string } | { kind: 'disc'; body: Body; discIndex: number };

export type LayerId = 'known_sites' | 'volcanoes' | 'lava_tubes' | 'lunar_pits' | 'sarawak_caves';

export interface RankResult {
  version: number;
  S: Float32Array;
  coverage: Float32Array;
  groups: Float32Array; // N×4
  cards: Card[];
  top: Int32Array;
  eligible: Uint8Array; // C4.7, derived once per result
}

export interface StabilityState {
  rows: Map<number, number>;
  kind: 'preset' | 'interactive';
}

export interface LoadState {
  phase: 'idle' | 'loading' | 'ready' | 'error';
  done: number;
  total: number;
  error: string | null;
}

export interface Timings {
  loadMs: number | null;
  rankMs: number | null;
  cardsMs: number | null;
  paintMs: number | null;
}

/** What the store needs from the worker client (implemented in workers/client.ts). */
export interface EngineLike {
  rank(target: RankTarget, weights: GroupWeights): Promise<RankedResponse | null>;
  stability(
    target: RankTarget,
    weights: GroupWeights,
    draws: number,
    onProgress: (done: number, total: number) => void,
  ): Promise<[number, number][] | null>;
  paint?(colorBy: ColorBy, palette: Palette): Promise<PaintedResponse | null>;
}

export interface StoreDeps {
  engine?: EngineLike;
  fetchStability?: (targetId: string, lens: LensId) => Promise<StabilityFile | null>;
  fetchImage?: (file: string) => Promise<ImageBitmap>;
  fetchLayer?: (id: string) => Promise<GeoJsonFeatureCollection | null>;
}

export type TextureId = 'earth' | Body;

/** C3 lens presets; replaced by manifest.lenses once the bundle is loaded. */
export const DEFAULT_LENSES: Record<LensId, GroupWeights> = {
  balanced: {
    terrain: 0.225,
    thermal: 0.225,
    cold_ice: 0.225,
    composition: 0.225,
    subsurface: 0.1,
  },
  landing_mobility: {
    terrain: 0.7,
    thermal: 0.15,
    cold_ice: 0.0,
    composition: 0.15,
    subsurface: 0.0,
  },
  cold_volatiles: {
    terrain: 0.15,
    thermal: 0.3,
    cold_ice: 0.45,
    composition: 0.1,
    subsurface: 0.0,
  },
  geology_minerals: {
    terrain: 0.2,
    thermal: 0.1,
    cold_ice: 0.1,
    composition: 0.55,
    subsurface: 0.05,
  },
};

export const SLIDER_DEBOUNCE_MS = 50;

/** Set group `g` to `value` and rescale the others proportionally so the five sum to 1. */
export function renormalise(weights: GroupWeights, g: GroupId, value: number): GroupWeights {
  const v = Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
  const others = GROUP_IDS.filter((k) => k !== g);
  const otherSum = others.reduce((acc, k) => acc + weights[k], 0);
  const out = { ...weights, [g]: v } as GroupWeights;
  for (const k of others) {
    out[k] = otherSum > 0 ? ((1 - v) * weights[k]) / otherSum : (1 - v) / others.length;
  }
  return out;
}

export const useSession = defineStore('session', () => {
  const body = ref<Body>('moon');
  const target = ref<TargetRef | null>(null);
  const lens = ref<LensId | 'custom'>('balanced');
  const presets = ref<Record<LensId, GroupWeights>>({ ...DEFAULT_LENSES });
  const weights = ref<GroupWeights>({ ...DEFAULT_LENSES.balanced });
  const lastPreset = ref<LensId>('balanced');
  const colorBy = ref<ColorBy>('S');
  const view = ref<'2d' | '3d'>('3d'); // 3D is the headline view; GlobeView falls back to 2D
  const selectedRow = ref<number | null>(null);
  const novelOnly = ref(false);
  const layers = reactive<Record<LayerId, boolean>>({
    known_sites: true,
    volcanoes: false,
    lava_tubes: false,
    lunar_pits: false,
    sarawak_caves: false,
  });
  const result = shallowRef<RankResult | null>(null);
  const stability = shallowRef<StabilityState | null>(null);
  const stabilityProgress = ref<{ done: number; total: number } | null>(null);
  const loading = reactive<LoadState>({ phase: 'idle', done: 0, total: 0, error: null });
  const timings = reactive<Timings>({ loadMs: null, rankMs: null, cardsMs: null, paintMs: null });
  const bundle = shallowRef<Bundle | null>(null);
  const synthetic = ref<boolean | null>(null);
  const aboutOpen = ref(false);
  /** Section id the About dialog should open on (consumed on mount), e.g. 'sources'. */
  const aboutSection = ref<string | null>(null);
  const introOpen = ref(false);
  const notice = ref<string | null>(null);
  const textures = shallowRef<Partial<Record<TextureId, ImageBitmap>>>({});
  const painted = shallowRef<{
    width: number;
    height: number;
    rgba: Uint8ClampedArray;
    version: number;
  } | null>(null);
  const layerData = shallowRef<Partial<Record<LayerId | 'land', GeoJsonFeatureCollection>>>({});

  let deps: StoreDeps = {};
  const requested = new Set<string>();

  /** Load a body texture once (components never fetch). */
  async function ensureTexture(id: TextureId): Promise<void> {
    if (!deps.fetchImage || requested.has(`tex:${id}`)) return;
    requested.add(`tex:${id}`);
    try {
      const bmp = await deps.fetchImage(`textures/${id}.jpg`);
      textures.value = { ...textures.value, [id]: bmp };
    } catch (e) {
      notice.value = e instanceof Error ? e.message : String(e);
    }
  }

  /** Load an overlay layer (layers/<id>.geojson) once. */
  async function ensureLayer(id: LayerId | 'land'): Promise<void> {
    if (!deps.fetchLayer || requested.has(`layer:${id}`)) return;
    requested.add(`layer:${id}`);
    try {
      const gj = await deps.fetchLayer(id);
      if (gj) layerData.value = { ...layerData.value, [id]: gj };
    } catch (e) {
      notice.value = e instanceof Error ? e.message : String(e);
    }
  }
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let version = 0;

  const lensLabel = computed(() => lens.value);
  const available = computed(() => groupAvailability(bundle.value?.discs[body.value]));
  const effective = computed(() => effectiveWeights(weights.value, available.value));
  /** A preset is disabled when its single largest-weight group has no data on this body. */
  function lensDisabled(id: LensId): boolean {
    const w = presets.value[id];
    const top = Math.max(...GROUP_IDS.map((g) => w[g]));
    const tops = GROUP_IDS.filter((g) => w[g] === top);
    return tops.length === 1 && !available.value[tops[0]];
  }

  function attach(d: StoreDeps): void {
    deps = { ...deps, ...d };
  }

  function setBundle(b: Bundle): void {
    bundle.value = b;
    presets.value = { ...b.manifest.lenses };
    if (lens.value !== 'custom') weights.value = { ...presets.value[lens.value] };
  }

  /** Raw target features/lith for the current target (NaN = missing). */
  function rankTarget(): RankTarget | null {
    const b = bundle.value;
    const t = target.value;
    if (!b || !t) return null;
    if (t.kind === 'landmark') {
      const tg = b.targets.find((x) => x.id === t.id);
      return tg ? { features: Array.from(tg.features), lith: Array.from(tg.lith) } : null;
    }
    const grid = b.discs[t.body];
    if (!grid || t.discIndex < 0 || t.discIndex >= grid.n) return null;
    const i = t.discIndex;
    return {
      features: Array.from(grid.features.subarray(i * N_FEATURES, (i + 1) * N_FEATURES)),
      lith: Array.from(grid.lith.subarray(i * 6, i * 6 + 6)),
    };
  }

  async function rankNow(): Promise<void> {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    const engine = deps.engine;
    const t = rankTarget();
    if (!engine || !t) return;
    const t0 = performance.now();
    const res = await engine.rank(t, { ...effective.value });
    if (!res) return; // superseded by a newer request (latest wins)
    timings.rankMs = performance.now() - t0;
    version += 1;
    result.value = {
      version,
      S: res.S,
      coverage: res.coverage,
      groups: res.groups,
      cards: res.cards,
      top: res.top,
      eligible: bundle.value
        ? eligibleMask(res.S, res.coverage, bundle.value.manifest.params.coverage_floor)
        : new Uint8Array(res.S.length),
    };
  }

  function rankDebounced(): void {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => void rankNow(), SLIDER_DEBOUNCE_MS);
  }

  async function loadPresetStability(): Promise<void> {
    const t = target.value;
    if (!deps.fetchStability || !t || t.kind !== 'landmark') {
      stability.value = null;
      return;
    }
    const lensId = lastPreset.value;
    const file = await deps.fetchStability(t.id, lensId);
    if (target.value !== t || lastPreset.value !== lensId) return;
    stability.value = file ? { rows: new Map(file.rows), kind: 'preset' } : null;
  }

  function onTargetChanged(): void {
    // keep the previous result on screen until the new one arrives (no grey flash, no extra
    // 85k-hex repaint competing with the rank response)
    selectedRow.value = null;
    stabilityProgress.value = null;
    void loadPresetStability();
    void rankNow();
  }

  function selectBody(b: Body): void {
    if (body.value === b) return;
    body.value = b;
    const t = target.value;
    const tBody =
      t?.kind === 'disc' ? t.body : bundle.value?.targets.find((x) => x.id === t?.id)?.body;
    if (t && tBody !== b) {
      target.value = null;
      result.value = null;
      selectedRow.value = null;
      stability.value = null;
    }
    // never leave the panel empty: open on that body's first landmark
    const first = bundle.value?.targets.find((x) => x.body === b);
    if (!target.value && first) selectLandmark(first.id);
    if (lens.value !== 'custom' && lensDisabled(lens.value)) setLens('balanced');
  }

  function selectLandmark(id: string): void {
    target.value = { kind: 'landmark', id };
    onTargetChanged();
  }

  function selectDisc(b: Body, discIndex: number): void {
    target.value = { kind: 'disc', body: b, discIndex };
    onTargetChanged();
  }

  function setLens(id: LensId): void {
    lens.value = id;
    lastPreset.value = id;
    weights.value = { ...presets.value[id] };
    stabilityProgress.value = null;
    void loadPresetStability();
    void rankNow();
  }

  function setWeight(g: GroupId, value: number): void {
    weights.value = renormalise(weights.value, g, value);
    lens.value = 'custom';
    stabilityProgress.value = null; // a running interactive result would be for old weights
    if (stability.value?.kind === 'interactive') {
      stability.value = null;
      void loadPresetStability();
    }
    rankDebounced();
  }

  async function runStability(draws: number): Promise<void> {
    const engine = deps.engine;
    const t = rankTarget();
    if (!engine || !t) return;
    const forTarget = target.value;
    const forWeights = weights.value;
    stabilityProgress.value = { done: 0, total: draws };
    const rows = await engine.stability(t, { ...effective.value }, draws, (done, total) => {
      if (target.value === forTarget) stabilityProgress.value = { done, total };
    });
    if (!rows) return; // cancelled by a newer request
    if (target.value !== forTarget || weights.value !== forWeights) return; // stale: inputs changed
    // (setWeight / target change already cleared the progress bar)
    stability.value = { rows: new Map(rows), kind: 'interactive' };
    stabilityProgress.value = null;
  }

  let paintVersion = 0;
  /** Ask the worker to paint the Earth globe texture for the active metric (3D view). */
  async function requestPaint(palette: Palette): Promise<void> {
    const engine = deps.engine;
    if (!engine?.paint) return;
    const t0 = performance.now();
    const res = await engine.paint(colorBy.value, palette);
    if (!res) return;
    timings.paintMs = performance.now() - t0;
    paintVersion += 1;
    painted.value = { width: res.width, height: res.height, rgba: res.rgba, version: paintVersion };
  }

  function selectRow(row: number | null): void {
    selectedRow.value = row;
  }
  function toggleLayer(id: LayerId): void {
    layers[id] = !layers[id];
  }
  function setView(v: '2d' | '3d'): void {
    view.value = v;
  }
  function setColorBy(c: ColorBy): void {
    colorBy.value = c;
  }
  function setNovelOnly(v: boolean): void {
    novelOnly.value = v;
  }

  return {
    body,
    target,
    lens,
    lensLabel,
    presets,
    weights,
    available,
    effective,
    lensDisabled,
    lastPreset,
    colorBy,
    view,
    selectedRow,
    novelOnly,
    layers,
    result,
    stability,
    stabilityProgress,
    loading,
    timings,
    bundle,
    synthetic,
    aboutOpen,
    aboutSection,
    introOpen,
    notice,
    textures,
    layerData,
    painted,
    requestPaint,
    ensureTexture,
    ensureLayer,
    attach,
    setBundle,
    rankTarget,
    rankNow,
    selectBody,
    selectLandmark,
    selectDisc,
    setLens,
    setWeight,
    runStability,
    selectRow,
    toggleLayer,
    setView,
    setColorBy,
    setNovelOnly,
  };
});
