# Design: 03 Web app

## 1. Layout (desktop 1440×900 primary; stacked below 1100 px)
```
┌ Header: title · body toggle (Moon|Mars) · lens select · 2D/3D switch · About ┐
├──────────── TargetPanel (40%) ────────────┬────────── EarthMap (60%) ─────────┤
│ body mosaic, landmark pins, footprint note │ hex heat map, legend, card rings  │
├────────────────────────────────────────────┴───────────────────────────────────┤
│ MatchCards (5 across)                                     LensControls (sliders) │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Shortlist (collapsible) · LayerToggles · StatusBar (data, timing, synthetic flag) │
└──────────────────────────────────────────────────────────────────────────────────┘
Scorecard + DivergencePanel open in a right-hand drawer when a hex/card is selected.
```

## 2. Modules and signatures
```ts
// data/types.ts — mirrors C6/C8 (from foundation task 0.6)
// data/loader.ts
export async function loadBundle(baseUrl: string, onProgress?: (done: number, total: number) => void): Promise<Bundle>
// engine/transforms.ts
export function applyTransforms(raw: Float32Array, nCols: number, transforms: Transform[]): Float64Array
// engine/scoring.ts
export interface ScoreInputs { Xe: Float64Array; Le: Float32Array; flags: Uint8Array; n: number;
  xt: Float64Array; lt: Float32Array | null; median: Float64Array; s: Float64Array;
  groupOfFeature: Uint8Array; wNum: Float64Array; wLith: number; C: Float64Array /* 6x6 */ }
export function scoreAll(inp: ScoreInputs): { S: Float32Array; coverage: Float32Array; groups: Float32Array }
export function featureWeights(weights: GroupWeights, features: FeatureMeta[]): { wNum: Float64Array; wLith: number }
// engine/percentile.ts
export function percentileLinear(values: Float32Array, mask: Uint8Array, p: number): number  // numpy "linear"
// engine/geo.ts
export const EARTH_R_KM = 6371.0088
export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number, rKm = EARTH_R_KM): number
// engine/cards.ts
export function selectCards(S: Float32Array, cov: Float32Array, groups: Float32Array, latlng: Float32Array, params: CardParams): Card[]
// engine/prng.ts + engine/stability.ts
export function mulberry32(seed: number): () => number
export function sampleDirichlet(alpha: Float64Array, rnd: () => number): Float64Array   // Marsaglia–Tsang gamma
export function stabilityRun(inp: ScoreInputs, base: GroupWeights, params: StabilityParams, draws: number, onProgress): Array<[number, number]>
// workers/protocol.ts — C8 message types; workers/engine.worker.ts — handlers; workers/client.ts — promise wrapper with reqId + latest-wins
// globe/painter.ts (runs in worker)
export function paint(indexRGB: Uint8ClampedArray, values: Float32Array, palette: Palette, eligible: Uint8Array): Uint8ClampedArray
// globe/GlobeScene.ts, globe/arcs.ts, globe/picking.ts (main thread, three.js)
```

## 3. Store (`stores/session.ts`)
```ts
state: { body: "moon" | "mars"; target: { kind: "landmark"; id: string } | { kind: "disc"; body; discIndex: number } | null;
         lens: LensId | "custom"; weights: GroupWeights; colorBy: "S" | GroupId | "novelty";
         view: "2d" | "3d"; selectedRow: number | null; novelOnly: boolean; layers: Record<LayerId, boolean>;
         result: RankResult | null; stability: { rows: Map<number, number>; kind: "preset" | "interactive" } | null;
         loading: LoadState; timings: { rankMs: number; paintMs: number } }
actions: selectBody, selectLandmark, selectDisc, setLens, setWeight(group, value), selectRow, toggleLayer, setView, setColorBy
```
`setWeight` renormalises: others scaled proportionally so the sum is 1; a weight can reach 0. Every action that changes target or weights posts a `rank` request (debounced 50 ms for sliders).

## 4. Rendering details
- **EarthMap:** deck.gl `MapView` (initial zoom ~1.2), layers: `GeoJsonLayer(land)` fill neutral; `H3HexagonLayer` (`getHexagon` from `earth_h3.txt`, `getFillColor` from active metric via viridis LUT, `updateTriggers` on result id, `pickable`); `ScatterplotLayer` rings for cards (radius in metres ≈ 30 km, stroked, labelled 1–5 with `TextLayer`); known sites as hollow diamonds. Mercator clips Antarctica beyond ~85°S: acceptable in 2D (3D shows it); mention in About.
- **TargetPanel:** deck.gl `OrthographicView` with x = lon (−180…180), y = lat (−90…90) and `flipY: false`; `BitmapLayer` image `textures/<body>.jpg` bounds `[-180,-90,180,90]`; `ScatterplotLayer` + `TextLayer` landmarks; optional `ScatterplotLayer` for lunar pits. Click → `{lon, lat}` from unprojected coordinates.
- **Palette:** viridis 10 stops `#440154 #482878 #3E4A89 #31688E #26828E #1F9E89 #35B779 #6DCD59 #B4DE2C #FDE725`; masked/ineligible `#9A9A9A` at 60% opacity; legend shows the metric name and unit ("Similarity S (0–100)", "km to nearest known site").
- **3D:** one `THREE.WebGLRenderer`, perspective camera, two three-globe objects (`moonOrMarsGlobe` at x = −1.4·R, `earthGlobe` at x = +1.4·R). Earth material map = `THREE.CanvasTexture` filled from the worker's `painted` RGBA (4096×2048). Body globe uses the body texture. Landmarks/cards as points; arcs as `THREE.Line` along a `QuadraticBezierCurve3` lifted above the midpoint. Picking: raycast against each globe sphere → lat/lng (three-globe coordinate helpers; verify API at build) → Earth: index-map lookup for row; body: nearest landmark within 3°. Orbit with simple pointer-drag rotation of each globe (no extra controls library).

## 5. Divergence content (static per body + dynamic)
- Always: "Gravity: Earth 9.81 m/s² vs Moon 1.62 / Mars 3.71 — not replicable"; "Atmosphere: vacuum (Moon) / ~0.6 kPa CO₂ (Mars) — not replicable"; "Radiation environment — not replicable".
- Moon polar targets: "Permanent-shadow illumination and cold traps — no Earth analogue".
- Moon thermal: "Lunar day–night range is hundreds of kelvin; no Earth surface reaches it (gap shown in K)".
- Dust: "Electrostatic regolith behaviour not captured by Earth proxies".
- Dynamic: any feature with similarity < 0.2 → "Weak match: <feature> gap <Δ> <unit>".
These strings live in `src/content/divergence.ts` (values above are standard physical constants; humans proof-read).

## 6. Error and empty states
Loading progress bar with file names; contract error screen; "No target selected" prompt; "No close Earth regime" notice when the target's flags include `no_close_regime`; 3D fallback notice.
