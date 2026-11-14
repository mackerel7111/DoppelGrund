"""Parity vector generator (spec 02 task 2.4, contract C7).

Writes ``tests/parity/vectors.json`` from the Python reference scorer so
``web/tests/parity.test.ts`` can check the TypeScript port to 1e-5. Vectors are regenerated, never
hand-edited::

    python -m doppelgrund.export.parity --out tests/parity/vectors.json

Small cases are hand-built (<= 12 rows); the last case is a 500-row slice of the synthetic bundle.
NaN is written as ``null``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from doppelgrund.config import REPO, Profiles, load_profiles
from doppelgrund.fixtures.synthetic import make_synthetic
from doppelgrund.harmonise import fit_scaler
from doppelgrund.scoring import GROUPS, ScoreResult, score, select_cards

CONTRACT = "doppelgrund-parity/1"
SMALL_PARAMS = {"coverage_floor": 0.6, "card_overall_percentile": 50, "card_min_separation_km": 300}


def _j(v: Any) -> Any:
    """JSON-safe copy: NaN -> None, numpy scalars/arrays -> Python."""
    if isinstance(v, np.ndarray):
        return [_j(x) for x in v.tolist()]
    if isinstance(v, dict):
        return {k: _j(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_j(x) for x in v]
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    return v


def make_case(
    prof: Profiles,
    name: str,
    X: np.ndarray,
    L: np.ndarray,
    latlng: np.ndarray,
    flags: np.ndarray,
    x_t: np.ndarray,
    l_t: np.ndarray,
    lens: str | dict[str, float] = "balanced",
    params: dict[str, Any] | None = None,
    scaler=None,
) -> dict[str, Any]:
    """One C7 case with its expected output computed by the reference scorer."""
    transforms = [f.transform for f in prof.features]
    names = [f.name for f in prof.features]
    sc = scaler or fit_scaler(X, X[:0], X[:0], transforms, names)
    weights = prof.lenses[lens] if isinstance(lens, str) else lens
    w_num, w_lith = prof.feature_weights(lens)
    gof = [GROUPS.index(f.group) for f in prof.features]
    params = params or SMALL_PARAMS
    res: ScoreResult = score(
        X, L, flags, x_t, None if np.isnan(l_t).all() else l_t, sc, transforms, gof, w_num, w_lith,
        prof.compat_matrix,
    )  # fmt: skip
    cards = select_cards(res, latlng, params)
    return {
        "name": name,
        "earth_features": _j(X),
        "earth_lith": _j(L),
        "latlng": _j(latlng),
        "flags": [int(f) for f in flags],
        "target_features": _j(x_t),
        "target_lith": _j(l_t),
        "median": _j(sc.median),
        "s": _j(sc.s),
        "transforms": transforms,
        "compat_matrix": _j(prof.compat_matrix),
        "lens_weights": _j({g: float(weights[g]) for g in GROUPS}),
        "params": params,
        "expected": {
            "S": _j(res.S),
            "coverage": _j(res.coverage),
            "group": _j(res.groups),
            "cards": _j(cards),
        },
    }


def _rows(
    rng: np.random.Generator, n: int, n_feat: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X = rng.uniform(0.0, 6.0, (n, n_feat))
    L = rng.dirichlet(np.ones(6), n)
    latlng = np.column_stack([rng.uniform(-60, 60, n), rng.uniform(-170, 170, n)])
    return X, L, latlng


def build_cases(prof: Profiles) -> list[dict[str, Any]]:
    rng = np.random.default_rng(int(prof.params["seed"]))
    nf = len(prof.features)
    cases: list[dict[str, Any]] = []

    def add(name: str, X, L, latlng, flags=None, x_t=None, l_t=None, **kw) -> None:
        n = len(X)
        flags = np.zeros(n, np.uint8) if flags is None else np.asarray(flags, np.uint8)
        x_t = rng.uniform(0.0, 6.0, nf) if x_t is None else np.asarray(x_t, float)
        l_t = rng.dirichlet(np.ones(6)) if l_t is None else np.asarray(l_t, float)
        cases.append(make_case(prof, name, X, L, latlng, flags, x_t, l_t, **kw))

    X, L, ll = _rows(rng, 10, nf)
    add("all_valid", X, L, ll)

    X, L, ll = _rows(rng, 12, nf)
    X[rng.random(X.shape) < 0.3] = np.nan
    x_t = rng.uniform(0.0, 6.0, nf)
    x_t[[1, 5, 9]] = np.nan
    L[2] = np.nan
    add("partial_nan", X, L, ll, x_t=x_t)

    X, L, ll = _rows(rng, 8, nf)
    X[3], L[3] = np.nan, np.nan
    add("all_nan_row", X, L, ll)

    X, L, ll = _rows(rng, 10, nf)
    add("masked_rows", X, L, ll, flags=[1, 0, 0, 1, 0, 0, 0, 1, 0, 0])

    X, L, ll = _rows(rng, 10, nf)
    zero = {"terrain": 0.5, "thermal": 0.0, "cold_ice": 0.5, "composition": 0.0, "subsurface": 0.0}
    add("zero_weight_groups", X, L, ll, lens=zero)

    X, L, ll = _rows(rng, 10, nf)
    x_t = X[0].copy()
    add("identical_target_and_row", X, L, ll, x_t=x_t, l_t=L[0])

    X, L, ll = _rows(rng, 9, nf)
    X[1], L[1] = X[0], L[0]  # exact duplicates -> tied scores; tie-breaks decide the cards
    X[2], L[2] = X[0], L[0]
    ll[:3] = [[10, 10], [10, 40], [10, 70]]
    add("ties", X, L, ll, x_t=X[0], l_t=L[0], params={**SMALL_PARAMS, "card_overall_percentile": 0})

    X, L, ll = _rows(rng, 8, nf)
    ll[:4] = [
        [0.0, 179.9],
        [0.0, -179.9],
        [20.0, 179.95],
        [20.0, -179.95],
    ]  # ~22 km apart across +-180
    X[1], L[1] = X[0], L[0]
    X[3], L[3] = X[2], L[2]
    add(
        "antimeridian_neighbours",
        X,
        L,
        ll,
        x_t=X[0],
        l_t=L[0],
        params={**SMALL_PARAMS, "card_overall_percentile": 0},
    )

    X, L, ll = _rows(rng, 8, nf)
    add("unmapped_target_lithology", X, L, ll, l_t=np.full(6, np.nan))

    X, L, ll = _rows(rng, 10, nf)
    X[:, -1] = np.where(
        rng.random(10) < 0.5, 0.0, rng.uniform(0, 40, 10)
    )  # the log1p feature, incl. 0
    add("log1p_feature_and_zeros", X, L, ll)

    cases.append(_synthetic_slice(prof))
    return cases


def _synthetic_slice(prof: Profiles) -> dict[str, Any]:
    """500 Earth rows from the synthetic tables, scored against one synthetic target."""
    t = make_synthetic(int(prof.params["seed"]), n_hex=6000)
    names = [f.name for f in prof.features]
    lith = [f"lith_{c}" for c in prof.lith_classes]
    earth, targets = t["earth_features"], t["targets"]
    sel = np.linspace(0, len(earth) - 1, 500).astype(int)
    sub = earth.iloc[sel]
    transforms = [f.transform for f in prof.features]
    X, L = sub[names].to_numpy(float), sub[lith].to_numpy(float)
    flags = sub["masked"].to_numpy(bool).astype(np.uint8)
    pool_e = earth.loc[~earth["masked"], names].to_numpy(float)
    sc = fit_scaler(pool_e, t["moon_discs"][names].to_numpy(float),
                    t["mars_discs"][names].to_numpy(float), transforms, names)  # fmt: skip
    tg = targets.iloc[0]
    return make_case(
        prof, "synthetic_slice_500", X, L,
        np.column_stack([sub["lat"].to_numpy(float), sub["lng"].to_numpy(float)]), flags,
        tg[names].to_numpy(float), tg[lith].to_numpy(float),
        params=prof.params, scaler=sc,
    )  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--out", type=Path, default=REPO / "tests/parity/vectors.json")
    a = p.parse_args(argv)
    prof = load_profiles()
    doc = {"contract": CONTRACT, "cases": build_cases(prof)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {a.out} ({a.out.stat().st_size / 1024:.0f} KB, {len(doc['cases'])} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
