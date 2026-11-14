"""HDBSCAN, Gaussian mixture and the cluster report (spec 02 task 2.8, requirement R6).

Clusters are an exploration aid ("regimes"), never a replacement for the scorer. HDBSCAN labels
(-1 = noise) go into the bundle's ``earth_cluster.i16``; the Gaussian mixture gives soft
assignments for targets. Runtime guard: above ``max_rows`` rows HDBSCAN is fitted on a subsample and
the rest take the label of their nearest fitted row (logged).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.cluster import HDBSCAN
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture

logger = logging.getLogger(__name__)

MAX_ROWS = 100_000
SUBSAMPLE = 30_000


def fit_hdbscan(
    Z: np.ndarray,
    min_cluster_size: int = 15,
    min_samples: int | None = None,
    max_rows: int = MAX_ROWS,
    seed: int = 0,
) -> np.ndarray:
    """HDBSCAN labels (-1 noise), shape (N,). Large inputs are subsampled and propagated."""
    if len(Z) <= max_rows:
        return HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples).fit_predict(Z)
    rng = np.random.default_rng(seed)
    pick = np.sort(rng.choice(len(Z), SUBSAMPLE, replace=False))
    logger.warning(
        "HDBSCAN on %d rows is too slow: fitting %d and assigning the rest by neighbour",
        len(Z),
        SUBSAMPLE,
    )
    lab = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples).fit_predict(Z[pick])
    _, nn = cKDTree(Z[pick]).query(Z)
    return lab[nn]


def fit_gmm_bic(
    Z: np.ndarray, ks: Sequence[int] = range(6, 26, 2), seed: int = 0
) -> tuple[GaussianMixture, dict[int, float]]:
    """The mixture with the lowest BIC over ``ks`` (components capped by the row count)."""
    scores: dict[int, float] = {}
    best: tuple[float, GaussianMixture] | None = None
    for k in ks:
        if k >= len(Z):
            continue
        g = GaussianMixture(k, covariance_type="full", reg_covar=1e-4, random_state=seed).fit(Z)
        scores[int(k)] = float(g.bic(Z))
        if best is None or scores[int(k)] < best[0]:
            best = (scores[int(k)], g)
    if best is None:
        raise ValueError("no component count fits the number of rows")
    return best[1], scores


def cluster_report(
    labels: np.ndarray, row_keys: Sequence[str], Z: np.ndarray, columns: Sequence[str]
) -> pd.DataFrame:
    """One row per cluster: size, share of each body, and the mean of every column."""
    body = np.array([k.split(":", 1)[0] for k in row_keys])
    df = pd.DataFrame(Z, columns=list(columns))
    df["label"], df["body"] = labels, body
    out = df.groupby("label").mean(numeric_only=True)
    out.insert(0, "n", df.groupby("label").size())
    for b in ("earth", "moon", "mars"):
        out.insert(
            1,
            f"share_{b}",
            df.groupby("label")["body"].apply(lambda s, b=b: float((s == b).mean())),
        )
    return out


def label_stability(
    Z: np.ndarray,
    fit_fn: Callable[[np.ndarray], np.ndarray],
    n: int = 5,
    frac: float = 0.8,
    seed: int = 0,
) -> float:
    """Mean adjusted Rand index between the full fit and fits on random ``frac`` subsamples."""
    rng = np.random.default_rng(seed)
    full = fit_fn(Z)
    aris = []
    for _ in range(n):
        pick = np.sort(rng.choice(len(Z), int(frac * len(Z)), replace=False))
        aris.append(adjusted_rand_score(full[pick], fit_fn(Z[pick])))
    return float(np.mean(aris))


def assign_regime(
    z_target: np.ndarray,
    pca,
    gmm: GaussianMixture,
    Z_ref: np.ndarray,
    hdb_labels: np.ndarray,
    k: int = 15,
) -> dict:
    """Regime of one imputed target row: GMM component, its probability and the HDBSCAN label that
    most of its ``k`` nearest reference rows (in PCA space) carry."""
    zt = pca.transform(z_target[None, :])
    comp = int(gmm.predict(zt)[0])
    prob = float(gmm.predict_proba(zt)[0].max())
    _, nn = cKDTree(pca.transform(Z_ref)).query(zt[0], k=min(k, len(Z_ref)))
    votes = hdb_labels[np.atleast_1d(nn)]
    vals, counts = np.unique(votes, return_counts=True)
    return {"gmm": comp, "gmm_prob": prob, "hdb": int(vals[np.argmax(counts)])}
