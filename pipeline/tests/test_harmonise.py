"""Harmonisation: transforms and the pooled median / MAD scaler (spec 02 task 2.1)."""

from __future__ import annotations

import logging

import numpy as np
import pytest

from doppelgrund.harmonise import Scaler, apply_transforms, fit_scaler, scaled


def test_log1p_only_on_listed_features_and_nan_survives() -> None:
    X = np.array([[1.0, 3.0], [np.nan, -5.0], [2.0, np.nan]])
    out = apply_transforms(X, ["none", "log1p"])
    assert out[0, 0] == 1.0 and out[2, 0] == 2.0 and np.isnan(out[1, 0])  # 'none' column untouched
    assert out[0, 1] == pytest.approx(np.log(4.0))
    assert out[1, 1] == 0.0  # negatives clamp to 0 before log1p
    assert np.isnan(out[2, 1])
    assert X[0, 1] == 3.0  # input not modified


def test_unknown_transform_and_bad_shape_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown transform"):
        apply_transforms(np.zeros((2, 1)), ["sqrt"])
    with pytest.raises(ValueError, match="expected"):
        apply_transforms(np.zeros((2, 3)), ["none"])


def test_pooled_median_and_mad_match_a_hand_computation() -> None:
    # pooled values of the one feature: earth 1,2,3 + moon 4,NaN + mars 10 -> finite 1,2,3,4,10
    # median 3, |x - 3| = 2,1,0,1,7 -> MAD = median(0,1,1,2,7) = 1 (no 1.4826 factor)
    sc = fit_scaler(
        np.array([[1.0], [2.0], [3.0]]), np.array([[4.0], [np.nan]]), np.array([[10.0]]), ["none"]
    )
    assert sc.median[0] == 3.0 and sc.s[0] == 1.0
    assert sc.counts == {"earth": 3, "moon": 2, "mars": 1}


def test_mad_is_taken_on_the_transformed_scale() -> None:
    x = np.array([[0.0], [1.0], [3.0], [7.0], [15.0]])  # log1p -> 0, ln2, ln4, ln8, ln16
    sc = fit_scaler(x, x[:0], x[:0], ["log1p"])
    t = np.log1p(x[:, 0])
    assert sc.median[0] == pytest.approx(np.median(t))
    assert sc.s[0] == pytest.approx(np.median(np.abs(t - np.median(t))))


def test_degenerate_feature_gets_s_one_with_a_warning(caplog) -> None:
    X = np.array([[5.0, 1.0], [5.0, 2.0], [5.0, 4.0]])
    with caplog.at_level(logging.WARNING):
        sc = fit_scaler(X, X[:0], X[:0], ["none", "none"], names=["flat", "ok"])
    assert sc.s[0] == 1.0 and sc.s[1] == 1.0  # flat feature: MAD 0 -> 1; ok feature: MAD 1
    assert "flat" in caplog.text and "ok" not in caplog.text


def test_scaled_is_median_centred_and_mad_divided() -> None:
    sc = Scaler(np.array([3.0]), np.array([2.0]), {"earth": 1, "moon": 0, "mars": 0})
    assert scaled(np.array([[7.0], [np.nan]]), sc)[0, 0] == 2.0
    assert np.isnan(scaled(np.array([[7.0], [np.nan]]), sc)[1, 0])


def test_scaler_json_round_trip_matches_c2(tmp_path) -> None:
    sc = fit_scaler(
        np.array([[1.0, 2.0], [2.0, 5.0], [9.0, 5.0]]),
        np.zeros((0, 2)),
        np.zeros((0, 2)),
        ["none", "log1p"],
        names=["a", "b"],
    )
    path = tmp_path / "scaler.json"
    sc.to_json(path)
    back = Scaler.from_json(path)
    assert back.names == ("a", "b") and back.counts == {"earth": 3, "moon": 0, "mars": 0}
    np.testing.assert_allclose(back.median, sc.median)
    np.testing.assert_allclose(back.s, sc.s)
    with pytest.raises(ValueError, match="names"):
        Scaler(sc.median, sc.s, sc.counts).to_json(tmp_path / "x.json")


def test_earth_only_feature_ignores_planet_rows() -> None:
    # aridity is 0 on the planets by definition: pooled MAD would be 0, Earth-only MAD is 1
    earth = np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]])
    zeros = np.zeros((10, 2))
    sc = fit_scaler(earth, zeros, zeros, ["none", "none"], names=["aridity_index", "other"])
    assert sc.median[0] == 2.0 and sc.s[0] == 1.0  # Earth rows only
    assert sc.median[1] == 0.0  # other features still pool all bodies
