---
inclusion: fileMatch
fileMatchPattern: ["pipeline/**/*.py", "notebooks/**/*.ipynb", "pipeline/pyproject.toml"]
---
# Python pipeline standards

## Code
- Type hints on every public function; NumPy-style docstrings with units for every array argument.
- Pure functions in `doppelgrund/`; I/O at the edges (`read_*`, `write_*` helpers). Functions take arrays/DataFrames and return arrays/DataFrames.
- Use `float32` for feature arrays, `float64` for coordinates. Use `np.nan`, never `None`, inside arrays.
- Configuration is read through `doppelgrund.config.load_profiles()` / `load_datasets()`; never hardcode dataset IDs, thresholds or weights.
- Randomness: `rng = np.random.default_rng(cfg.params.seed)` passed in explicitly.
- Logging via `logging.getLogger(__name__)`; no bare `print` in `doppelgrund/`.
- Every function that writes a file is idempotent: if the output exists and `overwrite=False`, skip and return the path.

## Notebooks
- First cell: `%pip install -e ../pipeline` (Colab: clone repo, then install) and imports. Second cell: config + paths.
- Each notebook writes exactly the outputs listed in its spec task and nothing else.
- Mount Drive in Colab; write outputs to the Drive mirror of `data/interim/` after each stage.
- No logic longer than ~10 lines in a notebook cell. Move it into `doppelgrund/`.

## Tests
- `pipeline/tests/test_<module>.py`; fast tests by default. Mark Earth Engine tests `@pytest.mark.ee` and slow tests `@pytest.mark.slow` (both skipped by `make test-py`).
- Use small synthetic arrays with hand-checked expected values. Use hypothesis for invariants (score in [0,100], coverage in [0,1], identical inputs give S = 100, NaN never becomes a number).

## Earth Engine
- Initialise with `ee.Initialize(project=<from env DOPPELGRUND_EE_PROJECT>)`; never commit project IDs with credentials.
- Use the `earth-engine-features` skill for batching, export and quotas.
