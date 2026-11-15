"""QA report for the real C2 tables (spec 01 task 1.18, Gate G1).

A human looks at this before real data supports any claim.
``python -m doppelgrund.qa.report --interim data/interim/real_partial --out data/interim/qa``

Writes one self-contained ``report.html`` (inline SVG, no plotting library): findings at the top
(impossible values, unusual values, features not measured), per-feature statistics for Earth, Moon
and Mars, a histogram and an equirectangular map of every feature, and the landmark table. It
judges nothing about the science; it makes outliers, NaN patterns and unit mistakes visible.
"""

from __future__ import annotations

import argparse
import html
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from doppelgrund.config import EXPECTED_FEATURES, REPO, load_profiles

BODIES = ("earth", "moon", "mars")
TABLE = {"earth": "earth_features", "moon": "moon_discs", "mars": "mars_discs"}
LATLON = {"earth": ("lat", "lng"), "moon": ("lat", "lon"), "mars": ("lat", "lon")}
INF = float("inf")
# Impossible values: a unit mistake or a bug, never real data. name -> (lowest, highest) allowed.
HARD = {
    "slope_p50_deg": (0, 90), "slope_p90_deg": (0, 90), "relief_std_m": (0, INF),
    "frac_slope_lt_10deg": (0, 1), "lst_mean_K": (0, 500), "diurnal_range_K": (0, INF),
    "annual_range_K": (0, INF), "frac_below_0C": (0, 1), "permafrost_prob": (0, 1),
    "aridity_index": (0, INF), "pit_cave_density_per_1000km2": (0, INF),
}  # fmt: skip
# Unusual values: (body, feature, low, high, largest share allowed outside). From the spec 01
# acceptance notes: Earth slope p50 0 to 40 deg, Earth lst_mean 200 to 330 K, Moon slope < 15.
SOFT = [
    ("earth", "slope_p50_deg", 0, 40, 0.01),
    ("earth", "lst_mean_K", 200, 330, 0.01),
    ("moon", "slope_p50_deg", 0, 15, 0.5),
]
COLORS = [(68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98), (253, 231, 37)]
CELL = 4  # degrees per map cell
NM = '<div class="nm">not measured</div>'


def colour(t: float) -> str:
    """Viridis-like hex colour for t in [0, 1]."""
    t = min(max(t, 0.0), 1.0) * (len(COLORS) - 1)
    i = min(int(t), len(COLORS) - 2)
    a, b, f = COLORS[i], COLORS[i + 1], t - i
    return "#" + "".join(f"{round(x + (y - x) * f):02x}" for x, y in zip(a, b, strict=True))


def num(x: float) -> str:
    return "—" if not np.isfinite(x) else f"{x:.4g}"


def finite(v: pd.Series) -> np.ndarray:
    x = pd.to_numeric(v, errors="coerce").to_numpy(float)
    return x[np.isfinite(x)]


def findings(tables: dict[str, pd.DataFrame], lith_cols: list[str]) -> list[tuple[str, str]]:
    """(level, text), level 'error' (impossible), 'warn' (unusual) or 'info' (not measured)."""
    out: list[tuple[str, str]] = []
    for body, df in tables.items():
        for name, (lo, hi) in HARD.items():
            x = finite(df[name])
            bad = (x < lo) | (x > hi)
            if bad.any():
                out.append((
                    "error",
                    f"{body} {name}: {int(bad.sum())} of {len(x)} values outside [{lo}, {hi}] "
                    f"(min {num(x.min())}, max {num(x.max())})",
                ))  # fmt: skip
        L = df[lith_cols].to_numpy(float)
        ok = np.isfinite(L).all(axis=1)
        bad_sum = np.abs(L.sum(axis=1) - 1) > 1e-3
        bad_range = (L < -1e-9).any(axis=1) | (L > 1 + 1e-9).any(axis=1)
        off = ok & (bad_sum | bad_range)
        if off.any():
            out.append(("error", f"{body} lithology: {int(off.sum())} rows do not sum to 1"))
        for feat in (*EXPECTED_FEATURES, *lith_cols):
            share = float(df[feat].isna().mean())
            if share == 1.0:
                out.append(("info", f"{body} {feat}: not measured (all NaN)"))
            elif share > 0.5:
                out.append(("info", f"{body} {feat}: {share:.0%} NaN"))
    for body, name, lo, hi, allowed in SOFT:
        x = finite(tables[body][name])
        share = float(((x < lo) | (x > hi)).mean()) if len(x) else 0.0
        if share > allowed:
            out.append((
                "warn",
                f"{body} {name}: {share:.1%} of values outside the expected range [{lo}, {hi}] "
                f"(allowed {allowed:.0%})",
            ))  # fmt: skip
    if "masked" in tables["earth"]:
        m = tables["earth"]["masked"].astype(bool)
        text = (
            f"earth: {int(m.sum())} of {len(m)} hexagons are masked ({m.mean():.0%}), never ranked"
        )
        out.append(("info", text))
    order = {"error": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda f: order[f[0]])


