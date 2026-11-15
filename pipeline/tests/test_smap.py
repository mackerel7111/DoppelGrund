"""SMAP cross-check: the pure parts (grid -> hex map, counting, fractions). No download is run."""

from __future__ import annotations

from datetime import date

import h3
import numpy as np
import pandas as pd
import pytest

from doppelgrund.smap import (
    accumulate,
    compare,
    find_group,
    frozen_fraction,
    grid_hex_index,
    month_windows,
)


def test_find_group_tolerates_the_guides_spelling() -> None:
    assert (
        find_group(["Metadata", "Freeze_Thaw_Retrival_Data_Global"])
        == "Freeze_Thaw_Retrival_Data_Global"
    )
    assert find_group(
        ["Freeze_Thaw_Retrieval_Data_Polar", "Freeze_Thaw_Retrieval_Data_Global"]
    ).endswith("Global")
    with pytest.raises(KeyError):
        find_group(["Metadata", "Freeze_Thaw_Retrieval_Data_Polar"])


def test_grid_hex_index_maps_points_and_rejects_fill_and_foreign_hexes() -> None:
    a, b = h3.latlng_to_cell(23.0, 10.0, 4), h3.latlng_to_cell(-24.0, -69.0, 4)
    cells = [a, b]
    lat = np.array([[23.0, -24.0, 70.0], [-9999.0, np.nan, 23.01]])
    lon = np.array([[10.0, -69.0, 20.0], [0.0, 0.0, 10.01]])
    idx = grid_hex_index(lat, lon, cells)
    assert idx.tolist() == [[0, 1, -1], [-1, -1, 0]]  # 70N is not in the set; fill/NaN are -1
    assert idx.dtype == np.int32


def test_accumulate_counts_by_hand() -> None:
    # layers AM, PM; one row of 4 grid cells -> hexes [0, 0, 1, -1]
    hex_idx = np.array([[0, 0, 1, -1]], np.int32)
    ft = np.array([[[1, 0, 254, 1]], [[1, 1, 0, 1]]], np.uint8)  # 254 = fill
    qual = np.zeros_like(ft, np.uint32)
    qual[1, 0, 1] = 1  # PM, second cell: retrieval not attempted (open water) -> excluded
    frozen, valid = np.zeros(2, np.int64), np.zeros(2, np.int64)
    accumulate(ft, qual, hex_idx, frozen, valid)
    # hex 0: AM 1,0 ; PM 1 (the other PM sample is excluded)  -> valid 3, frozen 2
    # hex 1: AM fill ; PM 0                                   -> valid 1, frozen 0
    assert valid.tolist() == [3, 1] and frozen.tolist() == [2, 0]
    accumulate(ft[0], qual[0], hex_idx, frozen, valid)  # a 2-D granule counts as one layer
    assert valid.tolist() == [5, 1] and frozen.tolist() == [3, 0]


def test_accumulate_rejects_a_different_grid() -> None:
    with pytest.raises(ValueError, match="does not match"):
        accumulate(
            np.zeros((2, 3, 3), np.uint8),
            np.zeros((2, 3, 3), np.uint32),
            np.zeros((2, 2), np.int32),
            np.zeros(1, np.int64),
            np.zeros(1, np.int64),
        )


def test_frozen_fraction_is_nan_not_zero_without_enough_samples() -> None:
    f = frozen_fraction(np.array([0, 3, 10]), np.array([0, 4, 40]), min_valid=30)
    assert np.isnan(f[0]) and np.isnan(f[1])  # no / too few samples: missing, never 0
    assert f[2] == pytest.approx(0.25)
    assert f.dtype == np.float32


def test_month_windows_cover_the_range_without_gaps() -> None:
    w = month_windows(date(2016, 1, 1), date(2016, 3, 10))
    assert w[0][0] == date(2016, 1, 1) and w[-1][1] == date(2016, 3, 10)
    assert all((b - a).days <= 30 for a, b in w)
    assert all(
        w[i + 1][0] == w[i][1] + (date(2016, 1, 2) - date(2016, 1, 1)) for i in range(len(w) - 1)
    )


def test_compare_reports_agreement_on_shared_hexes_only() -> None:
    smap = pd.DataFrame(
        {
            "h3": list("abcde"),
            "smap_frozen_frac": [0.0, 0.2, 0.9, np.nan, 0.5],
            "smap_valid_n": [50] * 5,
        }
    )
    earth = pd.DataFrame({"h3": list("abcdf"), "frac_below_0C": [0.0, 0.3, 0.8, 0.4, 0.1]})
    r = compare(smap, earth)
    assert r["n_hex"] == 3  # d has no SMAP value, e/f are not shared
    assert r["spearman"] == pytest.approx(1.0)
    assert r["mean_abs_diff"] == pytest.approx((0.0 + 0.1 + 0.1) / 3)
    assert r["mean_signed_diff"] == pytest.approx((0.0 - 0.1 + 0.1) / 3)
