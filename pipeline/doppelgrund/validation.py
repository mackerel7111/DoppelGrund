"""Validation by rediscovery (spec 02 task 2.11, requirement R11, plan section 10).

For every documented Earth analogue site, where does its hex rank among all Earth hexes when scored
against the target it was used for? Reported as recall@k, median percentile rank and MRR, against
random, terrain-only and unweighted baselines, with bootstrap CIs over sites.

Design choices (each is a human decision to confirm at Gate G2):

* ``spec`` mode (headline): only sites with a ``documented_target_id`` in known_sites.csv.
* ``body`` mode (labelled, weaker): a site is paired with every landmark of its ``target_body``.
  Per-site metrics are the MEAN over its pairs, never the best, which would inflate recall.
* A site is matched on its hex plus ring 1 (plan 10.1); the best-ranked eligible cell counts. That
  is best-of-several, so the random baseline is simulated with the same rule, not k/N.
* Eligible = not masked, finite score and coverage >= coverage_floor, as in the app. A site whose
  cells are all masked or below the floor is a MISS (reason recorded). A site with no cell in the
  sample is "not_in_sample": not evaluable, left out of the denominator and listed.
* Groups a target has no data for get weight 0 and the rest are renormalised (lens_for_target).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import h3
import numpy as np
import pandas as pd

from doppelgrund.config import EXPECTED_FEATURES, REPO, Profiles, load_known_sites, load_profiles
from doppelgrund.harmonise import Scaler
from doppelgrund.ml.stability import lens_for_target
from doppelgrund.scoring import GROUPS, score

KS = (100, 500, 1000)
DIM_LENS = {"terrain": "landing_mobility", "cold_ice": "cold_volatiles",
            "composition": "geology_minerals"}  # fmt: skip
NOT_BUILT = ["PCA + kNN", "Cluster-conditioned (GMM)", "Cluster-conditioned (HDBSCAN)",
             "+ calibrated weights (leave-one-site-out)"]  # fmt: skip
STATUS_OK, STATUS_MISSING = "ok", "not_in_sample"


def md(df: pd.DataFrame) -> str:
    """GitHub markdown table (no tabulate dependency)."""
    cells = [
        [str(c) for c in df.columns],
        *[[str(v) for v in r] for r in df.itertuples(index=False)],
    ]
    row = lambda r: "| " + " | ".join(r) + " |"  # noqa: E731
    return "\n".join([row(cells[0]), row(["---"] * len(cells[0])), *map(row, cells[1:])])


class Inputs:
    """Earth table, targets, scaler and profiles of one interim folder."""

    def __init__(self, interim: Path):
        interim = Path(interim)
        self.prof: Profiles = load_profiles()
        self.earth = pd.read_parquet(interim / "earth_features.parquet")
        self.targets = pd.read_parquet(interim / "targets.parquet").set_index(
            "target_id", drop=False
        )
        self.scaler = Scaler.from_json(interim / "scaler.json")
        lith = [f"lith_{c}" for c in self.prof.lith_classes]
        self.X = self.earth[list(EXPECTED_FEATURES)].to_numpy(float)
        self.L = self.earth[lith].to_numpy(float)
        masked = self.earth["masked"].to_numpy(bool) if "masked" in self.earth else None
        self.flags = (np.zeros(len(self.earth), bool) if masked is None else masked).astype(
            np.uint8
        )
        self.lith_cols = lith
        self.row_of = {c: i for i, c in enumerate(self.earth["h3"])}
        self._cache: dict[tuple[str, str], np.ndarray] = {}

    def target_vec(self, tid: str) -> tuple[np.ndarray, np.ndarray | None]:
        t = self.targets.loc[tid]
        x = np.array([t[n] for n in EXPECTED_FEATURES], float)
        lt = np.array([t[c] for c in self.lith_cols], float)
        return x, (lt if np.isfinite(lt).all() else None)

    def scores(self, tid: str, method: str) -> np.ndarray:
        """float64 (N,) score of every Earth row, NaN where not eligible (cached)."""
        key = (tid, method)
        if key not in self._cache:
            self._cache[key] = self._score(tid, method)
        return self._cache[key]

    def _score(self, tid: str, method: str) -> np.ndarray:
        prof = self.prof
        x, lt = self.target_vec(tid)
        if (
            method == "unweighted"
        ):  # equal weight on every measured feature (lithology counts as one)
            w_num, w_lith = np.isfinite(x).astype(float), float(lt is not None)
        elif method == "terrain_only":
            w = lens_for_target(prof, {g: float(g == "terrain") for g in GROUPS}, x, lt)
            w_num, w_lith = prof.feature_weights(w)
        else:  # a lens id
            w_num, w_lith = prof.feature_weights(lens_for_target(prof, method, x, lt))
        transforms = [f.transform for f in prof.features]
        gof = [GROUPS.index(f.group) for f in prof.features]
        r = score(
            self.X, self.L, self.flags, x, lt, self.scaler, transforms, gof,
            w_num, w_lith, prof.compat_matrix,
        )  # fmt: skip
        ok = np.isfinite(r.S) & (r.coverage >= float(prof.params["coverage_floor"]))
        return np.where(ok, r.S, np.nan).astype(np.float64)


def site_pairs(sites: pd.DataFrame, targets: pd.DataFrame, mode: str) -> pd.DataFrame:
    """(site_id, target_id, dimension) rows for ``mode`` 'spec' or 'body'."""
    rows = []
    for s in sites.itertuples():
        if mode == "spec":
            tids = [s.documented_target_id] if isinstance(s.documented_target_id, str) else []
        else:
            tids = targets.index[targets["body"] == s.target_body].tolist()
        rows += [(s.site_id, t, s.dimension) for t in tids if t in targets.index]
    return pd.DataFrame(rows, columns=["site_id", "target_id", "dimension"])


def candidate_rows(lat: float, lon: float, row_of: dict[str, int]) -> list[int]:
    """Rows of the site's hex and its six ring-1 neighbours that are present in the table."""
    cells = h3.grid_disk(h3.latlng_to_cell(lat, lon, 4), 1)
    return [row_of[c] for c in cells if c in row_of]


