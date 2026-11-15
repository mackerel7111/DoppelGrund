"""Clustering matrix, PCA, HDBSCAN, GMM and the report (spec 02 task 2.8)."""

from __future__ import annotations

import logging

import numpy as np
import pytest
from sklearn.metrics import adjusted_rand_score

from doppelgrund.ml import cluster as C
from doppelgrund.ml.embed import clustering_matrix, fit_pca

NAMES = ["a", "b", "c", "d"]


def blobs(n: int = 120, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    centres = np.array([[0, 0, 0, 0], [12, 0, 0, 0], [0, 12, 0, 0]], float)
    y = np.repeat(np.arange(3), n)
    return centres[y] + rng.normal(0, 0.5, (3 * n, 4)), y


def test_three_well_separated_blobs_are_recovered_by_both_methods() -> None:
    Z, y = blobs()
    assert adjusted_rand_score(y, C.fit_hdbscan(Z, min_cluster_size=20)) > 0.9
    g, bic = C.fit_gmm_bic(Z, ks=range(2, 7), seed=0)
    assert g.n_components == 3 and bic[3] == min(bic.values())
    assert adjusted_rand_score(y, g.predict(Z)) > 0.9


def test_label_stability_is_high_for_clean_clusters() -> None:
    Z, _ = blobs()
    ari = C.label_stability(Z, lambda z: C.fit_hdbscan(z, min_cluster_size=20), n=3, seed=1)
    assert ari > 0.9


def test_runtime_guard_subsamples_and_still_labels_every_row(caplog, monkeypatch) -> None:
    Z, y = blobs(n=200)
    monkeypatch.setattr(C, "SUBSAMPLE", 300)
    with caplog.at_level(logging.WARNING):
        lab = C.fit_hdbscan(Z, min_cluster_size=20, max_rows=500)  # 600 rows > 500: guard path
    assert "too slow" in caplog.text and len(lab) == len(Z)
    assert adjusted_rand_score(y, lab) > 0.9


def test_imputation_happens_only_in_the_clustering_matrix() -> None:
    scaled = {
        "earth": np.array(
            [[1.0, 2.0, np.nan, 4.0], [1.0, np.nan, np.nan, np.nan], [5.0, 6.0, 7.0, 8.0]]
        )
    }
    lith = {"earth": np.full((3, 6), 1 / 6)}
    keys = {"earth": ["e0", "e1", "e2"]}
    before = scaled["earth"].copy()
    ci = clustering_matrix(scaled, lith, keys, NAMES, min_coverage=0.8)
    assert ci.row_keys == ["e0", "e2"]  # e1 is mostly NaN (3 of 10 columns measured): dropped
    assert (
        np.isfinite(ci.Z).all() and ci.imputed.sum() == 1
    )  # only e0's NaN in column 'c' was filled
    assert ci.imputed[0, 2] and ci.Z[0, 2] == pytest.approx(
        7.0
    )  # the median of the kept rows' column
    np.testing.assert_array_equal(
        np.nan_to_num(scaled["earth"], nan=-1), np.nan_to_num(before, nan=-1)
    )


def test_separating_and_unmeasured_columns_are_left_out() -> None:
    rng = np.random.default_rng(0)
    scaled = {"earth": rng.normal(size=(6, 4)), "moon": rng.normal(size=(6, 4))}
    scaled["earth"][:, 3] = np.nan
    scaled["moon"][:, 3] = np.nan  # column d measured nowhere
    lith = {b: np.full((6, 6), 0.2) for b in scaled}
    keys = {b: [f"{b}:{i}" for i in range(6)] for b in scaled}
    ci = clustering_matrix(scaled, lith, keys, NAMES, separating=["b"])
    assert ci.columns[:2] == ["a", "c"] and "b" not in ci.columns and "d" not in ci.columns
    assert ci.Z.shape == (12, 2 + 6) and ci.row_keys[0] == "earth:0" and ci.row_keys[-1] == "moon:5"


def test_pca_keeps_enough_components_and_the_report_counts_bodies() -> None:
    Z, y = blobs(n=50)
    pca = fit_pca(Z, var=0.90)
    assert pca.explained_variance_ratio_.sum() >= 0.90 and pca.n_components_ < 4
    keys = [f"{'earth' if i % 2 else 'moon'}:{i}" for i in range(len(Z))]
    rep = C.cluster_report(y, keys, Z, NAMES)
    assert rep["n"].tolist() == [50, 50, 50] and rep["share_earth"].tolist() == [0.5, 0.5, 0.5]


def test_assign_regime_puts_a_target_with_the_blob_it_sits_in() -> None:
    Z, y = blobs()
    pca = fit_pca(Z, var=0.95)
    g, _ = C.fit_gmm_bic(pca.transform(Z), ks=range(2, 7), seed=0)
    lab = C.fit_hdbscan(Z, min_cluster_size=20)
    r = C.assign_regime(np.array([12.2, 0.1, 0.0, -0.1]), pca, g, Z, lab)
    in_blob = lab[y == 1]
    assert r["hdb"] == np.bincount(in_blob[in_blob >= 0]).argmax() and r["gmm_prob"] > 0.9
