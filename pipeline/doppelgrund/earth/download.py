"""Resumable no-login downloads for Plan B (docs/research/earth-plan-b-datasets.md).

* NOAA ETOPO 2022 15 arc-second ice-surface GeoTIFF tiles that touch land (tiles are named by
  their north-west corner: ``N75`` covers 60-75 N, ``W180`` covers 180-165 W).
* CGIAR Global Aridity Index v3.1, annual (figshare, CC BY 4.0).

A partial file is kept as ``<name>.part`` and continued with an HTTP Range request, so an
interrupted run resumes where it stopped. Finished files are recorded with size and sha256 in
``MANIFEST.csv``.

    python -m doppelgrund.earth.download --out data/raw/earth_plan_b             # no-login files
    python -m doppelgrund.earth.download --out data/raw/earth_plan_b --only modis  # Earthdata
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import platform
import re
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from doppelgrund.config import REPO

UA = {"User-Agent": "doppelgrund-download/0.1"}
ETOPO_BASE = "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/15s/15s_surface_elev_gtif/"
TILE_RE = re.compile(r"(ETOPO_2022_v1_15s_([NS])(\d+)([EW])(\d+)_surface\.tif)")
GAI_URL = "https://ndownloader.figshare.com/files/56300327"
GAI_NAME = "Global-AI_ET0__annual_v3_1.zip"
TILE_DEG = 15
CHUNK = 1 << 20
# MODIS 0.05-degree CMG products (NASA Earthdata login): short_name -> (version, [(start, end)]).
# Thermal and NDVI use the full 2010-2019 window; land cover barely changes, so two years.
EARTHDATA: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "MOD11C2": ("061", [("2010-01-01", "2019-12-31")]),
    "MOD13C2": ("061", [("2010-01-01", "2019-12-31")]),
    "MCD12C1": ("061", [("2010-01-01", "2010-12-31"), ("2019-01-01", "2019-12-31")]),
}
_lock = threading.Lock()


def tile_bbox(name: str) -> tuple[float, float, float, float]:
    """(lon0, lat0, lon1, lat1) of an ETOPO tile from its north-west-corner name."""
    m = TILE_RE.fullmatch(name)
    if not m:
        raise ValueError(f"not an ETOPO 15s surface tile name: {name}")
    lat = int(m.group(3)) * (1 if m.group(2) == "N" else -1)
    lon = int(m.group(5)) * (1 if m.group(4) == "E" else -1)
    return lon, lat - TILE_DEG, lon + TILE_DEG, lat


def land_tiles(listing_html: str, land) -> list[str]:
    """Tile names from the NOAA directory listing whose box touches the land geometry."""
    from shapely.geometry import box

    names = sorted({m.group(1) for m in TILE_RE.finditer(listing_html)})
    return [n for n in names if land.intersects(box(*tile_bbox(n)))]


def total_size(url: str, session: requests.Session) -> int:
    """File size via a 1-byte Range request (works through redirects that reject HEAD)."""
    r = session.get(url, headers={**UA, "Range": "bytes=0-0"}, stream=True, timeout=60)
    try:
        r.raise_for_status()
        cr = r.headers.get("Content-Range")
        if cr and "/" in cr:
            return int(cr.rsplit("/", 1)[1])
        return int(r.headers["Content-Length"])
    finally:
        r.close()


def download(url: str, dest: Path, tries: int = 8, session: requests.Session | None = None) -> Path:
    """Download ``url`` to ``dest``, resuming a ``.part`` file; verifies the final size."""
    dest = Path(dest)
    s = session or requests.Session()
    total = None
    for attempt in range(tries):
        try:
            total = total_size(url, s)
            break
        except requests.RequestException:
            time.sleep(min(60, 2**attempt))
    if total is None:
        raise OSError(f"{dest.name}: could not read the file size after {tries} tries")
    if dest.exists() and dest.stat().st_size == total:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    for attempt in range(tries):
        have = part.stat().st_size if part.exists() else 0
        if have > total:
            part.unlink()
            have = 0
        if have == total:
            break
        try:
            headers = {**UA, "Range": f"bytes={have}-"} if have else dict(UA)
            with s.get(url, headers=headers, stream=True, timeout=60) as r:
                r.raise_for_status()
                if have and r.status_code != 206:  # server ignored Range: start again
                    have = 0
                with open(part, "ab" if have else "wb") as f:
                    for chunk in r.iter_content(CHUNK):
                        f.write(chunk)
        except requests.RequestException:
            time.sleep(min(60, 2**attempt))
    if not part.exists() or part.stat().st_size != total:
        raise OSError(
            f"{dest.name}: got {part.stat().st_size if part.exists() else 0} of {total} bytes"
        )
    part.replace(dest)
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def record(manifest: Path, url: str, path: Path) -> None:
    with _lock:
        new = not manifest.exists()
        with open(manifest, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["file", "bytes", "sha256", "url"])
            w.writerow([path.name, path.stat().st_size, sha256(path), url])


def known(manifest: Path) -> set[str]:
    if not manifest.exists():
        return set()
    with open(manifest, newline="", encoding="utf-8") as f:
        return {row["file"] for row in csv.DictReader(f)}


def use_home_netrc() -> None:
    """earthaccess looks for ~/_netrc on Windows; point NETRC at ~/.netrc instead of copying it."""
    home = Path.home()
    if platform.system() == "Windows" and "NETRC" not in os.environ:
        if (home / ".netrc").is_file() and not (home / "_netrc").is_file():
            os.environ["NETRC"] = str(home / ".netrc")


def earthdata_jobs(out: Path, products=None) -> list[tuple[str, Path]]:
    """(url, dest) for every granule of the MODIS products (needs earthaccess + a login)."""
    import earthaccess

    jobs: dict[str, tuple[str, Path]] = {}
    for short, (version, windows) in (products or EARTHDATA).items():
        n = 0
        for a, b in windows:
            for g in earthaccess.search_data(short_name=short, version=version, temporal=(a, b)):
                url = next(link for link in g.data_links() if link.endswith(".hdf"))
                jobs[url] = (url, out / "modis" / short / Path(url).name)
                n += 1
        print(f"{short} v{version}: {n} granules", flush=True)
    return sorted(jobs.values(), key=lambda j: str(j[1]))


def run(
    jobs: list[tuple[str, Path]],
    manifest: Path,
    workers: int = 3,
    log: Callable[[str], None] = print,
    session: requests.Session | None = None,
) -> None:
    """Download every (url, dest) job, skipping files already finished and recorded."""
    done_already = known(manifest)
    todo = [(u, d) for u, d in jobs if d.name not in done_already or not d.exists()]
    log(f"{len(todo)} of {len(jobs)} files to fetch")
    counter = {"n": 0}

    failed: list[str] = []

    def one(job: tuple[str, Path]) -> None:
        url, dest = job
        try:
            download(url, dest, session=session)
            record(manifest, url, dest)
        except Exception as e:  # keep going; report every failure at the end
            with _lock:
                failed.append(dest.name)
                log(f"FAILED {dest.name}: {type(e).__name__}: {e}")
            return
        with _lock:
            counter["n"] += 1
            log(f"[{counter['n']}/{len(todo)}] {dest.name} ({dest.stat().st_size / 1e6:.0f} MB)")

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, todo))
    if failed:
        raise OSError(
            f"{len(failed)} file(s) failed (run again to retry): " + ", ".join(failed[:10])
        )


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--out", type=Path, default=REPO / "data/raw/earth_plan_b")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--only", choices=("etopo", "gai", "modis"), help="fetch just one group")
    a = p.parse_args(argv)
    if a.only == "modis":  # needs the Earthdata login; own manifest so it can run beside the others
        import earthaccess

        use_home_netrc()
        if not earthaccess.login(strategy="netrc").authenticated:
            raise SystemExit("Earthdata login failed")
        a.out.mkdir(parents=True, exist_ok=True)
        run(
            earthdata_jobs(a.out),
            a.out / "MANIFEST_modis.csv",
            a.workers,
            session=earthaccess.get_requests_https_session(),
        )
        print("all done")
        return 0
    jobs: list[tuple[str, Path]] = []
    if a.only in (None, "gai"):
        jobs.append((GAI_URL, a.out / "aridity_gai_v3_1" / GAI_NAME))
    if a.only in (None, "etopo"):
        from doppelgrund.fixtures.synthetic import load_land

        html = requests.get(ETOPO_BASE, headers=UA, timeout=60).text
        jobs += [
            (ETOPO_BASE + n, a.out / "etopo2022_15s_surface" / n)
            for n in land_tiles(html, load_land())
        ]
    a.out.mkdir(parents=True, exist_ok=True)
    run(jobs, a.out / "MANIFEST.csv", a.workers)
    print("all done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
