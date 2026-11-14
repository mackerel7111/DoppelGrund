"""Tests for the synthetic fixture (00/R4)."""

from __future__ import annotations

import json
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pytest
import shapely
from PIL import Image

from doppelgrund.config import EXPECTED_FEATURES, EXPECTED_LITH, load_profiles
from doppelgrund.fixtures.synthetic import (
    index_map,
    load_land,
    make_synthetic,
    write_synthetic_bundle,
    write_synthetic_interim,
)

SEED = 20261114
C6_FILES = [
    "manifest.json",
    "earth_h3.txt",
    "earth_features.f32",
    "earth_lith.f32",
    "earth_latlng.f32",
    "earth_novelty.f32",
    "earth_cluster.i16",
    "earth_flags.u8",
    "targets.json",
    "earth_index_4096x2048.png",
    "moon_features.f32",
    "moon_lith.f32",
    "moon_latlon.f32",
    "mars_features.f32",
    "mars_lith.f32",
    "mars_latlon.f32",
    "layers/land.geojson",
    "layers/known_sites.geojson",
    "layers/lunar_pits.geojson",
    "layers/lava_tubes.geojson",
    "layers/sarawak_caves.geojson",
    "layers/volcanoes.geojson",
    "textures/earth.jpg",
    "textures/moon.jpg",
    "textures/mars.jpg",
]


@pytest.fixture(scope="module")
def tables() -> dict[str, pd.DataFrame]:
    return make_synthetic(SEED, 6000)


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("bundle")
    write_synthetic_bundle(out, SEED, 400, sample=False)
    return out