def svg_hist(x: np.ndarray, w: int = 220, h: int = 80, bins: int = 24) -> str:
    if len(x) == 0:
        return NM
    lo, hi = float(x.min()), float(x.max())
    if lo == hi:
        hi = lo + 1.0
    n, _ = np.histogram(x, bins=bins, range=(lo, hi))
    bw, top = w / bins, max(int(n.max()), 1)
    bars = "".join(
        f'<rect x="{i * bw:.1f}" y="{h - 14 - (h - 18) * c / top:.1f}" width="{bw - 1:.1f}" '
        f'height="{(h - 18) * c / top:.1f}" fill="#3b6ea8"/>'
        for i, c in enumerate(n)
        if c
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}">{bars}'
        f'<text x="0" y="{h - 2}" font-size="9">{num(lo)}</text>'
        f'<text x="{w}" y="{h - 2}" font-size="9" text-anchor="end">{num(hi)}</text></svg>'
    )


def svg_map(lat: np.ndarray, lon: np.ndarray, v: np.ndarray) -> str:
    ok = np.isfinite(v) & np.isfinite(lat) & np.isfinite(lon)
    if not ok.any():
        return NM
    cells = pd.DataFrame(
        {
            "x": ((lon[ok] + 180) // CELL).astype(int),
            "y": ((90 - lat[ok]) // CELL).astype(int),
            "v": v[ok],
        }
    )  # fmt: skip
    g = cells.groupby(["x", "y"], as_index=False)["v"].mean()
    lo, hi = np.percentile(g["v"], [2, 98])
    span = (hi - lo) or 1.0
    rects = "".join(
        f'<rect x="{r.x * CELL}" y="{r.y * CELL}" width="{CELL}" height="{CELL}" '
        f'fill="{colour((r.v - lo) / span)}"/>'
        for r in g.itertuples()
    )
    line = '<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#888" stroke-width=".3"/>'
    grat = "".join(line.format(x, 0, x, 180) for x in range(0, 361, 60))
    grat += "".join(line.format(0, y, 360, y) for y in range(0, 181, 30))
    return f'<svg viewBox="0 0 360 180" width="320" height="160" class="map">{grat}{rects}</svg>'


def stats_rows(tables: dict[str, pd.DataFrame], units: dict[str, str]) -> str:
    cols = ["feature", "unit", "body", "n finite", "NaN", "min", "p5", "median", "p95", "max"]
    rows = []
    for name in EXPECTED_FEATURES:
        for body in BODIES:
            x = finite(tables[body][name])
            q = np.percentile(x, [0, 5, 50, 95, 100]) if len(x) else [np.nan] * 5
            nan = float(tables[body][name].isna().mean())
            cells = [name, html.escape(units[name]), body, str(len(x)), f"{nan:.0%}"]
            rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in [*cells, *map(num, q)]) + "</tr>")
    head = "".join(f"<th>{c}</th>" for c in cols)
    return f"<table><tr>{head}</tr>{''.join(rows)}</table>"


BAND_FEATURES = ("slope_p50_deg", "slope_p90_deg", "relief_std_m", "lst_mean_K", "diurnal_range_K")


def band_table(earth: pd.DataFrame) -> str:
    """Median of the terrain and thermal features by absolute latitude band: a systematic drop
    poleward (for example a slope computed without the cos(latitude) correction) shows up here."""
    band = pd.cut(earth["lat"].abs(), [0, 15, 30, 45, 60, 75, 90], include_lowest=True)
    g = earth.groupby(band, observed=True)
    med, n = g[list(BAND_FEATURES)].median(), g.size()
    head = "".join(f"<th>{c}</th>" for c in ["|lat| band", "n", *BAND_FEATURES])
    rows = [
        f"<tr><td>{b}</td><td>{n[b]}</td>"
        + "".join(f"<td>{num(v)}</td>" for v in med.loc[b])
        + "</tr>"
        for b in med.index
    ]
    return f"<table><tr>{head}</tr>{''.join(rows)}</table>"


