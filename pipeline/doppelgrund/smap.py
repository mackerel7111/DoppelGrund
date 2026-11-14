"""SMAP SPL3FTP_E freeze/thaw cross-check for ``frac_below_0C`` (Earth only).

NEVER scored and never fused into a C1 feature: SMAP observes at 6 a.m. / 6 p.m. (not the 10:30 /
22:30 Terra overpasses), reports soil freeze/thaw (not skin temperature) and only exists from 2015,
so it breaks science-invariant 6 if mixed into ``frac_below_0C``. It is written to its own file
(``smap_crosscheck.parquet``) and only compared against the Terra-based feature.

Needs the ``smap`` extra and an Earthdata login (never stored in code)::

    python -m doppelgrund.smap --start 2016-01-01 --end 2019-12-31
Product facts (NSIDC user guide, V004, read 2026-11-14; TODO(verify) against a real granule):
  * HDF5, group ``Freeze_Thaw_Retrieval_Data_Global`` (the guide also spells it ``Retrival``).
  * ``freeze_thaw`` uint8: 0 thawed, 1 frozen, 254 fill; shape (AM/PM, rows, cols), AM = index 0.
  * ``retrieval_qual_flag`` bit 0: 1 = retrieval not attempted (too much open water).
  * The guide says the grids are 9 km but also gives array sizes of 406 x 964 (a 36 km grid): the
    shape is read from the file, never assumed.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from doppelgrund.config import REPO

logger = logging.getLogger(__name__)

SHORT_NAME, VERSION = "SPL3FTP_E", "004"
FROZEN, THAWED = 1, 0
OUT = REPO / "data/interim/real"


def find_group(keys: Iterable[str]) -> str:
    """Name of the global freeze/thaw group; tolerates the guide's ``Retrival`` spelling."""
    for k in keys:
        if k.startswith("Freeze_Thaw_Retr") and k.endswith("_Global"):
            return k
    raise KeyError("no Freeze_Thaw_Retr*_Global group in the granule")


def grid_hex_index(
    lat: np.ndarray, lon: np.ndarray, cells: Sequence[str], res: int = 4
) -> np.ndarray:
    """int32 array shaped like ``lat``: index into ``cells`` of the H3 cell of each grid centre.

    -1 where the centre is not finite / out of range (fill values) or its hex is not in ``cells``.
    """
    import h3  # imported here so the module loads without h3 pulled in for pure helpers

    lat, lon = np.asarray(lat, np.float64), np.asarray(lon, np.float64)
    ok = np.isfinite(lat) & np.isfinite(lon) & (np.abs(lat) <= 90.0) & (np.abs(lon) <= 180.0)
    row = {c: i for i, c in enumerate(cells)}
    out = np.full(lat.shape, -1, np.int32)
    for k in np.flatnonzero(ok.ravel()):
        out.ravel()[k] = row.get(
            h3.latlng_to_cell(float(lat.ravel()[k]), float(lon.ravel()[k]), res), -1
        )
    return out


def accumulate(
    ft: np.ndarray, qual: np.ndarray, hex_idx: np.ndarray, frozen: np.ndarray, valid: np.ndarray
) -> None:
    """Add one granule's samples to the per-hex counters, in place.

    ``ft`` and ``qual`` are (AM/PM, rows, cols) or (rows, cols); ``hex_idx`` is (rows, cols).
    A sample counts when freeze_thaw is 0 or 1 and the retrieval was attempted (qual bit 0 clear).
    """
    ft = np.asarray(ft)
    qual = np.asarray(qual)
    if ft.ndim == 2:
        ft, qual = ft[None], qual[None]
    if ft.shape[1:] != hex_idx.shape or qual.shape != ft.shape:
        raise ValueError(f"granule shape {ft.shape} does not match the hex index {hex_idx.shape}")
    n = len(frozen)
    for layer in range(ft.shape[0]):
        ok = (ft[layer] <= FROZEN) & ((qual[layer] & 1) == 0) & (hex_idx >= 0)
        valid += np.bincount(hex_idx[ok], minlength=n)
        frozen += np.bincount(hex_idx[ok & (ft[layer] == FROZEN)], minlength=n)


def frozen_fraction(frozen: np.ndarray, valid: np.ndarray, min_valid: int = 30) -> np.ndarray:
    """Share of valid samples that are frozen; NaN (not 0) under ``min_valid`` samples."""
    out = np.full(len(valid), np.nan, np.float32)
    ok = valid >= max(min_valid, 1)
    out[ok] = frozen[ok] / valid[ok]
    return out


