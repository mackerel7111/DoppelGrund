"""Harmonisation (spec 02 task 2.1): feature transforms and the pooled median / MAD scaler.

The scaler is fitted once on pooled Earth (unmasked rows only: the caller filters) + Moon + Mars
rows, on the transformed scale, ignoring NaN. ``s`` is the plain median absolute deviation, WITHOUT
the 1.4826 normal-consistency factor (spec 02 design section 1); the synthetic generator's stand-in
still uses 1.4826 and a std fallback, so synthetic and real scalers differ by that constant.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MIN_S = 1e-6
# G2: 0 on the planets by definition (no water cycle), so their zeros say nothing about spread
EARTH_ONLY = frozenset({"aridity_index"})


def apply_transforms(X: np.ndarray, transforms: Sequence[str]) -> np.ndarray:
    """(N, F) -> (N, F) float64; ``log1p`` columns become log1p(max(x, 0)); NaN stays NaN."""
    X = np.array(X, dtype=np.float64, copy=True)
    if X.ndim != 2 or X.shape[1] != len(transforms):
        raise ValueError(f"X is {X.shape}, expected (N, {len(transforms)})")
    for j, t in enumerate(transforms):
        if t == "log1p":
            X[:, j] = np.log1p(np.maximum(X[:, j], 0.0))  # np.maximum(nan, 0) is nan
        elif t != "none":
            raise ValueError(f"unknown transform '{t}'")
    return X


@dataclass(frozen=True)
class Scaler:
    median: np.ndarray  # (F,) on the transformed scale
    s: np.ndarray  # (F,) tolerance = pooled MAD on the transformed scale
    counts: dict[str, int]  # rows per body used for the fit
    names: tuple[str, ...] = field(default_factory=tuple)

    def to_json(self, path: Path) -> None:
        """Write the C2 ``scaler.json``."""
        if len(self.names) != len(self.median):
            raise ValueError("Scaler.names is needed to write scaler.json")
        obj = {
            "features": [
                {"name": n, "median": float(m), "s": float(s)}
                for n, m, s in zip(self.names, self.median, self.s, strict=True)
            ],
            "fitted_on": {k: int(v) for k, v in self.counts.items()},
        }
        Path(path).write_text(json.dumps(obj, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path) -> Scaler:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        f = obj["features"]
        return cls(
            median=np.array([x["median"] for x in f], np.float64),
            s=np.array([x["s"] for x in f], np.float64),
            counts={k: int(v) for k, v in obj["fitted_on"].items()},
            names=tuple(x["name"] for x in f),
        )


def fit_scaler(
    earth: np.ndarray,
    moon: np.ndarray,
    mars: np.ndarray,
    transforms: Sequence[str],
    names: Sequence[str] = (),
) -> Scaler:
    """Pooled per-feature median and MAD over the three bodies on the transformed scale.

    ``earth`` must already exclude masked rows. Features in ``EARTH_ONLY`` are fitted on Earth rows
    alone. A feature with ``s < 1e-6`` (or no finite value)
    gets ``s = 1.0`` and a logged warning.
    """
    pooled = apply_transforms(np.vstack([earth, moon, mars]), transforms)
    n_earth = len(earth)
    n_feat = pooled.shape[1]
    med, s = np.zeros(n_feat), np.ones(n_feat)
    for j in range(n_feat):
        col = pooled[:n_earth, j] if _name(names, j) in EARTH_ONLY else pooled[:, j]
        x = col[np.isfinite(col)]
        if x.size == 0:
            logger.warning(
                "feature %s: no finite value on any body; median 0, s 1", _name(names, j)
            )
            continue
        med[j] = np.median(x)
        mad = np.median(np.abs(x - med[j]))
        if mad < MIN_S:
            logger.warning("feature %s: MAD %.3g < %g; s set to 1.0", _name(names, j), mad, MIN_S)
        else:
            s[j] = mad
    counts = {"earth": len(earth), "moon": len(moon), "mars": len(mars)}
    return Scaler(med, s, counts, tuple(names))


def scaled(X_t: np.ndarray, scaler: Scaler) -> np.ndarray:
    """(X' - median) / s on already-transformed values; for clustering only, never for scoring."""
    return (np.asarray(X_t, np.float64) - scaler.median) / scaler.s


def _name(names: Sequence[str], j: int) -> str:
    return names[j] if j < len(names) else f"#{j}"
