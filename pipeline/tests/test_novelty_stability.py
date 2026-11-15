"""Novelty (spec 02 task 2.10) and ranking stability (task 2.13)."""

from __future__ import annotations

import h3
import numpy as np
import pytest

from doppelgrund.config import load_profiles
from doppelgrund.harmonise import Scaler
from doppelgrund.ml.novelty import feat_novelty, geo_novelty, known_site_flag
from doppelgrund.ml.stability import available_groups, lens_for_target, stability, top_rows

PROF = load_profiles()
F = len(PROF.features)


def test_geo_novelty_at_a_known_offset_and_nan_without_sites() -> None:
    d = geo_novelty(np.array([[1.0, 0.0], [0.0, 0.0]]), np.array([[0.0, 0.0]]))
    assert d[0] == pytest.approx(111.195, abs=0.01) and d[1] == 0.0
    assert d.dtype == np.float32
    assert np.isnan(geo_novelty(np.array([[1.0, 0.0]]), np.empty((0, 2)))).all()


def test_feat_novelty_ignores_nan_features_and_needs_enough_shared_ones() -> None:
    sites = np.array([[0.0, 0.0, 0.0, 0.0]])
    X = np.array([[3.0, 4.0, 0.0, 0.0], [np.nan, 2.0, 2.0, 2.0], [1.0, np.nan, np.nan, np.nan]])
    d = feat_novelty(X, sites)
    assert d[0] == pytest.approx(np.sqrt((9 + 16) / 4))  # RMS over the 4 shared dimensions
    assert d[1] == pytest.approx(2.0)  # NaN dimension dropped, RMS of (2, 2, 2)
    assert np.isnan(d[2])  # only one shared feature: too few
    assert np.isnan(feat_novelty(X, np.empty((0, 4)))).all()  # no sites: nothing to compare with


def test_known_site_flag_marks_the_site_hex_and_its_ring_one() -> None:
    site = h3.latlng_to_cell(10.0, 10.0, 4)
    ring = h3.grid_ring(site, 1)
    ring2 = h3.grid_ring(site, 2)
    far = h3.latlng_to_cell(-40.0, 100.0, 4)
    f = known_site_flag([site, ring[0], ring2[0], far], [site])
    assert f.tolist() == [True, True, False, False]
    assert not known_site_flag([far], []).any()


def test_available_groups_follow_the_target_data_and_the_lens_is_renormalised() -> None:
    x = np.full(F, np.nan)
    for j, f in enumerate(PROF.features):
        if f.group in ("terrain", "composition"):
            x[j] = 1.0
    lith = np.full(6, 1 / 6)
    assert available_groups(PROF, x, lith) == (
        "terrain",
        "composition",
    )  # lithology counts as composition
    w = lens_for_target(PROF, "balanced", x, lith)
    assert w["thermal"] == 0 and w["subsurface"] == 0
    assert sum(w.values()) == pytest.approx(1.0) and w["terrain"] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        lens_for_target(
            PROF,
            {
                "thermal": 1.0,
                "terrain": 0.0,
                "cold_ice": 0.0,
                "composition": 0.0,
                "subsurface": 0.0,
            },
            x,
            lith,
        )


def make_world(n: int = 200, seed: int = 0):
    rng = np.random.default_rng(seed)
    Xe = rng.uniform(0, 5, (n, F))
    Le = rng.dirichlet(np.ones(6), n)
    sc = Scaler(np.zeros(F), np.full(F, 1.5), {"earth": n, "moon": 0, "mars": 0})
    return Xe, Le, np.zeros(n, np.uint8), sc


def test_a_row_identical_to_the_target_is_in_the_top_slice_in_every_draw() -> None:
    Xe, Le, flags, sc = make_world()
    x_t, l_t = Xe[7].copy(), Le[7].copy()
    w = lens_for_target(PROF, "balanced", x_t, l_t)
    s = stability(Xe, Le, flags, x_t, l_t, sc, PROF, w, np.random.default_rng(0), draws=40)
    assert s[7] == 1.0 and s.max() <= 1.0 and s.min() >= 0.0
    top = top_rows(s, 3)
    assert top[0] == (7, 1.0)


def test_stability_is_reproducible_and_masked_rows_never_count() -> None:
    Xe, Le, flags, sc = make_world(seed=2)
    flags[7] = 1  # the perfect match is masked
    x_t, l_t = Xe[7].copy(), Le[7].copy()
    w = lens_for_target(PROF, "balanced", x_t, l_t)
    a = stability(Xe, Le, flags, x_t, l_t, sc, PROF, w, np.random.default_rng(5), draws=20)
    b = stability(Xe, Le, flags, x_t, l_t, sc, PROF, w, np.random.default_rng(5), draws=20)
    np.testing.assert_array_equal(a, b)
    assert a[7] == 0.0


def test_zero_weight_groups_stay_zero_in_every_draw() -> None:
    Xe, Le, flags, sc = make_world(seed=3)
    x_t, l_t = Xe[3].copy(), Le[3].copy()
    only_terrain = {
        "terrain": 1.0,
        "thermal": 0.0,
        "cold_ice": 0.0,
        "composition": 0.0,
        "subsurface": 0.0,
    }
    base = stability(
        Xe, Le, flags, x_t, l_t, sc, PROF, only_terrain, np.random.default_rng(1), draws=15
    )
    Xe2 = Xe.copy()
    for j, f in enumerate(PROF.features):
        if f.group != "terrain":
            Xe2[:, j] = np.random.default_rng(9).uniform(
                0, 5, len(Xe)
            )  # change only zero-weight groups
    again = stability(
        Xe2, Le, flags, x_t, l_t, sc, PROF, only_terrain, np.random.default_rng(1), draws=15
    )
    np.testing.assert_array_equal(base, again)
