"""Plan B terrain from ETOPO-style tiles: planes of known slope, tile edges, ocean, antimeridian."""

from __future__ import annotations

from pathlib import Path

import h3
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from doppelgrund.earth.terrain import COLS, PX_DEG, R_M, Tiles, hex_terrain, terrain_table

PX_PER_DEG = round(1 / PX_DEG)  # 240


def write_tile(path: Path, west: float, north: float, deg: float, fn) -> None:
    """A float32 GeoTIFF on the 15 arc-second grid; fn(lat, lon) gives the elevation in metres."""
    n = round(deg * PX_PER_DEG)
    lat = north - (np.arange(n) + 0.5) * PX_DEG
    lon = west + (np.arange(n) + 0.5) * PX_DEG
    z = fn(lat[:, None], lon[None, :]).astype(np.float32)
    with rasterio.open(
        path, "w", driver="GTiff", height=n, width=n, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_origin(west, north, PX_DEG, PX_DEG), nodata=np.nan,
    ) as dst:  # fmt: skip
        dst.write(z, 1)


def east_plane(slope_deg: float):
    """Elevation rising to the east at a true slope (metres per degree of longitude)."""
    k = np.tan(np.radians(slope_deg))
    return lambda lat, lon: 1000.0 + k * R_M * np.cos(np.radians(lat)) * np.radians(lon)


CELL = h3.latlng_to_cell(0.5, 0.5, 4)


def test_a_tilted_plane_gives_its_slope_and_the_fraction_below_10(tmp_path: Path) -> None:
    write_tile(tmp_path / "a.tif", 0.0, 2.0, 2.0, east_plane(8.0))
    t = Tiles(tmp_path)
    r = hex_terrain(t, CELL)
    assert r["slope_p50_deg"] == pytest.approx(8.0, abs=0.15)
    assert r["slope_p90_deg"] == pytest.approx(8.0, abs=0.15)
    assert r["frac_slope_lt_10deg"] == 1.0
    t.close()
    steep = tmp_path / "steep"
    steep.mkdir()
    write_tile(steep / "a.tif", 0.0, 2.0, 2.0, east_plane(12.0))
    t = Tiles(steep)
    r = hex_terrain(t, CELL)
    assert r["slope_p50_deg"] == pytest.approx(12.0, abs=0.15) and r["frac_slope_lt_10deg"] == 0.0
    t.close()


def test_relief_std_is_the_spread_of_elevation_over_the_hex(tmp_path: Path) -> None:
    write_tile(tmp_path / "a.tif", 0.0, 2.0, 2.0, east_plane(8.0))
    t = Tiles(tmp_path)
    z, mask, _ = __import__("doppelgrund.earth.terrain", fromlist=["hex_window"]).hex_window(
        t, CELL
    )
    r = hex_terrain(t, CELL)
    # tan(8 deg) = 0.14 and a res-4 hex is about 44 km wide: it rises about 6 km, so std is ~1.4 km
    assert 1000 < r["relief_std_m"] < 2000
    t.close()


def test_a_hex_spanning_two_tiles_is_read_across_the_edge(tmp_path: Path) -> None:
    fn = east_plane(5.0)
    write_tile(tmp_path / "w.tif", -0.5, 1.5, 1.0, fn)  # lon -0.5..0.5, lat 0.5..1.5
    write_tile(tmp_path / "e.tif", 0.5, 1.5, 1.0, fn)  # lon 0.5..1.5: the seam is at lon 0.5
    t = Tiles(tmp_path)
    r = hex_terrain(t, h3.latlng_to_cell(1.0, 0.5, 4))  # centred on the seam
    assert r["slope_p50_deg"] == pytest.approx(5.0, abs=0.2)
    assert r["slope_p90_deg"] == pytest.approx(5.0, abs=0.2)  # no artefact along the seam
    t.close()


def test_ocean_pixels_are_dropped_and_an_all_ocean_hex_is_nan(tmp_path: Path) -> None:
    def half_ocean(lat, lon):  # west of lon 0.5 is below sea level
        return np.where(lon < 0.5, -200.0, east_plane(8.0)(lat, lon))

    write_tile(tmp_path / "a.tif", 0.0, 2.0, 2.0, half_ocean)
    t = Tiles(tmp_path)
    r = hex_terrain(
        t, CELL
    )  # centred on the coast: only land pixels count, and not the shoreline cliff
    assert r["slope_p50_deg"] == pytest.approx(8.0, abs=0.3)
    assert r["slope_p90_deg"] < 20  # no spurious cliff from the ocean neighbours
    sea = hex_terrain(t, h3.latlng_to_cell(1.0, 0.1, 4))
    assert all(np.isnan(v) for v in sea.values())
    t.close()


def test_missing_tiles_read_as_no_data(tmp_path: Path) -> None:
    write_tile(tmp_path / "a.tif", 0.0, 2.0, 2.0, east_plane(8.0))
    r = hex_terrain(Tiles(tmp_path), h3.latlng_to_cell(40.0, 40.0, 4))  # far from any tile
    assert all(np.isnan(v) for v in r.values())


def test_hex_across_the_antimeridian_uses_both_sides(tmp_path: Path) -> None:
    fn = east_plane(6.0)

    def seamless(lat, lon):  # the same plane continued across +-180 (longitude wraps)
        return fn(lat, np.where(lon < 0, lon + 360.0, lon))

    write_tile(tmp_path / "east.tif", 178.0, 2.0, 2.0, seamless)  # lon 178-180
    write_tile(tmp_path / "west.tif", -180.0, 2.0, 2.0, seamless)  # lon -180 to -178
    cell = h3.latlng_to_cell(1.0, 179.99, 4)
    lngs = [p[1] for p in h3.cell_to_boundary(cell)]
    assert max(lngs) - min(lngs) > 180  # this hex really straddles the antimeridian
    r = hex_terrain(Tiles(tmp_path), cell)
    assert r["slope_p50_deg"] == pytest.approx(6.0, abs=0.2)
    assert r["frac_slope_lt_10deg"] == 1.0


def test_terrain_table_has_the_contract_columns(tmp_path: Path) -> None:
    write_tile(tmp_path / "a.tif", 0.0, 2.0, 2.0, east_plane(8.0))
    df = terrain_table([CELL, h3.latlng_to_cell(40.0, 40.0, 4)], tmp_path)
    assert list(df.columns) == ["h3", *COLS] and df["slope_p50_deg"].notna().tolist() == [
        True,
        False,
    ]
    assert all(df[c].dtype == np.float32 for c in COLS)
    with pytest.raises(FileNotFoundError):
        Tiles(tmp_path / "none")