def read_granule(path: Path) -> dict[str, np.ndarray]:
    """freeze_thaw, retrieval_qual_flag, latitude, longitude of the global group (needs h5py)."""
    import h5py

    with h5py.File(path, "r") as f:
        g = f[find_group(f.keys())]
        return {
            k: g[k][()] for k in ("freeze_thaw", "retrieval_qual_flag", "latitude", "longitude")
        }


def month_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Consecutive <= 31-day windows covering start..end inclusive (keeps downloads small)."""
    out, d = [], start
    while d <= end:
        e = min(d + timedelta(days=30), end)
        out.append((d, e))
        d = e + timedelta(days=1)
    return out


def smap_crosscheck(
    cells: Sequence[str], start: date, end: date, workdir: Path, min_valid: int = 30
) -> pd.DataFrame:
    """Per-hex frozen share from SMAP over start..end. NOT RUN here (needs earthaccess + a login).

    Credentials come from the environment or ~/.netrc via ``earthaccess.login()``; none is stored.
    """
    import earthaccess

    earthaccess.login()
    frozen = np.zeros(len(cells), np.int64)
    valid = np.zeros(len(cells), np.int64)
    hex_idx: np.ndarray | None = None
    workdir.mkdir(parents=True, exist_ok=True)
    for a, b in month_windows(start, end):
        hits = earthaccess.search_data(
            short_name=SHORT_NAME, version=VERSION, temporal=(a.isoformat(), b.isoformat())
        )
        for p in earthaccess.download(hits, str(workdir)):
            g = read_granule(Path(p))
            if hex_idx is None:  # the grid is fixed, so build the grid -> hex map once
                lat, lon = g["latitude"], g["longitude"]
                hex_idx = grid_hex_index(
                    lat[0] if lat.ndim == 3 else lat, lon[0] if lon.ndim == 3 else lon, cells
                )
                logger.info(
                    "granule grid %s, %d grid cells land in the hex set",
                    g["freeze_thaw"].shape,
                    (hex_idx >= 0).sum(),
                )
            accumulate(g["freeze_thaw"], g["retrieval_qual_flag"], hex_idx, frozen, valid)
            Path(p).unlink()  # keep the disk use at one month
        logger.info("%s..%s done", a, b)
    return pd.DataFrame(
        {
            "h3": list(cells),
            "smap_frozen_frac": frozen_fraction(frozen, valid, min_valid),
            "smap_valid_n": valid.astype(np.int32),
        }
    )


def compare(smap: pd.DataFrame, earth: pd.DataFrame) -> dict[str, float]:
    """Agreement of the SMAP frozen share with the Terra ``frac_below_0C`` where both exist."""
    from scipy.stats import spearmanr

    m = smap.merge(earth[["h3", "frac_below_0C"]], on="h3").dropna(
        subset=["smap_frozen_frac", "frac_below_0C"]
    )
    if len(m) < 3:
        return {"n_hex": float(len(m))}
    a, b = m["smap_frozen_frac"].to_numpy(float), m["frac_below_0C"].to_numpy(float)
    return {
        "n_hex": float(len(m)),
        "spearman": float(spearmanr(a, b).statistic),
        "mean_abs_diff": float(np.mean(np.abs(a - b))),
        "mean_signed_diff": float(np.mean(a - b)),  # SMAP minus Terra
    }


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--start", type=date.fromisoformat, default=date(2016, 1, 1))
    p.add_argument("--end", type=date.fromisoformat, default=date(2019, 12, 31))
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--min-valid", type=int, default=30, help="samples needed per hex")
    p.add_argument("--limit", type=int, default=None, help="smoke test: only N evenly spaced hexes")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from doppelgrund.fixtures.synthetic import select_land_cells

    cells = select_land_cells()
    if args.limit:
        cells = cells[:: max(1, len(cells) // args.limit)]
    args.out.mkdir(parents=True, exist_ok=True)
    df = smap_crosscheck(cells, args.start, args.end, args.out / "_smap_work", args.min_valid)
    df.to_parquet(args.out / "smap_crosscheck.parquet", index=False)
    feats = args.out / "earth_features.parquet"
    if feats.exists():
        print("SMAP vs Terra frac_below_0C:", compare(df, pd.read_parquet(feats)))
    print(
        f"wrote {args.out / 'smap_crosscheck.parquet'}: "
        f"{df['smap_frozen_frac'].notna().sum()} of {len(df)} hexes have a value"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
