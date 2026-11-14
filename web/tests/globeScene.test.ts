// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import {
  FILL_FRACTION,
  FPS_FLOOR,
  FPS_WINDOW_S,
  FpsWatch,
  IDLE_RESUME_MS,
  IDLE_EASE_MS,
  IDLE_SPIN_RAD_S,
  decayVelocity,
  STAR_COUNT,
  STAR_SHELL,
  cameraFit,
  idleYaw,
  starPositions,
  webglAvailable,
} from '../src/globe/GlobeScene';

function feed(
  w: FpsWatch,
  fps: number,
  seconds: number,
  t0: number,
): { t: number; fired: boolean } {
  let t = t0;
  let fired = false;
  const dt = 1000 / fps;
  for (let i = 0; i < fps * seconds; i++) {
    t += dt;
    fired = w.frame(t) || fired;
  }
  return { t, fired };
}

describe('3D fallback rules (R10.4)', () => {
  it(`falls back only after fps < ${FPS_FLOOR} for ${FPS_WINDOW_S} consecutive seconds`, () => {
    const w = new FpsWatch(0);
    let r = feed(w, 60, 5, 0);
    expect(r.fired).toBe(false);
    r = feed(w, 12, 2, r.t);
    expect(r.fired).toBe(false);
    r = feed(w, 60, 1, r.t); // recovery resets the counter
    expect(r.fired).toBe(false);
    r = feed(w, 12, 3.2, r.t);
    expect(r.fired).toBe(true);
  });

  it('reports WebGL as unavailable when no context can be created (jsdom)', () => {
    expect(webglAvailable()).toBe(false);
  });
});

describe('space look', () => {
  it('places a deterministic star shell', () => {
    const a = starPositions();
    expect(a).toHaveLength(STAR_COUNT * 3);
    expect(Array.from(starPositions(5, 10, 1))).toEqual(Array.from(starPositions(5, 10, 1)));
    for (let i = 0; i < a.length; i += 3) {
      expect(Math.hypot(a[i], a[i + 1], a[i + 2])).toBeCloseTo(STAR_SHELL, 0);
    }
  });

  it('idle spin starts after IDLE_RESUME_MS and never with reduced motion', () => {
    expect(idleYaw(IDLE_RESUME_MS - 1, 0, 0.016, false)).toBe(0);
    expect(idleYaw(IDLE_RESUME_MS + 1, 0, 0.5, false)).toBeGreaterThan(0);
    // eases in: half-way through the ramp spins at half rate, then full rate
    expect(idleYaw(IDLE_RESUME_MS + IDLE_EASE_MS / 2, 0, 1, false)).toBeCloseTo(
      IDLE_SPIN_RAD_S / 2,
    );
    expect(idleYaw(IDLE_RESUME_MS + IDLE_EASE_MS, 0, 1, false)).toBeCloseTo(IDLE_SPIN_RAD_S);
    // inertia decay is frame-rate independent
    expect(decayVelocity(decayVelocity(2, 0.05), 0.05)).toBeCloseTo(decayVelocity(2, 0.1));
    expect(idleYaw(IDLE_RESUME_MS * 10, 0, 0.5, true)).toBe(0);
  });

  it('centres both globes right of the panel and fills the visible width', () => {
    const [w, h, panel, r, fov] = [1600, 900, 360, 100, 40];
    const fit = cameraFit(w, h, panel, r, fov);
    const cam = new THREE.PerspectiveCamera(fov, w / h, 1, 5000);
    cam.position.set(0, 0, fit.z);
    cam.setViewOffset(w, h, fit.offsetX, 0, w, h);
    cam.updateMatrixWorld(true);
    // world origin lands at the centre of the area right of the panel
    const centre = new THREE.Vector3(0, 0, 0).project(cam);
    expect(((centre.x + 1) / 2) * w).toBeCloseTo(panel + (w - panel) / 2, 3);
    // outer globe edges span FILL_FRACTION of the visible width
    const left = new THREE.Vector3(-2.35 * r, 0, 0).project(cam);
    const right = new THREE.Vector3(2.35 * r, 0, 0).project(cam);
    const px = ((right.x - left.x) / 2) * w;
    expect(px / (w - panel)).toBeCloseTo(FILL_FRACTION, 1);
    expect(cameraFit(w, h, 0, r, fov).offsetX).toBe(-0);
  });
});
