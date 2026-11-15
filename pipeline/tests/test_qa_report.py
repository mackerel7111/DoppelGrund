"""QA report (spec 01 task 1.18): findings, statistics, histograms, maps and the landmark table."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from doppelgrund.config import EXPECTED_FEATURES
from doppelgrund.fixtures import synthetic as syn
from doppelgrund.qa import report as R


def make_interim(tmp_path: Path, plant: bool = True) -> Path:
    t = syn.make_synthetic(20261114, 400)
    earth = t["earth_features"].copy()
    if plant:
        earth.loc[0, "slope_p50_deg"] = 95.0  # impossible: slope above 90 degrees
        earth.loc[1, "frac_below_0C"] = 1.5  # impossible: a fraction above 1
    d = tmp_path / "interim"
    d.mkdir()
    earth.to_parquet(d / "earth_features.parquet")
    for k in ("moon_discs", "mars_discs", "targets"):
        t[k].to_parquet(d / f"{k}.parquet")
    return d


def test_report_lists_planted_errors_and_unmeasured_features(tmp_path: Path) -> None:
    d = make_interim(tmp_path)
    page = R.build_report(d)
    assert "earth slope_p50_deg: 1 of" in page and "earth frac_below_0C: 1 of" in page
    assert "mars lst_mean_K: not measured (all NaN)" in page  # Mars thermal is NaN by contract
    assert page.index("Findings") < page.index("Statistics") < page.index("Histograms and maps")
    for name in EXPECTED_FEATURES:
        assert f'id="{name}"' in page
    assert page.count("<svg") > 3 * len(
        EXPECTED_FEATURES
    )  # a histogram or map per body and feature
    assert "<h2>Landmarks</h2>" in page
    assert "Earth by latitude band" in page and "|lat| band" in page


def test_main_writes_the_html_file(tmp_path: Path) -> None:
    d = make_interim(tmp_path, plant=False)
    out = tmp_path / "qa"
    assert R.main(["--interim", str(d), "--out", str(out)]) == 0
    text = (out / "report.html").read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>") and "tables_info.json not found" in text


def test_svg_helpers_handle_empty_and_nan_input() -> None:
    assert "not measured" in R.svg_hist(np.array([]))
    assert "not measured" in R.svg_map(np.array([0.0]), np.array([0.0]), np.array([np.nan]))
    assert "<rect" in R.svg_hist(np.array([1.0, 1.0, 1.0]))  # constant values do not divide by zero
    m = R.svg_map(np.array([11.0, 10.5]), np.array([20.0, 21.0]), np.array([1.0, 3.0]))
    assert m.count("<rect") == 1  # both points fall in one 4-degree cell
    assert R.colour(0.0) == "#440154" and R.colour(1.0) == "#fde725" and R.colour(2.0) == "#fde725"


def test_lithology_fractions_that_do_not_sum_to_one_are_an_error() -> None:
    n = 5
    cols = [f"lith_{c}" for c in ("a", "b")]
    df = pd.DataFrame({name: np.zeros(n) + 1.0 for name in EXPECTED_FEATURES})
    df[cols[0]], df[cols[1]] = 0.9, 0.9  # sums to 1.8
    out = R.findings({"earth": df, "moon": df, "mars": df}, cols)
    assert any(lv == "error" and "lithology" in t for lv, t in out)
