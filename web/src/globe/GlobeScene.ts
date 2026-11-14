// Two three-globe objects (target body left, Earth right) in one three.js scene (ADR-0003).
// Look: black space + stars, one fixed sun, Earth basemap with a smoothed heat overlay.
import * as THREE from 'three';
import ThreeGlobe from 'three-globe';
import type { Body, Target } from '../data/types';
import type { CardMarker } from '../stores/selectors';
import { mulberry32 } from '../engine/prng';

export const FPS_FLOOR = 20; // R10.4
export const FPS_WINDOW_S = 3;

// ---- look & feel knobs (alpha ramp constants A_LOW / GAMMA / TOP_FRACTION live in painter.ts) ----
/** Heat overlay is down-sampled to this size, then stretched back up: that blur is the smoothing. */
export const HEAT_W = 512;
export const HEAT_H = 256;
/** Opacity when the smoothed heat is drawn over the basemap (on top of the per-pixel alpha ramp). */
export const HEAT_OPACITY = 1;
/** Draw the blurred heat this many times (screen blend: each pass brightens the glow). */
export const HEAT_PASSES = 2;
/** Canvas blend for the heat: 'screen' makes it glow on the veiled basemap. */
export const HEAT_BLEND: GlobalCompositeOperation = 'screen';
/** Black veil over the basemap while a heat overlay is shown, so the glow pops. */
export const BASEMAP_VEIL = 0.12;
export const IDLE_RESUME_MS = 15_000;
export const IDLE_SPIN_RAD_S = 0.045;
/** Idle spin eases in over this long after IDLE_RESUME_MS. */
export const IDLE_EASE_MS = 1500;
/** Frame dt cap (s) so tab switches / hitches never jump the motion. */
export const MAX_DT_S = 0.1;
/** Drag-release velocity decays as exp(-INERTIA_DECAY * t) (frame-rate independent). */
export const INERTIA_DECAY = 4;
/** Scroll zoom: closest = this x the fit distance; wheel sensitivity; ease rate (1/s). */
export const ZOOM_MAX = 1.8;
export const ZOOM_PER_WHEEL = 0.0012;
export const ZOOM_EASE = 8;
/** Ease rate (1/s) of facePoint turns. */
export const FACE_EASE = 4;
/** Tone mapping / light rig: calm, bright base globe. */
export const SUN_INTENSITY = 2;
export const AMBIENT_INTENSITY = 0.6;
export const STAR_COUNT = 2000;
export const STAR_SHELL = 1800;
/** Globe centres sit at ±GLOBE_OFFSET × radius from the origin. */
export const GLOBE_OFFSET = 1.35;
/** Both globes together fill this fraction of the visible width. */
export const FILL_FRACTION = 0.82;

export const EARTH_ATMOSPHERE = { color: '#4FC3F7', altitude: 0.15 };
export const MARS_ATMOSPHERE = { color: '#c98a64', altitude: 0.05 };
export const MOON_ATMOSPHERE = { color: '#cfd4dc', altitude: 0.035 };
/** Earth texture width; 2048 still gives > 1 texel per screen pixel at full zoom, 4× cheaper to redraw than 4096. */
export const EARTH_TEX_W = 2048;
/** Glow radii in texture px: landmarks on the 2048-wide body texture, Earth halos on the EARTH_TEX_W-wide one. */
export const LANDMARK_GLOW_PX = 14;
export const LANDMARK_SELECTED_GLOW_PX = 30;
export const MATCH_HALO_PX = [100, 68] as const; // [overall card, others]
export const SELECTED_GLOW_PX = 45; // white glow on the place whose detail view is open

/** Soft radial glow at lat/lng on an equirectangular canvas; stretched by 1/cos(lat), wraps in longitude. */
export function paintGlow(
  ctx: CanvasRenderingContext2D,
  lat: number,
  lng: number,
  radius: number,
  rgb: string,
  alpha: number,
): void {
  const { width: W, height: H } = ctx.canvas;
  const y = ((90 - lat) / 180) * H;
  const sx = 1 / Math.max(0.2, Math.cos((lat * Math.PI) / 180));
  const x0 = ((lng + 180) / 360) * W;
  const g = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
  g.addColorStop(0, `rgba(${rgb},${alpha})`);
  g.addColorStop(0.4, `rgba(${rgb},${alpha * 0.35})`);
  g.addColorStop(1, `rgba(${rgb},0)`);
  for (const dx of [-W, 0, W]) {
    ctx.save();
    ctx.translate(x0 + dx, y);
    ctx.scale(sx, 1);
    ctx.fillStyle = g;
    ctx.fillRect(-radius, -radius, 2 * radius, 2 * radius);
    ctx.restore();
  }
}

