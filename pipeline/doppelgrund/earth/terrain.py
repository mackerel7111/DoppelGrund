"""Plan B terrain: per-hex slope statistics from NOAA ETOPO 2022 15 arc-second tiles.

No Earth Engine. Same four outputs as the Earth Engine route (``slope_p50_deg``,
``slope_p90_deg``, ``relief_std_m``, ``frac_slope_lt_10deg``): the Horn 3x3 slope in degrees on the
~460 m grid, summarised over the pixels whose centre falls inside each H3 res-4 hex.

Known limits (TODO(verify) against the Earth Engine probe values):
* Pixels below sea level are dropped as ocean, so real inland depressions (Dead Sea, Death Valley,
  the Caspian lowlands) are missing too. The ETOPO source-ID tiles could tell the two apart.
* East-west grid spacing is scaled by cos(latitude) at the window centre, not per row.
* A hex wider than the tiles on disk simply uses the pixels it finds; missing tiles read as no data.

    python -m doppelgrund.earth.terrain --tiles data/raw/earth_plan_b/etopo2022_15s_surface
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import rasterio
from PIL import Image, ImageDraw
from rasterio.merge import merge

from doppelgrund.config import REPO
from doppelgrund.export.index_map import unwrap
from doppelgrund.real import horn_slope_deg, terrain_stats

R_M = 6371008.8  # mean Earth radius, metres
PX_DEG = 15.0 / 3600.0  # ETOPO 15 arc-second grid
COLS = ["slope_p50_deg", "slope_p90_deg", "relief_std_m", "frac_slope_lt_10deg"]


class Tiles:
    """The open ETOPO tiles of one folder; reads grid-aligned windows across tile edges."""

    def __init__(self, tile_dir: Path):
        paths = sorted(Path(tile_dir).glob("*.tif"))
        if not paths:
            raise FileNotFoundError(f"no .tif tiles in {tile_dir}")
        self.ds = [rasterio.open(p) for p in paths]

    def close(self) -> None:
        for d in self.ds:
            d.close()

    def read(self, west: float, south: float, east: float, north: float) -> np.ndarray:
        """float32 (rows, cols) for the box, NaN where no tile covers it; north row first."""
        nrows, ncols = round((north - south) / PX_DEG), round((east - west) / PX_DEG)
        # only tiles that overlap the box are read
        hit = [
            d
            for d in self.ds
            if d.bounds.left < east and d.bounds.right > west
            and d.bounds.bottom < north and d.bounds.top > south
        ]  # fmt: skip
        if not hit:
            return np.full((nrows, ncols), np.nan, np.float32)
        arr, _ = merge(
            hit, bounds=(west, south, east, north), res=PX_DEG, nodata=np.nan, dtype="float32"
        )
        out = np.full((nrows, ncols), np.nan, np.float32)
        r, c = min(nrows, arr.shape[1]), min(ncols, arr.shape[2])
        out[:r, :c] = arr[0, :r, :c]
        return out


def _snap(v: float, up: bool) -> float:
    """Snap a coordinate (degrees) outward to the 15 arc-second grid."""
    k = np.ceil(v / PX_DEG) if up else np.floor(v / PX_DEG)
    return float(k * PX_DEG)


def hex_window(tiles: Tiles, cell: str) -> tuple[np.ndarray, np.ndarray, float]:
    """(elevation window, boolean mask of pixels inside the hex, centre latitude)."""
    boundary = h3.cell_to_boundary(cell)
    lats = [p[0] for p in boundary]
    lngs = unwrap([p[1] for p in boundary])
    pad = 2 * PX_DEG  # the slope needs a neighbour ring
    west, east = _snap(min(lngs) - pad, False), _snap(max(lngs) + pad, True)
    south, north = _snap(min(lats) - pad, False), _snap(max(lats) + pad, True)
    south, north = max(south, -90.0), min(north, 90.0)
    if east > 180.0:  # the hex crosses the antimeridian: stitch the two sides
        e1 = tiles.read(west, south, 180.0, north)
        e2 = tiles.read(-180.0, south, east - 360.0, north)
        z = np.hstack([e1, e2])
    elif west < -180.0:
        z = np.hstack(
            [tiles.read(west + 360.0, south, 180.0, north), tiles.read(-180.0, south, east, north)]
        )
    else:
        z = tiles.read(west, south, east, north)
    h, w = z.shape
    img = Image.new("L", (w, h), 0)
    pts = [((x - west) / PX_DEG, (north - y) / PX_DEG) for x, y in zip(lngs, lats, strict=True)]
    ImageDraw.Draw(img).polygon(pts, fill=1)
    return z, np.asarray(img, bool), float(np.mean(lats))


def hex_terrain(tiles: Tiles, cell: str) -> dict[str, float]:
    z, mask, lat = hex_window(tiles, cell)
    z = np.where(z < 0, np.nan, z).astype(np.float64)  # below sea level = ocean (see module note)
    dy = PX_DEG * np.pi / 180.0 * R_M
    dx = max(dy * np.cos(np.radians(lat)), 1.0)
    slope = horn_slope_deg(z, dx, dy)
    return terrain_stats(z, slope, mask & np.isfinite(z))


def terrain_table(cells: Sequence[str], tile_dir: Path) -> pd.DataFrame:
    """One row per cell with the four terrain columns (NaN where the tiles hold no land)."""
    tiles = Tiles(tile_dir)
    try:
        rows = [hex_terrain(tiles, c) for c in cells]
    finally:
        tiles.close()
    df = pd.DataFrame(rows, columns=COLS).astype(np.float32)
    df.insert(0, "h3", list(cells))
    return df


def main(argv: Sequence[str] | None = None) -> int:
    from doppelgrund.fixtures.synthetic import select_land_cells

    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument(
        "--tiles", type=Path, default=REPO / "data/raw/earth_plan_b/etopo2022_15s_surface"
    )
    p.add_argument(
        "--out", type=Path, default=REPO / "data/interim/real/earth_terrain_planb.parquet"
    )
    p.add_argument("--limit", type=int, default=None, help="smoke test: N evenly spaced hexes")
    a = p.parse_args(argv)
    cells = select_land_cells()
    if a.limit:
        cells = cells[:: max(1, len(cells) // a.limit)][: a.limit]
    df = terrain_table(cells, a.tiles)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out, index=False)
    print(
        f"wrote {a.out}: {df['slope_p50_deg'].notna().sum()} of {len(df)} hexes have terrain values"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
