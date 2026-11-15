"""GeoJSON layers (spec 02 task 2.6): hand-built inputs plus the committed config lists."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from doppelgrund.config import KNOWN_SITE_COLUMNS
from doppelgrund.export import layers as L
from doppelgrund.export.bundle import LAYER_NAMES
from doppelgrund.export.layers import (
    build_layers,
    known_sites_layer,
    land_layer,
    lava_tubes_layer,
    lunar_pits_layer,
    point,
    sarawak_caves_layer,
    volcanoes_layer,
)


def test_point_is_lon_lat_and_drops_nan_properties() -> None:
    f = point(10.123456789, -20.5, name="a", kind="x", depth=float("nan"))
    assert f["geometry"] == {"type": "Point", "coordinates": [10.12346, -20.5]}
    assert f["properties"] == {"name": "a", "kind": "x"}


def test_known_sites_layer_is_empty_not_invented_when_there_are_no_sites() -> None:
    cols = list(KNOWN_SITE_COLUMNS)
    gj = known_sites_layer(pd.DataFrame(columns=cols))
    assert gj == {"type": "FeatureCollection", "features": []}
    values = ["s1", "Site", 1.0, 2.0, "moon", "t", "thermal", "https://x", True]
    row = pd.DataFrame([values], columns=cols)
    f = known_sites_layer(row)["features"][0]
    assert f["geometry"]["coordinates"] == [2.0, 1.0] and f["properties"]["well_known"] is True
    assert f["properties"]["kind"] == "known_site" and f["properties"]["source"] == "https://x"


def test_lunar_pits_keep_uncertain_ones_with_their_type(tmp_path: Path) -> None:
    csv = tmp_path / "pits.csv"
    csv.write_bytes(
        "Name,Terrain,Type,Latitude,Longitude_180,Extra\nA 1,Mare,,14.0917,-56.7701,x\n"
        "B 2,Highland,Uncertain,-3.5,100.25,y\n".encode("cp1252")
    )
    feats = lunar_pits_layer(csv)["features"]
    assert [f["properties"]["name"] for f in feats] == ["A 1", "B 2"]
    assert feats[0]["geometry"]["coordinates"] == [-56.7701, 14.0917]  # lon, lat
    assert "type" not in feats[0]["properties"]  # blank type (NaN) is dropped
    assert (
        feats[1]["properties"]["type"] == "Uncertain" and feats[1]["properties"]["body"] == "moon"
    )


def test_hand_lists_filter_by_type_and_carry_verified(tmp_path: Path) -> None:
    csv = tmp_path / "c.csv"
    csv.write_text(
        "name,type,country,lat,lon,coord_source,verified\n"
        "Tube,lava_tube,Iceland,64.0,-20.0,Wikipedia,false\n"
        "Karst,karst_cave,Malaysia,4.0,114.0,Wikipedia,false\n",
        encoding="utf-8",
    )
    tubes = lava_tubes_layer(csv)["features"]
    assert [f["properties"]["name"] for f in tubes] == [
        "Tube"
    ]  # karst never in the lava-tube layer
    assert (
        tubes[0]["properties"]["verified"] is False
        and tubes[0]["properties"]["kind"] == "lava_tube"
    )
    karst = sarawak_caves_layer(csv)["features"]
    assert [f["properties"]["name"] for f in karst] == ["Karst"]
    assert karst[0]["properties"]["kind"] == "karst_cave"


def test_volcanoes_skip_non_point_geometry_and_keep_lon_lat(tmp_path: Path) -> None:
    gj = {
        "type": "FeatureCollection",
        "features": [
            {"geometry": {"type": "Point", "coordinates": [6.85, 50.17]},
             "properties": {"Volcano_Name": "West Eifel", "Country": "Germany",
                            "Primary_Volcano_Type": "Volcanic field", "Last_Eruption_Year": -8300}},
            {"geometry": None, "properties": {"Volcano_Name": "No place"}},
            {"geometry": {"type": "Polygon", "coordinates": []}, "properties": {}},
        ],
    }  # fmt: skip
    p = tmp_path / "v.geojson"
    p.write_text(json.dumps(gj), encoding="utf-8")
    feats = volcanoes_layer(p)["features"]
    assert len(feats) == 1 and feats[0]["geometry"]["coordinates"] == [6.85, 50.17]
    assert (
        feats[0]["properties"]["name"] == "West Eifel"
        and feats[0]["properties"]["kind"] == "volcano"
    )


def test_land_layer_adds_name_source_kind_and_enforces_the_size_budget(
    tmp_path: Path, monkeypatch
) -> None:
    gj = land_layer()
    assert gj["features"] and all(
        {"name", "source", "kind"} <= set(f["properties"]) for f in gj["features"]
    )
    monkeypatch.setattr(L, "LAND_MAX_BYTES", 100)
    with pytest.raises(ValueError, match="budget"):
        land_layer()


def test_committed_config_lists_build_valid_layers(tmp_path: Path) -> None:
    assert len(lava_tubes_layer()["features"]) == 6  # config/earth_lava_tubes.csv
    sar = sarawak_caves_layer()["features"]
    assert len(sar) == 2 and not any(f["properties"]["verified"] for f in sar)


def test_build_layers_names_match_the_bundle_contract_and_missing_inputs_are_listed(
    tmp_path: Path, monkeypatch
) -> None:
    raw = [L.LUNAR_PITS, L.VOLCANOES]
    if not all(p.is_file() for p in raw):  # raw downloads are git-ignored; CI has none
        monkeypatch.setattr(L, "LUNAR_PITS", tmp_path / "nope.csv")
        with pytest.raises(FileNotFoundError, match="nope.csv"):
            build_layers(tmp_path / "out")
        pytest.skip("raw LROC / GVP downloads not present")
    written = build_layers(tmp_path / "out")
    assert [p.stem for p in written] == list(LAYER_NAMES)
    for p in written:
        assert json.loads(p.read_text(encoding="utf-8"))["type"] == "FeatureCollection"
