# DoppelGrund: Global Analogue Discovery Engine

NASA Space Apps 2026 entry for "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars".

Pick a landmark on the Moon or Mars. DoppelGrund scores every Earth land hexagon (H3 resolution 4) against it, shows the
best Earth match per dimension (terrain, thermal, cold & ice, composition) plus best overall, flags places nobody
has studied, and states where each analogy fails.

## Requirements

- Python 3.12+ (`python3`, or `python` on Windows)
- Node.js LTS (22.x) and npm
- GNU Make (on Windows: Git Bash, MSYS or WSL)

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

## Layout

See `.kiro/steering/structure.md`. Planning lives in `.kiro/specs/`, status in `docs/STATUS.md`.

## Licence

MIT (see `LICENSE`). Dataset licences and citations are listed in `config/datasets.yaml`.