def _all_bytes(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_deterministic_bytes(tmp_path: Path, bundle: Path) -> None:
    write_synthetic_bundle(tmp_path / "b", SEED, 400, sample=False)
    assert _all_bytes(tmp_path / "b") == _all_bytes(bundle)
    write_synthetic_interim(tmp_path / "i1", SEED, 400)
    write_synthetic_interim(tmp_path / "i2", SEED, 400)
    assert _all_bytes(tmp_path / "i1") == _all_bytes(tmp_path / "i2")


def test_all_c6_files_present(bundle: Path) -> None:
    for name in C6_FILES:
        assert (bundle / name).is_file(), name
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    targets = json.loads((bundle / "targets.json").read_text(encoding="utf-8"))
    for t in targets:
        for lens in load_profiles().lenses:
            assert (bundle / "stability" / f"{t['id']}__{lens}.json").is_file()
    for key, fname in manifest["files"].items():
        assert (bundle / fname).is_file(), key


def test_manifest_validates(bundle: Path) -> None:
    m = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert m["contract"] == "doppelgrund-bundle/1"
    assert m["synthetic"] is True
    assert m["h3_res"] == 4
    assert [f["name"] for f in m["features"]] == list(EXPECTED_FEATURES)
    assert m["lith_classes"] == list(EXPECTED_LITH)
    assert all(f["s"] > 0 and np.isfinite(f["median"]) for f in m["features"])
    assert set(m["lenses"]) == set(load_profiles().lenses)
    assert np.asarray(m["compat_matrix"]).shape == (6, 6)


def test_array_lengths_match_n_hex(bundle: Path) -> None:
    m = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    n = m["n_hex"]
    h3_lines = (bundle / "earth_h3.txt").read_text().splitlines()
    assert len(h3_lines) == n
    assert all(h3.get_resolution(c) == 4 for c in h3_lines)
    sizes = {
        "earth_features.f32": n * 11 * 4,
        "earth_lith.f32": n * 6 * 4,
        "earth_latlng.f32": n * 2 * 4,
        "earth_novelty.f32": n * 2 * 4,
        "earth_cluster.i16": n * 2,
        "earth_flags.u8": n,
    }
    for name, size in sizes.items():
        assert (bundle / name).stat().st_size == size, name
    moon = np.fromfile(bundle / "moon_features.f32", dtype="<f4")
    assert moon.size % 11 == 0
    assert np.fromfile(bundle / "moon_latlon.f32", dtype="<f4").size == moon.size // 11 * 2


def test_nan_fraction_per_feature(tables: dict[str, pd.DataFrame]) -> None:
    earth = tables["earth_features"]
    for name in EXPECTED_FEATURES:
        x = earth[name].to_numpy()
        if name == "permafrost_prob":  # defined only north of 45°N (design §5)
            x = x[earth["lat"].to_numpy() > 45.0]
        frac = float(np.isnan(x).mean())
        if name == "pit_cave_density_per_1000km2":  # only surveyed hexes carry a value
            assert 0.80 <= frac <= 0.97, (name, frac)
            continue
        assert 0.05 <= frac <= 0.15, (name, frac)
    feats = earth[list(EXPECTED_FEATURES)].to_numpy()
    assert np.isnan(feats).all(axis=1).sum() > 0  # some all-NaN rows
    assert 0.25 < earth["masked"].mean() < 0.35
    assert len(earth) >= 5000


def test_value_ranges_and_definitions(tables: dict[str, pd.DataFrame]) -> None:
    earth, moon, mars = tables["earth_features"], tables["moon_discs"], tables["mars_discs"]
    assert np.nanmin(earth["lst_mean_K"]) >= 220 and np.nanmax(earth["lst_mean_K"]) <= 325
    assert np.nanmax(earth["frac_slope_lt_10deg"]) <= 1.0
    assert np.isnan(earth.loc[earth["lat"] <= 45, "permafrost_prob"]).all()
    for discs in (moon, mars):
        assert (discs["aridity_index"] == 0.0).all()  # 0.0 by definition
        assert discs["permafrost_prob"].isna().all()
        assert ((discs["lon"] >= -180) & (discs["lon"] < 180)).all()
    assert mars["lst_mean_K"].isna().all()
    cave = "pit_cave_density_per_1000km2"
    assert mars[cave].isna().all()  # no Mars catalogue
    for df in (earth, moon):
        x = df[cave].to_numpy()
        assert np.nanmin(x) == 0.0 and np.isnan(x).any() and (x[np.isfinite(x)] >= 0).all()
        assert (x[np.isfinite(x)] > 0).any()  # some catalogued hits
    lith = earth[[f"lith_{c}" for c in EXPECTED_LITH]].to_numpy()
    ok = ~np.isnan(lith).any(axis=1)
    np.testing.assert_allclose(lith[ok].sum(axis=1), 1.0, atol=1e-5)


def test_targets(tables: dict[str, pd.DataFrame], bundle: Path) -> None:
    t = tables["targets"]
    assert len(t) >= 6
    assert set(t["body"]) == {"moon", "mars"}
    assert all(i.startswith("synthetic_") for i in t["target_id"])
    assert t["lat"].min() < -88.5  # a near-pole target exercises the polar path
    targets = json.loads((bundle / "targets.json").read_text(encoding="utf-8"))
    assert all(len(x["features"]) == 11 and len(x["lith"]) == 6 for x in targets)
    assert any(x["features"][10] is not None for x in targets)  # a pit-bearing target exists
    mars = next(x for x in targets if x["body"] == "mars")
    assert mars["features"][4] is None  # NaN written as null


def test_index_map_decodes_to_rows(bundle: Path) -> None:
    img = np.asarray(Image.open(bundle / "earth_index_4096x2048.png").convert("RGB"), np.int64)
    assert img.shape == (2048, 4096, 3)
    val = img[..., 0] * 65536 + img[..., 1] * 256 + img[..., 2]
    n = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))["n_hex"]
    assert val.max() <= n and val.min() >= 0
    latlng = np.fromfile(bundle / "earth_latlng.f32", dtype="<f4").reshape(-1, 2)
    x = ((latlng[:, 1] + 180.0) / 360.0 * 4096).astype(int).clip(0, 4095)
    y = ((90.0 - latlng[:, 0]) / 180.0 * 2048).astype(int).clip(0, 2047)
    hit = val[y, x] - 1 == np.arange(n)
    assert hit.mean() > 0.9


def test_index_map_antimeridian() -> None:
    cell = h3.latlng_to_cell(66.0, 179.95, 4)
    img = np.asarray(index_map([cell]))
    cols = np.flatnonzero(img.any(axis=(0, 2)))
    assert cols.min() == 0 or cols.max() == 4095  # painted on at least one edge
    if any(p[1] < 0 for p in h3.cell_to_boundary(cell)):
        assert cols.min() == 0 and cols.max() == 4095


def test_land_coverage_subset() -> None:
    """Land mode on a Europe/N. Africa box: every centre on real land, NaN injection kept."""
    t = make_synthetic(SEED, coverage="land", bbox=(30.0, 55.0, -10.0, 40.0))
    earth = t["earth_features"]
    assert 2500 < len(earth) < 6000  # ~7 M km² of land / 1,770 km² per cell
    assert shapely.contains_xy(load_land(), earth["lng"].to_numpy(), earth["lat"].to_numpy()).all()
    assert all(h3.get_resolution(c) == 4 for c in earth["h3"])
    lst = earth["lst_mean_K"].to_numpy()
    assert 0.05 <= np.isnan(lst).mean() <= 0.15  # NaN injection kept
