"""Domain-gap diagnostic (spec 02 task 2.7): separable toy data, identical data, support by hand."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from doppelgrund.fixtures import synthetic as syn
from doppelgrund.ml.domain_gap import (
    balanced_sample,
    domain_gap,
    feature_auc,
    report_from_interim,
    support_fraction,
)

NAMES = ["a", "b", "c"]


def toy(shift: float, n: int = 300, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Earth and planetary rows; feature 'a' is shifted by ``shift`` on the planets only."""
    rng = np.random.default_rng(seed)
    earth = rng.normal(0, 1, (n, 3))
    plan = rng.normal(0, 1, (n, 3))
    plan[:, 0] += shift
    return earth, plan, np.r_[np.zeros(n // 2, int), np.ones(n - n // 2, int)]


def test_a_perfectly_separable_feature_gives_auc_one_and_is_flagged() -> None:
    earth, plan, body = toy(shift=20.0)
    r = domain_gap(earth, plan, seed=1, plan_body=body, feature_names=NAMES)
    assert r.auc_mean > 0.99
    assert r.auc_per_feature["a"] == pytest.approx(0.0, abs=1e-9)  # Earth always lower: AUC 0
    assert r.separating == ["a"]  # 'b' and 'c' are not separating
    assert 0.35 < r.auc_per_feature["b"] < 0.65


def test_identical_distributions_give_auc_near_half_and_flag_nothing() -> None:
    earth, plan, body = toy(shift=0.0, n=600, seed=3)
    r = domain_gap(earth, plan, seed=2, plan_body=body, feature_names=NAMES)
    assert 0.4 < r.auc_mean < 0.6
    assert r.separating == []


def test_a_feature_missing_on_one_side_has_no_auc_and_is_not_flagged() -> None:
    earth, plan, body = toy(shift=0.0, seed=4)
    plan[:, 2] = np.nan  # e.g. Mars and Moon thermal not measured
    r = domain_gap(earth, plan, seed=1, plan_body=body, feature_names=NAMES)
    assert r.auc_per_feature["c"] is None and "c" not in r.separating
    assert any(n.startswith("c:") for n in r.notes)


def test_balanced_sample_has_equal_bodies_and_equal_classes() -> None:
    rng = np.random.default_rng(0)
    earth = rng.normal(size=(1000, 2))
    plan = rng.normal(size=(120, 2))
    body = np.r_[np.zeros(100, int), np.ones(20, int)]  # Moon is 5x bigger than Mars
    X, y = balanced_sample(earth, plan, body, rng)
    assert (y == 1).sum() == (y == 0).sum() == 40  # 20 Moon + 20 Mars; as many Earth rows


def test_support_fraction_by_hand() -> None:
    earth_s = np.array([[0.0, 5.0], [0.5, 5.2], [2.0, np.nan], [-0.9, 9.0]])
    target_s = np.array([0.0, 5.0])
    f = support_fraction(earth_s, target_s)
    assert f[0] == pytest.approx(3 / 4)  # 0, 0.5, -0.9 are within 1 of 0; 2.0 is not
    assert f[1] == pytest.approx(2 / 3)  # 5.0 and 5.2 of three finite values
    assert np.isnan(support_fraction(earth_s, np.array([np.nan, 1.0]))[0])  # target missing


def test_feature_auc_needs_enough_values_on_both_sides() -> None:
    y = np.r_[np.ones(20, int), np.zeros(20, int)]
    x = np.r_[np.arange(20.0), np.arange(20.0) + 100]
    assert feature_auc(x, y) == pytest.approx(0.0)
    x[20:] = np.nan
    assert feature_auc(x, y) is None


def test_report_on_the_synthetic_interim_tables_writes_valid_json(tmp_path: Path) -> None:
    t = syn.make_synthetic(20261114, 600)
    d = tmp_path / "interim"
    d.mkdir()
    t["earth_features"].to_parquet(
        d / "earth_features.parquet"
    )  # has 'masked': the diagnostic drops it
    for k in ("moon_discs", "mars_discs", "targets"):
        t[k].to_parquet(d / f"{k}.parquet")
    r = report_from_interim(d)
    out = tmp_path / "ml" / "domain_gap.json"
    r.to_json(out)
    doc = json.loads(out.read_text())
    assert 0.0 <= doc["auc_mean"] <= 1.0 and set(doc["auc_per_feature"]) >= {"slope_p50_deg"}
    assert len(doc["support"]) == len(t["targets"])
    # aridity is 0 on both planets by definition, so it cannot match Earth and must be flagged
    assert "aridity_index" in doc["separating"]


def test_a_feature_with_no_value_anywhere_is_skipped_not_fatal(tmp_path: Path) -> None:
    earth, plan, body = toy(shift=20.0, seed=5)
    earth[:, 2] = np.nan
    plan[:, 2] = np.nan  # e.g. the cave density before any catalogue exists
    r = domain_gap(earth, plan, seed=1, plan_body=body, feature_names=NAMES)
    assert r.auc_mean > 0.99 and r.auc_per_feature["c"] is None
    assert any("c: no value on any body" in n for n in r.notes)
    allnan = domain_gap(earth * np.nan, plan * np.nan, seed=1, plan_body=body, feature_names=NAMES)
    assert np.isnan(allnan.auc_mean)
    out = tmp_path / "r.json"
    allnan.to_json(out)  # NaN must be written as null, not crash
    assert json.loads(out.read_text())["auc_mean"] is None
