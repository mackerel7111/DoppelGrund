// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import ThreeGlobe from 'three-globe';
import { latLngToCell } from 'h3-js';
import { arcControl, arcPoints, ARC_SEGMENTS } from '../src/globe/arcs';
import {
  buildRowLookup,
  nearestLandmark,
  pickGlobe,
  pickMatchMarker,
  rowAt,
} from '../src/globe/picking';
import type { GlobeScene } from '../src/globe/GlobeScene';
import type { Target } from '../src/data/types';

describe('arcs', () => {
  it('lifts the control point above the midpoint and ends exactly on both globes', () => {
    const a = new THREE.Vector3(-140, 0, 100);
    const b = new THREE.Vector3(140, 0, 100);
    const c = arcControl(a, b);
    expect(c.y).toBeGreaterThan(0);
    expect(c.x).toBeCloseTo(0, 10);
    const pts = arcPoints(a, b);
    expect(pts).toHaveLength(ARC_SEGMENTS + 1);
    expect(pts[0].equals(a)).toBe(true);
    expect(pts[ARC_SEGMENTS].distanceTo(b)).toBeLessThan(1e-9);
  });
});

describe('picking', () => {
  it('opens the exact visible match near its number, not an unrelated cell or far-side marker', () => {
    const camera = new THREE.PerspectiveCamera(40, 2, 1, 5000);
    camera.position.set(0, 0, 500);
    camera.updateMatrixWorld();
    const scene = {
      camera,
      earthGlobe: { position: new THREE.Vector3() },
      worldPoint: (_body: string, lat: number) => new THREE.Vector3(0, 0, lat === 0 ? 100 : -100),
    } as unknown as GlobeScene;
    const front = { n: 1, row: 42, lat: 0, lng: 0 };
    const back = { n: 2, row: 99, lat: 1, lng: 0 };
    expect(pickMatchMarker(scene, [front, back], 0.02, 0, 1600, 900)).toBe(42);
    expect(pickMatchMarker(scene, [back], 0, 0, 1600, 900)).toBeNull();
    expect(pickMatchMarker(scene, [front], 0.5, 0, 1600, 900)).toBeNull();
    expect(pickMatchMarker(scene, [front], 0, 0, 0, 0)).toBeNull();
  });

  it('finds the nearest landmark within 3° only', () => {
    const t = (id: string, lat: number, lon: number) => ({ id, lat, lon }) as Target;
    const targets = [t('a', -88.5, 5), t('b', 10, 30)];
    expect(nearestLandmark(targets, -89.9, 170)?.id).toBe('a'); // across the pole
    expect(nearestLandmark(targets, 12, 31)?.id).toBe('b');
    expect(nearestLandmark(targets, 30, 30)).toBeNull();
  });

  it('maps a lat/lng to the Earth row of its H3 res-4 cell', () => {
    const cells = [latLngToCell(23, 10, 4), latLngToCell(-78, 160, 4)];
    const lookup = buildRowLookup(cells);
    expect(rowAt(lookup, 23, 10)).toBe(0);
    expect(rowAt(lookup, -78, 160)).toBe(1);
    expect(rowAt(lookup, 0, 0)).toBeNull();
  });

  it('ray-casts against rotated, offset globes and returns lat/lng in globe coordinates', () => {
    const body = new ThreeGlobe({ animateIn: false });
    const earth = new ThreeGlobe({ animateIn: false });
    const r = earth.getGlobeRadius();
    body.position.set(-1.4 * r, 0, 0);
    earth.position.set(1.4 * r, 0, 0);
    earth.rotation.set((20 * Math.PI) / 180, (-45 * Math.PI) / 180, 0);
    const camera = new THREE.PerspectiveCamera(40, 2, 1, 5000);
    camera.position.set(0, 0, 3.4 * r);
    const root = new THREE.Scene();
    root.add(body, earth, camera);
    root.updateMatrixWorld(true);
    // project the Earth globe point (20°N, 45°E) to NDC and pick it back
    const local = earth.getCoords(20, 45, 0);
    const world = earth.localToWorld(new THREE.Vector3(local.x, local.y, local.z));
    const ndc = world.clone().project(camera);
    const hit = pickGlobe(
      { camera, bodyGlobe: body, earthGlobe: earth } as unknown as GlobeScene,
      ndc.x,
      ndc.y,
    );
    expect(hit?.globe).toBe('earth');
    expect(hit?.lat).toBeCloseTo(20, 3);
    expect(hit?.lng).toBeCloseTo(45, 3);
    const left = body.localToWorld(new THREE.Vector3(0, 0, r)).project(camera);
    expect(
      pickGlobe(
        { camera, bodyGlobe: body, earthGlobe: earth } as unknown as GlobeScene,
        left.x,
        left.y,
      )?.globe,
    ).toBe('body');
    expect(
      pickGlobe({ camera, bodyGlobe: body, earthGlobe: earth } as unknown as GlobeScene, 0, 0.95),
    ).toBeNull();
  });

  it('stays correct with a left-panel view offset', () => {
    const earth = new ThreeGlobe({ animateIn: false });
    const r = earth.getGlobeRadius();
    earth.position.set(1.4 * r, 0, 0);
    const camera = new THREE.PerspectiveCamera(40, 16 / 9, 1, 5000);
    camera.position.set(0, 0, 5 * r);
    camera.setViewOffset(1600, 900, -180, 0, 1600, 900);
    camera.updateMatrixWorld(true);
    const root = new THREE.Scene();
    root.add(earth, camera);
    root.updateMatrixWorld(true);
    const local = earth.getCoords(10, 20, 0);
    const world = earth.localToWorld(new THREE.Vector3(local.x, local.y, local.z));
    const ndc = world.clone().project(camera);
    const hit = pickGlobe(
      { camera, bodyGlobe: new ThreeGlobe(), earthGlobe: earth } as unknown as GlobeScene,
      ndc.x,
      ndc.y,
    );
    expect(hit?.globe).toBe('earth');
    expect(hit?.lat).toBeCloseTo(10, 3);
    expect(hit?.lng).toBeCloseTo(20, 3);
  });
});
