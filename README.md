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

## Sharing the Earth Engine extraction (4 people)

The Earth Engine step is slow (about 818 batches of 100 hexes). Split it: each person runs one shard (`0/4`, `1/4`, `2/4` or `3/4`), then one person merges. Everyone must be on the same code (`dev-branch`) and leave the batch size alone, or the batches will not line up.

You need a Google account with Earth Engine access and a Google Cloud project registered for Earth Engine (free for non-commercial use: <https://code.earthengine.google.com/register>). The project ID is `YOUR_GCP_PROJECT` below.

```powershell
# 1. setup (once, from the repo root)
git switch dev-branch; git pull origin dev-branch
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e "pipeline[dev,ee]"
.venv\Scripts\earthengine authenticate          # opens a browser, sign in, paste the code back

# 2. run your shard (change 0 to your number; re-run the same command if it stops, finished batches are kept)
.venv\Scripts\python -m doppelgrund.real --ee-project YOUR_GCP_PROJECT --shard 0/4

# 3. progress: one .parquet per finished batch
(Get-ChildItem data\interim\real\ee_batches).Count
```

Use `--threads 2` if Earth Engine reports quota errors (default is 4). To stop, Ctrl+C; if it will not die, close the terminal.

When your shard says all batches are done, zip `data\interim\real\ee_batches\` and send it to whoever merges. The merger copies every `.parquet` from all four zips into their own `data\interim\real\ee_batches\`, then runs the final step with no `--shard` (it skips the finished batches and writes the real tables to `data\interim\real\`):

```powershell
.venv\Scripts\python -m doppelgrund.real --ee-project YOUR_GCP_PROJECT
```

## Layout

See `.kiro/steering/structure.md`. Planning lives in `.kiro/specs/`, status in `docs/STATUS.md`.

## Licence

MIT (see `LICENSE`). Dataset licences and citations are listed in `config/datasets.yaml`.