/** Exponential velocity decay over dt seconds; snaps to 0 when negligible. */
export function decayVelocity(v: number, dt: number): number {
  const out = v * Math.exp(-INERTIA_DECAY * dt);
  return Math.abs(out) < 1e-3 ? 0 : out;
}

/** Deterministic star shell: xyz triples uniformly distributed on a sphere of `radius`. */
export function starPositions(n = STAR_COUNT, radius = STAR_SHELL, seed = 0x5742): Float32Array {
  const rnd = mulberry32(seed);
  const out = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const z = 2 * rnd() - 1;
    const a = 2 * Math.PI * rnd();
    const q = Math.sqrt(1 - z * z);
    out[i * 3] = radius * q * Math.cos(a);
    out[i * 3 + 1] = radius * q * Math.sin(a);
    out[i * 3 + 2] = radius * z;
  }
  return out;
}

/**
 * Camera distance and horizontal view offset (px) so both globes are centred in the visible area
 * right of a `panel`-px overlay and fill FILL_FRACTION of its width (never taller than the viewport).
 */
export function cameraFit(
  w: number,
  h: number,
  panel: number,
  r: number,
  fovDeg: number,
): { z: number; offsetX: number } {
  const tanHalf = Math.tan((fovDeg / 2) * (Math.PI / 180));
  const visibleW = Math.max(1, w - panel);
  const span = 2 * (GLOBE_OFFSET + 1) * r; // world width of both globes
  const zWidth = ((span / FILL_FRACTION) * h) / (2 * tanHalf * visibleW);
  const zHeight = (2 * r) / (0.8 * 2 * tanHalf); // globe diameter ≤ 80 % of viewport height
  return { z: Math.max(zWidth, zHeight), offsetX: -panel / 2 };
}

/** Idle-spin step in radians: 0 while the user is active or prefers reduced motion. */
export function idleYaw(
  now: number,
  lastInteraction: number,
  dtSec: number,
  reduced: boolean,
): number {
  const idle = now - lastInteraction - IDLE_RESUME_MS;
  if (reduced || idle < 0) return 0;
  return IDLE_SPIN_RAD_S * Math.min(1, idle / IDLE_EASE_MS) * dtSec;
}

export interface GlobeSceneOptions {
  onFallback: (reason: string) => void;
}

/** True when a WebGL context can be created. */
export function webglAvailable(): boolean {
  try {
    const c = document.createElement('canvas');
    return Boolean(c.getContext('webgl2') ?? c.getContext('webgl'));
  } catch {
    return false;
  }
}

/** Tracks per-second frame counts; reports when fps stayed below the floor for the window. */
export class FpsWatch {
  private frames = 0;
  private windowStart: number;
  private lowSeconds = 0;
  constructor(now: number) {
    this.windowStart = now;
  }
  /** Returns true when the fallback should trigger. */
  frame(now: number): boolean {
    this.frames++;
    const dt = now - this.windowStart;
    if (dt < 1000) return false;
    const fps = (this.frames * 1000) / dt;
    this.lowSeconds = fps < FPS_FLOOR ? this.lowSeconds + 1 : 0;
    this.frames = 0;
    this.windowStart = now;
    return this.lowSeconds >= FPS_WINDOW_S;
  }
}

function makeCanvas(
  width: number,
  height: number,
  willReadFrequently = false,
): { canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D } {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d', { willReadFrequently });
  if (!ctx) throw new Error('2D canvas unavailable');
  return { canvas, ctx };
}

