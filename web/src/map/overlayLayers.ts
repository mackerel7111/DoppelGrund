// Curated point layers (known sites, volcanoes, lava tubes, Sarawak caves, lunar pits).
// They are priors shown for context, never detections and never scored.
import { ScatterplotLayer } from '@deck.gl/layers';
import type { Layer } from '@deck.gl/core';
import type { GeoJsonFeature, GeoJsonFeatureCollection } from '../data/loader';
import type { LayerId } from '../stores/session';

type RGBA = [number, number, number, number];

export interface OverlayStyle {
  label: string;
  color: RGBA;
  hollow: boolean;
  radius: number;
  panel: 'earth' | 'body';
}

export const OVERLAY_STYLES: Record<LayerId, OverlayStyle> = {
  known_sites: {
    label: 'Known analogue sites',
    color: [230, 234, 242, 255],
    hollow: true,
    radius: 6,
    panel: 'earth',
  },
  volcanoes: {
    label: 'Volcanoes',
    color: [255, 107, 107, 230],
    hollow: false,
    radius: 3,
    panel: 'earth',
  },
  lava_tubes: {
    label: 'Lava tubes',
    color: [91, 214, 160, 255],
    hollow: false,
    radius: 4,
    panel: 'earth',
  },
  sarawak_caves: {
    label: 'Sarawak caves',
    color: [179, 157, 219, 255],
    hollow: false,
    radius: 4,
    panel: 'earth',
  },
  lunar_pits: {
    label: 'Lunar pits (Moon panel)',
    color: [79, 195, 247, 255],
    hollow: true,
    radius: 4,
    panel: 'body',
  },
};

export const LAYER_ORDER: LayerId[] = [
  'known_sites',
  'volcanoes',
  'lava_tubes',
  'sarawak_caves',
  'lunar_pits',
];

function position(f: GeoJsonFeature): [number, number] {
  const c = f.geometry.coordinates;
  return Array.isArray(c) && typeof c[0] === 'number' && typeof c[1] === 'number'
    ? [c[0], c[1]]
    : [NaN, NaN];
}

function pointLayer(id: LayerId, fc: GeoJsonFeatureCollection): Layer {
  const st = OVERLAY_STYLES[id];
  const points = fc.features.filter((f) => f.geometry.type === 'Point');
  return new ScatterplotLayer<GeoJsonFeature>({
    id: `overlay-${id}`,
    data: points,
    getPosition: position,
    getRadius: st.radius,
    radiusUnits: 'pixels',
    filled: !st.hollow,
    stroked: st.hollow,
    getFillColor: st.color,
    getLineColor: st.color,
    lineWidthUnits: 'pixels',
    getLineWidth: 2,
    pickable: false,
  });
}

/** Overlay layers for one panel given toggles and the loaded GeoJSON. */
export function buildOverlays(
  panel: 'earth' | 'body',
  toggles: Record<LayerId, boolean>,
  data: Partial<Record<LayerId | 'land', GeoJsonFeatureCollection>>,
): Layer[] {
  const out: Layer[] = [];
  for (const id of LAYER_ORDER) {
    const fc = data[id];
    if (OVERLAY_STYLES[id].panel === panel && toggles[id] && fc) out.push(pointLayer(id, fc));
  }
  return out;
}

/** CSS colour for legend swatches. */
export function cssColor(c: RGBA): string {
  return `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${(c[3] / 255).toFixed(2)})`;
}