def rank_pair(S: np.ndarray, cand: Sequence[int]) -> tuple[str, int, int]:
    """(status, rank, n_eligible): rank 1 = best; a miss gets rank n_eligible + 1."""
    n = int(np.isfinite(S).sum())
    if not cand:
        return STATUS_MISSING, n + 1, n
    ok = [i for i in cand if np.isfinite(S[i])]
    if not ok:
        return "ineligible", n + 1, n  # masked or below the coverage floor
    best = max(S[i] for i in ok)
    return STATUS_OK, int((S[np.isfinite(S)] > best).sum()) + 1, n  # ties share the better rank


def pair_metrics(rank: np.ndarray, n: np.ndarray) -> dict[str, np.ndarray]:
    out = {f"recall@{k}": (rank <= k).astype(float) for k in KS}
    out["pct_rank"] = np.minimum(rank / np.maximum(n, 1), 1.0)
    out["mrr"] = 1.0 / rank
    return out


def random_metrics(n_cand: int, n: int, rng: np.random.Generator, draws: int = 200) -> dict:
    """Expected per-pair metrics of random scores under the same best-of-candidates rule.

    ponytail: ranks drawn with replacement (collisions are negligible for n >> 7)."""
    if n_cand == 0 or n == 0:
        rank = np.full(draws, n + 1)
    else:
        rank = rng.integers(1, n + 1, size=(draws, n_cand)).min(axis=1)
    m = pair_metrics(rank, np.full(draws, n))
    return {k: float(v.mean()) for k, v in m.items()}


