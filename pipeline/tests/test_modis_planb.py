"""Plan B thermal from MOD11C2-style grids: accumulation by hand, pixel mapping, a real file."""

from __future__ import annotations

from pathlib import Path

import h3
import numpy as np
import pytest

from doppelgrund.config import REPO
from doppelgrund.earth.modis import (
    COLS,
    FREEZE_K,
    HexPixels,
    ThermalAccumulator,
    build_hex_pixels,
    granule_month,
    kelvin,
    thermal_table,
)


def raw(k: float) -> int:
    """uint16 raw value for a temperature in K (scale 0.02)."""
    return int(round(k / 0.02))


def hp(owner: list[int], n_cells: int = 2) -> HexPixels:
    return HexPixels(
        tuple(f"c{i}" for i in range(n_cells)), np.arange(len(owner)), np.array(owner, np.int32)
    )


def test_granule_month_uses_the_first_day_of_the_composite() -> None:
    assert granule_month("MOD11C2.A2010001.061.2021154180139.hdf") == 1
    assert granule_month("MOD11C2.A2010361.061.x.hdf") == 12
    assert granule_month("MOD11C2.A2012061.061.x.hdf") == 3  # 2012 is a leap year: day 61 = 1 March
    with pytest.raises(ValueError):
        granule_month("other.hdf")


def test_kelvin_scales_and_masks_the_fill_value() -> None:
    k = kelvin(np.array([0, raw(300.0)], np.uint16))
    assert np.isnan(k[0]) and k[1] == pytest.approx(300.0)


def test_statistics_by_hand_on_one_pixel() -> None:
    # one pixel, two granules in different months: day 300 and 280 K, night 280 and 260 K
    acc = ThermalAccumulator(hp([0]))
    acc.add(np.array([raw(300.0)], np.uint16), np.array([raw(280.0)], np.uint16), 1)
    acc.add(np.array([raw(280.0)], np.uint16), np.array([raw(260.0)], np.uint16), 7)
    t = acc.table().iloc[0]
    assert t["lst_mean_K"] == pytest.approx(((300 + 280) / 2 + (280 + 260) / 2) / 2)  # 280
    assert t["diurnal_range_K"] == pytest.approx(20.0)  # day mean 290 - night mean 270
    assert t["annual_range_K"] == pytest.approx(290.0 - 270.0)  # Jan mean 290, Jul mean 270
    # day samples never freeze; night samples are 280 K (no) and 260 K (yes): (0 + 0.5) / 2
    assert t["frac_below_0C"] == pytest.approx(0.25)


def test_freezing_share_counts_day_and_night_samples_separately() -> None:
    acc = ThermalAccumulator(hp([0]))
    day = np.array([raw(FREEZE_K + 5)], np.uint16)  # warm by day
    cold = np.array([raw(FREEZE_K - 5)], np.uint16)  # frozen at night
    for m in (1, 2, 3, 4):
        acc.add(day, cold, m)
    t = acc.table().iloc[0]
    assert t["frac_below_0C"] == pytest.approx(0.5)  # day share 0, night share 1 -> mean 0.5
    assert t["lst_mean_K"] == pytest.approx(FREEZE_K, abs=0.05)  # the day/night mean is exactly 0 C


def test_hex_value_is_the_mean_over_its_valid_pixels_and_nan_without_any() -> None:
    acc = ThermalAccumulator(hp([0, 0, 1]))
    day = np.array([raw(300.0), raw(310.0), 0], np.uint16)  # third pixel (hex 1) is all fill
    night = np.array([raw(280.0), raw(290.0), 0], np.uint16)
    acc.add(day, night, 1)
    acc.add(day, night, 2)
    t = acc.table()
    assert t.loc[0, "lst_mean_K"] == pytest.approx(295.0)  # pixels (290, 300) -> 295
    assert t.loc[0, "diurnal_range_K"] == pytest.approx(20.0)
    assert t.loc[1, OUT0].__class__ is np.float32 and np.isnan(t.loc[1, OUT0])


OUT0 = "lst_mean_K"


def test_a_missing_night_makes_the_mean_nan_but_keeps_the_day_statistics_out_of_it() -> None:
    acc = ThermalAccumulator(hp([0]))
    acc.add(np.array([raw(300.0)], np.uint16), np.array([0], np.uint16), 1)
    t = acc.table().iloc[0]
    assert np.isnan(t["lst_mean_K"]) and np.isnan(t["diurnal_range_K"])
    assert t["frac_below_0C"] == 0.0  # the day samples still count for the freezing share
    assert np.isnan(t["annual_range_K"])  # needs both day and night and two months


def test_hex_pixels_cover_the_hex_area_and_wrap_the_antimeridian() -> None:
    cell = h3.latlng_to_cell(0.0, 10.0, 4)
    h = build_hex_pixels([cell])
    area_px = h3.cell_area(cell, unit="km^2") / (0.05 * 111.195) ** 2
    assert 0.8 * area_px < len(h) < 1.2 * area_px
    assert (h.owner == 0).all() and len(np.unique(h.idx)) == len(h.idx)
    edge = build_hex_pixels([h3.latlng_to_cell(0.0, 179.99, 4)])
    cols = edge.idx % COLS
    assert cols.min() < 20 and cols.max() > COLS - 20  # pixels on both sides of the +-180 seam


def test_hex_pixels_stay_inside_the_grid_near_the_poles() -> None:
    for lat in (89.0, -89.0):
        h = build_hex_pixels([h3.latlng_to_cell(lat, 20.0, 4)])
        assert len(h) > 0 and h.idx.min() >= 0 and h.idx.max() < 3600 * COLS


def test_a_real_granule_gives_plausible_probe_hex_values() -> None:
    files = sorted((REPO / "data/raw/earth_plan_b/modis/MOD11C2").glob("MOD11C2.A2010*.hdf"))[:2]
    if not files:
        pytest.skip("MOD11C2 downloads not present")
    pytest.importorskip("pyhdf")
    cells = [h3.latlng_to_cell(23.0, 10.0, 4)]  # Sahara
    t = thermal_table(cells, files, log=lambda m: None).iloc[0]
    assert 270 < t["lst_mean_K"] < 320 and 5 < t["diurnal_range_K"] < 40
    assert 0.0 <= t["frac_below_0C"] <= 1.0


def test_thermal_table_needs_files() -> None:
    with pytest.raises(FileNotFoundError):
        thermal_table(["8409b1bffffffff"], [])
    assert Path  # keep the import used
