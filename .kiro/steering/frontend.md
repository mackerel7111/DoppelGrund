---
inclusion: fileMatch
fileMatchPattern: ["web/**/*.ts", "web/**/*.vue", "web/**/*.css", "web/package.json", "web/vite.config.ts"]
---
# Frontend standards

## Architecture
- `src/engine/` is pure TypeScript: no DOM, no Vue, no deck.gl imports. It must run in a Web Worker and in Vitest.
- All scoring runs in `src/workers/engine.worker.ts`. Components never loop over all hexes.
- State lives in the Pinia store `src/stores/session.ts`. Components read state and emit events; they do not fetch data.
- `src/data/loader.ts` is the only code that fetches bundle files.
- Typed arrays are transferred (not copied) between worker and UI.

## Rendering
- Earth 2D: deck.gl `MapView`, `GeoJsonLayer` with `layers/land.geojson` as basemap, `H3HexagonLayer` coloured by the active metric, `ScatterplotLayer` rings for match cards and known sites. No tile servers.
- Moon/Mars 2D: deck.gl `OrthographicView` with `BitmapLayer` bounds `[-180, -90, 180, 90]` in plain x = lon, y = lat units (works at the poles), `ScatterplotLayer` + `TextLayer` for landmarks.
- 3D (stretch): one three.js scene, two three-globe objects, Earth texture painted from `earth_index_4096x2048.png` by the worker; arcs are curves between world-space points.
- Colour scales: one sequential scale for scores (colour-blind safe), grey for masked or ineligible hexes. Every colour legend states units.

## Code style
- `<script setup lang="ts">`, strict TypeScript, no `any` (use `unknown` + narrowing).
- Props and emits fully typed. Components ≤ ~200 lines; split otherwise.
- Accessibility: every control has a label; keyboard focus visible; colour is never the only signal (cards also show text).
- Typographic text in UI copy: units always shown (e.g. "Δ 212 K").

## Tests
- Engine: Vitest unit tests + `tests/parity` vectors (tolerance 1e-5). Property tests with fast-check for score ranges.
- Components: test logic-bearing components (MatchCards, LensControls) with @vue/test-utils.
- Performance assertions in `engine/*.bench.ts` are informational, not CI gates.
