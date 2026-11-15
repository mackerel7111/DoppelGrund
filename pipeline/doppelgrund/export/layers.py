"""GeoJSON map layers (spec 02 task 2.6, contract C6 ``layers/*.geojson``).

Six FeatureCollections for the web map toggles. Every point carries ``name``, ``source`` and
``kind``; the hand-listed layers also carry ``verified`` (false until a human checks the
coordinates). Nothing is invented here: an input with no rows gives an empty FeatureCollection,
never a fake point.

    python -m doppelgrund.export.layers --out data/interim/real/layers
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from doppelgrund.config import REPO, load_known_sites
from doppelgrund.export.bundle import LAYER_NAMES, json_bytes

LAND_MAX_BYTES = 1_500_000  # spec 02 design section 6: land.geojson <= 1.5 MB
LAND = REPO / "config/ne_land.geojson"
LUNAR_PITS = REPO / "data/raw/moon_pits/LUNAR_PIT_LOCATIONS.CSV"
VOLCANOES = REPO / "data/raw/earth_volcanoes/Smithsonian_VOTW_Holocene_Volcanoes.geojson"
LAVA_TUBES = REPO / "config/earth_lava_tubes.csv"
SARAWAK_CAVES = REPO / "config/sarawak_caves.csv"

SRC_LAND = "Natural Earth 1:110m land"
SRC_PITS = "LROC lunar pit catalogue (Wagner and Robinson 2021)"
SRC_VOLCANOES = "Smithsonian Global Volcanism Program, Volcanoes of the World (Holocene)"


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def point(lon: float, lat: float, **props: Any) -> dict[str, Any]:
    """One GeoJSON point (coordinates are [lon, lat]); NaN properties are dropped."""
    clean = {k: (v.item() if hasattr(v, "item") else v) for k, v in props.items()}
    clean = {k: v for k, v in clean.items() if not (isinstance(v, float) and v != v)}
    geom = {"type": "Point", "coordinates": [round(float(lon), 5), round(float(lat), 5)]}
    return {"type": "Feature", "properties": clean, "geometry": geom}


def land_layer(path: Path = LAND) -> dict[str, Any]:
    """Natural Earth land polygons; every feature gets name, source and kind."""
    gj = json.loads(Path(path).read_text(encoding="utf-8"))
    feats = [
        {
            "type": "Feature",
            "properties": {"name": "Land", "source": SRC_LAND, "kind": "land"},
            "geometry": f["geometry"],
        }
        for f in gj["features"]
    ]
    out = feature_collection(feats)
    size = len(json_bytes(out))
    if size > LAND_MAX_BYTES:
        raise ValueError(f"land layer is {size} bytes, over the {LAND_MAX_BYTES} byte budget")
    return out


def known_sites_layer(sites: pd.DataFrame | None = None) -> dict[str, Any]:
    """Documented analogue sites from config/known_sites.csv (human-owned; may be empty)."""
    df = load_known_sites() if sites is None else sites
    return feature_collection(
        [
            point(
                r.lon,
                r.lat,
                name=r.name,
                source=r.reference_url,
                kind="known_site",
                site_id=r.site_id,
                dimension=r.dimension,
                well_known=bool(r.well_known),
            )
            for r in df.itertuples()
        ]
    )


def lunar_pits_layer(path: Path = LUNAR_PITS) -> dict[str, Any]:
    """All catalogued LROC pits, including the ones typed 'Uncertain' (the type is a property)."""
    d = pd.read_csv(
        path,
        encoding="cp1252",
        usecols=["Name", "Terrain", "Type", "Latitude", "Longitude_180"],
    )
    return feature_collection(
        [
            point(
                r.Longitude_180,
                r.Latitude,
                name=r.Name,
                source=SRC_PITS,
                kind="lunar_pit",
                body="moon",
                terrain=r.Terrain,
                type=r.Type,
            )
            for r in d.itertuples()
        ]
    )


def _hand_list(path: Path, kind: str, source: str, only_type: str | None = None) -> dict[str, Any]:
    d = pd.read_csv(path)
    if only_type is not None:
        d = d[d["type"] == only_type]
    return feature_collection(
        [
            point(
                r.lon,
                r.lat,
                name=r.name,
                source=f"{source}; coordinates: {r.coord_source}",
                kind=kind,
                country=r.country,
                verified=bool(r.verified),
            )
            for r in d.itertuples()
        ]
    )


def lava_tubes_layer(path: Path = LAVA_TUBES) -> dict[str, Any]:
    """Hand-listed lava tubes (the structural analogues); rows typed lava_tube only."""
    return _hand_list(path, "lava_tube", "config/earth_lava_tubes.csv", "lava_tube")


def sarawak_caves_layer(path: Path = SARAWAK_CAVES) -> dict[str, Any]:
    """Sarawak karst caves, shown for the story only: never presented as lava-tube analogues."""
    return _hand_list(path, "karst_cave", "config/sarawak_caves.csv", "karst_cave")


def volcanoes_layer(path: Path = VOLCANOES) -> dict[str, Any]:
    """Holocene volcanoes (Smithsonian GVP); features without a point geometry are skipped."""
    gj = json.loads(Path(path).read_text(encoding="utf-8"))
    feats = []
    for f in gj["features"]:
        g, p = f.get("geometry") or {}, f.get("properties") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        feats.append(
            point(
                lon,
                lat,
                name=p.get("Volcano_Name"),
                source=SRC_VOLCANOES,
                kind="volcano",
                country=p.get("Country"),
                type=p.get("Primary_Volcano_Type"),
                last_eruption_year=p.get("Last_Eruption_Year"),
            )
        )
    return feature_collection(feats)


def build_layers(out_dir: Path) -> list[Path]:
    """Write the six C6 layers into ``out_dir``; raises FileNotFoundError listing missing inputs."""
    inputs = {
        "land": LAND,
        "known_sites": REPO / "config/known_sites.csv",
        "lunar_pits": LUNAR_PITS,
        "lava_tubes": LAVA_TUBES,
        "sarawak_caves": SARAWAK_CAVES,
        "volcanoes": VOLCANOES,
    }
    missing = [str(p) for p in inputs.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError("layer inputs missing: " + ", ".join(missing))
    makers = {
        "land": land_layer,
        "known_sites": known_sites_layer,
        "lunar_pits": lunar_pits_layer,
        "lava_tubes": lava_tubes_layer,
        "sarawak_caves": sarawak_caves_layer,
        "volcanoes": volcanoes_layer,
    }
    assert set(makers) == set(LAYER_NAMES)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in LAYER_NAMES:
        path = out_dir / f"{name}.geojson"
        path.write_bytes(json_bytes(makers[name]()))
        written.append(path)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--out", type=Path, default=REPO / "data/interim/real/layers")
    a = p.parse_args(argv)
    for path in build_layers(a.out):
        n = len(json.loads(path.read_text(encoding="utf-8"))["features"])
        print(f"{path.name}: {n} features, {path.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
