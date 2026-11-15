// deck.gl layers for the Earth map (MapView): land basemap, H3 heat map, card rings, selection.
import { GeoJsonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import { H3HexagonLayer } from '@deck.gl/geo-layers';
import type { Layer } from '@deck.gl/core';
import type { GeoJsonFeatureCollection } from '../data/loader';
import type { CardMarker } from '../stores/selectors';

type RGBA = [number, number, number, number];
export const EARTH_ACCENT: RGBA = [79, 195, 247, 255];
export const MOON_ACCENT: RGBA = [242, 181, 68, 255];
const LAND_FILL: RGBA = [26, 34, 51, 255];
const LAND_LINE: RGBA = [38, 48, 70, 255];
const DARK: RGBA = [11, 15, 23, 230];

export interface EarthLayerInput {
  land: GeoJsonFeatureCollection | null;
  h3: string[];
  rows: number[]; // [0..N)
  colors: Uint8ClampedArray; // N×4
  colorVersion: number;
  cards: CardMarker[];
  selected: { lat: number; lng: number } | null;
}

export function buildEarthLayers(inp: EarthLayerInput, overlays: Layer[] = []): Layer[] {
  const layers: Layer[] = [];
  if (inp.land) {
    layers.push(
      new GeoJsonLayer({
        id: 'land',
        // our minimal FeatureCollection type is structurally GeoJSON; deck's type is stricter
        data: inp.land as never,
        filled: true,
        stroked: true,
        getFillColor: LAND_FILL,
        getLineColor: LAND_LINE,
        lineWidthMinPixels: 1,
        pickable: false,
      }),
    );
  }
  layers.push(
    new H3HexagonLayer<number>({
      id: 'hexes',
      data: inp.rows,
      getHexagon: (i) => inp.h3[i],
      // single-resolution fast path (instanced hexagons)
      highPrecision: false,
      extruded: false,
      stroked: false,
      filled: true,
      coverage: 1,
      getFillColor: (i, { target }) => {
        const t = target as number[];
        const o = i * 4;
        t[0] = inp.colors[o];
        t[1] = inp.colors[o + 1];
        t[2] = inp.colors[o + 2];
        t[3] = inp.colors[o + 3];
        return t as RGBA;
      },
      updateTriggers: { getFillColor: inp.colorVersion },
      pickable: true,
    }),
    ...overlays,
  );
  if (inp.selected) {
    layers.push(
      new ScatterplotLayer<{ lat: number; lng: number }>({
        id: 'selected-hex',
        data: [inp.selected],
        getPosition: (p) => [p.lng, p.lat],
        getRadius: 30_000,
        radiusMinPixels: 15,
        filled: false,
        stroked: true,
        getLineColor: MOON_ACCENT,
        lineWidthUnits: 'pixels',
        getLineWidth: 3,
      }),
    );
  }
  layers.push(
    new ScatterplotLayer<CardMarker>({
      id: 'card-rings',
      data: inp.cards,
      getPosition: (c) => [c.lng, c.lat],
      getRadius: 30_000,
      radiusUnits: 'meters',
      radiusMinPixels: 11,
      filled: true,
      getFillColor: DARK,
      stroked: true,
      getLineColor: EARTH_ACCENT,
      lineWidthUnits: 'pixels',
      getLineWidth: 2,
      pickable: true,
    }),
    new TextLayer<CardMarker>({
      id: 'card-numbers',
      pickable: true,
      data: inp.cards,
      getPosition: (c) => [c.lng, c.lat],
      getText: (c) => String(c.n),
      getSize: 13,
      getColor: [230, 234, 242, 255],
      fontWeight: 700,
      fontFamily: 'system-ui, "Segoe UI", sans-serif',
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'center',
    }),
  );
  return layers;
}
