"""Catalogued pits / lava tubes per 1000 km2 (``pit_cave_density_per_1000km2``), POSITIVE-ONLY.

A place gets a value only where the catalogue lists at least one feature; elsewhere it is NaN
("not measured"), never 0. No catalogue states its survey coverage, so a zero would claim "surveyed,
found nothing" (science-invariant 1; user decision 2026-11-14). Mars has no catalogue yet.

Moon: LROC lunar pit catalogue (Wagner & Robinson 2021), pits typed "Uncertain" excluded.
Earth: config/earth_lava_tubes.csv, rows typed lava_tube only (karst caves are never counted).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import h3
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

MOON_R_KM = 1737.4


def density(counts: np.ndarray, area_km2: np.ndarray | float) -> np.ndarray:
    """count / area * 1000 as float32; NaN (not 0) where the count is 0."""
    c = np.asarray(counts, np.float64)
    out = np.where(c > 0, c / np.asarray(area_km2, np.float64) * 1000.0, np.nan)
    return out.astype(np.float32)


def hex_density(
    plat: np.ndarray, plon: np.ndarray, cells: Sequence[str], res: int = 4
) -> np.ndarray:
    """Per H3 cell: points inside it per 1000 km2 of that cell's true area."""
    n = Counter(h3.latlng_to_cell(float(a), float(b), res) for a, b in zip(plat, plon, strict=True))
    area = np.array([h3.cell_area(c, unit="km^2") for c in cells])
    return density(np.array([n.get(c, 0) for c in cells]), area)


def _xyz(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    la, lo = np.radians(np.asarray(lat, np.float64)), np.radians(np.asarray(lon, np.float64))
    return np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]


def disc_density(
    dlat: np.ndarray,
    dlon: np.ndarray,
    plat: np.ndarray,
    plon: np.ndarray,
    r_km: float,
    body_r_km: float = MOON_R_KM,
) -> np.ndarray:
    """Per disc (centre dlat/dlon, radius r_km): points inside it per 1000 km2 of flat disc area."""
    chord = 2 * np.sin(r_km / (2 * body_r_km))  # great-circle radius -> chord on the unit sphere
    hits = cKDTree(_xyz(plat, plon)).query_ball_point(_xyz(dlat, dlon), chord)
    return density(np.array([len(h) for h in hits]), np.pi * r_km**2)


def load_lroc_pits(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """(lat, lon in -180..180) of the LROC pits minus those typed 'Uncertain'; the CSV is cp1252."""
    d = pd.read_csv(path, encoding="cp1252", usecols=["Type", "Latitude", "Longitude_180"])
    d = d[d["Type"].fillna("") != "Uncertain"]
    return d["Latitude"].to_numpy(float), d["Longitude_180"].to_numpy(float)


def load_earth_lava_tubes(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """(lat, lon) of the rows typed lava_tube."""
    d = pd.read_csv(path)
    d = d[d["type"] == "lava_tube"]
    return d["lat"].to_numpy(float), d["lon"].to_numpy(float)
