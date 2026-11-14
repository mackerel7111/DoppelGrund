# Requirements: 03 Web app

Scope: the static Vue app that loads the bundle, scores in a Web Worker and presents the target-to-Earth flow in 2D, with a 3D dual-globe upgrade as a stretch. Built against the synthetic bundle from H4; switches to real data at gate G3.

## R1 Loading
1. WHEN the app starts THE SYSTEM SHALL load `manifest.json`, validate it (00/R5) and load all required C6 files in parallel, showing progress.
2. IF any file is missing or invalid THEN THE SYSTEM SHALL show an error screen naming the file and contract field.
3. WHEN `manifest.synthetic` is true THE SYSTEM SHALL show a persistent "Synthetic data — not real results" banner.
4. The app SHALL make no network requests other than same-origin bundle and asset files.

## R2 Engine parity
1. `src/engine` SHALL implement C4 and C5 and pass every case in `tests/parity/vectors.json` within 1e-5 (S, coverage, group scores) and exactly for cards.
2. Engine code SHALL contain no DOM, Vue or deck.gl imports.

## R3 Worker
1. All scoring, card selection, stability and painting SHALL run in `engine.worker.ts` using the C8 protocol.
2. Re-ranking 85,000 rows SHALL complete in < 150 ms on the demo laptop; the UI SHALL stay responsive during stability runs (progress shown, cancellable by a newer request).

## R4 Target selection
1. THE SYSTEM SHALL show a Moon/Mars toggle and an equirectangular map of the selected body with preloaded landmarks as labelled pins.
2. WHEN the user clicks a landmark THE SYSTEM SHALL select it as the target and re-rank.
3. WHERE full disc grids exist in the bundle, WHEN the user clicks elsewhere on the body THE SYSTEM SHALL snap to the nearest disc (great-circle on the body sphere) and use it as a custom target, labelled with its coordinates.
4. THE SYSTEM SHALL state that a match compares ~47 km-wide surroundings, not the landmark itself.

## R5 Earth view
1. THE SYSTEM SHALL show an Earth map with hexes coloured by the active metric (overall S by default; any group score or novelty selectable), masked/ineligible hexes in grey, and a legend with units.
2. Match-card hexes SHALL be highlighted with numbered rings; known analogue sites shown as distinct markers (toggleable).
3. WHEN the user clicks a hex THE SYSTEM SHALL open its scorecard.

## R6 Match cards
1. THE SYSTEM SHALL show five cards in C5 order: Best overall, Best terrain, Best thermal, Best cold & ice, Best composition.
2. Each card SHALL show lat/lon, the card's dimension score, overall S, coverage, stability (if available), geographic novelty (km to nearest known site) and shared process tags.
3. A card with no eligible match SHALL say so in words (e.g. "No eligible thermal match — data unavailable for this target").

## R7 Lenses and sliders
1. THE SYSTEM SHALL offer lens presets (Balanced default, Landing & mobility, Cold regions & volatiles, Geology & minerals) and four group sliders.
2. Moving a slider SHALL renormalise the four weights to sum to 1, switch the lens label to "Custom", and re-rank.
3. Preset stability values SHALL be marked "preset" when the weights are custom until an interactive stability run finishes.

## R8 Scorecard and divergence
1. The scorecard SHALL show: radar chart of the four group scores; a per-feature table (target value, Earth value, gap in units, similarity, source dataset); coverage; stability; novelty (both columns); tags; stage.
2. The divergence panel SHALL always list gravity, vacuum/atmosphere and radiation as not replicable, plus body-specific notes (C: design §5), plus every scored feature with similarity < 0.2 as "weak match" with its physical gap.
3. Missing features SHALL be shown as "not measured", never as zero.

## R9 Shortlist, novelty and layers
1. THE SYSTEM SHALL show a ranked shortlist (top 50 eligible) with S, coverage, stability and novelty.
2. A "Novel only" toggle SHALL filter to hexes with `geo_novelty_km >= params.novelty_gate_km`.
3. Layer toggles SHALL show/hide known sites, volcanoes, lava tubes, lunar pits (on the Moon panel) and Sarawak caves.

## R10 3D dual globes (stretch)
1. THE SYSTEM SHALL offer a 2D/3D switch. In 3D, one scene shows the target body globe and the Earth globe side by side.
2. The Earth globe texture SHALL be painted from the index map using the active metric and update after each re-rank.
3. Arcs SHALL connect the selected target to each match-card location; clicking the Earth globe opens the scorecard; clicking the target globe selects landmarks.
4. IF WebGL is unavailable or frame rate stays below 20 fps for 3 s THEN THE SYSTEM SHALL fall back to 2D with a notice.

## R11 About and honesty
1. An "About & methods" dialog SHALL explain features, scoring, the honest-labelling table (numerical method vs unsupervised ML vs weakly supervised), validation results (from the bundle or a static file), data sources and limitations.

## R12 Quality
1. Initial load (real bundle, local static server) SHALL be < 5 s on the demo laptop.
2. All controls SHALL be keyboard-accessible with visible focus and labels.
3. The production build SHALL work from a sub-path (`DOPPELGRUND_BASE`) and from a local `vite preview`.
