"""Plan B thermal: per-hex surface temperature from MODIS Terra MOD11C2 V061 (0.05 deg CMG).

Same four outputs as the Earth Engine route, computed from the downloaded 8-day files:

* ``lst_mean_K``       mean of the 10-year day mean and night mean (both must exist),
* ``diurnal_range_K``  day mean minus night mean,
* ``annual_range_K``   max minus min of the 12 calendar-month means of (day + night) / 2,
* ``frac_below_0C``    share of valid day samples < 273.15 K and of night samples, averaged.

Everything is accumulated per 0.05 degree pixel first and averaged over a hex afterwards, as the
Earth Engine reducers do. Only Terra (10:30 / 22:30) is used, so science invariant 6 holds; MOD21 is
not part of Plan B (HDF4 files, read with pyhdf). Pixel values: ``LST_Day_CMG`` and
``LST_Night_CMG`` are uint16 with scale 0.02 K and fill 0.

    python -m doppelgrund.earth.modis --files data/raw/earth_plan_b/modis/MOD11C2
"""

from __future__ import annotations

import argparse
import re
import warnings
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import h3
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from doppelgrund.config import REPO
from doppelgrund.export.index_map import unwrap

PX = 0.05  # degrees
ROWS, COLS = 3600, 7200
SCALE_K = 0.02
FREEZE_K = 273.15
OUT_COLS = ["lst_mean_K", "diurnal_range_K", "annual_range_K", "frac_below_0C"]
NAME_RE = re.compile(r"\.A(\d{4})(\d{3})\.")


@dataclass(frozen=True)
class HexPixels:
    """Pixel-to-hex map: flat pixel ``idx[k]`` (row * COLS + col) lies in hex ``owner[k]``."""

    cells: tuple[str, ...]
    idx: np.ndarray  # int64 (K,)
    owner: np.ndarray  # int32 (K,) index into cells

    def __len__(self) -> int:
        return len(self.idx)


def build_hex_pixels(cells: Sequence[str]) -> HexPixels:
    """Rasterise every hex onto the 0.05 degree grid (pixel centre inside the polygon)."""
    idx, owner = [], []
    for k, cell in enumerate(cells):
        boundary = h3.cell_to_boundary(cell)
        lats = [p[0] for p in boundary]
        lngs = unwrap([p[1] for p in boundary])
        r0, r1 = int(np.floor((90 - max(lats)) / PX)) - 1, int(np.ceil((90 - min(lats)) / PX)) + 1
        c0, c1 = int(np.floor((min(lngs) + 180) / PX)) - 1, int(np.ceil((max(lngs) + 180) / PX)) + 1
        img = Image.new("L", (c1 - c0, r1 - r0), 0)
        # pixel (r, c) has its centre at (r + 0.5, c + 0.5) in grid units; PIL fills pixel (x, y) if
        # its centre (x + 0.5, y + 0.5) is inside, so polygon vertices are given in grid units too
        pts = [((x + 180) / PX - c0, (90 - y) / PX - r0) for x, y in zip(lngs, lats, strict=True)]
        ImageDraw.Draw(img).polygon(pts, fill=1)
        rr, cc = np.nonzero(np.asarray(img, bool))
        rr, cc = rr + r0, (cc + c0) % COLS  # longitudes wrap
        keep = (rr >= 0) & (rr < ROWS)
        idx.append(rr[keep].astype(np.int64) * COLS + cc[keep])
        owner.append(np.full(int(keep.sum()), k, np.int32))
    cat = np.concatenate
    return HexPixels(tuple(cells), cat(idx) if idx else np.zeros(0, np.int64),
                     cat(owner) if owner else np.zeros(0, np.int32))  # fmt: skip


def granule_month(path: str | Path) -> int:
    """Calendar month of the first day of the 8-day composite named in the file."""
    m = NAME_RE.search(Path(path).name)
    if not m:
        raise ValueError(f"not a MODIS file name: {path}")
    return (date(int(m.group(1)), 1, 1) + timedelta(days=int(m.group(2)) - 1)).month


