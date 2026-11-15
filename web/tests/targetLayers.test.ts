import { describe, expect, it } from 'vitest';
import {
  buildTargetLayers,
  clampLonLat,
  fitZoom,
  labelOffsets,
  nearestDisc,
} from '../src/map/targetLayers';
import type { DiscGrid, Target } from '../src/data/types';
import { formatLatLon } from '../src/stores/selectors';

function grid(points: [number, number][]): DiscGrid {
  return {
    n: points.length,
    features: new Float32Array(points.length * 10),
    lith: new Float32Array(points.length * 6),
    latlon: Float32Array.from(points.flat()),
  };
}

describe('target panel helpers', () => {
  it('keeps landmark layers usable while a world texture is loading', () => {
    const input = { texture: null, landmarks: [], selectedId: null, custom: null };
    expect(buildTargetLayers(input).some((layer) => layer.id === 'body-texture')).toBe(false);
    expect(buildTargetLayers(input).some((layer) => layer.id === 'landmarks')).toBe(true);
    const texture = {} as ImageBitmap;
    expect(
      buildTargetLayers({ ...input, texture }).some((layer) => layer.id === 'body-texture'),
    ).toBe(true);
  });

  it('snaps to the nearest disc on the sphere, across the antimeridian and near the pole', () => {
    const g = grid([
      [0, 179],
      [0, 150],
      [-88.5, 5],
      [-80, 180],
    ]);
    expect(nearestDisc(g, 0, -179.5, 'moon')).toBe(0);
    expect(nearestDisc(g, -89.5, -170, 'moon')).toBe(2);
    expect(nearestDisc(grid([]), 0, 0, 'mars')).toBe(-1);
  });

  it('formats coordinates and clamps clicks to the map', () => {
    expect(formatLatLon(-89.04, 12.25)).toBe('89.0°S, 12.3°E');
    expect(formatLatLon(18.4, -77.5)).toBe('18.4°N, 77.5°W');
    expect(clampLonLat(200, -95)).toEqual({ lon: 180, lat: -90 });
  });

  it('fits 360×180 units into the canvas', () => {
    expect(fitZoom(720, 360)).toBeCloseTo(1, 12);
    expect(fitZoom(720, 100)).toBeCloseTo(Math.log2(100 / 180), 12);
  });

  it('stacks labels of nearby polar landmarks', () => {
    const t = (id: string, lat: number, lon: number) => ({ id, lat, lon }) as Target;
    const off = labelOffsets([t('a', -88.5, 5), t('b', -85, 60), t('c', 10, 30)]);
    expect(off.get('a')).toBe(0);
    expect(off.get('b')).toBe(-16);
    expect(off.get('c')).toBe(0);
  });
});
