"""Validation harness (spec 02 task 2.11): ranks, random baseline, eligibility, bootstrap."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from doppelgrund import validation as V
from doppelgrund.config import EXPECTED_FEATURES, KNOWN_SITE_COLUMNS, load_profiles
from doppelgrund.fixtures import synthetic as syn
from doppelgrund.harmonise import fit_scaler


def make_interim(tmp_path: Path) -> tuple[Path, pd.DataFrame, int]:
    """Synthetic interim folder where target 'plant' is an exact copy of Earth row ``i``."""
    t = syn.make_synthetic(20261114, 400)
    d = tmp_path / "interim"
    d.mkdir()
    earth, targets = t["earth_features"], t["targets"].copy()
    names, prof = list(EXPECTED_FEATURES), load_profiles()
    ok = earth[names].notna().all(axis=1) & ~earth.get(
        "masked", pd.Series(False, index=earth.index)
    )
    i = int(np.flatnonzero(ok)[0])
    lith = [c for c in earth.columns if c.startswith("lith_")]
    targets.loc[0, names + lith] = earth.loc[i, names + lith].to_numpy()
    targets.loc[0, ["target_id", "body"]] = ["plant", "moon"]
    for k, df in {"earth_features": earth, "targets": targets, "moon_discs": t["moon_discs"],
                  "mars_discs": t["mars_discs"]}.items():  # fmt: skip
        df.to_parquet(d / f"{k}.parquet")
    tr = [f.transform for f in prof.features]
    moon, mars = (t[k][names].to_numpy(float) for k in ("moon_discs", "mars_discs"))
    fit_scaler(earth[names].to_numpy(float), moon, mars, tr, names).to_json(d / "scaler.json")
    return d, earth, i


def one_site(earth: pd.DataFrame, i: int, target: str | None = "plant") -> pd.DataFrame:
    row = {c: None for c in KNOWN_SITE_COLUMNS}
    row.update(site_id="s", lat=float(earth["lat"].iat[i]), lon=float(earth["lng"].iat[i]),
               target_body="moon", documented_target_id=target, dimension="terrain")  # fmt: skip
    return pd.DataFrame([row])


def test_a_site_whose_hex_equals_the_target_ranks_first(tmp_path: Path) -> None:
    d, earth, i = make_interim(tmp_path)
    inp = V.Inputs(d)
    per_pair, per_site = V.evaluate(inp, one_site(earth, i), "spec")
    bal = per_pair[per_pair.method == "balanced"].iloc[0]
    assert bal.status == "ok" and bal["rank"] == 1
    m = per_site[per_site.method == "balanced"].iloc[0]
    assert m["recall@100"] == 1.0 and m["mrr"] == 1.0
    s = V.summarise(per_site)  # one site: runs, CIs are NaN
    assert s.loc[s.method == "balanced", "recall@500_ci"].iat[0] == "[nan, nan]"


def test_random_baseline_matches_k_over_n_for_a_single_cell() -> None:
    m = V.random_metrics(1, 1000, np.random.default_rng(1), draws=20000)
    assert abs(m["recall@100"] - 0.1) < 0.01 and abs(m["pct_rank"] - 0.5) < 0.02
    assert (
        V.random_metrics(7, 1000, np.random.default_rng(1), 20000)["recall@100"] > 0.3
    )  # best-of-7


def test_masked_site_is_a_miss_and_absent_site_is_not_evaluable() -> None:
    S = np.array([5.0, np.nan, 3.0, 9.0])
    assert V.rank_pair(S, [3]) == ("ok", 1, 3)
    assert V.rank_pair(S, [1]) == ("ineligible", 4, 3)  # all candidate cells ineligible: last place
    assert V.rank_pair(S, [])[0] == V.STATUS_MISSING


def test_spec_mode_needs_a_documented_target_and_body_mode_pairs_every_landmark(
    tmp_path: Path,
) -> None:
    d, earth, i = make_interim(tmp_path)
    inp = V.Inputs(d)
    sites = one_site(earth, i, target=None)
    assert len(V.site_pairs(sites, inp.targets, "spec")) == 0
    assert len(V.site_pairs(sites, inp.targets, "body")) == (inp.targets["body"] == "moon").sum()


def test_a_clearly_better_method_has_a_paired_ci_excluding_zero() -> None:
    rng = np.random.default_rng(0)
    n = 40
    rows = []
    for method, shift in (("balanced", 0.5), ("terrain_only", 0.2)):
        for s in range(n):
            pr = float(np.clip(shift + rng.normal(0, 0.03), 0, 1))
            zero = {"recall@100": 0.0, "recall@500": 0.0, "recall@1000": 0.0, "mrr": 0.0}
            rows.append(
                {"site_id": f"s{s}", "method": method, "n_pairs": 1, "pct_rank": pr, **zero}
            )
    out = V.summarise(pd.DataFrame(rows))
    diff = out.loc[out.method == "terrain_only", "pct_rank_diff_vs_balanced"].iat[0]
    hi = float(diff.split(",")[1].strip(" ]"))
    assert hi < 0  # terrain_only's percentile rank is clearly lower, CI excludes zero


def test_no_evaluable_site_gives_an_empty_summary_not_an_error(tmp_path: Path) -> None:
    d, earth, i = make_interim(tmp_path)
    far = one_site(earth, i)
    far["lat"], far["lon"] = -89.99, 0.0  # no table hex there
    per_pair, per_site = V.evaluate(V.Inputs(d), far, "spec")
    assert set(per_pair.status) == {V.STATUS_MISSING} and per_site.empty
    assert V.summarise(per_site).empty
    V.write_report(tmp_path / "out", V.Inputs(d), {"spec": (per_pair, per_site)}, far)
    assert "not in sample" in (tmp_path / "out" / "ablation.md").read_text(encoding="utf-8")
