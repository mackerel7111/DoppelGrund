"""Synthetic DoppelGrund data: schema-valid (contracts C2 and C6) and clearly fake.

Every value here is invented by a seeded random generator. Targets, sites and layer points carry
ids prefixed ``synthetic_`` and are never written into ``config/``. Real data replaces all of it.

CLI::

    python -m doppelgrund.fixtures.synthetic --bundle web/public/data --interim data/interim/synthetic
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h3
import numpy as np
import pandas as pd
import shapely
from PIL import Image, ImageDraw
from shapely.geometry import shape
from shapely.ops import unary_union

from doppelgrund.config import EXPECTED_FEATURES, EXPECTED_LITH, REPO, Profiles, load_profiles

logger = logging.getLogger(__name__)

# Fixed so that output bytes are identical across runs (R4.4).
SYNTHETIC_CREATED_UTC = "2026-01-01T00:00:00Z"
INDEX_W, INDEX_H = 4096, 2048
TEXTURE_W, TEXTURE_H = 2048, 1024
SAMPLE_N_HEX = 500
LAND_GEOJSON = REPO / "config/ne_land.geojson"  # Natural Earth 1:110m land, public domain
TEXTURE_DIR = REPO / "config/textures"  # real NASA/USGS basemaps; absent => placeholder
N_DISCS = 3000
EARTH_R_KM = 6371.0088
LITH_COLS = [f"lith_{c}" for c in EXPECTED_LITH]
AUX_COLS = [
    "barren_frac",
    "snow_ice_frac",
    "ndvi_mean",
    "aster_mafic_idx",
    "land_frac",
    "vf_dem",
    "vf_lst",
    "vf_lith",
]

# Anchor points for fake "land" patches: (lat, lng, regime). Regimes only bias the fake values.
# These are generic regions chosen to exercise deserts, poles, volcanic areas and the antimeridian;
# they are NOT analogue claims.
ANCHORS: tuple[tuple[float, float, str], ...] = (
    (23.0, 10.0, "desert"),
    (-24.0, -69.0, "desert"),
    (23.0, 47.0, "desert"),
    (43.0, 105.0, "desert"),
    (-25.0, 130.0, "desert"),
    (64.8, -18.0, "volcanic"),
    (19.6, -155.5, "volcanic"),
    (-78.0, 160.0, "polar"),
    (75.0, -90.0, "polar"),
    (70.0, 120.0, "polar"),
    (33.0, 88.0, "polar"),
    (66.0, 179.0, "polar"),
    (35.0, -116.0, "desert"),
    (-23.0, 15.0, "desert"),
    (-16.0, -69.0, "volcanic"),
)

# Fake targets: (id, name, body, latitude band used to pick a disc). Coordinates come from the
# synthetic disc lattice, so they are not real landmark positions.
TARGET_SPECS: tuple[tuple[str, str, str, float, float], ...] = (
    ("synthetic_moon_polar_a", "Synthetic Moon target A (polar)", "moon", -89.2, 0.0),
    ("synthetic_moon_polar_b", "Synthetic Moon target B (polar)", "moon", -85.0, 60.0),
    ("synthetic_moon_mare_c", "Synthetic Moon target C (low latitude)", "moon", 10.0, 30.0),
    ("synthetic_moon_highland_d", "Synthetic Moon target D (mid latitude)", "moon", -40.0, -120.0),
    ("synthetic_mars_low_e", "Synthetic Mars target E (low latitude)", "mars", 18.0, 77.0),
    ("synthetic_mars_mid_f", "Synthetic Mars target F (mid latitude)", "mars", -5.0, 137.0),
    ("synthetic_mars_polar_g", "Synthetic Mars target G (high latitude)", "mars", 80.0, -100.0),
)


# --------------------------------------------------------------------------------------------
# Cells
# --------------------------------------------------------------------------------------------
def select_cells(n_hex: int) -> list[str]:
    """Pick ``n_hex`` real H3 res-4 cells as contiguous patches around ``ANCHORS``.

    Candidate res-2 cells are the children of each anchor's res-0 cell and its neighbours,
    sorted by distance to the anchor; patches grow round-robin across anchors.
    """
    queues: list[list[str]] = []
    for lat, lng, _ in ANCHORS:
        base = h3.latlng_to_cell(lat, lng, 0)
        res2 = sorted({c for b in h3.grid_disk(base, 1) for c in h3.cell_to_children(b, 2)})
        res2.sort(key=lambda c: h3.great_circle_distance((lat, lng), h3.cell_to_latlng(c)))
        queues.append(res2)
    chosen: set[str] = set()
    order: list[str] = []
    depth = 0
    while len(order) < n_hex:
        progressed = False
        for q in queues:
            if depth < len(q):
                progressed = True
                for child in sorted(h3.cell_to_children(q[depth], 4)):
                    if child not in chosen:
                        chosen.add(child)
                        order.append(child)
        if not progressed:
            raise ValueError(f"cannot select {n_hex} cells from the anchor set")
        depth += 1
    return sorted(order[:n_hex])


def load_land() -> Any:
    """Natural Earth land polygons as one shapely geometry."""
    gj = json.loads(LAND_GEOJSON.read_text(encoding="utf-8"))
    return unary_union([shape(f["geometry"]) for f in gj["features"]])


def select_land_cells(bbox: tuple[float, float, float, float] | None = None) -> list[str]:
    """Every H3 res-4 cell with its centre on land; ``bbox`` = (lat0, lat1, lng0, lng1)."""
    if bbox:
        la0, la1, ln0, ln1 = bbox
        ring = [(la0, ln0), (la0, ln1), (la1, ln1), (la1, ln0)]
        cells = list(h3.h3shape_to_cells(h3.LatLngPoly(ring), 4))
    else:
        cells = [c for b in h3.get_res0_cells() for c in h3.cell_to_children(b, 4)]
    ll = np.array([h3.cell_to_latlng(c) for c in cells])
    keep = shapely.contains_xy(load_land(), ll[:, 1], ll[:, 0])
    return sorted(c for c, k in zip(cells, keep, strict=True) if k)


def _smooth_field(lat: np.ndarray, lng: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Smooth ~N(0, 1) field: random plane waves in 3-D, so no seam at the antimeridian."""
    la, ln = np.radians(lat), np.radians(lng)
    xyz = np.column_stack([np.cos(la) * np.cos(ln), np.cos(la) * np.sin(ln), np.sin(la)])
    k = 10  # ponytail: fixed 10 waves (scales ~3,000-20,000 km), more waves for finer detail
    dirs = rng.normal(size=(k, 3))
    dirs *= rng.uniform(2.0, 9.0, (k, 1)) / np.linalg.norm(dirs, axis=1, keepdims=True)
    return np.cos(xyz @ dirs.T + rng.uniform(0, 2 * np.pi, k)).sum(axis=1) / math.sqrt(k / 2)


