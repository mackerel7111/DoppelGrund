"""Cluster-conditioned retrieval (spec 02 task 2.9, requirement R7).

Candidates are the Earth rows in the target's regime, ranked by the usual score S (coverage floor
included). If the target is HDBSCAN noise (label -1) or its regime holds fewer than ``MIN_MEMBERS``
Earth rows, there is no close regime: retrieval falls back to the global ranking and says so
(``no_close_regime``). Clusters are an exploration aid; this never replaces the scorer.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

MIN_MEMBERS = 50
GMM_MIN_PROB = 0.5


def regime_mask(
    kind: str, earth_h3: Sequence[str], clusters: pd.DataFrame, regime: dict
) -> tuple[np.ndarray | None, bool]:
    """``(mask, no_close_regime)``: bool (N,) of Earth rows in the regime, or ``(None, True)``.

    ``kind`` is "hdbscan" (rows with the target's HDBSCAN label) or "gmm" (rows assigned to the
    target's GMM component with probability >= 0.5). ``clusters`` is clusters.parquet; rows it does
    not hold (masked hexes) are never in a regime.
    """
    earth = clusters[clusters["row_key"].str.startswith("earth:")].copy()
    earth["h3"] = earth["row_key"].str.slice(len("earth:"))
    at = earth.set_index("h3")
    if kind == "hdbscan":
        want = int(regime["hdb"])
        if want == -1:
            return None, True  # noise: no close regime
        member = at["hdb_label"] == want
    elif kind == "gmm":
        member = (at["gmm_label"] == int(regime["gmm"])) & (at["gmm_maxprob"] >= GMM_MIN_PROB)
    else:
        raise ValueError(f"unknown regime kind {kind!r}")
    mask = pd.Index(earth_h3).isin(member[member].index)
    if mask.sum() < MIN_MEMBERS:
        return None, True
    return mask, False


def restrict(S: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    """Scores with rows outside the regime set to NaN (ineligible); ``None`` = global ranking."""
    return S if mask is None else np.where(mask, S, np.nan)
