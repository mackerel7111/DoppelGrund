"""Tests for doppelgrund.config (contract C3 validation)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest
import yaml

from doppelgrund.config import (
    EXPECTED_FEATURES,
    REPO,
    ConfigError,
    load_crosswalk,
    load_datasets,
    load_known_sites,
    load_landmarks,
    load_profiles,
    require_dataset,
)


def _raw() -> dict:
    with open(REPO / "config/profiles.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _write(tmp_path: Path, raw: dict) -> Path:
    p = tmp_path / "profiles.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return p


def test_valid_profiles_load() -> None:
    prof = load_profiles()
    assert tuple(f.name for f in prof.features) == EXPECTED_FEATURES
    assert prof.compat_matrix.shape == (6, 6)
    lens_ids = {"balanced", "landing_mobility", "cold_volatiles", "geology_minerals"}
    assert set(prof.lenses) == lens_ids
    assert prof.params["coverage_floor"] == 0.6
    assert [f.transform for f in prof.features].count("log1p") == 3


def test_wrong_feature_order(tmp_path: Path) -> None:
    raw = _raw()
    raw["features"][0], raw["features"][1] = raw["features"][1], raw["features"][0]
    with pytest.raises(ConfigError, match="features"):
        load_profiles(_write(tmp_path, raw))


def test_missing_lens_group(tmp_path: Path) -> None:
    raw = _raw()
    del raw["lenses"]["balanced"]["thermal"]
    with pytest.raises(ConfigError, match=r"lenses\.balanced"):
        load_profiles(_write(tmp_path, raw))


def test_lens_sum_not_one(tmp_path: Path) -> None:
    raw = _raw()
    raw["lenses"]["cold_volatiles"]["terrain"] = 0.5
    with pytest.raises(ConfigError, match=r"lenses\.cold_volatiles.*sum"):
        load_profiles(_write(tmp_path, raw))


def test_asymmetric_matrix(tmp_path: Path) -> None:
    raw = _raw()
    raw["compat_matrix"][0][1] = 0.9
    with pytest.raises(ConfigError, match="compat_matrix"):
        load_profiles(_write(tmp_path, raw))


def test_wrong_matrix_shape(tmp_path: Path) -> None:
    raw = _raw()
    raw["compat_matrix"] = raw["compat_matrix"][:5]
    with pytest.raises(ConfigError, match="compat_matrix.*shape"):
        load_profiles(_write(tmp_path, raw))


def test_missing_param(tmp_path: Path) -> None:
    raw = _raw()
    del raw["params"]["coverage_floor"]
    with pytest.raises(ConfigError, match=r"params\.coverage_floor"):
        load_profiles(_write(tmp_path, raw))


def test_feature_weights_balanced() -> None:
    w_num, w_lith = load_profiles().feature_weights("balanced")
    assert w_num.shape == (11,)
    np.testing.assert_allclose(w_num[:4], 0.225 / 4)
    np.testing.assert_allclose(w_num[4:7], 0.225 / 3)
    np.testing.assert_allclose(w_num[7:10], 0.225 / 3)
    assert w_num[10] == pytest.approx(0.10)  # subsurface: one feature, n_group = 1
    assert w_lith == pytest.approx(0.225)
    assert w_num.sum() + w_lith == pytest.approx(1.0)


def test_feature_weights_custom_and_zero_group() -> None:
    prof = load_profiles()
    w_num, w_lith = prof.feature_weights("landing_mobility")
    np.testing.assert_allclose(w_num[7:10], 0.0)
    assert w_num[10] == 0.0
    with pytest.raises(ConfigError):
        prof.feature_weights({"terrain": 1.0})


def test_datasets_and_require_warning(caplog: pytest.LogCaptureFixture) -> None:
    ds = load_datasets()
    assert "earth_dem" in ds and ds["earth_dem"]["verified"] is False
    with caplog.at_level(logging.WARNING, logger="doppelgrund.config"):
        require_dataset("earth_dem")
    assert "earth_dem" in caplog.text


def test_human_owned_tables_load_with_schema() -> None:
    lm = load_landmarks()
    assert list(lm.columns) == ["id", "name", "body", "lat", "lon", "source", "notes"]
    assert "well_known" in load_known_sites().columns
    assert "ice" in load_crosswalk().columns
