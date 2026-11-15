# DoppelGrund: gap resolution tasks (for task distribution)

Snapshot taken 2026-11-15. Written so each task can be handed to an agent or a person on its own.
Owners are suggestions; `HUMAN` means the code cannot decide it.

## Where things stand

- Branch state: everything through commit `f204222` is on `origin/dev-branch`.
- Working data: `data/interim/real_partial/` (stride-20 sample: 4,089 Earth hexes, 3,000 Moon and
  3,000 Mars discs, 13 landmarks), built in Earth Engine **fast mode** (overview-level DEM,
  MOD11A2-only thermal). Its web bundle is `web/public/data/real_partial/` (`synthetic: false`,
  opt-in with `?bundle=real_partial`; the app default is still the synthetic bundle).
- A larger run is in progress on one machine: `python -m doppelgrund.real --fast --stride 4
  --threads 4 --ee-project <project>` (about 20,440 hexes, 818 batches of 25, output
  `data/interim/real/`, batches kept in `ee_batches_fast/`, resumable). Still fast mode, so same
  resolution as `real_partial`, more hexes. Expected to finish a few hours after 2026-11-15 09:54.
- The full run (81,772 hexes, normal mode, about 3,271 batches) has NOT been done.
- Stage 2 (scaler, domain gap, clusters, novelty, stability, retrieval) and the validation harness
  exist and are tested. Validation numbers are not meaningful yet (see G8).

## Rules for any agent working on these tasks

1. Read `.kiro/steering/science-invariants.md` and `.kiro/steering/agent-rules.md` first.
2. Do not push to any remote. Commit locally and stop; the owner pushes. No `Co-Authored-By` lines.
3. Do not change `select_land_cells()`, the `--stride` rule, the batch size (25) or `--fast` while
   an Earth Engine run is using `data/interim/real/ee_batches_fast/`: each batch is keyed by its hex
   set, so a shifted list recomputes everything.
4. Human-owned files (do not fill or "verify" them yourself): `config/known_sites.csv`,
   `config/landmarks.yaml`, `config/ontology_crosswalk.csv`, and every `verified:` flag in
   `config/datasets.yaml`.
5. One Earth Engine job at a time per account. Eight concurrent requests hit "User memory limit
   exceeded"; 4 threads is the tested setting. Use your own `--ee-project`; never commit it.
6. Missing data stays NaN, never 0 (science invariant). Never invent a result number.
7. Before finishing: from `pipeline/`, `python -m pytest tests -q` (all pass), `ruff check .` and
   `ruff format --check .` (clean), then add one line to `docs/STATUS.md` Log.
8. Run Python tools with the repo venv (`.venv`). Windows: use `python`, not `python3`.

## Tasks

Dependencies are in brackets. "After run" means after the stride-4 Earth Engine run finishes.

### A. Can start now (no new data needed)

**G1. Label the bundle with what was really used** (owner: agent)
- Problem: the `real_partial` manifest says slopes come from "GLO30 + NASADEM" and thermal from
  "MOD11A2 + MOD21A1D/N". Fast mode used an overview DEM and MOD11A2 only, so the sources text
  overstates the data.
- Do: `real.py` already writes `tables_source.txt` ("real" or "real-partial"). Have
  `export/bundle.py` read it and write `resolution` ("fast" | "full") and `stride` into the manifest;
  make the sources text in the manifest and `web/src/content/about.md` say what fast mode uses.
  Add the optional field to `web/src/data/types.ts`. Log a `CONTRACT ISSUE` line in `docs/STATUS.md`
  (C6 manifest gains optional fields).
- Accept: manifest of a rebuilt `real_partial` shows `resolution: "fast"`; the About page states it;
  bundle and web tests pass.

**G2. Check the scaler fallback for `permafrost_prob` and `aridity_index`** (owner: agent)
- Problem: stage 2 logs "MAD 0 < 1e-06; s set to 1.0" for both. The scaler is fitted on unmasked
  (barren) Earth hexes plus all discs, where most values are 0.
- Do: confirm the cause in `harmonise.fit_scaler`; decide between fitting on all land hexes,
  keeping the fallback, or a documented per-feature tolerance. Report the effect on scores.
- Accept: a short note in `docs/STATUS.md` with the finding and the chosen action; tests if code
  changes. If the fix changes C3/C4 behaviour, log a `CONTRACT ISSUE` and ask the owner first.

**G3. Resolve the R6.2 clustering difference** (owner: HUMAN decides, agent applies)
- Spec R6.2: HDBSCAN `min_cluster_size` 100, `min_samples` 10; GMM K by BIC over 6 to 24. The
  driver (`ml/pipeline.py`) uses `max(10, N//200)` and K in 2..10 step 2.
- Do: owner picks code-follows-spec or spec-follows-code; the agent makes the one-line change and
  updates `requirements.md` or `ml/pipeline.py` plus its test.

**G4. Write-up skeleton** (owner: agent) [needs official guide for format, see G6]
- Do: create `docs/submission/writeup.md` (2 to 4 pages) following
  `.kiro/specs/04-submission/requirements.md` R2 and R4: motivation, data, harmonisation, scoring,
  ML with honest labels, validation, discoveries with caveats, limitations, future work, Sarawak
  framing. Mark every result as a placeholder to be filled from `data/interim/validation/ablation.md`.
