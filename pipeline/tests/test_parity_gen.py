"""Parity vector generator (spec 02 task 2.4): required C7 cases, determinism, JSON validity."""

from __future__ import annotations

import json

from doppelgrund.config import load_profiles
from doppelgrund.export.parity import CONTRACT, build_cases, main

REQUIRED = {
    "all_valid",
    "partial_nan",
    "all_nan_row",
    "masked_rows",
    "zero_weight_groups",
    "ties",
    "antimeridian_neighbours",
    "identical_target_and_row",
}


def test_required_c7_cases_and_shapes() -> None:
    prof = load_profiles()
    cases = build_cases(prof)
    assert REQUIRED <= {c["name"] for c in cases}
    nf, ng = len(prof.features), len(prof.groups)
    for c in cases:
        n = len(c["earth_features"])
        assert all(len(r) == nf for r in c["earth_features"]) and len(c["target_features"]) == nf
        assert len(c["transforms"]) == nf == len(c["median"]) == len(c["s"])
        assert len(c["expected"]["S"]) == n and all(len(g) == ng for g in c["expected"]["group"])
        assert len(c["expected"]["cards"]) == ng + 1
    small = [c for c in cases if c["name"] != "synthetic_slice_500"]
    assert all(len(c["earth_features"]) <= 12 for c in small)
    assert (
        len(next(c for c in cases if c["name"] == "synthetic_slice_500")["earth_features"]) == 500
    )


def test_identical_row_scores_100_and_masked_and_nan_rows_are_null() -> None:
    cases = {c["name"]: c for c in build_cases(load_profiles())}
    assert cases["identical_target_and_row"]["expected"]["S"][0] == 100.0
    assert cases["masked_rows"]["expected"]["S"][0] is None  # row 0 is masked
    assert cases["all_nan_row"]["expected"]["S"][3] is None
    assert cases["all_nan_row"]["expected"]["coverage"][3] == 0.0


def test_output_is_deterministic_and_valid_json(tmp_path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert main(["--out", str(a)]) == 0 and main(["--out", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()
    doc = json.loads(a.read_text(), parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    assert doc["contract"] == CONTRACT  # parse_constant rejects NaN/Infinity tokens
