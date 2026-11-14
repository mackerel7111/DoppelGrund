// Pointer handling for the 3D view: drag rotates the globe under the pointer, a click picks.
// Earth clicks resolve to an Earth row via h3-js (same cell id as earth_h3.txt); body clicks pick
// the nearest landmark within 3°.
import * as THREE from 'three';
import { latLngToCell } from 'h3-js';
import type { Target } from '../data/types';
import { haversineKm } from '../engine/geo';
import type { GlobeScene } from './GlobeScene';

export const LANDMARK_PICK_DEG = 3;
const DRAG_PX = 4; // movement beyond this is a drag, not a click
const ROTATE_PER_PX = 0.006; // radians

export interface GlobeHit {
  globe: 'body' | 'earth';
  lat: number;
  lng: number;
}

/** Ray-cast normalised device coordinates against both globe spheres; nearest hit wins. */
export function pickGlobe(scene: GlobeScene, ndcX: number, ndcY: number): GlobeHit | null {
  const ray = new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2(ndcX, ndcY), scene.camera);
  let best: (GlobeHit & { d: number }) | null = null;
  for (const id of ['body', 'earth'] as const) {
    const g = id === 'body' ? scene.bodyGlobe : scene.earthGlobe;
    const center = g.getWorldPosition(new THREE.Vector3());
    const hit = ray.ray.intersectSphere(
      new THREE.Sphere(center, g.getGlobeRadius()),
      new THREE.Vector3(),
    );
    if (!hit) continue;
    const d = hit.distanceTo(ray.ray.origin);
    if (best && best.d <= d) continue;
    const local = g.worldToLocal(hit.clone());
    const geo = g.toGeoCoords({ x: local.x, y: local.y, z: local.z });
    best = { globe: id, lat: geo.lat, lng: geo.lng, d };
  }
  return best ? { globe: best.globe, lat: best.lat, lng: best.lng } : null;
}

/** Nearest landmark within `maxDeg` of great-circle angle, or null. */
export function nearestLandmark(
  targets: Target[],
  lat: number,
  lng: number,
  maxDeg = LANDMARK_PICK_DEG,
): Target | null {
  let best: Target | null = null;
  let bestDeg = maxDeg;
  for (const t of targets) {
    const deg = (haversineKm(lat, lng, t.lat, t.lon, 1) * 180) / Math.PI;
    if (deg <= bestDeg) {
      best = t;
      bestDeg = deg;
    }
  }
  return best;
}

/** Earth row for a lat/lng: the H3 res-4 cell containing the point, if it is in the bundle. */
export function rowAt(lookup: Map<string, number>, lat: number, lng: number): number | null {
  return lookup.get(latLngToCell(lat, lng, 4)) ?? null;
}

export function buildRowLookup(h3: string[]): Map<string, number> {
  return new Map(h3.map((c, i) => [c, i]));
}

export interface PickHandlers {
  onEarth: (lat: number, lng: number) => void;
  onBody: (lat: number, lng: number) => void;
}

/** Attach drag-rotate + click-pick to the renderer canvas; returns a detach function. */
export function attachPicking(scene: GlobeScene, handlers: PickHandlers): () => void {
  const el = scene.renderer.domElement;
  let start: { x: number; y: number; globe: GlobeHit['globe'] | null } | null = null;
  let last = { x: 0, y: 0 };
  let dragged = false;
  let vel = { yaw: 0, pitch: 0, t: 0 }; // rad/s from the latest pointer move

  const ndc = (ev: PointerEvent): [number, number] => {
    const r = el.getBoundingClientRect();
    return [((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1];
  };
  const down = (ev: PointerEvent): void => {
    scene.markInteraction();
    const [x, y] = ndc(ev);
    start = { x: ev.clientX, y: ev.clientY, globe: pickGlobe(scene, x, y)?.globe ?? null };
    last = { x: ev.clientX, y: ev.clientY };
    dragged = false;
    scene.fling('body', 0, 0);
    scene.fling('earth', 0, 0);
    vel = { yaw: 0, pitch: 0, t: ev.timeStamp };
    el.setPointerCapture(ev.pointerId);
  };
  const move = (ev: PointerEvent): void => {
    if (!start) return;
    if (Math.hypot(ev.clientX - start.x, ev.clientY - start.y) > DRAG_PX) dragged = true;
    if (dragged && start.globe) {
      const dYaw = (ev.clientX - last.x) * ROTATE_PER_PX;
      const dPitch = (ev.clientY - last.y) * ROTATE_PER_PX;
      scene.rotateBy(start.globe, dYaw, dPitch);
      const dt = Math.max(1, ev.timeStamp - vel.t) / 1000;
      vel = { yaw: dYaw / dt, pitch: dPitch / dt, t: ev.timeStamp };
    }
    last = { x: ev.clientX, y: ev.clientY };
  };
  const up = (ev: PointerEvent): void => {
    if (start && !dragged) {
      const [x, y] = ndc(ev);
      const hit = pickGlobe(scene, x, y);
      if (hit?.globe === 'earth') handlers.onEarth(hit.lat, hit.lng);
      else if (hit?.globe === 'body') handlers.onBody(hit.lat, hit.lng);
    }
    // a pause before release means no fling
    if (start?.globe && dragged && ev.timeStamp - vel.t < 80)
      scene.fling(start.globe, vel.yaw, vel.pitch);
    start = null;
  };
  const wheel = (ev: WheelEvent): void => {
    ev.preventDefault();
    const r = el.getBoundingClientRect();
    const hit = pickGlobe(
      scene,
      ((ev.clientX - r.left) / r.width) * 2 - 1,
      -((ev.clientY - r.top) / r.height) * 2 + 1,
    );
    scene.zoomBy(hit?.globe ?? null, ev.deltaY);
  };
  el.addEventListener('wheel', wheel, { passive: false });
  el.addEventListener('pointerdown', down);
  el.addEventListener('pointermove', move);
  el.addEventListener('pointerup', up);
  el.style.cursor = 'grab';
  return () => {
    el.removeEventListener('wheel', wheel);
    el.removeEventListener('pointerdown', down);
    el.removeEventListener('pointermove', move);
    el.removeEventListener('pointerup', up);
  };
}