function canvasTexture(
  width: number,
  height: number,
): {
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D;
  texture: THREE.CanvasTexture;
} {
  const c = makeCanvas(width, height);
  const texture = new THREE.CanvasTexture(c.canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return { ...c, texture };
}

export class GlobeScene {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(40, 1, 1, 5000);
  readonly bodyGlobe = new ThreeGlobe({ animateIn: false });
  readonly earthGlobe = new ThreeGlobe({ animateIn: false });
  private readonly container: HTMLElement;
  private readonly opts: GlobeSceneOptions;
  private readonly earthTex = canvasTexture(EARTH_TEX_W, EARTH_TEX_W / 2); // basemap + smoothed heat
  private readonly bodyTex = canvasTexture(2048, 1024);
  // worker RGBA (resized to whatever it sends); CPU-backed: halo colours are read back per card
  private readonly heatFull = makeCanvas(1024, 512, true);
  private readonly heatSmall = makeCanvas(HEAT_W, HEAT_H);
  private readonly stars: THREE.Points;
  private basemap: ImageBitmap | null = null;
  private bodyImg: ImageBitmap | null = null;
  private bodyKind: Body = 'moon';
  private landmarks: Target[] = [];
  private selectedId: string | null = null;
  private custom: { lat: number; lon: number } | null = null;
  private cards: CardMarker[] = [];
  private selected: { lat: number; lng: number } | null = null;
  private readonly spin = {
    body: { yaw: 0, pitch: 0 },
    earth: { yaw: 0, pitch: 0 },
  };
  private fitZ = 3.4;
  private readonly aim: Record<'body' | 'earth', { x: number; y: number } | null> = {
    body: null,
    earth: null,
  };
  private zoom = 1;
  private zoomTarget = 1;
  private zoomCx = 0;
  private zoomCxTarget = 0;
  private hasHeat = false;
  private lastInteraction = performance.now();
  private lastFrame = performance.now();
  private readonly reducedMotion: MediaQueryList | null =
    typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)')
      : null;
  private readonly fps = new FpsWatch(performance.now());
  private readonly resizeObs: ResizeObserver;
  private disposed = false;
  /** Called every frame before rendering (arcs follow rotating globes). */
  readonly onFrame: (() => void)[] = [];

  constructor(container: HTMLElement, opts: GlobeSceneOptions) {
    this.container = container;
    this.opts = opts;
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setClearColor(0x000000, 1);
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    const aniso = this.renderer.capabilities.getMaxAnisotropy();
    this.earthTex.texture.anisotropy = aniso;
    this.bodyTex.texture.anisotropy = aniso;
    // absolutely positioned so the canvas never drives the container's size (resize loop)
    Object.assign(this.renderer.domElement.style, { position: 'absolute', inset: '0' });
    container.appendChild(this.renderer.domElement);

    const r = this.earthGlobe.getGlobeRadius();
    this.bodyGlobe.position.set(-GLOBE_OFFSET * r, 0, 0);
    this.earthGlobe.position.set(GLOBE_OFFSET * r, 0, 0);
    this.compositeEarth();
    const phong = (map: THREE.Texture) =>
      new THREE.MeshPhongMaterial({ map, shininess: 18, specular: 0x222222 });
    this.earthGlobe.globeMaterial(phong(this.earthTex.texture));
    this.setAtmosphere(this.earthGlobe, EARTH_ATMOSPHERE);
    this.bodyGlobe.globeMaterial(phong(this.bodyTex.texture));
    this.setAtmosphere(this.bodyGlobe, MOON_ATMOSPHERE);

    this.scene.background = new THREE.Color(0x000000);
    const starGeom = new THREE.BufferGeometry();
    starGeom.setAttribute('position', new THREE.BufferAttribute(starPositions(), 3));
    this.stars = new THREE.Points(
      starGeom,
      new THREE.PointsMaterial({
        color: 0xffffff,
        size: 1.4,
        sizeAttenuation: false,
        transparent: true,
        opacity: 0.85,
        depthWrite: false,
      }),
    );
    // fixed in world, upper-left-front: the camera-facing side is always lit, limbs fall off softly
    const sun = new THREE.DirectionalLight(0xffffff, SUN_INTENSITY);
    sun.position.set(-0.6, 0.5, 1).multiplyScalar(500);
    this.scene.add(
      this.stars,
      this.bodyGlobe,
      this.earthGlobe,
      sun,
      new THREE.AmbientLight(0xffffff, AMBIENT_INTENSITY),
    );
    this.camera.position.set(0, 0, 3.4 * r);

    this.resizeObs = new ResizeObserver(() => this.resize());
    this.resizeObs.observe(container);
    this.resize();
    this.renderer.setAnimationLoop(() => this.frame());
  }

  private setAtmosphere(g: ThreeGlobe, a: { color: string; altitude: number } | null): void {
    g.showAtmosphere(a !== null);
    if (a) g.atmosphereColor(a.color).atmosphereAltitude(a.altitude);
  }

  /** Point the body globe at a body texture (drawn into a canvas so orientation is standard). */
  setBodyTexture(img: ImageBitmap | null, body: Body): void {
    this.bodyImg = img;
    this.bodyKind = body;
    this.paintBody();
    this.setAtmosphere(this.bodyGlobe, body === 'mars' ? MARS_ATMOSPHERE : MOON_ATMOSPHERE);
  }

  /** Body texture + soft landmark glows (selected: larger, warm). */
  private paintBody(): void {
    const { ctx, canvas, texture } = this.bodyTex;
    ctx.fillStyle = this.bodyKind === 'moon' ? '#6e6e6e' : '#7a5a46';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (this.bodyImg) ctx.drawImage(this.bodyImg, 0, 0, canvas.width, canvas.height);
    for (const t of this.landmarks) {
      if (t.id !== this.selectedId)
        paintGlow(ctx, t.lat, t.lon, LANDMARK_GLOW_PX, '230,234,242', 0.45);
    }
    const sel = this.landmarks.find((t) => t.id === this.selectedId) ?? this.custom;
    if (sel) paintGlow(ctx, sel.lat, sel.lon, LANDMARK_SELECTED_GLOW_PX, '242,181,68', 0.95);
    texture.needsUpdate = true;
  }

  /** Real Earth imagery: always visible, the heat overlay is composited on top of it. */
  setEarthBasemap(img: ImageBitmap | null): void {
    this.basemap = img;
    this.compositeEarth();
  }

  /** Heat overlay from the worker's painted RGBA (equirectangular, x=0 at −180°, y=0 at +90°). */
  setEarthTexture(rgba: Uint8ClampedArray, width: number, height: number): void {
    const { canvas, ctx } = this.heatFull;
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    ctx.putImageData(new ImageData(new Uint8ClampedArray(rgba), width, height), 0, 0);
    this.hasHeat = true;
    this.compositeEarth();
  }

  /** basemap, then the heat blurred by a down-then-up canvas resample (hexagons → gradient). */
  private compositeEarth(): void {
    const { canvas, ctx, texture } = this.earthTex;
    ctx.globalAlpha = 1;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    if (this.basemap) ctx.drawImage(this.basemap, 0, 0, canvas.width, canvas.height);
    else {
      ctx.fillStyle = '#0b1020';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    if (this.hasHeat) {
      ctx.fillStyle = `rgba(0,0,0,${BASEMAP_VEIL})`;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      // ponytail: canvas down/up-sample blur; gaussian splat in the worker if edges look blocky
      const sm = this.heatSmall;
      sm.ctx.imageSmoothingEnabled = true;
      sm.ctx.imageSmoothingQuality = 'high';
      sm.ctx.clearRect(0, 0, HEAT_W, HEAT_H);
      sm.ctx.drawImage(this.heatFull.canvas, 0, 0, HEAT_W, HEAT_H);
      ctx.globalAlpha = HEAT_OPACITY;
      ctx.globalCompositeOperation = HEAT_BLEND;
      for (let i = 0; i < HEAT_PASSES; i++)
        ctx.drawImage(sm.canvas, 0, 0, canvas.width, canvas.height);
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';
    }
    // soft match-zone halos on top of the heat, in the heat colour under each match (score colour)
    const heat = this.heatFull;
    for (const c of this.cards) {
      const first = c.n === 1;
      let rgb = '255,255,255';
      if (this.hasHeat) {
        const x = Math.min(
          heat.canvas.width - 1,
          Math.floor(((c.lng + 180) / 360) * heat.canvas.width),
        );
        const y = Math.min(
          heat.canvas.height - 1,
          Math.floor(((90 - c.lat) / 180) * heat.canvas.height),
        );
        const [r, g, b] = heat.ctx.getImageData(x, y, 1, 1).data;
        rgb = `${r},${g},${b}`;
      }
      paintGlow(ctx, c.lat, c.lng, MATCH_HALO_PX[first ? 0 : 1], rgb, first ? 1 : 0.8);
    }
    const sel = this.selected;
    if (sel) paintGlow(ctx, sel.lat, sel.lng, SELECTED_GLOW_PX, '255,255,255', 0.9);
    texture.needsUpdate = true;
  }

  /** Mark the place whose detail view is open (white glow on Earth); null clears it. */
  setSelected(p: { lat: number; lng: number } | null): void {
    this.selected = p;
    this.compositeEarth();
  }

  /** Any user input: pauses the idle spin for IDLE_RESUME_MS. */
  markInteraction(): void {
    this.lastInteraction = performance.now();
  }

  /** `custom` marks a clicked spot (disc target) when no landmark is selected. */
  setLandmarks(
    targets: Target[],
    selectedId: string | null,
    custom: { lat: number; lon: number } | null = null,
  ): void {
    this.landmarks = targets;
    this.selectedId = selectedId;
    this.custom = custom;
    this.paintBody();
  }

  setCards(cards: CardMarker[]): void {
    this.cards = cards;
    this.compositeEarth();
    this.earthGlobe
      .labelsData(cards)
      .labelLat((d) => (d as CardMarker).lat)
      .labelLng((d) => (d as CardMarker).lng)
      .labelText((d) => String((d as CardMarker).n))
      .labelSize(5)
      .labelDotRadius(1.5)
      .labelAltitude(0.015)
      .labelColor(() => '#4FC3F7')
      .labelResolution(2)
      .labelsTransitionDuration(0);
  }

  /** Rotate a globe so (lat, lng) faces the camera (three-globe puts lat 0, lng 0 at +z). */
  facePoint(globe: 'body' | 'earth', lat: number, lng: number): void {
    this.markInteraction();
    const g = globe === 'body' ? this.bodyGlobe : this.earthGlobe;
    // globes sit left/right of the camera axis: aim at the camera, not along +z
    const yawToCamera = Math.atan2(
      this.camera.position.x - g.position.x,
      this.camera.position.z - g.position.z,
    );
    let y = (-lng * Math.PI) / 180 + yawToCamera;
    y = g.rotation.y + Math.atan2(Math.sin(y - g.rotation.y), Math.cos(y - g.rotation.y)); // shortest turn
    this.spin[globe] = { yaw: 0, pitch: 0 };
    this.aim[globe] = { x: (lat * Math.PI) / 180, y };
    if (this.reduced()) this.stepAim(globe, 1e3);
  }

  private stepAim(globe: 'body' | 'earth', dt: number): void {
    const a = this.aim[globe];
    if (!a) return;
    const g = globe === 'body' ? this.bodyGlobe : this.earthGlobe;
    const k = 1 - Math.exp(-FACE_EASE * dt);
    g.rotation.x += (a.x - g.rotation.x) * k;
    g.rotation.y += (a.y - g.rotation.y) * k;
    g.rotation.z = 0;
    if (Math.abs(a.x - g.rotation.x) + Math.abs(a.y - g.rotation.y) < 1e-4) this.aim[globe] = null;
  }

  /** World-space position of a lat/lng on one of the globes (used by arcs and picking). */
  worldPoint(globe: 'body' | 'earth', lat: number, lng: number, alt = 0): THREE.Vector3 {
    const g = globe === 'body' ? this.bodyGlobe : this.earthGlobe;
    const c = g.getCoords(lat, lng, alt);
    return g.localToWorld(new THREE.Vector3(c.x, c.y, c.z));
  }

  /** Width (px) of the control panel overlaying the left of the canvas (CSS var --panel-w). */
  private panelWidth(): number {
    const v = parseFloat(getComputedStyle(this.container).getPropertyValue('--panel-w'));
    return Number.isFinite(v) && v > 0 ? v : 0;
  }

  resize(): void {
    const w = Math.max(1, this.container.clientWidth);
    const h = Math.max(1, this.container.clientHeight);
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = '100%';
    this.renderer.domElement.style.height = '100%';
    this.camera.aspect = w / h;
    const panel = Math.min(this.panelWidth(), w * 0.6);
    const fit = cameraFit(w, h, panel, this.earthGlobe.getGlobeRadius(), this.camera.fov);
    this.fitZ = fit.z;
    this.applyCamera();
    // shift the projection so the globes centre in the area right of the panel
    if (panel > 0) this.camera.setViewOffset(w, h, fit.offsetX, 0, w, h);
    else this.camera.clearViewOffset();
    this.camera.updateProjectionMatrix();
  }

  /** Camera dollies from the fit framing toward the zoomed globe's centre (zoom 1 = exact fit). */
  private applyCamera(): void {
    this.camera.position.x = this.zoomCx * (1 - 1 / this.zoom);
    this.camera.position.z = this.fitZ / this.zoom;
  }

  /** Wheel zoom toward `globe` (null keeps the current one); deltaY in wheel units. */
  zoomBy(globe: 'body' | 'earth' | null, deltaY: number): void {
    this.markInteraction();
    if (globe) {
      const sign = globe === 'body' ? -1 : 1;
      this.zoomCxTarget = sign * GLOBE_OFFSET * this.earthGlobe.getGlobeRadius();
    }
    const z = this.zoomTarget * Math.exp(-deltaY * ZOOM_PER_WHEEL);
    this.zoomTarget = Math.max(1, Math.min(ZOOM_MAX, z));
    if (this.reduced()) this.stepZoom(1e3);
  }

  private stepZoom(dt: number): void {
    const k = 1 - Math.exp(-ZOOM_EASE * dt);
    this.zoom += (this.zoomTarget - this.zoom) * k;
    this.zoomCx += (this.zoomCxTarget - this.zoomCx) * k;
    if (Math.abs(this.zoomTarget - this.zoom) < 1e-4) this.zoom = this.zoomTarget;
    this.applyCamera();
  }

  private reduced(): boolean {
    return this.reducedMotion?.matches ?? false;
  }

  /** Release velocity (rad/s) of a drag; decays in the frame loop. No-op with reduced motion. */
  fling(globe: 'body' | 'earth', vYaw: number, vPitch: number): void {
    this.spin[globe] = this.reduced() ? { yaw: 0, pitch: 0 } : { yaw: vYaw, pitch: vPitch };
  }

  /** Drag rotation of one globe (radians); tilt is clamped to ±90°. */
  rotateBy(globe: 'body' | 'earth', dYaw: number, dPitch: number): void {
    this.markInteraction();
    this.aim[globe] = null; // a drag cancels an in-flight facePoint turn
    const g = globe === 'body' ? this.bodyGlobe : this.earthGlobe;
    g.rotation.y += dYaw;
    g.rotation.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, g.rotation.x + dPitch));
  }

  private frame(): void {
    if (this.disposed) return;
    const now = performance.now();
    const dt = Math.min(MAX_DT_S, (now - this.lastFrame) / 1000);
    const dYaw = idleYaw(now, this.lastInteraction, dt, this.reduced());
    this.lastFrame = now;
    for (const id of ['body', 'earth'] as const) {
      const v = this.spin[id];
      if (!v.yaw && !v.pitch) continue;
      this.rotateBy(id, v.yaw * dt, v.pitch * dt);
      v.yaw = decayVelocity(v.yaw, dt);
      v.pitch = decayVelocity(v.pitch, dt);
    }
    this.stepAim('body', dt);
    this.stepAim('earth', dt);
    if (this.zoom !== this.zoomTarget || this.zoomCx !== this.zoomCxTarget) this.stepZoom(dt);
    if (dYaw) {
      this.bodyGlobe.rotation.y += dYaw;
      this.earthGlobe.rotation.y += dYaw;
    }
    for (const f of this.onFrame) f();
    this.renderer.render(this.scene, this.camera);
    if (this.fps.frame(now)) {
      this.opts.onFallback(`frame rate stayed below ${FPS_FLOOR} fps for ${FPS_WINDOW_S} s`);
    }
  }

  dispose(): void {
    this.disposed = true;
    this.renderer.setAnimationLoop(null);
    this.resizeObs.disconnect();
    this.earthTex.texture.dispose();
    this.bodyTex.texture.dispose();
    this.stars.geometry.dispose();
    (this.stars.material as THREE.Material).dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