def evaluate(
    inp: Inputs, sites: pd.DataFrame, mode: str, seed: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-pair table (all methods) and per-site metrics table (evaluable sites only)."""
    rng = np.random.default_rng(seed)
    pairs = site_pairs(sites, inp.targets, mode)
    where = sites.set_index("site_id")
    recs = []
    for p in pairs.itertuples():
        s = where.loc[p.site_id]
        cand = candidate_rows(float(s.lat), float(s.lon), inp.row_of)
        methods = ["unweighted", "terrain_only", "balanced"]
        if p.dimension in DIM_LENS:
            methods.append(DIM_LENS[p.dimension])
        for m in methods:
            status, rank, n = rank_pair(inp.scores(p.target_id, m), cand)
            name = "profile_dimension_lens" if m in DIM_LENS.values() else m
            recs.append((p.site_id, p.target_id, name, status, rank, n))
        S = inp.scores(p.target_id, "balanced")
        n_ok = int(np.isfinite(S).sum())
        n_cand = sum(bool(np.isfinite(S[i])) for i in cand) if cand else 0
        recs.append(
            (p.site_id, p.target_id, "random", STATUS_OK if cand else STATUS_MISSING, -1, n_ok)
        )
        recs[-1] += (random_metrics(n_cand, n_ok, rng),)
    cols = ["site_id", "target_id", "method", "status", "rank", "n_eligible"]
    base = [r[:6] for r in recs]
    per_pair = pd.DataFrame(base, columns=cols)
    rand = {(r[0], r[1]): r[6] for r in recs if r[2] == "random"}
    rows = []
    for (site, method), g in per_pair[per_pair.status != STATUS_MISSING].groupby(
        ["site_id", "method"]
    ):
        if method == "random":
            ms = [rand[(site, t)] for t in g.target_id]
            m = {k: float(np.mean([x[k] for x in ms])) for k in ms[0]}
        else:
            m = {
                k: float(v.mean())
                for k, v in pair_metrics(
                    g["rank"].to_numpy(float), g["n_eligible"].to_numpy(float)
                ).items()
            }
        rows.append({"site_id": site, "method": method, "n_pairs": len(g), **m})
    metric_cols = ["site_id", "method", "n_pairs", *(f"recall@{k}" for k in KS), "pct_rank", "mrr"]
    return per_pair, pd.DataFrame(rows, columns=metric_cols)


def boot_ci(x: np.ndarray, stat, idx: np.ndarray) -> tuple[float, float]:
    if len(x) < 2:
        return float("nan"), float("nan")
    v = np.array([stat(x[i]) for i in idx])
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def summarise(per_site: pd.DataFrame, boots: int = 2000, seed: int = 0) -> pd.DataFrame:
    """One row per method: metrics over sites, bootstrap 95% CIs, paired diff vs the baseline."""
    if per_site.empty:  # no evaluable site (e.g. none of them is in the sample)
        return pd.DataFrame()
    wide = {m: g.set_index("site_id") for m, g in per_site.groupby("method")}
    sites = sorted(set.intersection(*(set(g.index) for g in wide.values()))) if wide else []
    n = len(sites)
    idx = np.random.default_rng(seed).integers(0, max(n, 1), size=(boots, max(n, 1)))
    stats = {"recall@500": np.mean, "pct_rank": np.median, "mrr": np.mean}
    stats.update({f"recall@{k}": np.mean for k in KS if k != 500})
    base = wide.get("balanced")
    out = []
    for m, g in wide.items():
        g = g.loc[sites]
        row = {"method": m, "n_sites": n}
        for k, f in stats.items():
            x = g[k].to_numpy(float)
            lo, hi = boot_ci(x, f, idx) if n else (np.nan, np.nan)
            row[k] = float(f(x)) if n else np.nan
            row[f"{k}_ci"] = f"[{lo:.3f}, {hi:.3f}]"
        for k in ("pct_rank", "recall@500"):  # paired difference to the profile-weighted baseline
            if base is not None and n:
                d = g[k].to_numpy(float) - base.loc[sites, k].to_numpy(float)
                lo, hi = boot_ci(d, np.mean, idx)
                row[f"{k}_diff_vs_balanced"] = f"{d.mean():+.3f} [{lo:.3f}, {hi:.3f}]"
        out.append(row)
    return pd.DataFrame(out)


def write_report(
    out: Path,
    inp: Inputs,
    results: dict[str, tuple[pd.DataFrame, pd.DataFrame]],
    sites: pd.DataFrame,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    n_all = len(inp.earth)
    lines = [
        "# Ablation (spec 02 task 2.11)",
        "",
        f"Earth table: N = {n_all} hexes. Random baseline simulated with the same ring-1 "
        "best-of rule (not k/N). `profile_dimension_lens` = the lens matching the site's "
        "dimension; `balanced` is the profile-weighted baseline. Percentile rank: lower is better.",
        "",
        "**Smoke-test status: a harness check, not a Gate G2 result, unless a human has reviewed "
        "the site list and documented targets.**",
        "",
    ]
    for mode, (per_pair, per_site) in results.items():
        summ = summarise(per_site)
        summ.to_csv(out / f"ablation_{mode}.csv", index=False)
        used = per_site["site_id"].nunique()
        miss = sorted(set(per_pair.loc[per_pair.status == STATUS_MISSING, "site_id"]))
        n_pairs = int((per_pair.method == "balanced").sum())
        absent = f" ({', '.join(miss)})" if miss else ""
        lines += [
            f"## Mode: {mode}",
            "",
            f"Sites evaluated: {used}; pairs: {n_pairs}; not in sample (not evaluable, outside "
            f"the denominator): {len(miss)}{absent}",
            "",
        ]
        if len(summ):
            lines += [md(summ.round(3)), ""]
        lines += ["Not built yet: " + "; ".join(NOT_BUILT) + " (tasks 2.9 and 2.12).", ""]
        bal = per_pair[(per_pair.method == "balanced") & (per_pair.status != STATUS_MISSING)]
        if len(bal):
            tab = bal.assign(pct=(bal["rank"] / bal["n_eligible"].clip(lower=1)).round(3))
            tab["status"] = tab["status"].replace(
                {"ineligible": "miss: masked or below coverage floor"}
            )
            show = tab[["site_id", "target_id", "status", "rank", "n_eligible", "pct"]]
            lines += ["Per-pair rank under the balanced lens:", "", md(show), ""]
    (out / "ablation.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--interim", type=Path, default=REPO / "data/interim/real")
    ap.add_argument("--out", type=Path, default=REPO / "data/interim/validation")
    a = ap.parse_args(argv)
    inp, sites = Inputs(a.interim), load_known_sites()
    results = {mode: evaluate(inp, sites, mode) for mode in ("spec", "body")}
    write_report(a.out, inp, results, sites)
    print(f"wrote {a.out / 'ablation.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
