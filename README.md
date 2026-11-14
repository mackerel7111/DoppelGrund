# DoppelGrund: Global Analogue Discovery Engine

NASA Space Apps 2026 entry for "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars".

Pick a landmark on the Moon or Mars. DoppelGrund scores every Earth land hexagon (H3 resolution 4) against it, shows the
best Earth match per dimension (terrain, thermal, cold & ice, composition) plus best overall, flags places nobody
has studied, and states where each analogy fails.

## Requirements

- Python 3.12+ (`python3`, or `python` on Windows)
- Node.js LTS (22.x) and npm
- GNU Make (optional; on Windows: Git Bash, MSYS or WSL). Without it, use the plain commands below.

## Setup and everyday commands

The Makefile is the interface. Run make targets, not raw tools.

```sh
make setup              # create .venv, pip install -e pipeline[dev], npm ci in web/
make bundle-synthetic   # write a schema-valid synthetic bundle to web/public/data/
make verify-quick       # lint + Python tests + web tests
make dev                # Vite dev server
make build              # production build into web/dist/
make preview            # serve the production build
```

Override the Python interpreter with `make setup SYS_PY=/path/to/python` if auto-detection picks the wrong one.

### Without make (Windows PowerShell, from the repo root)

On Linux/macOS use `.venv/bin/python` instead of `.venv\Scripts\python`.

```powershell
# setup (once)
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e "pipeline[dev]"      # add ,ee for Earth Engine: "pipeline[dev,ee]"
cd web; npm ci; cd ..

# synthetic bundle, then the app
.venv\Scripts\python -m doppelgrund.fixtures.synthetic --bundle web/public/data --interim data/interim/synthetic --coverage land
cd web; npm run dev

# real feature tables -> data/interim/real (needs `earthengine authenticate`)
.venv\Scripts\python -m doppelgrund.real --ee-project YOUR_GCP_PROJECT
.venv\Scripts\python -m doppelgrund.real --no-ee --limit 200   # quick smoke test, no Earth Engine

# checks
.venv\Scripts\python -m ruff check pipeline
.venv\Scripts\python -m pytest pipeline/tests -m "not ee and not slow" -q
cd web; npm run lint; npm test -- --run
cd web; npm run build            # production build into web/dist/
```

If `npm run` fails with odd path errors on Windows, run `node scripts/npm-run.mjs <script>` from `web/` instead.

Notes:

- Without a bundle in `web/public/data/` the app shows "manifest.json: invalid JSON". Run the synthetic bundle step first, or open `/?bundle=sample` to use the committed 500-hex sample.
- Node 22 LTS is the supported version. Newer odd-numbered releases (for example 25) install with `EBADENGINE` warnings but the tests pass.

## Layout

See `.kiro/steering/structure.md`. Planning lives in `.kiro/specs/`, status in `docs/STATUS.md`.

## Licence

MIT (see `LICENSE`). Dataset licences and citations are listed in `config/datasets.yaml`.