def feature_blocks(tables: dict[str, pd.DataFrame], units: dict[str, str]) -> str:
    out = []
    for name in EXPECTED_FEATURES:
        cols = []
        for body in BODIES:
            df = tables[body]
            la, lo = LATLON[body]
            v = pd.to_numeric(df[name], errors="coerce").to_numpy(float)
            cols.append(
                f"<div><h4>{body}</h4>{svg_hist(v[np.isfinite(v)])}"
                f"{svg_map(df[la].to_numpy(float), df[lo].to_numpy(float), v)}</div>"
            )
        title = f'<h3 id="{name}">{name} <small>({html.escape(units[name])})</small></h3>'
        out.append(f'<section>{title}<div class="row">{"".join(cols)}</div></section>')
    return "".join(out)


def cell_html(v: object) -> str:
    if isinstance(v, float) and not np.isfinite(v):
        return '<td class="na">—</td>'
    return f"<td>{html.escape(str(round(v, 3) if isinstance(v, float) else v))}</td>"


def target_table(targets: pd.DataFrame) -> str:
    cols = ["target_id", "body", "lat", "lon", *EXPECTED_FEATURES]
    head = "".join(f"<th>{c}</th>" for c in cols)
    rows = [
        "<tr>" + "".join(map(cell_html, r)) + "</tr>" for r in targets[cols].itertuples(index=False)
    ]
    return f"<table><tr>{head}</tr>{''.join(rows)}</table>"


CSS = """body{font:14px system-ui,sans-serif;margin:24px;max-width:1150px;color:#1b1f24}
h1{margin:0 0 4px}small{color:#667}table{border-collapse:collapse;margin:8px 0;font-size:12px}
td,th{border:1px solid #d0d7de;padding:2px 6px;text-align:right}th{background:#f3f5f7}
td:first-child,th:first-child{text-align:left}
.error{color:#b42318}.warn{color:#b54708}.info{color:#475467}.na{background:#fef0c7}
.row{display:flex;gap:16px;flex-wrap:wrap}.map{border:1px solid #d0d7de;background:#f8fafc}
.nm{color:#98a2b3;padding:8px 0}section{margin:18px 0;border-top:1px solid #e4e7ec}
h3{margin:8px 0 4px}h4{margin:4px 0}"""


def build_report(interim: Path) -> str:
    interim = Path(interim)
    prof = load_profiles()
    units = {f.name: f.unit for f in prof.features}
    lith_cols = [f"lith_{c}" for c in prof.lith_classes]
    tables = {b: pd.read_parquet(interim / f"{TABLE[b]}.parquet") for b in BODIES}
    targets = pd.read_parquet(interim / "targets.parquet")
    info_path = interim / "tables_info.json"
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.is_file() else {}
    found = findings(tables, lith_cols)
    n_err = sum(f[0] == "error" for f in found)
    n_warn = sum(f[0] == "warn" for f in found)
    if info:
        mode = f"Earth Engine mode: {'fast' if info.get('fast') else 'full'}, "
        mode += f"stride {info.get('stride', '?')}"
    else:
        mode = "tables_info.json not found: mode unknown"
    items = "".join(f'<li class="{lv}"><b>{lv}</b> {html.escape(t)}</li>' for lv, t in found)
    counts = ", ".join(f"{b}: {len(tables[b])} rows" for b in BODIES) + f", targets: {len(targets)}"
    note = (
        f"Map colour: mean per {CELL}° cell, 2nd to 98th percentile of each body; grey lines "
        "every 60° of longitude and 30° of latitude."
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>DoppelGrund QA report</title><style>{CSS}</style></head><body>"
        f"<h1>QA report: real tables</h1><p><small>{html.escape(str(interim))} · "
        f"{html.escape(mode)} · {counts}</small></p>"
        "<p>Gate G1: a human reviews this before real data supports any claim. It only makes "
        "problems visible; it does not judge the science.</p>"
        f"<h2>Findings: {n_err} errors, {n_warn} warnings</h2><ul>{items or '<li>none</li>'}</ul>"
        f"<h2>Statistics</h2>{stats_rows(tables, units)}"
        f"<h2>Earth by latitude band (median)</h2>{band_table(tables['earth'])}"
        f"<h2>Landmarks</h2>{target_table(targets)}"
        f"<h2>Histograms and maps</h2><p><small>{note}</small></p>{feature_blocks(tables, units)}"
        "</body></html>"
    )


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--interim", type=Path, default=REPO / "data/interim/real")
    ap.add_argument("--out", type=Path, default=REPO / "data/interim/qa")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.html").write_text(build_report(a.interim), encoding="utf-8")
    print(f"wrote {a.out / 'report.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
