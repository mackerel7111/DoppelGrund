"""Novelty (spec 02 task 2.10, requirement R9): how far a hex is from documented analogue sites.

* ``geo_novelty``  great-circle km to the nearest documented site,
* ``feat_novelty`` distance to the nearest site in harmonised feature space (NaN features ignored),
* ``known_site_flag`` the hex of a site or one of its six neighbours (ring 1).

With NO documented sites nothing can be called novel or known, so both distances are NaN (never a
made-up large number) and no hex is flagged.
"""

from __future__ import annotations

from collections.abc import Sequence

import h3
import numpy as np
from sklearn.neighbors import BallTree

EARTH_R_KM = 6371.0088
MIN_DIMS = 3  # a feature distance needs at least this many jointly measured features


def geo_novelty(latlng: np.ndarray, sites_latlng: np.ndarray) -> np.ndarray:
    """float32 (N,) km to the nearest site; all NaN when ``sites_latlng`` is empty."""
    latlng = np.asarray(latlng, float)
    sites = np.asarray(sites_latlng, float).reshape(-1, 2)
    if len(sites) == 0:
        return np.full(len(latlng), np.nan, np.float32)
    tree = BallTree(np.radians(sites), metric="haversine")
    d, _ = tree.query(np.radians(latlng), k=1)
    return (d[:, 0] * EARTH_R_KM).astype(np.float32)


def feat_novelty(X_scaled: np.ndarray, site_rows: np.ndarray) -> np.ndarray:
    """float32 (N,): RMS distance over jointly finite features to the nearest site row; NaN if none.

    Rows sharing fewer than ``MIN_DIMS`` finite features with every site get NaN.
    """
    X = np.asarray(X_scaled, float)
    sites = np.asarray(site_rows, float).reshape(-1, X.shape[1])
    best = np.full(len(X), np.inf)
    for s in sites:
        both = np.isfinite(X) & np.isfinite(s)[None, :]
        n = both.sum(axis=1)
        with np.errstate(invalid="ignore"):
            d2 = np.where(both, (X - s[None, :]) ** 2, 0.0).sum(axis=1) / np.maximum(n, 1)
        best = np.where(n >= MIN_DIMS, np.minimum(best, np.sqrt(d2)), best)
    return np.where(np.isfinite(best), best, np.nan).astype(np.float32)


def known_site_flag(cells: Sequence[str], site_cells: Sequence[str]) -> np.ndarray:
    """bool (N,): the cell is a site's hex or lies in its ring 1."""
    near = {n for c in site_cells for n in h3.grid_disk(c, 1)}
    return np.array([c in near for c in cells], bool)
