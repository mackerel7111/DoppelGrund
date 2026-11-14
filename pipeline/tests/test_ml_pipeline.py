"""The stage-2 driver end to end on a small synthetic interim folder, then the bundle exporter."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from doppelgrund.config import KNOWN_SITE_COLUMNS
from doppelgrund.export.bundle import build_bundle
from doppelgrund.fixtures import synthetic as syn
from doppelgrund.ml import pipeline as P
from doppelgrund.ml.pipeline import run


def make_interim(tmp_path: Path) -> Path:
    t = syn.make_synthetic(20261114, 400)
    d = tmp_path / "interim"
    d.mkdir()
    for k in ("earth_features", "moon_discs", "mars_discs", "targets"):
        t[k].to_parquet(d / f"{k}.parquet")
    return d


def no_sites() -> pd.DataFrame:
    return pd.DataFrame(columns=list(KNOWN_SITE_COLUMNS))


def test_driver_writes_every_c2_file_the_bundle_needs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(P, "load_known_sites", no_sites)  # independent of config/known_sites.csv
    d = make_interim(tmp_path)
    out = run(d, draws=3, with_layers=False, log=lambda m: None)
    earth = pd.read_parquet(d / "earth_features.parquet")
    assert json.loads((d / "scaler.json").read_text())["fitted_on"]["moon"] == 3000
    assert (d / "ml" / "domain_gap.json").is_file()
    nov = pd.read_parquet(d / "novelty.parquet")
    assert len(nov) == len(earth) and nov["geo_novelty_km"].isna().all()  # no documented sites: NaN
    assert not nov["known_site_flag"].any()
    cl = pd.read_parquet(d / "clusters.parquet")
    assert cl["row_key"].str.startswith(("earth:", "moon:", "mars:")).all() and len(cl) > 100
    n_targets = len(pd.read_parquet(d / "targets.parquet"))
    assert len(list((d / "stability").glob("*.parquet"))) == n_targets * 4
    st = pd.read_parquet(next((d / "stability").glob("*.parquet")))
    assert st["stability"].between(0, 1).all() and (st["h3"] == earth["h3"]).all()
    assert set(json.loads((d / "target_regimes.json").read_text())) == set(out["regimes"])


def test_the_exporter_accepts_the_driver_output_and_carries_the_regimes(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(P, "load_known_sites", no_sites)
    d = make_interim(tmp_path)
    run(d, draws=3, with_layers=False, log=lambda m: None)
    (d / "layers").mkdir()
    for n in ("land", "known_sites", "lunar_pits", "lava_tubes", "sarawak_caves", "volcanoes"):
        (d / "layers" / f"{n}.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    tex = tmp_path / "tex"
    tex.mkdir()
    for body in ("earth", "moon", "mars"):
        (tex / f"{body}.jpg").write_bytes(syn._jpeg_bytes(syn._texture(body)))
    build_bundle(d, tmp_path / "out", textures_dir=tex)  # validates
    targets = json.loads((tmp_path / "out" / "targets.json").read_text())
    regimes = json.loads((d / "target_regimes.json").read_text())
    assert {t["id"]: t["cluster"] for t in targets} == regimes
    nov = np.fromfile(tmp_path / "out" / "earth_novelty.f32", "<f4")
    assert np.isnan(nov).all()


def test_documented_sites_give_real_novelty_and_flag_their_hexes(
    tmp_path: Path, monkeypatch
) -> None:
    d = make_interim(tmp_path)
    earth = pd.read_parquet(d / "earth_features.parquet")
    r0 = earth.iloc[0]
    site = pd.DataFrame(
        [["s", "Site", r0["lat"], r0["lng"], "moon", "", "terrain", "https://x", True]],
        columns=list(KNOWN_SITE_COLUMNS),
    )
    monkeypatch.setattr(P, "load_known_sites", lambda: site)
    run(d, draws=2, with_layers=False, log=lambda m: None)
    nov = pd.read_parquet(d / "novelty.parquet")
    assert nov["geo_novelty_km"].notna().all() and nov["geo_novelty_km"].iloc[0] < 50
    assert nov["feat_novelty"].iloc[0] == 0.0 and nov["known_site_flag"].iloc[0]
    assert nov["known_site_flag"].sum() <= 7  # the site hex and its six neighbours at most
