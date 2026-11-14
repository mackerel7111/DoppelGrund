"""Domain-gap diagnostic (spec 02 task 2.7, R5): how different are Earth and planetary rows?

Three things are reported on harmonised values ``(x' - median) / s`` (never raw units):

* the mean ROC AUC of a gradient-boosted classifier (Earth vs planetary) in 5-fold cross-validation
  on a body-balanced sample, so the classes are equal in size and Moon and Mars weigh the same;
* the AUC of each single feature; features at or above 0.95, or at or below 0.05, are **separating**
  and are left out of the clustering (R6) because they only say "this is not Earth";
* the support fraction: for every target and feature, the share of Earth rows within one tolerance
  ``s_f`` of the target's value (``|z| <= 1`` on the scaled axis).

NaN never counts as a value: a feature missing on a body is skipped for that body.

    python -m doppelgrund.ml.domain_gap --interim data/interim/real
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

from doppelgrund.config import EXPECTED_FEATURES, REPO, load_profiles
from doppelgrund.harmonise import Scaler, apply_transforms, fit_scaler, scaled

logger = logging.getLogger(__name__)

SEPARATING_HI, SEPARATING_LO = 0.95, 0.05
MIN_PER_CLASS = 10  # fewer finite rows than this and a feature has no AUC


@dataclass
class DomainGapReport:
    auc_mean: float
    auc_std: float
    auc_per_feature: dict[str, float | None]
    separating: list[str]
    support: dict[str, dict[str, float | None]]
    n_per_class: int
    notes: list[str] = field(default_factory=list)

    def to_json(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        doc = {**self.__dict__, "auc_mean": _clean(self.auc_mean), "auc_std": _clean(self.auc_std)}
        Path(path).write_text(json.dumps(doc, indent=2, allow_nan=False), encoding="utf-8")


def _clean(v: float) -> float | None:
    return None if not np.isfinite(v) else float(v)


def balanced_sample(
    earth: np.ndarray, plan: np.ndarray, plan_body: np.ndarray, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """X, y (1 = Earth) with equal Moon and Mars counts and as many Earth rows as planetary rows."""
    bodies = [b for b in np.unique(plan_body)]
    k = min(int((plan_body == b).sum()) for b in bodies)
    pick = np.concatenate(
        [rng.choice(np.flatnonzero(plan_body == b), k, replace=False) for b in bodies]
    )
    e = rng.choice(len(earth), min(len(earth), len(pick)), replace=False)
    X = np.vstack([earth[e], plan[pick]])
    y = np.r_[np.ones(len(e), int), np.zeros(len(pick), int)]
    return X, y


def feature_auc(x: np.ndarray, y: np.ndarray) -> float | None:
    """ROC AUC of one feature as an Earth-vs-planetary score; None if a class has few values."""
    ok = np.isfinite(x)
    if (ok & (y == 1)).sum() < MIN_PER_CLASS or (ok & (y == 0)).sum() < MIN_PER_CLASS:
        return None
    return float(roc_auc_score(y[ok], x[ok]))


def support_fraction(earth_s: np.ndarray, target_s: np.ndarray) -> np.ndarray:
    """Per feature: share of finite Earth values within one tolerance of the target."""
    with np.errstate(invalid="ignore"):
        close = np.abs(earth_s - target_s[None, :]) <= 1.0
    n = np.isfinite(earth_s).sum(axis=0)
    return np.where((n > 0) & np.isfinite(target_s), close.sum(axis=0) / np.maximum(n, 1), np.nan)


def domain_gap(
    earth_s: np.ndarray,
    plan_s: np.ndarray,
    seed: int,
    plan_body: np.ndarray | None = None,
    feature_names: Sequence[str] = EXPECTED_FEATURES,
    targets_s: dict[str, np.ndarray] | None = None,
    folds: int = 5,
) -> DomainGapReport:
    """Run the diagnostic on harmonised matrices (rows x features)."""
    rng = np.random.default_rng(seed)
    body = np.zeros(len(plan_s), int) if plan_body is None else np.asarray(plan_body)
    X, y = balanced_sample(earth_s, plan_s, body, rng)
    clf = HistGradientBoostingClassifier(max_iter=100, random_state=seed)  # NaN handled natively
    cv = StratifiedKFold(folds, shuffle=True, random_state=seed)
    usable = np.isfinite(X).any(axis=0)  # the booster fails on a column with no value at all
    if usable.any():
        aucs = cross_val_score(clf, X[:, usable], y, cv=cv, scoring="roc_auc")
    else:
        aucs = np.full(folds, np.nan)
    per = {n: feature_auc(X[:, j], y) for j, n in enumerate(feature_names)}
    sep = [
        n for n, a in per.items() if a is not None and (a >= SEPARATING_HI or a <= SEPARATING_LO)
    ]
    support = {
        t: {n: _clean(v) for n, v in zip(feature_names, support_fraction(earth_s, ts), strict=True)}
        for t, ts in (targets_s or {}).items()
    }
    notes = [f"{n}: too few finite values on one side; no AUC" for n, a in per.items() if a is None]
    notes += [
        f"{n}: no value on any body; left out of the classifier"
        for n, u in zip(feature_names, usable, strict=True)
        if not u
    ]
    return DomainGapReport(
        auc_mean=float(aucs.mean()),
        auc_std=float(aucs.std()),
        auc_per_feature={n: None if a is None else _clean(a) for n, a in per.items()},
        separating=sep,
        support=support,
        n_per_class=int((y == 1).sum()),
        notes=notes,
    )


def report_from_interim(interim: Path, seed: int | None = None) -> DomainGapReport:
    """Load the C2 tables, harmonise (using scaler.json, or a fresh fit if it is absent) and run."""
    prof = load_profiles()
    names = list(EXPECTED_FEATURES)
    transforms = [f.transform for f in prof.features]
    interim = Path(interim)
    earth = pd.read_parquet(interim / "earth_features.parquet")
    if "masked" in earth:
        earth = earth[~earth["masked"].astype(bool)]
    moon, mars = (pd.read_parquet(interim / f"{b}_discs.parquet") for b in ("moon", "mars"))
    targets = pd.read_parquet(interim / "targets.parquet")
    E, M, R = (d[names].to_numpy(float) for d in (earth, moon, mars))
    sc_path = interim / "scaler.json"
    if sc_path.is_file():
        sc = Scaler.from_json(sc_path)
    else:
        logger.warning("no scaler.json in %s; fitting a pooled scaler for this diagnostic", interim)
        sc = fit_scaler(E, M, R, transforms, names)

    def harmonise(X: np.ndarray) -> np.ndarray:
        return scaled(apply_transforms(X, transforms), sc)

    tgt = {
        r.target_id: harmonise(np.array([[getattr(r, n) for n in names]], float))[0]
        for r in targets.itertuples()
    }
    plan = np.vstack([harmonise(M), harmonise(R)])
    body = np.r_[np.zeros(len(M), int), np.ones(len(R), int)]
    return domain_gap(
        harmonise(E), plan, int(seed if seed is not None else prof.params["seed"]), body, names, tgt
    )


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--interim", type=Path, default=REPO / "data/interim/real")
    p.add_argument("--out", type=Path, default=REPO / "data/interim/ml/domain_gap.json")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    r = report_from_interim(a.interim)
    r.to_json(a.out)
    print(
        f"wrote {a.out}: mean AUC {r.auc_mean:.3f} +- {r.auc_std:.3f}; separating: {r.separating}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
