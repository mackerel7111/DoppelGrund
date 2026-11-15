// deck.gl layers for the Moon/Mars panel: x = lon (−180…180), y = lat (−90…90).
import { BitmapLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import type { Layer } from '@deck.gl/core';
import type { Body, DiscGrid, Target } from '../data/types';
import { haversineKm } from '../engine/geo';

/** Body radii (km) from science-invariants.md §5. */
export const BODY_R_KM: Record<Body, number> = { moon: 1737.4, mars: 3389.5 };

export type RGBA = [number, number, number, number];
export const MOON_ACCENT: RGBA = [242, 181, 68, 255];
export const TEXT: RGBA = [230, 234, 242, 255];
export const BG: RGBA = [11, 15, 23, 210];

export interface CustomPoint {
  lat: number;
  lon: number;
  label: string;
}

export interface TargetLayerInput {
  texture: ImageBitmap | null;
  landmarks: Target[];
  selectedId: string | null;
  custom: CustomPoint | null;
}

/** Nearest disc (great-circle on the body sphere) to (lat, lon); −1 when the grid is empty. */
export function nearestDisc(grid: DiscGrid, lat: number, lon: number, body: Body): number {
  let best = -1;
  let bestD = Infinity;
  for (let i = 0; i < grid.n; i++) {
    const d = haversineKm(lat, lon, grid.latlon[i * 2], grid.latlon[i * 2 + 1], BODY_R_KM[body]);
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  }
  return best;
}

/** Clamp an unprojected click to the map rectangle. */
export function clampLonLat(x: number, y: number): { lon: number; lat: number } {
  return { lon: Math.max(-180, Math.min(180, x)), lat: Math.max(-90, Math.min(90, y)) };
}

/** Orthographic zoom so the 360×180 map fits a w×h canvas. */
export function fitZoom(w: number, h: number): number {
  return Math.log2(Math.max(1e-3, Math.min(w / 360, h / 180)));
}

/** Vertical pixel offsets that stack labels of nearby landmarks instead of overlapping them. */
export function labelOffsets(landmarks: Target[]): Map<string, number> {
  const placed: { lat: number; lon: number; dy: number }[] = [];
  const out = new Map<string, number>();
  for (const t of [...landmarks].sort((a, b) => a.lat - b.lat || a.lon - b.lon)) {
    let dy = 0;
    for (const p of placed) {
      if (Math.abs(p.lat - t.lat) < 8 && Math.abs(p.lon - t.lon) < 120 && p.dy - 16 < dy) {
        dy = p.dy - 16;
      }
    }
    placed.push({ lat: t.lat, lon: t.lon, dy });
    out.set(t.id, dy);
  }
  return out;
}

export function buildTargetLayers(inp: TargetLayerInput, extra: Layer[] = []): Layer[] {
  const offsets = labelOffsets(inp.landmarks);
  const layers: Layer[] = [
    // While switching worlds the new texture may still be loading. deck.gl cannot use null as an image.
    ...(inp.texture
      ? [
          new BitmapLayer({
            id: 'body-texture',
            image: inp.texture,
            bounds: [-180, -90, 180, 90],
          }),
        ]
      : []),
    ...extra,
    new ScatterplotLayer<Target>({
      id: 'landmarks',
      data: inp.landmarks,
      getPosition: (t) => [t.lon, t.lat],
      getRadius: (t) => (t.id === inp.selectedId ? 9 : 6),
      radiusUnits: 'pixels',
      getFillColor: (t) => (t.id === inp.selectedId ? MOON_ACCENT : TEXT),
      getLineColor: [11, 15, 23, 255],
      lineWidthUnits: 'pixels',
      getLineWidth: 2,
      stroked: true,
      pickable: true,
      updateTriggers: { getRadius: inp.selectedId, getFillColor: inp.selectedId },
    }),
    new TextLayer<Target>({
      id: 'landmark-labels',
      data: inp.landmarks,
      getPosition: (t) => [t.lon, t.lat],
      getText: (t) => t.name,
      getSize: 12,
      getColor: (t) => (t.id === inp.selectedId ? MOON_ACCENT : TEXT),
      getPixelOffset: (t) => [12, offsets.get(t.id) ?? 0],
      getTextAnchor: 'start',
      getAlignmentBaseline: 'center',
      fontFamily: 'system-ui, "Segoe UI", sans-serif',
      characterSet: 'auto',
      background: true,
      getBackgroundColor: BG,
      backgroundPadding: [4, 2],
      updateTriggers: { getColor: inp.selectedId },
    }),
  ];
  if (inp.custom) {
    layers.push(
      new ScatterplotLayer<CustomPoint>({
        id: 'custom-target',
        data: [inp.custom],
        getPosition: (p) => [p.lon, p.lat],
        getRadius: 9,
        radiusUnits: 'pixels',
        filled: false,
        stroked: true,
        getLineColor: MOON_ACCENT,
        lineWidthUnits: 'pixels',
        getLineWidth: 3,
      }),
    );
  }
  return layers;
}