def read_lst(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """(day, night) uint16 grids (ROWS, COLS) from a MOD11C2 file; 0 is the fill value."""
    from pyhdf.SD import SD, SDC

    f = SD(str(path), SDC.READ)
    try:
        return f.select("LST_Day_CMG").get(), f.select("LST_Night_CMG").get()
    finally:
        f.end()


def kelvin(raw: np.ndarray) -> np.ndarray:
    """Scaled temperature in K as float64, NaN where the raw value is the fill 0."""
    return np.where(raw == 0, np.nan, raw.astype(np.float64) * SCALE_K)


class ThermalAccumulator:
    """Running per-pixel sums over granules; ``add`` once per file, ``table`` at the end."""

    def __init__(self, hp: HexPixels):
        n = len(hp)
        self.hp = hp
        z = lambda dt: np.zeros(n, dt)  # noqa: E731
        self.sum_d, self.sum_n = z(np.float64), z(np.float64)
        self.n_d, self.n_n = z(np.int32), z(np.int32)
        self.below_d, self.below_n = z(np.int32), z(np.int32)
        self.msum, self.mn = np.zeros((12, n), np.float64), np.zeros((12, n), np.int32)
        self.files = 0

    def add(self, day: np.ndarray, night: np.ndarray, month: int) -> None:
        """Add one granule: full (ROWS, COLS) uint16 grids or already-gathered 1-D arrays."""
        d, nt = (kelvin(a.reshape(-1)[self.hp.idx] if a.ndim == 2 else a) for a in (day, night))
        vd, vn = np.isfinite(d), np.isfinite(nt)
        self.sum_d += np.where(vd, d, 0.0)
        self.n_d += vd
        self.below_d += vd & (d < FREEZE_K)
        self.sum_n += np.where(vn, nt, 0.0)
        self.n_n += vn
        self.below_n += vn & (nt < FREEZE_K)
        both = vd & vn
        self.msum[month - 1] += np.where(both, (d + nt) / 2.0, 0.0)
        self.mn[month - 1] += both
        self.files += 1

    def pixel_stats(self) -> dict[str, np.ndarray]:
        """Per-entry (pixel) statistics before averaging over each hex."""
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_d = np.where(self.n_d > 0, self.sum_d / self.n_d, np.nan)
            mean_n = np.where(self.n_n > 0, self.sum_n / self.n_n, np.nan)
            monthly = np.where(self.mn > 0, self.msum / self.mn, np.nan)
            frac_d = np.where(self.n_d > 0, self.below_d / self.n_d, np.nan)
            frac_n = np.where(self.n_n > 0, self.below_n / self.n_n, np.nan)
        enough = np.isfinite(monthly).sum(axis=0) >= 2
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN slices are expected (sea)
            hi, lo = np.nanmax(monthly, axis=0), np.nanmin(monthly, axis=0)
            rng = np.where(enough, hi - lo, np.nan)
            frac = np.nanmean(np.vstack([frac_d, frac_n]), axis=0)
        return {
            "lst_mean_K": (mean_d + mean_n) / 2.0,
            "diurnal_range_K": mean_d - mean_n,
            "annual_range_K": rng,
            "frac_below_0C": frac,
        }

    def table(self) -> pd.DataFrame:
        """One row per hex: the mean of each pixel statistic over the hex's valid pixels."""
        k = len(self.hp.cells)
        out = {"h3": list(self.hp.cells)}
        for name, v in self.pixel_stats().items():
            ok = np.isfinite(v)
            tot = np.bincount(self.hp.owner[ok], weights=v[ok], minlength=k)
            cnt = np.bincount(self.hp.owner[ok], minlength=k)
            out[name] = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan).astype(np.float32)
        return pd.DataFrame(out)


def thermal_table(cells: Sequence[str], files: Iterable[Path], log=print) -> pd.DataFrame:
    """Per-hex thermal columns from MOD11C2 files (any date range)."""
    files = sorted(files)
    if not files:
        raise FileNotFoundError("no MOD11C2 .hdf files given")
    acc = ThermalAccumulator(build_hex_pixels(cells))
    for i, f in enumerate(files, 1):
        acc.add(*read_lst(f), granule_month(f))
        if i % 50 == 0 or i == len(files):
            log(f"{i}/{len(files)} files")
    return acc.table()


def main(argv: Sequence[str] | None = None) -> int:
    from doppelgrund.fixtures.synthetic import select_land_cells

    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--files", type=Path, default=REPO / "data/raw/earth_plan_b/modis/MOD11C2")
    p.add_argument(
        "--out", type=Path, default=REPO / "data/interim/real/earth_thermal_planb.parquet"
    )
    p.add_argument("--limit", type=int, default=None, help="smoke test: N evenly spaced hexes")
    a = p.parse_args(argv)
    cells = select_land_cells()
    if a.limit:
        cells = cells[:: max(1, len(cells) // a.limit)][: a.limit]
    df = thermal_table(cells, a.files.glob("*.hdf"))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out, index=False)
    print(f"wrote {a.out}: {df['lst_mean_K'].notna().sum()} of {len(df)} hexes have thermal values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
