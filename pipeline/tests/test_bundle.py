"""Bundle exporter, validator and index map (spec 02 task 2.5, contract C6)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from doppelgrund.config import EXPECTED_FEATURES, load_profiles
from doppelgrund.export import bundle as B
from doppelgrund.export.bundle import build_bundle, earth_flags, mask_flag, validate_bundle
from doppelgrund.export.index_map import INDEX_W, rasterise_index
from doppelgrund.fixtures import synthetic as syn
from doppelgrund.harmonise import fit_scaler

SEED = 20261114
PROF = load_profiles()


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("bundle")
    syn.write_synthetic_bundle(out, SEED, 400, sample=False)  # calls write_bundle, which validates
    return out


def copy_of(bundle: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "b"
    shutil.copytree(bundle, dst)
    return dst


def test_synthetic_bundle_passes_validation(bundle: Path) -> None:
    validate_bundle(bundle)
    assert json.loads((bundle / "manifest.json").read_text())["contract"] == "doppelgrund-bundle/1"


def test_validator_reports_every_kind_of_c6_breakage(bundle: Path, tmp_path: Path) -> None:
    b = copy_of(bundle, tmp_path)
    (b / "earth_features.f32").write_bytes(b"\0" * 12)  # wrong length
    (b / "layers" / "land.geojson").unlink()  # missing layer
    man = json.loads((b / "manifest.json").read_text())
    man["features"][0], man["features"][1] = man["features"][1], man["features"][0]  # order
    (b / "manifest.json").write_text(json.dumps(man))
    with pytest.raises(ValueError) as e:
        validate_bundle(b)
    msg = str(e.value)
    assert "earth_features.f32" in msg and "layers/land.geojson" in msg and "feature order" in msg


def test_validator_rejects_a_wrong_index_image_and_bad_stability(
    bundle: Path, tmp_path: Path
) -> None:
    b = copy_of(bundle, tmp_path)
    Image.new("RGB", (64, 32)).save(b / "earth_index_4096x2048.png")
    p = next((b / "stability").glob("*.json"))
    st = json.loads(p.read_text())
    st["rows"][0] = [10**9, 0.5]
    p.write_text(json.dumps(st))
    with pytest.raises(ValueError, match="index image") as e:
        validate_bundle(b)
    assert "out of range" in str(e.value)


def test_size_budget_failure_lists_the_largest_files(
    bundle: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(B, "BUNDLE_BUDGET_MB", 0.001)
    with pytest.raises(ValueError, match="size budget exceeded") as e:
        validate_bundle(bundle)
    assert "largest:" in str(e.value)


def test_antimeridian_hexes_are_drawn_at_both_image_edges() -> None:
    straddling = [
        c
        for c in h3.grid_disk(h3.latlng_to_cell(0.0, 180.0, 4), 2)
        if max(p[1] for p in h3.cell_to_boundary(c)) - min(p[1] for p in h3.cell_to_boundary(c))
        > 180
    ]
    assert len(straddling) >= 3  # these cells really straddle +-180
    for cell in straddling:
        img = np.asarray(rasterise_index([cell]))
        assert img[:, :2].any() and img[:, -2:].any(), cell  # pixels at x = 0 and x = width - 1
        assert (img[img.any(axis=2)] == [0, 0, 1]).all()  # every drawn pixel has value row + 1 = 1
        assert not img[:, INDEX_W // 2].any()  # nothing in the middle of the map


def test_index_map_decodes_row_plus_one_for_large_rows() -> None:
    cells = [h3.latlng_to_cell(10.0, 10.0, 4)]
    img = np.asarray(rasterise_index(cells * 1, 360, 180))
    assert int(img[80, 190, 2]) == 1  # lat 10 -> y = 80, lon 10 -> x = 190
    big = rasterise_index(["8409b1bffffffff"] * 70000, 360, 180)  # row + 1 reaches 70000 > 65535
    r, g, bl = (
        np.asarray(big)[:, :, 0].max(),
        np.asarray(big)[:, :, 1].max(),
        np.asarray(big)[:, :, 2].max(),
    )
    assert 70000 == int(r) * 65536 + int(g) * 256 + int(bl)


def test_mask_rule_keeps_barren_or_low_ndvi_and_masks_nan() -> None:
    df = pd.DataFrame(
        {
            "barren_frac": [0.6, 0.1, 0.1, np.nan, 0.3],
            "snow_ice_frac": [0.0, 0.1, 0.5, 0.0, 0.3],
            "ndvi_mean": [0.9, 0.5, 0.9, 0.1, np.nan],
        }
    )
    # keep if barren+ice >= 0.5 OR ndvi <= 0.2: rows 0 and 2 (cover) and 3 (ndvi) are kept; row 4
    # has NaN ndvi but cover 0.6, so the cover branch keeps it; row 1 is masked
    assert mask_flag(df, PROF.params).tolist() == [False, True, False, False, False]
    nan_both = pd.DataFrame(
        {"barren_frac": [np.nan], "snow_ice_frac": [np.nan], "ndvi_mean": [np.nan]}
    )
    assert mask_flag(nan_both, PROF.params).tolist() == [True]


def test_earth_flags_set_each_bit() -> None:
    e = pd.DataFrame(
        {
            "barren_frac": [0.0, 1.0], "snow_ice_frac": [0.0, 0.0], "ndvi_mean": [0.9, 0.0],
            "tag_volcanic": [False, True],
            "tag_periglacial": [False, True],
            "tag_evaporitic": [False, True],
        }
    )  # fmt: skip
    f = earth_flags(e, PROF.params, np.array([False, True]))
    assert f.tolist() == [B.MASKED, B.VOLCANIC | B.PERIGLACIAL | B.EVAPORITIC | B.KNOWN_SITE]


def _interim(tmp_path: Path) -> tuple[Path, dict[str, pd.DataFrame], np.ndarray]:
    """C2 interim tables for a 300-hex synthetic Earth plus the extras the exporter reads."""
    t = syn.make_synthetic(SEED, 300)
    d = tmp_path / "interim"
    (d / "layers").mkdir(parents=True)
    earth = t["earth_features"]
    earth.drop(columns=["masked"]).to_parquet(d / "earth_features.parquet")
    for k in ("moon_discs", "mars_discs", "targets"):
        t[k].to_parquet(d / f"{k}.parquet")
    names = list(EXPECTED_FEATURES)
    sc = fit_scaler(
        earth.loc[~earth["masked"], names].to_numpy(float),
        t["moon_discs"][names].to_numpy(float),
        t["mars_discs"][names].to_numpy(float),
        [f.transform for f in PROF.features],
        names,
    )
    sc.to_json(d / "scaler.json")
    fl = syn.flags(earth, t["known_sites"])
    pd.DataFrame({"h3": earth["h3"], "geo_novelty_km": 1.0, "feat_novelty": 0.5,
                  "known_site_flag": (fl & 16) > 0}).to_parquet(d / "novelty.parquet")  # fmt: skip
    pd.DataFrame(
        {
            "row_key": "earth:" + earth["h3"],
            "hdb_label": np.int16(3),
            "gmm_label": np.int16(1),
            "gmm_maxprob": np.float32(0.9),
        }
    ).to_parquet(d / "clusters.parquet")
    for n in B.LAYER_NAMES:
        (d / "layers" / f"{n}.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    tex = tmp_path / "tex"
    tex.mkdir()
    for body in B.BODIES:
        (tex / f"{body}.jpg").write_bytes(syn._jpeg_bytes(syn._texture(body)))
    return d, t, fl


def test_build_bundle_from_interim_tables_round_trips(tmp_path: Path) -> None:
    d, t, fl = _interim(tmp_path)
    out = tmp_path / "out"
    build_bundle(d, out, PROF, textures_dir=tmp_path / "tex")  # validates internally
    n = len(t["earth_features"])
    man = json.loads((out / "manifest.json").read_text())
    assert man["n_hex"] == n and man["synthetic"] is False
    feats = np.fromfile(out / "earth_features.f32", "<f4").reshape(n, len(EXPECTED_FEATURES))
    ref = t["earth_features"][list(EXPECTED_FEATURES)].to_numpy(np.float32)
    np.testing.assert_array_equal(np.nan_to_num(feats, nan=-1), np.nan_to_num(ref, nan=-1))
    assert (
        np.fromfile(out / "earth_flags.u8", "u1") == fl
    ).all()  # mask rule == the generator's mask
    assert (np.fromfile(out / "earth_cluster.i16", "<i2") == 3).all()
    assert json.loads((out / "targets.json").read_text())[0]["cluster"] == -1  # unassigned


def test_build_bundle_lists_every_missing_input(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as e:
        build_bundle(tmp_path, tmp_path / "o", PROF, textures_dir=tmp_path / "none")
    msg = str(e.value)
    assert "scaler.json" in msg and "novelty.parquet" in msg and "layers/land.geojson" in msg
    assert "earth.jpg" in msg
