"""Web bundle exporter and validator (spec 02 task 2.5, contract C6).

Two entry points share one writer:

* ``write_bundle`` takes finished in-memory arrays (the synthetic generator uses it).
* ``build_bundle`` reads the C2 interim tables and calls it::

    python -m doppelgrund.export.bundle --interim data/interim/real --out web/public/data

Every output is re-read and checked against C6 by ``validate_bundle`` (lengths, dtypes, feature
order, size budget) before the exporter returns; a failure raises with every problem listed.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import shutil
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image

from doppelgrund.config import EXPECTED_FEATURES, EXPECTED_LITH, REPO, Profiles, load_profiles
from doppelgrund.export.index_map import INDEX_H, INDEX_W, rasterise_index
from doppelgrund.harmonise import Scaler

logger = logging.getLogger(__name__)

CONTRACT = "doppelgrund-bundle/1"
BUNDLE_BUDGET_MB, TEXTURE_BUDGET_MB = 40.0, 15.0  # C6: bundle excluding textures, textures total
LITH_COLS = [f"lith_{c}" for c in EXPECTED_LITH]
LAYER_NAMES = ("land", "known_sites", "lunar_pits", "lava_tubes", "sarawak_caves", "volcanoes")
BODIES = ("earth", "moon", "mars")
F, N_LITH = len(EXPECTED_FEATURES), len(EXPECTED_LITH)

# earth_flags.u8 bits (C6)
MASKED, VOLCANIC, PERIGLACIAL, EVAPORITIC, KNOWN_SITE = 1, 2, 4, 8, 16

# TODO(verify): dataset strings for the manifest `sources`; versions are filled by hand once the
# datasets are confirmed (config/datasets.yaml entries are still verified: false).
REAL_SOURCES: dict[str, dict[str, str]] = {
    "terrain": {
        "earth": "COPERNICUS/DEM/GLO30_2024_1 + NASA/NASADEM_HGT/001 (mean where both exist)",
        "moon": "LRO LOLA LDEM_64",
        "mars": "MGS MOLA 463 m DEM",
    },
    "thermal": {
        "earth": "MODIS/061/MOD11A2 + MODIS/061/MOD21A1D/N (Terra; MOD21 only where dense)",
        "moon": "LRO Diviner global cumulative averages",
    },
    "cold_ice": {
        "earth": "Obu et al. 2018 permafrost + TerraClimate aridity + MODIS Terra LST",
        "moon": "LRO Diviner global cumulative averages; aridity 0 by definition",
        "mars": "aridity 0 by definition",
    },
    "subsurface": {
        "earth": "config/earth_lava_tubes.csv (hand-listed lava tubes)",
        "moon": "LROC lunar pit catalogue (Wagner and Robinson 2021)",
    },
}
# Fast mode (real.py --fast) reads Earth Engine's coarser overview levels and skips MOD21, so the
# sources text must say so rather than name the full-resolution inputs.
FAST_EARTH_SOURCES: dict[str, str] = {
    "terrain": "COPERNICUS/DEM/GLO30_2024_1 + NASA/NASADEM_HGT/001, read from Earth Engine "
    "overview levels at 470 m (fast mode, coarser than the 30 m source)",
    "thermal": "MODIS/061/MOD11A2 only (Terra); MOD21A1D/N not used in fast mode",
    "cold_ice": "Obu et al. 2018 permafrost + TerraClimate aridity + MODIS Terra LST "
    "(MOD11A2 only, fast mode)",
}
LITH_SOURCES = {
    "earth": "GLiM (Hartmann and Moosdorf 2012)",
    "moon": "LP GRS FeO",
    "mars": "USGS SIM 3292 geologic map",
}


# ---- low-level writers --------------------------------------------------------------------------
def f32_bytes(a: np.ndarray) -> bytes:
    return np.ascontiguousarray(np.asarray(a, np.float32)).astype("<f4").tobytes()


def json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, indent=1, allow_nan=False, ensure_ascii=False) + "\n").encode("utf-8")


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def null_list(values: Any) -> list[float | None]:
    """NaN -> None so the JSON stays valid (C6)."""
    return [None if not np.isfinite(v) else float(v) for v in np.asarray(values, np.float64)]


def write_file(path: Path, data: bytes, overwrite: bool, written: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite or not path.exists():
        path.write_bytes(data)
    written.append(path)


def scaler_rows(prof: Profiles, scaler: Scaler) -> list[dict[str, Any]]:
    return [
        {"name": f.name, "median": float(m), "s": float(s)}
        for f, m, s in zip(prof.features, scaler.median, scaler.s, strict=True)
    ]


# ---- derived columns ----------------------------------------------------------------------------
def mask_flag(earth: pd.DataFrame, params: Mapping[str, Any]) -> np.ndarray:
    """bool (N,): the barren-ground mask. Keep a hex if barren + snow/ice >= min OR ndvi <= max.

    NaN cover or NDVI makes the comparisons False, so such a hex is masked (never kept by default).
    """
    m = params["mask"]
    cover = (earth["barren_frac"] + earth["snow_ice_frac"]).to_numpy(float)
    ndvi = earth["ndvi_mean"].to_numpy(float)
    with np.errstate(invalid="ignore"):
        keep = (cover >= m["barren_plus_ice_min"]) | (ndvi <= m["ndvi_max"])
    return ~keep


def earth_flags(
    earth: pd.DataFrame, params: Mapping[str, Any], known_site: np.ndarray
) -> np.ndarray:
    """uint8 (N,) with the C6 bits; bit 0 comes from the mask rule."""
    f = mask_flag(earth, params).astype(np.uint8) * MASKED
    f |= earth["tag_volcanic"].to_numpy(bool).astype(np.uint8) * VOLCANIC
    f |= earth["tag_periglacial"].to_numpy(bool).astype(np.uint8) * PERIGLACIAL
    f |= earth["tag_evaporitic"].to_numpy(bool).astype(np.uint8) * EVAPORITIC
    f |= np.asarray(known_site, bool).astype(np.uint8) * KNOWN_SITE
    return f


def targets_json(
    targets: pd.DataFrame, clusters: Mapping[str, int] | None = None, notes: str = ""
) -> list[dict[str, Any]]:
    """C6 targets.json rows from the C2 targets table; NaN features become null and are listed."""
    out = []
    for _, t in targets.iterrows():
        feats = t[list(EXPECTED_FEATURES)].to_numpy(np.float64)
        missing = [n for n, v in zip(EXPECTED_FEATURES, feats, strict=True) if not np.isfinite(v)]
        out.append(
            {
                "id": t["target_id"],
                "name": t["name"],
                "body": t["body"],
                "lat": round(float(t["lat"]), 6),
                "lon": round(float(t["lon"]), 6),
                "features": null_list(feats),
                "lith": null_list(t[LITH_COLS].to_numpy(np.float64)),
                "cluster": int((clusters or {}).get(t["target_id"], -1)),  # -1 = not assigned
                "notes": notes,
                "coverage_notes": [f"{n}: not measured" for n in missing],
            }
        )
    return out


def sources_for(prof: Profiles, fast: bool = False) -> list[dict[str, str]]:
    out = []
    for f in prof.features:
        for body, dataset in REAL_SOURCES.get(f.group, {}).items():
            if fast and body == "earth" and f.group in FAST_EARTH_SOURCES:
                dataset = FAST_EARTH_SOURCES[f.group]
            out.append({"feature": f.name, "body": body, "dataset": dataset, "version": ""})
    out += [
        {"feature": "lith", "body": b, "dataset": d, "version": ""} for b, d in LITH_SOURCES.items()
    ]
    return out


# ---- the writer ---------------------------------------------------------------------------------
def write_bundle(
    out_dir: Path,
    *,
    prof: Profiles,
    scaler: list[dict[str, Any]],
    cells: Sequence[str],
    earth_features: np.ndarray,
    earth_lith: np.ndarray,
    earth_latlng: np.ndarray,
    novelty: np.ndarray,
    cluster: np.ndarray,
    flags: np.ndarray,
    discs: Mapping[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    targets: list[dict[str, Any]],
    stability: Sequence[dict[str, Any]],
    layers: Mapping[str, Any],
    textures: Mapping[str, bytes],
    sources: list[dict[str, str]],
    synthetic: bool,
    created_utc: str,
    overwrite: bool = True,
    validate: bool = True,
    resolution: Mapping[str, Any] | None = None,
) -> list[Path]:
    """Write every C6 file under ``out_dir`` and (by default) validate the result."""
    out_dir = Path(out_dir)
    w: list[Path] = []

    def put(rel: str, data: bytes) -> None:
        write_file(out_dir / rel, data, overwrite, w)

    put("earth_h3.txt", ("\n".join(cells) + "\n").encode())
    put("earth_features.f32", f32_bytes(earth_features))
    put("earth_lith.f32", f32_bytes(earth_lith))
    put("earth_latlng.f32", f32_bytes(earth_latlng))
    put("earth_novelty.f32", f32_bytes(novelty))
    put("earth_cluster.i16", np.asarray(cluster).astype("<i2").tobytes())
    put("earth_flags.u8", np.asarray(flags, np.uint8).tobytes())
    for body in ("moon", "mars"):
        feats, lith, latlon = discs[body]
        put(f"{body}_features.f32", f32_bytes(feats))
        put(f"{body}_lith.f32", f32_bytes(lith))
        put(f"{body}_latlon.f32", f32_bytes(latlon))
    put("targets.json", json_bytes(targets))
    for st in stability:
        put(f"stability/{st['target']}__{st['lens']}.json", json_bytes(st))
    put("earth_index_4096x2048.png", png_bytes(rasterise_index(cells, INDEX_W, INDEX_H)))
    for name, gj in layers.items():
        put(f"layers/{name}.geojson", json_bytes(gj))
    for body, data in textures.items():
        put(f"textures/{body}.jpg", data)

    files = {
        "h3": "earth_h3.txt",
        "features": "earth_features.f32",
        "lith": "earth_lith.f32",
        "latlng": "earth_latlng.f32",
        "novelty": "earth_novelty.f32",
        "cluster": "earth_cluster.i16",
        "flags": "earth_flags.u8",
        "targets": "targets.json",
        "index_map": "earth_index_4096x2048.png",
    }
    for body in ("moon", "mars"):
        files[f"{body}_features"] = f"{body}_features.f32"
        files[f"{body}_lith"] = f"{body}_lith.f32"
        files[f"{body}_latlon"] = f"{body}_latlon.f32"
    manifest = {
        "contract": CONTRACT,
        "created_utc": created_utc,
        "synthetic": synthetic,
        "h3_res": 4,
        "n_hex": len(cells),
        "features": [
            {
                "name": f.name,
                "group": f.group,
                "unit": f.unit,
                "transform": f.transform,
                "median": sc["median"],
                "s": sc["s"],
            }
            for f, sc in zip(prof.features, scaler, strict=True)
        ],  # fmt: skip
        "lith_classes": list(prof.lith_classes),
        "compat_matrix": prof.compat_matrix.tolist(),
        "lenses": prof.lenses,
        "params": prof.params,
        "files": files,
        "sources": sources,
    }
    if (
        resolution
    ):  # optional: how the Earth Engine step was run ({"mode": "fast"|"full", "stride": n})
        manifest["resolution"] = dict(resolution)
    put("manifest.json", json_bytes(manifest))
    if validate:
        validate_bundle(out_dir)
    logger.info("wrote %d bundle files to %s", len(w), out_dir)
    return w


# ---- the validator ------------------------------------------------------------------------------
def validate_bundle(out: Path) -> None:
    """Re-read a bundle and check it against C6; raises ValueError listing every problem."""
    out = Path(out)
    bad: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            bad.append(msg)

    try:
        man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"manifest.json: {e}") from e
    need(man.get("contract") == CONTRACT, f"manifest.contract is {man.get('contract')!r}")
    n = int(man.get("n_hex", -1))
    names = [f.get("name") for f in man.get("features", [])]
    need(names == list(EXPECTED_FEATURES), f"manifest feature order {names}")
    need(man.get("lith_classes") == list(EXPECTED_LITH), "manifest lith_classes differ from C1")
    need(all(f.get("s", 0) > 0 for f in man.get("features", [])), "a scaler s is not positive")
    need(len(man.get("compat_matrix", [])) == N_LITH, "compat_matrix is not 6x6")

    def size(rel: str) -> int:
        p = out / rel
        need(p.is_file(), f"missing {rel}")
        return p.stat().st_size if p.is_file() else -1

    h3_file = out / "earth_h3.txt"
    n_lines = len(h3_file.read_text().split()) if h3_file.is_file() else -1
    need(n_lines == n, f"earth_h3.txt holds {n_lines} lines, n_hex = {n}")
    for rel, per_row in (("earth_features.f32", F * 4), ("earth_lith.f32", N_LITH * 4),
                         ("earth_latlng.f32", 8), ("earth_novelty.f32", 8),
                         ("earth_cluster.i16", 2), ("earth_flags.u8", 1)):  # fmt: skip
        need(size(rel) == n * per_row, f"{rel}: {size(rel)} bytes, expected {n * per_row}")
    for body in ("moon", "mars"):
        m = size(f"{body}_latlon.f32") // 8
        need(
            size(f"{body}_latlon.f32") == m * 8 and m > 0, f"{body}_latlon.f32 is not M x 2 float32"
        )
        need(size(f"{body}_features.f32") == m * F * 4, f"{body}_features.f32 is not {m} x {F}")
        need(size(f"{body}_lith.f32") == m * N_LITH * 4, f"{body}_lith.f32 is not {m} x {N_LITH}")

    try:
        for t in json.loads((out / "targets.json").read_text(encoding="utf-8")):
            need(
                len(t["features"]) == F and len(t["lith"]) == N_LITH, f"target {t.get('id')} shape"
            )
    except (OSError, ValueError, KeyError) as e:
        bad.append(f"targets.json: {e}")
    for p in sorted((out / "stability").glob("*.json")) if (out / "stability").is_dir() else []:
        st = json.loads(p.read_text(encoding="utf-8"))
        need(
            all(0 <= r < n and 0.0 <= v <= 1.0 for r, v in st["rows"]),
            f"{p.name}: row or fraction out of range",
        )
    try:
        with Image.open(out / "earth_index_4096x2048.png") as im:
            need(
                im.size == (INDEX_W, INDEX_H) and im.mode == "RGB",
                f"index image is {im.size} {im.mode}",
            )
    except OSError as e:
        bad.append(f"earth_index_4096x2048.png: {e}")
    for name in LAYER_NAMES:
        p = out / "layers" / f"{name}.geojson"
        need(p.is_file(), f"missing layers/{name}.geojson")
        if p.is_file():
            need(
                json.loads(p.read_text(encoding="utf-8")).get("type") == "FeatureCollection",
                f"{name}: not a FeatureCollection",
            )
    for body in BODIES:
        need((out / "textures" / f"{body}.jpg").is_file(), f"missing textures/{body}.jpg")

    tex = (
        sum(p.stat().st_size for p in (out / "textures").glob("*") if p.is_file()) / 1e6
        if (out / "textures").is_dir()
        else 0.0
    )
    allf = [
        p for p in out.rglob("*") if p.is_file() and "sample" not in p.relative_to(out).parts[:1]
    ]
    body_mb = (
        sum(p.stat().st_size for p in allf if "textures" not in p.relative_to(out).parts) / 1e6
    )
    if body_mb > BUNDLE_BUDGET_MB or tex > TEXTURE_BUDGET_MB:
        top = sorted(allf, key=lambda p: -p.stat().st_size)[:5]
        bad.append(
            f"size budget exceeded: bundle {body_mb:.1f} MB (limit {BUNDLE_BUDGET_MB}), "
            f"textures {tex:.1f} MB (limit {TEXTURE_BUDGET_MB}); largest: "
            + ", ".join(f"{p.name} {p.stat().st_size / 1e6:.1f} MB" for p in top)
        )
    if bad:
        raise ValueError("bundle fails C6:\n  " + "\n  ".join(bad))


# ---- the interim-table reader -------------------------------------------------------------------
def build_bundle(
    interim: Path,
    out: Path,
    prof: Profiles | None = None,
    synthetic: bool = False,
    top_k: int | None = None,
    textures_dir: Path = REPO / "config/textures",
    resolution: Mapping[str, Any] | None = None,
) -> list[Path]:
    """Build the bundle from the C2 interim tables.

    ``resolution`` ({"mode": "fast"|"full", "stride": n}) goes into the manifest and selects the
    sources text; when None it is read from ``interim/tables_info.json`` if that file exists.

    Needs earth_features, moon_discs, mars_discs, targets, scaler.json, clusters, novelty (all
    parquet except the scaler) and layers/*.geojson under ``interim``; stability/*.parquet are
    optional only for a ``synthetic`` run. Missing files raise FileNotFoundError listing them.
    """
    prof = prof or load_profiles()
    info = Path(interim) / "tables_info.json"
    if resolution is None and info.is_file():
        d = json.loads(info.read_text(encoding="utf-8"))
        resolution = {
            "mode": "fast" if d.get("fast") else "full",
            "stride": int(d.get("stride", 1)),
        }
    interim = Path(interim)
    need = ["earth_features.parquet", "moon_discs.parquet", "mars_discs.parquet", "targets.parquet",
            "scaler.json", "clusters.parquet", "novelty.parquet",
            *(f"layers/{n}.geojson" for n in LAYER_NAMES)]  # fmt: skip
    missing = [f for f in need if not (interim / f).is_file()]
    textures = {b: Path(textures_dir) / f"{b}.jpg" for b in BODIES}
    missing += [str(p) for p in textures.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError("bundle inputs missing: " + ", ".join(missing))

    earth = pd.read_parquet(interim / "earth_features.parquet")
    cells = earth["h3"].tolist()
    nov = pd.read_parquet(interim / "novelty.parquet").set_index("h3").reindex(cells)
    clu = pd.read_parquet(interim / "clusters.parquet").set_index("row_key")
    keys = [f"earth:{c}" for c in cells]
    sc = Scaler.from_json(interim / "scaler.json")
    discs = {}
    for b in ("moon", "mars"):
        d = pd.read_parquet(interim / f"{b}_discs.parquet")
        discs[b] = (
            d[list(EXPECTED_FEATURES)].to_numpy(np.float32),
            d[LITH_COLS].to_numpy(np.float32),
            d[["lat", "lon"]].to_numpy(np.float32),
        )
    k = top_k or int(prof.params["stability"]["store_top_k"])
    row_of = {c: i for i, c in enumerate(cells)}
    stability = []
    for p in sorted((interim / "stability").glob("*__*.parquet")):
        tgt, lens = p.stem.split("__", 1)
        df = pd.read_parquet(p).sort_values("stability", ascending=False, kind="stable").head(k)
        rows = [
            [row_of[h], round(float(v), 4)]
            for h, v in zip(df["h3"], df["stability"], strict=True)
            if h in row_of
        ]
        stability.append(
            {
                "target": tgt,
                "lens": lens,
                "draws": int(prof.params["stability"]["draws"]),
                "rows": rows,
            }
        )
    layers = {
        n: json.loads((interim / "layers" / f"{n}.geojson").read_text(encoding="utf-8"))
        for n in LAYER_NAMES
    }
    reg_file = interim / "target_regimes.json"  # written by doppelgrund.ml.pipeline when it ran
    regimes = json.loads(reg_file.read_text(encoding="utf-8")) if reg_file.is_file() else None
    return write_bundle(
        Path(out),
        prof=prof,
        scaler=scaler_rows(prof, sc),
        cells=cells,
        earth_features=earth[list(EXPECTED_FEATURES)].to_numpy(np.float32),
        earth_lith=earth[LITH_COLS].to_numpy(np.float32),
        earth_latlng=earth[["lat", "lng"]].to_numpy(np.float32),
        novelty=nov[["geo_novelty_km", "feat_novelty"]].to_numpy(np.float32),
        cluster=clu["hdb_label"].reindex(keys).fillna(-1).to_numpy(np.int16),
        flags=earth_flags(earth, prof.params, nov["known_site_flag"].fillna(False).to_numpy(bool)),
        discs=discs,
        targets=targets_json(pd.read_parquet(interim / "targets.parquet"), regimes),
        stability=stability,
        layers=layers,
        textures={b: p.read_bytes() for b, p in textures.items()},
        sources=sources_for(prof, fast=(resolution or {}).get("mode") == "fast"),
        resolution=resolution,
        synthetic=synthetic,
        created_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--interim", type=Path, default=REPO / "data/interim/real")
    p.add_argument("--out", type=Path, default=REPO / "web/public/data")
    p.add_argument("--synthetic", action="store_true", help="mark the manifest synthetic: true")
    p.add_argument("--clean", action="store_true", help="delete --out first")
    p.add_argument(
        "--fast",
        action="store_true",
        help="tables came from real.py --fast (overrides tables_info.json)",
    )
    p.add_argument(
        "--stride", type=int, help="tables came from real.py --stride N (with --fast or full)"
    )
    a = p.parse_args(argv)
    res = None
    if a.fast or a.stride:
        res = {"mode": "fast" if a.fast else "full", "stride": a.stride or 1}
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if a.clean and a.out.exists():
        shutil.rmtree(a.out)
    written = build_bundle(a.interim, a.out, synthetic=a.synthetic, resolution=res)
    print(f"wrote {len(written)} files to {a.out}; validate_bundle passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
