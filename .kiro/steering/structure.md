---
inclusion: always
---
# Repository structure and naming

```
repo/
├── .kiro/                     steering, specs, hooks, skills (planning; humans edit specs/contracts)
├── config/
│   ├── profiles.yaml          features, lith classes, compat matrix, lenses, params (single source of truth)
│   ├── datasets.yaml          every dataset: id/url, version, licence, citation, verified: true|false
│   ├── landmarks.yaml         preloaded Moon/Mars targets (id, name, body, lat, lon, source)
│   ├── known_sites.csv        documented analogue sites (rediscovery + novelty)
│   └── ontology_crosswalk.csv source map unit -> shared lithology class weights
├── pipeline/
│   ├── pyproject.toml
│   ├── doppelgrund/
│   │   ├── config.py          load + validate config files
│   │   ├── tiling.py          H3 land cells, land fraction, antimeridian handling
│   │   ├── localzonal.py      zonal stats for local rasters via H3 child-point sampling
│   │   ├── earth/             ee_client.py, batch.py, terrain.py, thermal.py, cold.py, composition.py, mask.py, tags.py, assemble.py
│   │   ├── planetary/         lattice.py, rasterio_io.py, terrain.py, thermal.py, composition.py, targets.py
│   │   ├── harmonise.py       transforms, pooled scaler, tolerances
│   │   ├── scoring.py         reference scorer, group scores, cards (Python is the source of truth)
│   │   ├── ml/                domain_gap.py, embed.py, cluster.py, retrieval.py, calibrate.py, novelty.py, stability.py
│   │   ├── validation.py      rediscovery metrics + ablation table
│   │   ├── export/            bundle.py, index_map.py, parity.py
│   │   ├── qa/                report.py (coverage maps, value ranges)
│   │   └── fixtures/          synthetic.py
│   └── tests/                 test_<module>.py mirrors doppelgrund/
├── notebooks/                 01_tiling … 09_export (thin wrappers only)
├── data/                      raw/ interim/ export/ (git-ignored; never edited by agents)
├── web/
│   ├── public/data/           the bundle (generated; git-ignored except a tiny synthetic sample)
│   ├── src/
│   │   ├── data/              types.ts, loader.ts, config.ts
│   │   ├── engine/            transforms.ts, scoring.ts, cards.ts, percentile.ts, geo.ts, stability.ts, prng.ts
│   │   ├── workers/           engine.worker.ts, protocol.ts
│   │   ├── stores/            session.ts
│   │   ├── components/        TargetPanel, EarthMap, MatchCards, LensControls, Scorecard, DivergencePanel, Shortlist, LayerToggles, StatusBar
│   │   ├── globe/             GlobeScene.ts, painter.ts, arcs.ts, picking.ts
│   │   └── App.vue, main.ts
│   └── tests/                 *.test.ts (unit), parity.test.ts
├── tests/parity/vectors.json  golden vectors produced by Python, consumed by TS
├── docs/
│   ├── STATUS.md              orchestration board (append-only log + current wave)
│   ├── decisions/ADR-*.md     one decision per file
│   ├── plan/                  science plan
│   └── submission/            writeup.md, demo-script.md, slides.md, data-sources.md, ai-use-log.md
├── Makefile
└── tech_stack.md
```

## Naming
- Python: snake_case modules and functions; feature columns use unit suffixes (`_deg`, `_m`, `_K`, `_km`; fractions have `frac_` prefix or `_prob`).
- TypeScript: camelCase functions, PascalCase components and types; feature names stay exactly as in `profiles.yaml` (snake_case strings).
- Target ids: lowercase slugs (`shackleton_rim`, `jezero`).
- Lens ids: `balanced`, `landing_mobility`, `cold_volatiles`, `geology_minerals`.
- Group ids: `terrain`, `thermal`, `cold_ice`, `composition`.
- Tests: `test_<module>.py`, `<module>.test.ts`.
