"""Clustering matrix and PCA (spec 02 task 2.8, requirement R6.1-6.2).

The matrix holds the harmonised values of every feature that is not "separating" (see
``domain_gap``) plus the six lithology fractions. Rows with less than ``min_coverage`` of their
columns measured are dropped; the NaNs left in kept rows are filled with the pooled column median,
and that fill is recorded in ``imputed``. Imputation happens ONLY here, never in scoring (science
invariant 1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


@dataclass(frozen=True)
class ClusterInput:
    Z: np.ndarray  # (K, D) float64, no NaN
    row_keys: list[str]  # "earth:<h3>", "moon:<id>", "mars:<id>"
    imputed: np.ndarray  # (K, D) bool, True where a value was filled
    columns: list[str]
    medians: np.ndarray  # (D,) pooled medians used for the fill
    lith_scale: np.ndarray  # (6,) divisor that puts lithology fractions on the z scale


def _lith_scale(frames: Sequence[np.ndarray]) -> np.ndarray:
    L = np.vstack(frames)
    with np.errstate(all="ignore"):
        sd = np.nanstd(L, axis=0)
    return np.where(np.isfinite(sd) & (sd > 1e-9), sd, 1.0)


def clustering_matrix(
    scaled: Mapping[str, np.ndarray],
    lith: Mapping[str, np.ndarray],
    keys: Mapping[str, Sequence[str]],
    feature_names: Sequence[str],
    separating: Sequence[str] = (),
    min_coverage: float = 0.8,
) -> ClusterInput:
    """Build the matrix from per-body harmonised features (``scaled``) and lithology fractions.

    ``scaled``, ``lith`` and ``keys`` are dicts over the bodies ("earth", "moon", "mars").
    Columns with no measured value anywhere are dropped.
    """
    keep_f = [j for j, n in enumerate(feature_names) if n not in set(separating)]
    ls = _lith_scale(list(lith.values()))
    blocks, row_keys = [], []
    for body in scaled:
        X = np.hstack([scaled[body][:, keep_f], lith[body] / ls])
        blocks.append(X)
        row_keys += list(keys[body])
    Xall = np.vstack(blocks)
    names = [feature_names[j] for j in keep_f] + [
        f"lith_{i}" for i in range(lith[next(iter(lith))].shape[1])
    ]
    alive = np.isfinite(Xall).any(axis=0)  # a column nobody measured cannot cluster anything
    Xall, names = Xall[:, alive], [n for n, a in zip(names, alive, strict=True) if a]
    ok = np.isfinite(Xall).mean(axis=1) >= min_coverage
    Xk = Xall[ok]
    with np.errstate(all="ignore"):
        med = np.nanmedian(Xk, axis=0)
    miss = ~np.isfinite(Xk)
    Z = np.where(miss, med[None, :], Xk)
    return ClusterInput(
        Z, [k for k, o in zip(row_keys, ok, strict=True) if o], miss, names, med, ls
    )


def fit_pca(Z: np.ndarray, var: float = 0.90, seed: int = 0) -> PCA:
    """PCA keeping the fewest components that explain ``var`` of the variance."""
    return PCA(n_components=var, svd_solver="full", random_state=seed).fit(Z)


def to_frame(ci: ClusterInput) -> pd.DataFrame:
    return pd.DataFrame(ci.Z, index=ci.row_keys, columns=ci.columns)