def _anchor_blend(lat: np.ndarray, lng: np.ndarray, base: dict[str, list[float]]) -> np.ndarray:
    """(n, 6) lithology prior: anchor regimes blended by great-circle distance (e-fold 1,500 km)."""
    d = np.column_stack([haversine_km(lat, lng, a[0], a[1]) for a in ANCHORS])
    w = np.exp(-(d - d.min(axis=1, keepdims=True)) / 1500.0)
    w /= w.sum(axis=1, keepdims=True)
    return w @ np.array([base[a[2]] for a in ANCHORS])


def _regime_of(lat: np.ndarray, lng: np.ndarray) -> np.ndarray:
    a_lat = np.radians([a[0] for a in ANCHORS])
    a_lng = np.radians([a[1] for a in ANCHORS])
    la, ln = np.radians(lat)[:, None], np.radians(lng)[:, None]
    d = np.sin((la - a_lat) / 2) ** 2 + np.cos(la) * np.cos(a_lat) * np.sin((ln - a_lng) / 2) ** 2
    return np.array([ANCHORS[i][2] for i in np.argmin(d, axis=1)])


def haversine_km(lat1: np.ndarray, lng1: np.ndarray, lat2: float, lng2: float) -> np.ndarray:
    """Great-circle distance (km) on a sphere of radius 6371.0088 km; inputs in degrees."""
    p1, p2 = np.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lng2) - np.radians(lng1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * math.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# --------------------------------------------------------------------------------------------
# Value generators
# --------------------------------------------------------------------------------------------
def _lith_rows(rng: np.random.Generator, probs: np.ndarray, mix_frac: float = 0.4) -> np.ndarray:
    """One-hot or two-class mixtures; ``probs`` (n, 6) gives the class distribution per row."""
    n = probs.shape[0]
    cum = probs.cumsum(axis=1)
    first = (rng.random((n, 1)) > cum).sum(axis=1).clip(0, 5)
    second = (rng.random((n, 1)) > cum).sum(axis=1).clip(0, 5)
    out = np.zeros((n, 6), dtype=np.float64)
    share = np.where(rng.random(n) < mix_frac, rng.uniform(0.5, 0.9, n), 1.0)
    out[np.arange(n), first] += share
    out[np.arange(n), second] += 1.0 - share
    return out.astype(np.float32)


def _inject_nan(rng: np.random.Generator, x: np.ndarray, frac: float) -> np.ndarray:
    x = x.astype(np.float32).copy()
    x[rng.random(x.shape[0]) < frac] = np.nan
    return x


def earth_table(
    cells: Sequence[str], rng: np.random.Generator, smooth: bool = False
) -> pd.DataFrame:
    """Fake Earth features (C2 ``earth_features.parquet`` columns) for the given res-4 cells.

    ``smooth`` replaces the i.i.d. draws of the main features by low-frequency fields of lat/lng.
    """
    n = len(cells)
    ll = np.array([h3.cell_to_latlng(c) for c in cells], dtype=np.float64).reshape(n, 2)
    lat, lng = ll[:, 0], ll[:, 1]
    regime = _regime_of(lat, lng)
    alat = np.abs(lat)
    p50 = np.clip(rng.lognormal(math.log(2.5), 0.8, n), 0.05, 60.0)
    p90 = np.clip(p50 * rng.uniform(1.5, 3.0, n), 0.1, 75.0)
    relief = rng.lognormal(math.log(80.0), 0.9, n)
    frac_lt10 = np.clip(1.0 - p50 / 15.0, 0.0, 1.0)
    lst = np.clip(302.0 - 0.95 * alat + rng.normal(0, 5, n), 220.0, 325.0)
    diurnal = rng.uniform(5.0, 40.0, n)
    annual = np.clip(5.0 + 0.7 * alat + rng.normal(0, 4, n), 5.0, 60.0)
    below0 = 1.0 / (1.0 + np.exp(-(273.15 - lst) / 8.0))
    perma = np.where(lat > 45.0, np.clip((lat - 45.0) / 30.0 + rng.normal(0, 0.1, n), 0, 1), np.nan)
    aridity = np.exp(rng.uniform(math.log(0.02), math.log(3.0), n))
    if smooth:
        z = [_smooth_field(lat, lng, rng) for _ in range(14)]
        p50 = np.clip(2.5 * np.exp(0.8 * z[0]), 0.05, 60.0)
        p90 = np.clip(p50 * (2.25 + 0.4 * z[1]), 0.1, 75.0)
        relief = 80.0 * np.exp(0.9 * z[2])
        frac_lt10 = np.clip(1.0 - p50 / 15.0, 0.0, 1.0)
        lst = np.clip(302.0 - 0.95 * alat + 5 * z[3], 220.0, 325.0)
        diurnal = np.clip(22.5 + 8 * z[4], 5.0, 40.0)
        annual = np.clip(5.0 + 0.7 * alat + 4 * z[5], 5.0, 60.0)
        below0 = 1.0 / (1.0 + np.exp(-(273.15 - lst) / 8.0))
        perma = np.where(lat > 45.0, np.clip((lat - 45.0) / 30.0 + 0.1 * z[6], 0, 1), np.nan)
        aridity = 0.25 * np.exp(1.2 * z[7])
    aridity = np.where(regime == "desert", aridity * 0.2, aridity)
    base = {
        "desert": [0.10, 0.15, 0.20, 0.40, 0.15, 0.00],
        "volcanic": [0.80, 0.10, 0.00, 0.10, 0.00, 0.00],
        "polar": [0.15, 0.20, 0.05, 0.30, 0.00, 0.30],
    }
    probs = np.array([base[r] for r in regime], dtype=np.float64)
    lith = _lith_rows(rng, probs)
    if smooth:  # fractions follow the blended anchor prior, tilted by smooth per-class fields
        w = _anchor_blend(lat, lng, base) * np.exp(0.5 * np.column_stack(z[8:14]))
        lith = (w / w.sum(axis=1, keepdims=True)).astype(np.float32)
    lith[rng.random(n) < 0.10] = np.nan  # unmapped footprints

    feats = {
        "slope_p50_deg": p50,
        "slope_p90_deg": p90,
        "relief_std_m": relief,
        "frac_slope_lt_10deg": frac_lt10,
        "lst_mean_K": lst,
        "diurnal_range_K": diurnal,
        "annual_range_K": annual,
        "frac_below_0C": below0,
        "permafrost_prob": perma,
        "aridity_index": aridity,
    }
    df = pd.DataFrame({"h3": list(cells)})
    for name in EXPECTED_FEATURES:
        df[name] = _inject_nan(rng, feats[name], 0.10)
    for j, col in enumerate(LITH_COLS):
        df[col] = lith[:, j]
    all_nan = rng.random(n) < 0.01
    df.loc[all_nan, list(EXPECTED_FEATURES) + LITH_COLS] = np.nan

    masked = rng.random(n) < 0.30
    df["barren_frac"] = np.where(masked, rng.uniform(0, 0.3, n), rng.uniform(0.5, 1.0, n))
    df["snow_ice_frac"] = np.where(regime == "polar", rng.uniform(0, 0.15, n), 0.0)
    df["ndvi_mean"] = np.where(masked, rng.uniform(0.25, 0.8, n), rng.uniform(0.0, 0.2, n))
    df["aster_mafic_idx"] = np.where(regime == "polar", np.nan, rng.uniform(0, 1, n))
    df["land_frac"] = rng.uniform(0.3, 1.0, n)
    df["vf_dem"] = rng.uniform(0.9, 1.0, n)
    df["vf_lst"] = rng.uniform(0.6, 1.0, n)
    df["vf_lith"] = np.where(np.isnan(lith[:, 0]), 0.0, rng.uniform(0.5, 1.0, n))
    for col in AUX_COLS:
        df[col] = df[col].astype(np.float32)
    df["tag_volcanic"] = (regime == "volcanic") | (rng.random(n) < 0.02)
    df["tag_periglacial"] = np.nan_to_num(df["frac_below_0C"].to_numpy()) > 0.5
    df["tag_evaporitic"] = np.nan_to_num(df["lith_evaporite"].to_numpy()) > 0.3
    df["masked"] = masked  # convenience column for the bundle flags (not part of C2)
    df["lat"], df["lng"] = lat, lng
    return df


def fibonacci_lattice(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (lat, lon) in degrees of ``n`` near-uniform points; lon in [-180, 180)."""
    i = np.arange(n, dtype=np.float64)
    lat = np.degrees(np.arcsin(1.0 - 2.0 * (i + 0.5) / n))
    golden = math.pi * (3.0 - math.sqrt(5.0))
    lon = np.degrees((i * golden) % (2 * math.pi)) - 180.0
    return lat, lon


def disc_table(body: str, rng: np.random.Generator, n: int = N_DISCS) -> pd.DataFrame:
    """Fake Moon or Mars disc grid (C2 ``<body>_discs.parquet`` columns)."""
    lat, lon = fibonacci_lattice(n)
    alat = np.abs(lat)
    nan = np.full(n, np.nan)
    if body == "moon":
        mare = (rng.random(n) < 0.3) & (alat < 60)
        p50 = np.clip(rng.lognormal(np.log(np.where(mare, 2.0, 5.0)), 0.6), 0.1, 45)
        lst = np.clip(250.0 - 130.0 * (alat / 90.0) ** 4 + rng.normal(0, 8, n), 60, 330)
        diurnal = np.clip(250.0 * np.cos(np.radians(alat)) ** 0.5 + rng.normal(0, 10, n), 5, 300)
        below0 = 1.0 / (1.0 + np.exp(-(273.15 - lst) / 30.0))
        ice = alat > 85
        probs = np.where(mare[:, None], [0.9, 0.1, 0, 0, 0, 0], [0.1, 0.9, 0, 0, 0, 0])
        probs = np.where(ice[:, None], [0.05, 0.75, 0, 0, 0, 0.2], probs)
        thermal = (lst, diurnal, nan, below0)
        relief = rng.lognormal(math.log(150.0), 0.7, n)
    else:
        p50 = np.clip(rng.lognormal(math.log(2.0), 0.8, n), 0.05, 45)
        relief = rng.lognormal(math.log(120.0), 0.9, n)
        thermal = (nan, nan, nan, nan)  # no verified Mars thermal source (C1 open item)
        probs = np.tile([0.5, 0.1, 0.05, 0.3, 0.05, 0.0], (n, 1))
        probs = np.where((alat > 75)[:, None], [0.2, 0.0, 0.0, 0.3, 0.0, 0.5], probs)
    p90 = np.clip(p50 * rng.uniform(1.5, 3.0, n), 0.1, 70)
    feats = {
        "slope_p50_deg": p50,
        "slope_p90_deg": p90,
        "relief_std_m": relief,
        "frac_slope_lt_10deg": np.clip(1.0 - p50 / 15.0, 0, 1),
        "lst_mean_K": thermal[0],
        "diurnal_range_K": thermal[1],
        "annual_range_K": thermal[2],
        "frac_below_0C": thermal[3],
        "permafrost_prob": nan,
        "aridity_index": np.zeros(n),  # 0.0 by definition (profiles.yaml assumption)
    }
    df = pd.DataFrame({"disc_id": np.arange(n, dtype=np.int32), "lat": lat, "lon": lon})
    for name in EXPECTED_FEATURES:
        x = feats[name].astype(np.float32)
        if name in ("lst_mean_K", "diurnal_range_K", "frac_below_0C") and body == "moon":
            x = _inject_nan(rng, x, 0.03)
        df[name] = x
    lith = _lith_rows(rng, probs.astype(np.float64), mix_frac=0.3)
    for j, col in enumerate(LITH_COLS):
        df[col] = lith[:, j]
    df["vf_dem"] = rng.uniform(0.9, 1.0, n).astype(np.float32)
    return df


def targets_table(moon: pd.DataFrame, mars: pd.DataFrame) -> pd.DataFrame:
    """Fake targets: each copies the features of the disc nearest its spec position."""
    rows = []
    for tid, name, body, lat, lon in TARGET_SPECS:
        discs = moon if body == "moon" else mars
        d = haversine_km(discs["lat"].to_numpy(), discs["lon"].to_numpy(), lat, lon)
        disc = discs.iloc[int(np.argmin(d))]
        row = {"target_id": tid, "name": name, "body": body}
        row["lat"], row["lon"] = float(disc["lat"]), float(disc["lon"])
        for col in list(EXPECTED_FEATURES) + LITH_COLS:
            row[col] = np.float32(disc[col])
        rows.append(row)
    df = pd.DataFrame(rows)
    for col in list(EXPECTED_FEATURES) + LITH_COLS:
        df[col] = df[col].astype(np.float32)
    return df


def fit_scaler(frames: Sequence[pd.DataFrame], prof: Profiles) -> list[dict[str, Any]]:
    """Pooled median and 1.4826·MAD per feature on the transformed scale (synthetic stand-in)."""
    out = []
    for f in prof.features:
        x = np.concatenate([fr[f.name].to_numpy(np.float64) for fr in frames])
        x = x[np.isfinite(x)]
        if f.transform == "log1p":
            x = np.log1p(np.maximum(x, 0.0))
        med = float(np.median(x))
        s = float(1.4826 * np.median(np.abs(x - med)))
        if not s > 0:
            s = float(np.std(x)) or 1.0
        out.append({"name": f.name, "median": med, "s": s})
    return out


def _points(
    rng: np.random.Generator, lat: np.ndarray, lng: np.ndarray, k: int, prefix: str, label: str
) -> pd.DataFrame:
    idx = np.sort(rng.choice(len(lat), size=min(k, len(lat)), replace=False))
    return pd.DataFrame(
        {
            "id": [f"synthetic_{prefix}_{i + 1:02d}" for i in range(len(idx))],
            "name": [f"Synthetic {label} {i + 1}" for i in range(len(idx))],
            "lat": lat[idx] + rng.normal(0, 0.05, len(idx)),
            "lng": lng[idx] + rng.normal(0, 0.05, len(idx)),
        }
    )


def make_synthetic(
    seed: int,
    n_hex: int = 6000,
    coverage: str = "patches",
    bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, pd.DataFrame]:
    """Build every synthetic table in memory.

    ``coverage="land"`` uses every land cell (``n_hex`` ignored, ``bbox`` restricts it) with
    spatially smooth values; ``"patches"`` keeps the anchor patches.

    Returns keys ``earth_features``, ``moon_discs``, ``mars_discs``, ``targets``, ``known_sites``,
    ``volcanoes``, ``lava_tubes``, ``sarawak_caves``, ``lunar_pits``.
    """
    rng = np.random.default_rng(seed)
    land = coverage == "land"
    cells = select_land_cells(bbox) if land else select_cells(n_hex)
    n_hex = len(cells)
    earth = earth_table(cells, rng, smooth=land)
    moon = disc_table("moon", rng)
    mars = disc_table("mars", rng)
    targets = targets_table(moon, mars)
    lat, lng = earth["lat"].to_numpy(), earth["lng"].to_numpy()
    # capped near the size of real analogue-site lists, so all-land runs don't flood the map
    known = _points(rng, lat, lng, min(60, max(5, n_hex // 300)), "site", "known site")
    known["well_known"] = np.arange(len(known)) % 4 == 0
    known["dimension"] = [
        ("terrain", "thermal", "cold_ice", "composition")[i % 4] for i in range(len(known))
    ]
    volc = earth["tag_volcanic"].to_numpy()
    out = {
        "earth_features": earth,
        "moon_discs": moon,
        "mars_discs": mars,
        "targets": targets,
        "known_sites": known,
        "volcanoes": _points(rng, lat[volc], lng[volc], 25, "volcano", "volcano"),
        "lava_tubes": _points(rng, lat[volc], lng[volc], 8, "lava_tube", "lava tube"),
        "sarawak_caves": _points(rng, lat, lng, 6, "cave", "cave"),
    }
    m_lat, m_lon = moon["lat"].to_numpy(), moon["lon"].to_numpy()
    out["lunar_pits"] = _points(rng, m_lat, m_lon, 20, "lunar_pit", "lunar pit")
    return out


# --------------------------------------------------------------------------------------------
# Derived bundle arrays
# --------------------------------------------------------------------------------------------
def novelty(earth: pd.DataFrame, known: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """(N, 2) float32: km to nearest synthetic known site, fake feature novelty in [0, 1]."""
    lat, lng = earth["lat"].to_numpy(), earth["lng"].to_numpy()
    d = np.full(len(lat), np.inf)
    for s_lat, s_lng in zip(known["lat"], known["lng"], strict=True):
        d = np.minimum(d, haversine_km(lat, lng, float(s_lat), float(s_lng)))
    feat = rng.beta(2.0, 5.0, len(lat))
    return np.column_stack([d, feat]).astype(np.float32)


def flags(earth: pd.DataFrame, known: pd.DataFrame) -> np.ndarray:
    """C6 earth_flags.u8 bits: 0 masked, 1 volcanic, 2 periglacial, 3 evaporitic, 4 known site."""
    f = earth["masked"].to_numpy().astype(np.uint8)
    f |= earth["tag_volcanic"].to_numpy().astype(np.uint8) << 1
    f |= earth["tag_periglacial"].to_numpy().astype(np.uint8) << 2
    f |= earth["tag_evaporitic"].to_numpy().astype(np.uint8) << 3
    row_of = {c: i for i, c in enumerate(earth["h3"])}
    for s_lat, s_lng in zip(known["lat"], known["lng"], strict=True):
        r = row_of.get(h3.latlng_to_cell(float(s_lat), float(s_lng), 4))
        if r is not None:
            f[r] |= 16
    return f


def _unwrap(lngs: list[float]) -> list[float]:
    if max(lngs) - min(lngs) > 180.0:
        return [x + 360.0 if x < 0 else x for x in lngs]
    return lngs


def index_map(cells: Sequence[str]) -> Image.Image:
    """Rasterise cells onto a 4096x2048 equirectangular RGB image; value = row + 1 (C6)."""
    img = Image.new("RGB", (INDEX_W, INDEX_H), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    sx, sy = INDEX_W / 360.0, INDEX_H / 180.0
    for row, cell in enumerate(cells):
        v = row + 1
        colour = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
        boundary = h3.cell_to_boundary(cell)
        lats = [p[0] for p in boundary]
        lngs = _unwrap([p[1] for p in boundary])
        shifts = [0.0, -360.0] if max(lngs) > 180.0 else [0.0]
        for shift in shifts:
            pts = [
                ((x + shift + 180.0) * sx, (90.0 - y) * sy) for x, y in zip(lngs, lats, strict=True)
            ]
            draw.polygon(pts, fill=colour)
    return img


def _texture(body: str) -> Image.Image:  # placeholder when config/textures/<body>.jpg is absent
    grey = {"earth": 46, "moon": 120, "mars": 110}[body]
    tint = {"earth": (0, 4, 10), "moon": (0, 0, 0), "mars": (25, 0, -15)}[body]
    base = tuple(int(np.clip(grey + t, 0, 255)) for t in tint)
    img = Image.new("RGB", (TEXTURE_W, TEXTURE_H), base)
    draw = ImageDraw.Draw(img)
    line = tuple(min(255, c + 25) for c in base)
    for lon in range(-180, 181, 30):
        x = (lon + 180) / 360 * (TEXTURE_W - 1)
        draw.line([(x, 0), (x, TEXTURE_H)], fill=line, width=1)
    for lat in range(-90, 91, 30):
        y = (90 - lat) / 180 * (TEXTURE_H - 1)
        draw.line([(0, y), (TEXTURE_W, y)], fill=line, width=1)
    return img


def _jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=False)
    return buf.getvalue()


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def _null_list(values: Any) -> list[float | None]:
    return [None if not np.isfinite(v) else float(v) for v in np.asarray(values, np.float64)]


def _points_geojson(df: pd.DataFrame, extra: Sequence[str] = (), body: str = "earth") -> dict:
    lng_col = "lng" if "lng" in df.columns else "lon"
    feats = []
    for _, r in df.iterrows():
        props = {"id": r["id"], "name": r["name"], "body": body, "synthetic": True}
        for k in extra:
            v = r[k]
            props[k] = v.item() if hasattr(v, "item") else v
        geom = {
            "type": "Point",
            "coordinates": [round(float(r[lng_col]), 5), round(float(r["lat"]), 5)],
        }
        feats.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": feats}


def _land_geojson(cells: Sequence[str]) -> dict:
    parents = sorted({h3.cell_to_parent(c, 2) for c in cells})
    feats = []
    for p in parents:
        boundary = h3.cell_to_boundary(p)
        lngs = _unwrap([q[1] for q in boundary])
        ring = [[round(x, 5), round(y[0], 5)] for x, y in zip(lngs, boundary, strict=True)]
        ring.append(ring[0])
        feats.append(
            {
                "type": "Feature",
                "properties": {"synthetic": True},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def _real_land_geojson() -> dict:
    return json.loads(LAND_GEOJSON.read_text(encoding="utf-8"))


def _stability_rows(rng: np.random.Generator, n: int, k: int) -> list[list[float]]:
    rows = np.sort(rng.choice(n, size=min(k, n), replace=False))
    frac = np.round(np.sort(rng.beta(2.0, 1.5, len(rows)))[::-1], 4)
    order = rng.permutation(len(rows))
    return [[int(rows[i]), float(frac[j])] for j, i in enumerate(order)]


def _write(path: Path, data: bytes, overwrite: bool, written: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        written.append(path)
        return
    path.write_bytes(data)
    written.append(path)


def _json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, indent=1, allow_nan=False, ensure_ascii=False) + "\n").encode("utf-8")


# --------------------------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------------------------
def write_synthetic_interim(
    out_dir: Path, seed: int, n_hex: int = 6000, overwrite: bool = True, coverage: str = "patches"
) -> list[Path]:
    """Write synthetic C2 tables (earth_features, moon/mars discs, targets) as Parquet."""
    tables = make_synthetic(seed, n_hex, coverage)
    out_dir = Path(out_dir)
    written: list[Path] = []
    earth = tables["earth_features"].drop(columns=["masked"])
    for name, df in (
        ("earth_features", earth),
        ("moon_discs", tables["moon_discs"]),
        ("mars_discs", tables["mars_discs"]),
        ("targets", tables["targets"]),
    ):
        buf = io.BytesIO()
        df.to_parquet(buf, index=False, engine="pyarrow", compression="zstd")
        _write(out_dir / f"{name}.parquet", buf.getvalue(), overwrite, written)
    return written


def write_synthetic_bundle(
    out_dir: Path,
    seed: int,
    n_hex: int = 6000,
    overwrite: bool = True,
    sample: bool = True,
    coverage: str = "patches",
    bbox: tuple[float, float, float, float] | None = None,
) -> list[Path]:
    """Write a complete C6 bundle with ``"synthetic": true``.

    Uses its own minimal writer (``doppelgrund.export.bundle`` does not exist yet). When ``sample`` is
    true a ≤ 500-hex copy (always patches) is also written to ``out_dir/sample`` for CI.
    ``coverage="land"`` covers all land (see ``make_synthetic``).
    """
    out_dir = Path(out_dir)
    prof = load_profiles()
    tables = make_synthetic(seed, n_hex, coverage, bbox)
    rng = np.random.default_rng(seed + 1)
    earth, moon, mars = tables["earth_features"], tables["moon_discs"], tables["mars_discs"]
    targets = tables["targets"]
    cells = earth["h3"].tolist()
    scaler = fit_scaler([earth, moon, mars], prof)
    written: list[Path] = []

    def arr(df: pd.DataFrame, cols: Sequence[str]) -> bytes:
        return np.ascontiguousarray(df[list(cols)].to_numpy(np.float32)).astype("<f4").tobytes()

    _write(out_dir / "earth_h3.txt", ("\n".join(cells) + "\n").encode(), overwrite, written)
    _write(out_dir / "earth_features.f32", arr(earth, EXPECTED_FEATURES), overwrite, written)
    _write(out_dir / "earth_lith.f32", arr(earth, LITH_COLS), overwrite, written)
    _write(out_dir / "earth_latlng.f32", arr(earth, ["lat", "lng"]), overwrite, written)
    nov = novelty(earth, tables["known_sites"], rng)
    _write(out_dir / "earth_novelty.f32", nov.astype("<f4").tobytes(), overwrite, written)
    regimes = _regime_of(earth["lat"].to_numpy(), earth["lng"].to_numpy())
    cluster = np.array([{"desert": 0, "volcanic": 1, "polar": 2}[r] for r in regimes], np.int16)
    cluster = np.where(
        rng.random(len(cluster)) < 0.1, -1, cluster * 2 + (rng.random(len(cluster)) < 0.5)
    ).astype("<i2")
    _write(out_dir / "earth_cluster.i16", cluster.tobytes(), overwrite, written)
    fl = flags(earth, tables["known_sites"])
    _write(out_dir / "earth_flags.u8", fl.tobytes(), overwrite, written)
    for body, df in (("moon", moon), ("mars", mars)):
        _write(out_dir / f"{body}_features.f32", arr(df, EXPECTED_FEATURES), overwrite, written)
        _write(out_dir / f"{body}_lith.f32", arr(df, LITH_COLS), overwrite, written)
        _write(out_dir / f"{body}_latlon.f32", arr(df, ["lat", "lon"]), overwrite, written)

    tjson = []
    for i, t in targets.iterrows():
        feats = t[list(EXPECTED_FEATURES)].to_numpy(np.float64)
        missing = [n for n, v in zip(EXPECTED_FEATURES, feats, strict=True) if not np.isfinite(v)]
        tjson.append(
            {
                "id": t["target_id"],
                "name": t["name"],
                "body": t["body"],
                "lat": round(float(t["lat"]), 6),
                "lon": round(float(t["lon"]), 6),
                "features": _null_list(feats),
                "lith": _null_list(t[LITH_COLS].to_numpy(np.float64)),
                "cluster": int(i % 3),
                "notes": "Synthetic target generated for development; not a real landmark.",
                "coverage_notes": [f"{n}: not measured (synthetic)" for n in missing],
            }
        )
    _write(out_dir / "targets.json", _json_bytes(tjson), overwrite, written)

    k = int(prof.params["stability"]["store_top_k"])
    draws = int(prof.params["stability"]["draws"])
    for t in tjson:
        for lens in prof.lenses:
            st = {
                "target": t["id"],
                "lens": lens,
                "draws": draws,
                "rows": _stability_rows(rng, len(cells), min(k, len(cells) // 3)),
            }
            _write(
                out_dir / "stability" / f"{t['id']}__{lens}.json",
                _json_bytes(st),
                overwrite,
                written,
            )

    _write(out_dir / "earth_index_4096x2048.png", _png_bytes(index_map(cells)), overwrite, written)
    layers = {
        "land": _real_land_geojson() if coverage == "land" else _land_geojson(cells),
        "known_sites": _points_geojson(tables["known_sites"], ("well_known", "dimension")),
        "volcanoes": _points_geojson(tables["volcanoes"]),
        "lava_tubes": _points_geojson(tables["lava_tubes"]),
        "sarawak_caves": _points_geojson(tables["sarawak_caves"]),
        "lunar_pits": _points_geojson(tables["lunar_pits"], body="moon"),
    }
    for name, gj in layers.items():
        _write(out_dir / "layers" / f"{name}.geojson", _json_bytes(gj), overwrite, written)
    for body in ("earth", "moon", "mars"):
        real = TEXTURE_DIR / f"{body}.jpg"
        data = real.read_bytes() if real.is_file() else _jpeg_bytes(_texture(body))
        _write(out_dir / "textures" / f"{body}.jpg", data, overwrite, written)

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
    features_meta = [
        {
            "name": f.name,
            "group": f.group,
            "unit": f.unit,
            "transform": f.transform,
            "median": sc["median"],
            "s": sc["s"],
        }
        for f, sc in zip(prof.features, scaler, strict=True)
    ]
    manifest = {
        "contract": "doppelgrund-bundle/1",
        "created_utc": SYNTHETIC_CREATED_UTC,
        "synthetic": True,
        "h3_res": 4,
        "n_hex": len(cells),
        "features": features_meta,
        "lith_classes": list(prof.lith_classes),
        "compat_matrix": prof.compat_matrix.tolist(),
        "lenses": prof.lenses,
        "params": prof.params,
        "files": files,
        "sources": [
            {"feature": name, "body": b, "dataset": "synthetic", "version": f"seed {seed}"}
            for name in [*(f.name for f in prof.features), "lith"]
            for b in ("earth", "moon", "mars")
        ],
    }
    _write(out_dir / "manifest.json", _json_bytes(manifest), overwrite, written)
    if sample and n_hex > SAMPLE_N_HEX:
        written += write_synthetic_bundle(
            out_dir / "sample", seed, SAMPLE_N_HEX, overwrite, sample=False
        )
    logger.info("wrote %d synthetic bundle files to %s", len(written), out_dir)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``--bundle DIR --interim DIR --seed N --n-hex N``."""
    parser = argparse.ArgumentParser(description="Write a synthetic DoppelGrund bundle and interim tables")
    parser.add_argument("--bundle", type=Path, help="web bundle directory (C6)")
    parser.add_argument("--interim", type=Path, help="interim Parquet directory (C2)")
    parser.add_argument("--seed", type=int, default=None, help="default: profiles params.seed")
    parser.add_argument("--n-hex", type=int, default=6000, help="patches mode only")
    parser.add_argument(
        "--coverage", choices=("patches", "land"), default="patches", help="land = all land cells"
    )
    parser.add_argument("--no-sample", action="store_true", help="skip the 500-hex sample copy")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    seed = args.seed if args.seed is not None else int(load_profiles().params["seed"])
    if args.bundle:
        write_synthetic_bundle(
            args.bundle, seed, args.n_hex, sample=not args.no_sample, coverage=args.coverage
        )
    if args.interim:
        write_synthetic_interim(args.interim, seed, args.n_hex, coverage=args.coverage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