- Accept: no invented numbers; claims follow the plan's claims discipline (similarity scores, not
  "twin" or "qualified site").

**G5. Data sources table** (owner: agent drafts, HUMAN verifies)
- Do: fill `docs/submission/data-sources.md` from `config/datasets.yaml` (dataset, version, citation,
  licence, `verified` state). List which entries are still unverified. Do not set `verified: true`.

**G6. Judging checklist** (owner: HUMAN supplies the official guide, agent maps)
- Task 4.1 (reconcile with the 2026 Submission and Judging guides) is not recorded in
  `docs/STATUS.md`. Paste the criteria; the agent maps each to evidence in the app, write-up or demo.

**G7. Prepare the real-data switch for the web app (task 3.18)** (owner: agent, investigate first)
- Problem: `web/public/data/*` is gitignored except `sample/`, so a real bundle is not deployed and
  the default view is synthetic. Bundle choice is `?bundle=<name>` in `web/src/main.ts`.
- Do: read `.github/workflows/deploy.yml`, `web/src/main.ts`, `.gitignore`; propose how a real
  bundle ships (committed folder, release asset, or build step) and what changes when
  `synthetic: false`. Report options before changing the default. Needs the real bundle (G10) to
  finish.

### B. After the Earth Engine run

**G8-prep. Site-hex top-up job** (owner: whoever has Earth Engine access) [after run]
- Why: validation needs each known site's hex (plus ring 1) in the Earth table. 14 of 18 sites are
  not in the stride-20 sample; for stride 4, 61 hexes are missing (about 3 batches). `teide_np` and
  `lanzarote_pangaea` are on islands the 110 m land mask treats as sea and can never be evaluated.
- Run (same `--fast --stride 4`, its OWN `--out` folder):
  `python -m doppelgrund.real --site-hexes --fast --stride 4 --ee-project <project> --out data/interim/real_sites`
  then
  `python -m doppelgrund.real --out data/interim/real --merge-site-hexes data/interim/real_sites/earth_site_hexes.parquet`
- Accept: `earth_features.parquet` in `data/interim/real` has the extra rows (command prints how many).

**G9. Stage 2, validation and bundle on the larger tables** [after run, G8-prep]
- `python -m doppelgrund.ml.pipeline --interim data/interim/real`
- `python -m doppelgrund.validation --interim data/interim/real --out data/interim/validation`
- `python -m doppelgrund.export.bundle --interim data/interim/real --out web/public/data/real`
  (check the bundle command and output name against `ml/pipeline.py` docstring and the Makefile)
- Accept: bundle validates, `synthetic: false`, loads in the app; `ablation.md` produced. Treat the
  validation output as a harness check until G8 is done by a human.

**G10. Task 2.14 and 3.18: real bundle export and web switch** [G7, G9] (Gate G3)

### C. Needs a human decision or input

**G11. Map the known sites to targets** (HUMAN)
- Edit `config/known_sites.csv`: set `documented_target_id` (the landmark each site was used for) and
  grow the list toward the plan's 30 to 50 sites. Today 1 of 18 is mapped (`lake_salda` to
  `jezero`) and 98% of sampled hexes count as "novel" because the list is short. Validation (task
  2.11, Gate G2) is not meaningful until this is done.

**G12. Cave catalogues** (HUMAN)
- Verify the coordinates in `config/earth_lava_tubes.csv` (hand-listed, from Wikipedia), the licence
  of the Moon LROC pit catalogue, and decide Mars (currently deliberately NaN). Until then the
  `subsurface` trait is unmeasured on Earth; say so in the limitations.

**G13. Full-scale run decision** (HUMAN)
- Option A: the README's 4-shard route (`--shard I/N`, normal mode, one shard per person, then
  merge; see README "Earth Engine step"). Raising `--threads` may help if Earth Engine allows.
- Option B: keep fast, 1 in 4 hexes, and keep the manifest label from G1.
- Option C: keep `real_partial` and treat the full run as future work.

### D. Optional / later

**G14. Weight calibration, task 2.12** (owner: agent) [after G11 gives enough sites]. Cut if Gate G2
is late.

**G15. Clustering stability** (owner: agent, optional). GMM label stability is ARI 0.68 on
`real_partial` (HDBSCAN 0.98). Try other K or covariance types only if the cluster rows matter in
the ablation.

**G16. Notebook wrappers 05 to 09 and CI/Pages (tasks 2.15, 0.9)** (owner: agent, low priority).
Pages deploy has never been pushed, so CI is unverified.

## Dependency order

G1, G2, G3, G4, G5 can run now, in parallel, by different agents.
G11 and G12 run in parallel by humans.
After the Earth Engine run: G8-prep, then G9, then G10 (with G7 done).
G6 gates the final shape of G4.

## Quick reference

- Status log: `docs/STATUS.md` (append only, one line per task).
- Specs: `.kiro/specs/00-foundation` to `04-submission` (`tasks.md` has the checkboxes).
- Stage 2 driver: `pipeline/doppelgrund/ml/pipeline.py`. Validation: `pipeline/doppelgrund/validation.py`.
- Tests: `cd pipeline && python -m pytest tests -q`.
