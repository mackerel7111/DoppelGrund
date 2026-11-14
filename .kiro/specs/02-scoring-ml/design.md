# Design: 02 Scoring, ML and export

## 1. Harmonisation (`doppelgrund/harmonise.py`)
```python
def apply_transforms(X: np.ndarray, transforms: Sequence[str]) -> np.ndarray      # (N,10) -> (N,10), NaN-safe
def fit_scaler(earth: np.ndarray, moon: np.ndarray, mars: np.ndarray, transforms) -> Scaler
@dataclass class Scaler: median: np.ndarray; s: np.ndarray; counts: dict[str, int]
    def to_json(self, path: Path) -> None; @classmethod def from_json(cls, path) -> "Scaler"
def scaled(X_t: np.ndarray, scaler: Scaler) -> np.ndarray   # (X' - median)/s, for clustering only
```
MAD: `s = nanmedian(|X' − nanmedian(X')|)` over the pooled matrix, no 1.4826 factor (keep consistent; documented).

## 2. Scorer (`doppelgrund/scoring.py`) — reference for TypeScript
```python
GROUPS = ("terrain", "thermal", "cold_ice", "composition")
@dataclass class ScoreResult:
    S: np.ndarray          # (N,) float32, 0-100 or NaN
    coverage: np.ndarray   # (N,) float32
    groups: np.ndarray     # (N,4) float32, order GROUPS
def lith_similarity(L_e: np.ndarray, l_t: np.ndarray, C: np.ndarray) -> tuple[np.ndarray, np.ndarray]  # (k, valid)
def score(X_e, L_e, flags, x_t, l_t, scaler: Scaler, transforms, groups_of_feature, w_num, w_lith, C) -> ScoreResult
def lens_weights(profiles, lens_or_weights) -> tuple[np.ndarray, float]   # delegates to Profiles.feature_weights
def select_cards(res: ScoreResult, latlng: np.ndarray, params: dict) -> list[dict]   # C5
def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray
```
Implementation notes: compute `Xe' = apply_transforms(X_e)` once per session (cache); `z = |x_t' − Xe'| / s`; `k = exp(−0.5 z²)`; `valid = isfinite(z)`; numerators and denominators with `np.where(valid, w*k, 0)`. Lithology: smoothing `P = L_e @ C` then row-normalise; rows with non-finite or zero-sum → invalid. Group scores reuse the same arrays masked by group. Use float64 internally, return float32.

## 3. Parity (`doppelgrund/export/parity.py`)
Generates C7 cases from small hand-built arrays (≤ 12 rows each) plus one 500-row slice of the synthetic bundle. Writes NaN as `null`. Includes expected `cards`. CLI `--out`.

## 4. ML (`doppelgrund/ml/`)
```python
# domain_gap.py
def domain_gap(X_earth_s, X_plan_s, seed) -> DomainGapReport   # auc_mean, auc_per_feature, separating: list[str], support: dict[target_id, dict[feature, float]]
# embed.py
def clustering_matrix(tables, separating, min_coverage=0.8) -> tuple[np.ndarray, list[str], np.ndarray]  # Z_in, row_keys, imputed_mask
def fit_pca(Z_in, var=0.90, seed) -> PCA
# cluster.py
def fit_hdbscan(Z, min_cluster_size, min_samples) -> np.ndarray
def fit_gmm_bic(Z, ks=range(6, 26, 2), seed) -> tuple[GaussianMixture, dict[int, float]]
def cluster_report(Z, labels, row_keys, X_scaled, feature_names) -> pd.DataFrame
def label_stability(Z, fit_fn, n=5, frac=0.8, seed) -> float      # mean ARI
def assign_regime(z_target, pca, gmm, Z_ref, hdb_labels, k=15) -> dict
# retrieval.py
def cluster_conditioned(res: ScoreResult, earth_labels, target_regime, params) -> tuple[np.ndarray, list[str]]  # ranked rows, flags
# calibrate.py
def mrr(ranks: np.ndarray) -> float
def calibrate(lens, known_pairs, score_fn, w0, lam, seed, maxiter) -> CalibrationResult  # scipy differential_evolution on θ (4 values)
def leave_one_out(...) -> pd.DataFrame
# novelty.py
def geo_novelty(latlng, sites_latlng) -> np.ndarray     # BallTree(haversine)
def feat_novelty(X_scaled, site_rows) -> np.ndarray
# stability.py
def stability(score_fn, w_lens, s, params, rng) -> np.ndarray   # fraction in top fraction
```
Runtime guards: HDBSCAN on ≤ 100k rows × ≤ 15 dims; if > 10 min, fit on a 30k subsample and assign the rest by nearest neighbour (log it).

## 5. Validation (`doppelgrund/validation.py`)
```python
def rank_of(rows_ranked: np.ndarray, site_rows: set[int]) -> int   # best rank among site hex + ring-1
def evaluate(method_fn, pairs, N) -> pd.DataFrame                    # per site: rank, pct_rank, hit@k
def ablation(methods: dict[str, Callable], pairs, n_boot=2000, seed) -> pd.DataFrame
def write_ablation(df, out_dir) -> None                               # .csv + .md
```
Methods: random, terrain-only, unweighted (equal weight per feature), profile-weighted (lens chosen by the site's `dimension`), PCA+kNN, cluster-conditioned (GMM), cluster-conditioned (HDBSCAN), calibrated weights (LOO).

## 6. Export (`doppelgrund/export/bundle.py`, `index_map.py`)
```python
def build_bundle(interim: Path, out: Path, profiles, synthetic=False) -> list[Path]
def write_f32(path, arr) / write_i16 / write_u8 / write_h3_txt(path, cells)
def targets_json(targets_df, regimes) -> list[dict]
def stability_json(...)
def validate_bundle(out: Path) -> None    # re-reads files and checks C6
# index_map.py
def rasterise_index(cells: list[str], width=4096, height=2048) -> PIL.Image.Image   # C6 encoding, antimeridian split
```
Layers: convert `known_sites.csv`, pit atlas shapefile, volcano list, curated lava-tube and Sarawak cave lists to GeoJSON points; `land.geojson` = Natural Earth 50m land simplified to ≤ 1.5 MB.

## 7. Notebooks
`05_harmonise_score.ipynb`, `06_domain_clusters.ipynb`, `07_validation.ipynb`, `08_novelty_stability.ipynb`, `09_export.ipynb` — thin wrappers.
