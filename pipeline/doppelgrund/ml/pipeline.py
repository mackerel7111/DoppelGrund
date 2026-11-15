"""Run the stage-2 steps on a folder of C2 tables and leave everything the bundle exporter needs.

Reads ``earth_features`` / ``moon_discs`` / ``mars_discs`` / ``targets`` (parquet) and writes,
next to them: ``scaler.json``, ``ml/domain_gap.json``, ``clusters.parquet``,
``target_regimes.json``, ``novelty.parquet``, ``stability/<target>__<lens>.parquet`` and
``layers/*.geojson``.
Then::

    python -m doppelgrund.export.bundle --interim <folder> --out web/public/data/<name>

    python -m doppelgrund.ml.pipeline --interim data/interim/real_partial
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

from doppelgrund.config import EXPECTED_FEATURES, REPO, load_known_sites, load_profiles
from doppelgrund.export.layers import build_layers
from doppelgrund.harmonise import apply_transforms, fit_scaler, scaled
from doppelgrund.ml.cluster import (
    assign_regime,
    cluster_report,
    fit_gmm_bic,
    fit_hdbscan,
    label_stability,
)
from doppelgrund.ml.domain_gap import report_from_interim
from doppelgrund.ml.embed import clustering_matrix, fit_pca
from doppelgrund.ml.novelty import feat_novelty, geo_novelty, known_site_flag
from doppelgrund.ml.stability import lens_for_target, stability

logger = logging.getLogger(__name__)


def run(interim: Path, draws: int | None = None, with_layers: bool = True, log=print) -> dict:
    interim = Path(interim)
    prof = load_profiles()
    names = list(EXPECTED_FEATURES)
    tr = [f.transform for f in prof.features]
    lith_cols = [f"lith_{c}" for c in prof.lith_classes]
    seed = int(prof.params["seed"])
    earth = pd.read_parquet(interim / "earth_features.parquet")
    moon, mars = (pd.read_parquet(interim / f"{b}_discs.parquet") for b in ("moon", "mars"))
    targets = pd.read_parquet(interim / "targets.parquet")
    masked = earth["masked"].to_numpy(bool) if "masked" in earth else np.zeros(len(earth), bool)

    # 1. scaler (unmasked Earth + all discs, pooled)
    E, M, R = (d[names].to_numpy(float) for d in (earth, moon, mars))
    sc = fit_scaler(E[~masked], M, R, tr, names)
    sc.to_json(interim / "scaler.json")
    log(f"scaler: {sc.counts}")

    # 2. domain gap
    gap = report_from_interim(interim)
    gap.to_json(interim / "ml" / "domain_gap.json")
    log(f"domain gap: AUC {gap.auc_mean:.3f}; separating {gap.separating}")

    # 3. clusters on unmasked Earth + Moon + Mars
    h = lambda X: scaled(apply_transforms(X, tr), sc)  # noqa: E731
    keep = np.flatnonzero(~masked)
    ci = clustering_matrix(
        {"earth": h(E[keep]), "moon": h(M), "mars": h(R)},
        {"earth": earth[lith_cols].to_numpy(float)[keep], "moon": moon[lith_cols].to_numpy(float),
         "mars": mars[lith_cols].to_numpy(float)},
        {"earth": [f"earth:{earth['h3'].iat[i]}" for i in keep],
         "moon": [f"moon:{i}" for i in moon["disc_id"]],
         "mars": [f"mars:{i}" for i in mars["disc_id"]]},
        names, gap.separating,
    )  # fmt: skip
    pca = fit_pca(ci.Z, 0.90, seed)
    P = pca.transform(ci.Z)
    mcs = max(10, len(P) // 200)
    hdb = fit_hdbscan(P, min_cluster_size=mcs, seed=seed)
    gmm, _ = fit_gmm_bic(P, ks=range(2, 11, 2), seed=seed)
    pd.DataFrame(
        {"row_key": ci.row_keys, "hdb_label": hdb.astype(np.int16),
         "gmm_label": gmm.predict(P).astype(np.int16),
         "gmm_maxprob": gmm.predict_proba(P).max(axis=1).astype(np.float32)}
    ).to_parquet(interim / "clusters.parquet", index=False)  # fmt: skip
    log(
        f"clusters: {len(ci.row_keys)} rows, {ci.Z.shape[1]} columns, "
        f"{len(set(hdb) - {-1})} HDBSCAN clusters"
    )
    # report (per-cluster mean z-scores and body mix) and label stability (ARI over 5 refits on 80%)
    cluster_report(hdb, ci.row_keys, ci.Z, ci.columns).to_csv(interim / "ml" / "cluster_report.csv")
    k = gmm.n_components
    refit_gmm = lambda X: (  # noqa: E731 - same K as the BIC choice; refitting the BIC search is slow
        GaussianMixture(k, covariance_type="full", reg_covar=1e-4, random_state=seed)
        .fit(X)
        .predict(X)
    )
    ari = {
        "hdbscan": label_stability(
            P, lambda X: fit_hdbscan(X, min_cluster_size=mcs, seed=seed), seed=seed
        ),
        "gmm": label_stability(P, refit_gmm, seed=seed),
    }
    (interim / "ml" / "cluster_stability.json").write_text(
        json.dumps({"ari_mean_5_refits_80pct": ari, "min_cluster_size": mcs, "gmm_k": k}, indent=1),
        encoding="utf-8",
    )
    log(f"cluster stability (ARI): HDBSCAN {ari['hdbscan']:.2f}, GMM {ari['gmm']:.2f}")

    # regime of each target: its own imputed row, placed in the same PCA space
    regimes: dict[str, int] = {}
    full_regimes: dict[str, dict] = {}
    lith_names = [f"lith_{i}" for i in range(len(lith_cols))]
    for t in targets.itertuples():
        zt = h(np.array([[getattr(t, n) for n in names]], float))[0]
        lt = np.array([getattr(t, c) for c in lith_cols], float) / ci.lith_scale
        vec = dict(zip([*names, *lith_names], np.r_[zt, lt], strict=True))
        row = np.array([vec[c] for c in ci.columns])
        row = np.where(np.isfinite(row), row, ci.medians)
        full_regimes[t.target_id] = assign_regime(row, pca, gmm, ci.Z, hdb)
        regimes[t.target_id] = full_regimes[t.target_id]["hdb"]
    (interim / "target_regimes.json").write_text(json.dumps(regimes, indent=1), encoding="utf-8")
    (interim / "ml" / "regimes.json").write_text(
        json.dumps(full_regimes, indent=1), encoding="utf-8"
    )

    # 4. novelty from config/known_sites.csv (NaN everywhere when it is empty)
    import h3

    sites = load_known_sites()  # documented Earth analogue sites (human-owned; may be empty)

    site_cells = [h3.latlng_to_cell(float(r.lat), float(r.lon), 4) for r in sites.itertuples()]
    ll = earth[["lat", "lng"]].to_numpy(float)
    row_of = {c: i for i, c in enumerate(earth["h3"])}
    site_rows = (
        h(E[[row_of[c] for c in site_cells if c in row_of]])
        if site_cells
        else np.empty((0, E.shape[1]))
    )
    pd.DataFrame(
        {"h3": earth["h3"],
         "geo_novelty_km": geo_novelty(ll, sites[["lat", "lon"]].to_numpy(float)),
         "feat_novelty": feat_novelty(h(E), site_rows),
         "known_site_flag": known_site_flag(earth["h3"], site_cells)}
    ).to_parquet(interim / "novelty.parquet", index=False)  # fmt: skip
    log(
        f"novelty: {len(site_cells)} documented sites"
        + (" (none: novelty is NaN, not zero)" if not site_cells else "")
    )

    # 5. stability per target and lens
    sdir = interim / "stability"
    sdir.mkdir(exist_ok=True)
    rng = np.random.default_rng(seed + 1)
    flags = masked.astype(np.uint8)
    t0 = time.time()
    for t in targets.itertuples():
        x_t = np.array([getattr(t, n) for n in names], float)
        l_t = np.array([getattr(t, c) for c in lith_cols], float)
        l_t = l_t if np.isfinite(l_t).all() else None
        for lens in prof.lenses:
            w = lens_for_target(prof, lens, x_t, l_t)
            s = stability(
                E, earth[lith_cols].to_numpy(float), flags, x_t, l_t, sc, prof, w, rng, draws
            )
            pd.DataFrame({"h3": earth["h3"], "stability": s}).to_parquet(
                sdir / f"{t.target_id}__{lens}.parquet", index=False
            )
    log(f"stability: {len(targets)} targets x {len(prof.lenses)} lenses in {time.time() - t0:.0f}s")

    if with_layers:
        build_layers(interim / "layers")
        log("layers written")
    return {"scaler": sc, "gap": gap, "regimes": regimes}


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--interim", type=Path, default=REPO / "data/interim/real_partial")
    p.add_argument(
        "--draws", type=int, default=None, help="stability draws (default: profiles.yaml)"
    )
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    run(a.interim, a.draws)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
