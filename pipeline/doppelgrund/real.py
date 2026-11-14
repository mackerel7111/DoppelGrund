"""Real-data pipeline, stage 1: builds the C2 tables from data/raw (+ Earth Engine for Earth terrain/thermal/cover/aridity).

Local port of notebooks/01_datasets_features.ipynb (same code, module globals instead of notebook cells).

    python -m doppelgrund.real --ee-project MY_GCP_PROJECT            # full run (needs `earthengine authenticate`)
    python -m doppelgrund.real --no-ee --limit 200                    # smoke test: Moon + Mars only, Earth EE columns NaN

Writes earth_features / moon_discs / mars_discs / targets .parquet, tables_source.txt and
glim_ontology_proposal.csv to data/interim/real (never to web/public). Missing raw files are downloaded
(sha256-checked) into data/raw.
"""

from __future__ import annotations

import argparse
import json
import re
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from doppelgrund.config import (
    EXPECTED_FEATURES,
    REPO,
    load_crosswalk,
    load_landmarks,
    load_profiles,
)
from doppelgrund.fixtures.synthetic import (
    EARTH_R_KM,
    LITH_COLS,
    N_DISCS,
    fibonacci_lattice,
    haversine_km,
    load_land,
    select_land_cells,
    targets_table,
)

DATA = REPO / "data/raw"
OUT = REPO / "data/interim/real"
WORK = REPO / "data/interim/_work"  # scratch: unzipped permafrost, Diviner tables in flight
EE_PROJECT = ""
FETCH_DIVINER = (
    True  # False: skip the 2.8 GB Diviner download; Moon thermal stays NaN outside reduced bands
)
prof = load_profiles()
SEED, R_KM = prof.params["seed"], prof.params["footprint_radius_km"]
BODY_R_M = {"moon": 1_737_400.0, "mars": 3_396_190.0}
SCALE_M = 470  # stage-1 baseline for every body (LDEM_64 ~474 m, MOLA 463 m, Earth resampled)

import hashlib
import os

import requests

PDS = "https://pds-geosciences.wustl.edu"
FILES = {  # key: (url, sha256, path under DATA)
    "glim": (
        "https://epic.awi.de/31092/1/hartmann-moosdorf_2012.zip",
        "43b4ce3276b155d804db8ff9fb227d620b4c35015a4cf564eac4d06d2b69d88e",
        "earth_glim/hartmann-moosdorf_2012.zip",
    ),
    "perprob": (
        "https://store.pangaea.de/Publications/ObuJ-etal_2018/UiO_PEX_PERPROB_5.0_20181128_2000_2016_NH.zip",
        "d19338ada0c188eb99e1a06eeeccc8e4055f037aeff96590f61f2f427c3cac5d",
        "earth_permafrost/UiO_PEX_PERPROB_5.0_20181128_2000_2016_NH.zip",
    ),
    "gvp": (
        "https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=GVP-VOTW:Smithsonian_VOTW_Holocene_Volcanoes&outputFormat=application/json",
        None,
        "earth_volcanoes/Smithsonian_VOTW_Holocene_Volcanoes.geojson",
    ),  # live database, hash not stable
    "ldem": (
        PDS + "/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.img",
        "1c4958699d4cffd7e777d51421b6044bba300aa0bef286a544309efb082cdbd6",
        "moon_dem_stage1/ldem_64.img",
    ),
    "lpgrs": (
        PDS
        + "/lunar/lp-l-grs-5-elem-abundance-v1/lp_9001/data/lpgrs_high1_elem_abundance_2deg.tab",
        "e866953499813ec089067f1985dfb92fe7adc8957a2121bb115a3b27ea14e946",
        "moon_feo/lpgrs_high1_elem_abundance_2deg.tab",
    ),
    "mola": (
        "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif",
        "38a4eb0b4452855b8dabfac40a367b458555ab4c01b31235807ad0a53c031f4c",
        "mars_dem/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif",
    ),
    "tes_ti": (
        "http://tes.asu.edu/mineral_map/ti_nmap2003.bin",
        "ce28ab69365023cf3d85d8a12d9758f38d61f77c9b0af7580b5fbc186c3e1379",
        "mars_tes_ti/ti_nmap2003.bin",
    ),
    "tes_mask": (
        "http://web.archive.org/web/20070208014625id_/http://lasp.colorado.edu:80/inertia/nmsk2003.bin",
        "4d3ceb3160c83fa51eee464955b59aa0cc7933e66e540bbaa10cfd2b5f789ec9",
        "mars_tes_ti/nmsk2003.bin",
    ),
    "sim3292": (
        "https://pubs.usgs.gov/sim/3292/downloads/sim3292_database.zip",
        "ef75f059b1f2f5a47aff55e6c6e39500cf1ab65e743fabc5d463b97bc10b6541",
        None,
    ),  # zip only; shapefile extracted below
}
GCP_SHA = {  # band -> sha256 of the 156 MB raw table (data/raw/moon_diviner/SOURCE.md)
    "80n90n": "b8f5e30354e086bf0c5e3559c35f05aed0f3de887a2792dcf07a9b0f66837e5b",
    "70n80n": "82d6f73429410e08a8fdb4f41dab44cf278129ed8e47d8f0dd6667102defefb6",
    "60n70n": "2191949f8618239793b6d412fa937e2438386ec098f9adc09a82546c519bd0f8",
    "50n60n": "4f1c2a43dd7e61e715df560aaebd400e950e7edc1cc195dc62ff6c86d7b8b4a6",
    "40n50n": "5377ddbdfe226c216288c1116c20845fdf101a462847108ad887f11176b992e2",
    "30n40n": "5c69b39ef0173d1fb282b3e7e74ac1a5a43cd9c1dd956299f2c778715204cea3",
    "20n30n": "e15ea704b50adf16c25210dbc1669b965eb636fa81c90828778c853e8c2e21aa",
    "10n20n": "9c3fc386357f082f0c4b9b00e64682475478cf9449430832da684384d1f2c4b5",
    "00n10n": "d333fc13b605beff4d977bd78299d3dd4c98905ea9008f69f4ee45073d7bedea",
    "10s00s": "b47dd7ee7fe90ade46e376b4aa62bf153e8a9f2aeecd3593a32f3a514d61d981",
    "20s10s": "321033b7550795d8be70627c192f40779c5de757dacb42b36ff15e7d62854071",
    "30s20s": "08ec2886b74e4ce80096f983b4b352ee51defa2ab3089a060c2407bfe26c5a3b",
    "40s30s": "12c422698db88de3e9156e4c1aa4c94b2be97678cac2b05444caccc4fd32c344",
    "50s40s": "973609411fe7ab82f52f9b57c3a7d3f23753273a5934a92c1656b81505f5f5c4",
    "60s50s": "f050506f56618075a296f7544e10a5fd199d5d5fa82bc3a40053a99943f1d097",
    "70s60s": "c8c0ae10968961740a5fe80cddc97856ffeb1f83821587d0b6fe2114658c7294",
    "80s70s": "c6c9b3a84e1e9972237b07fd8dd1c0f44899ab8ffe9a403a7528ef7cd38b1cda",
    "90s80s": "4bc7093fe5bf08ca7fd0c7ddaf94f7c452b27f705fe975a73c8614d8d41e28b6",
}
GCP_BANDS = list(GCP_SHA)
GCP_URL = (
    PDS + "/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_gcp/global_cumul_avg_cyl_{}_002.tab"
)


def fetch(key, url, sha256, dest):
    """Download url to dest unless it exists; verify sha256 (None = live endpoint, hash only printed). Written as .part then renamed, so an existing file is complete."""
    dest = Path(dest)
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    h = hashlib.sha256()
    with (
        requests.get(
            url, stream=True, timeout=60, headers={"User-Agent": "doppelgrund-notebook"}
        ) as r,
        open(part, "wb") as f,
    ):
        r.raise_for_status()
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
            h.update(chunk)
    if sha256 and h.hexdigest() != sha256:
        part.unlink()
        raise ValueError(f"{key}: sha256 {h.hexdigest()} != expected {sha256}")
    os.replace(part, dest)
    print(f"fetched {key}: {dest.stat().st_size / 1e6:.0f} MB, sha256 {h.hexdigest()[:12]}")
    return dest


get = lambda key: fetch(key, *FILES[key][:2], DATA / FILES[key][2])


def mars_shapefile():
    """SIM 3292 geology shapefile under DATA; downloads the 809 MB zip to WORK only if it is missing, extracts the Geology members, deletes the zip."""
    d = DATA / "mars_geology/SIM3292_MarsGlobalGeologicGIS_20M/SIM3292_Shapefiles"
    shp = d / "SIM3292_Global_Geology.shp"
    if not shp.exists():
        z = fetch("sim3292", *FILES["sim3292"][:2], WORK / "sim3292_database.zip")
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if "/SIM3292_Shapefiles/SIM3292_Global_Geology." in n and n.rsplit(".", 1)[-1] in (
                    "shp",
                    "shx",
                    "dbf",
                    "prj",
                ):
                    d.mkdir(parents=True, exist_ok=True)
                    (d / n.rsplit("/", 1)[-1]).write_bytes(zf.read(n))
        z.unlink()
    return shp


def horn_slope_deg(z, dx, dy):
    """Horn 3x3 slope in degrees; z (m), dx/dy grid spacing (m). Edge ring is NaN."""
    p = np.pad(z.astype(np.float64), 1, mode="edge")
    a, b, c, d, f, g, h, i = (
        p[:-2, :-2],
        p[:-2, 1:-1],
        p[:-2, 2:],
        p[1:-1, :-2],
        p[1:-1, 2:],
        p[2:, :-2],
        p[2:, 1:-1],
        p[2:, 2:],
    )
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy)
    s = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    s[[0, -1], :] = np.nan
    s[:, [0, -1]] = np.nan
    return s


def terrain_stats(z, slope, mask):
    s = slope[mask & np.isfinite(slope)]
    if s.size < 9:
        return dict.fromkeys(EXPECTED_FEATURES[:4], np.nan)
    return dict(
        slope_p50_deg=np.percentile(s, 50),
        slope_p90_deg=np.percentile(s, 90),
        relief_std_m=float(np.nanstd(z[mask])),
        frac_slope_lt_10deg=float(np.mean(s < 10)),
    )


# self-check: a 10 degree plane gives 10 degrees
yy, xx = np.mgrid[0:20, 0:20]
assert abs(np.nanmedian(horn_slope_deg(np.tan(np.radians(10)) * 470 * xx, 470, 470)) - 10) < 1e-6

# Reducer outputs we need back, by the names the reducers give them (z_mean and z2_mean become relief_std_m)
EE_RAW = [
    "slope_p50_deg",
    "slope_p90_deg",
    "z_mean",
    "z2_mean",
    "frac_slope_lt_10deg",
    "lst_mean_K",
    "diurnal_range_K",
    "annual_range_K",
    "frac_below_0C",
    "barren_frac",
    "snow_ice_frac",
    "ndvi_mean",
    "aster_mafic_idx",
    "aridity_index",
]
EE_COLS = [c for c in EE_RAW if c not in ("z_mean", "z2_mean")] + ["relief_std_m"]


def earth_remote(cells, batch=2000):
    """Earth Engine reducers per hex. Terrain fuses GLO-30 + NASADEM, thermal fuses MOD11A2 + MOD21A1D/N (mean where both exist). Finished batches are kept in OUT/ee_batches/NNNN.parquet and skipped on a re-run (Colab disconnect). NOT RUN here: no Earth Engine credentials."""
    import ee
    import h3  # imported here so the offline run needs no earthengine-api

    if not EE_PROJECT:
        raise ValueError(
            "set EE_PROJECT (a Google Cloud project with Earth Engine enabled) in the first code cell"
        )
    try:
        ee.Initialize(project=EE_PROJECT)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=EE_PROJECT)
    # Mean where both DEMs have a pixel, else whichever has one (ImageCollection.mean ignores masked pixels).
    # NASADEM (SRTM, 2000) stops near +-60 deg, so poleward the DEM is GLO-30 alone (TODO(verify) the limit).
    glo = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM").mosaic()
    nasadem = ee.Image("NASA/NASADEM_HGT/001").select("elevation").rename("DEM")
    dem = ee.ImageCollection([glo, nasadem]).mean().setDefaultProjection("EPSG:4326", None, 30)
    z = dem.reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(
        "EPSG:4326", None, SCALE_M
    )
    kx = ee.Kernel.fixed(3, 3, [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], normalize=False)
    ky = ee.Kernel.fixed(3, 3, [[-1, -2, -1], [0, 0, 0], [1, 2, 1]], normalize=False)
    # ponytail: 'scale' is metres at the equator; EW shrink ignored, so poleward slopes are biased. Reproject for |lat|>60.
    gx = z.convolve(kx).divide(8 * SCALE_M)
    gy = z.convolve(ky).divide(8 * SCALE_M)
    slope = gx.hypot(gy).atan().multiply(180 / np.pi).rename("slope")
    terrain = (
        z.rename("z_mean")
        .addBands(z.pow(2).rename("z2_mean"))
        .addBands(slope.lt(10).rename("frac_slope_lt_10deg"))
    )
    lst = ee.ImageCollection("MODIS/061/MOD11A2").filterDate("2010-01-01", "2020-01-01")
    # MOD21A1D/N: Terra daily LST (K, scale already applied), same overpasses as MOD11A2, so science
    # invariant 6 holds. ponytail: ~7,300 daily images; if reducers time out, aggregate monthly or
    # shorten the window (record it in datasets.yaml). Aqua/VIIRS/ECOSTRESS/SMAP are NOT overpass-matched.
    d21 = ee.ImageCollection("MODIS/061/MOD21A1D").filterDate("2010-01-01", "2020-01-01")
    n21 = ee.ImageCollection("MODIS/061/MOD21A1N").filterDate("2010-01-01", "2020-01-01")

    def fuse(a, b):
        """Mean where both images have a pixel, else the one that does (masked pixels are ignored)."""
        return ee.ImageCollection([a, b]).mean()

    day = fuse(
        lst.select("LST_Day_1km").mean().multiply(0.02).rename("LST"),
        d21.select("LST_1KM").mean().rename("LST"),
    )
    night = fuse(
        lst.select("LST_Night_1km").mean().multiply(0.02).rename("LST"),
        n21.select("LST_1KM").mean().rename("LST"),
    )
    mean_ = lst.map(
        lambda i: (
            i.select("LST_Day_1km")
            .add(i.select("LST_Night_1km"))
            .multiply(0.01)
            .rename("m")
            .copyProperties(i, ["system:time_start"])
        )  # map() drops the timestamp calendarRange needs
    )
    months = ee.ImageCollection(
        [
            fuse(
                mean_.filter(ee.Filter.calendarRange(m, m, "month")).mean().rename("LST"),
                d21.filter(ee.Filter.calendarRange(m, m, "month"))
                .select("LST_1KM")
                .mean()
                .add(n21.filter(ee.Filter.calendarRange(m, m, "month")).select("LST_1KM").mean())
                .divide(2)
                .rename("LST"),
            )
            for m in range(1, 13)
        ]
    )
    # share of valid samples < 0 C, averaged over the two products (MOD21 pools its day and night samples)
    lt0 = lambda ic, b: ic.select(b).map(lambda i: i.lt(273.15)).mean().rename("f")
    below0 = fuse(
        mean_.map(lambda i: i.lt(273.15)).mean().rename("f"),
        fuse(lt0(d21, "LST_1KM"), lt0(n21, "LST_1KM")),
    )
    thermal = (
        day.add(night)
        .divide(2)
        .rename("lst_mean_K")
        .addBands(day.subtract(night).rename("diurnal_range_K"))
        .addBands(months.max().subtract(months.min()).rename("annual_range_K"))
        .addBands(below0.rename("frac_below_0C"))
    )
    lc = (
        ee.ImageCollection("MODIS/061/MCD12Q1")
        .filterDate("2010-01-01", "2020-01-01")
        .select("LC_Type1")
    )
    cover = (
        lc.map(lambda i: i.eq(16))
        .mean()
        .rename("barren_frac")
        .addBands(lc.map(lambda i: i.eq(15)).mean().rename("snow_ice_frac"))
    )
    ndvi = (
        ee.ImageCollection("MODIS/061/MOD13A2")
        .filterDate("2010-01-01", "2020-01-01")
        .select("NDVI")
        .mean()
        .multiply(0.0001)
        .rename("ndvi_mean")
    )
    ged = ee.Image("NASA/ASTER_GED/AG100_003")
    e = lambda n: ged.select(f"emissivity_band{n}")
    mafic = (
        e(13).add(e(14)).subtract(e(10)).subtract(e(11)).multiply(0.001).rename("aster_mafic_idx")
    )  # UNVERIFIED placeholder index
    tc = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterDate("2010-01-01", "2020-01-01")
    arid = (
        tc.select("pr").sum().divide(tc.select("pet").sum().multiply(0.1)).rename("aridity_index")
    )  # same 10-yr window in numerator and denominator; pet scaled x0.1
    # single-band images keep the reducer's own output name (p50, p90, mean), multi-band images keep band names; hence the renames
    groups = [
        (
            slope,
            ee.Reducer.percentile([50, 90]),
            SCALE_M,
            {"p50": "slope_p50_deg", "p90": "slope_p90_deg"},
        ),
        (terrain, ee.Reducer.mean(), SCALE_M, {}),
        (thermal, ee.Reducer.mean(), 1000, {}),
        (cover.addBands(ndvi), ee.Reducer.mean(), 500, {}),
        (mafic, ee.Reducer.mean(), 100, {"mean": "aster_mafic_idx"}),
        (arid, ee.Reducer.mean(), 4638, {"mean": "aridity_index"}),
    ]

    def reduce(hexes):
        fc = ee.FeatureCollection(
            [
                ee.Feature(
                    ee.Geometry.Polygon([[p[1], p[0]] for p in h3.cell_to_boundary(c)]), {"h3": c}
                )
                for c in hexes
            ]
        )
        got = [
            pd.DataFrame(
                [f["properties"] for f in img.reduceRegions(fc, red, sc).getInfo()["features"]]
            )
            .set_index("h3")
            .rename(columns=ren)
            for img, red, sc, ren in groups
        ]
        return pd.concat(got, axis=1)

    def finish(df):
        df = df.copy()
        df["relief_std_m"] = np.sqrt((df["z2_mean"] - df["z_mean"] ** 2).clip(lower=0))
        return df.reindex(
            columns=EE_COLS
        )  # a batch where a dataset has no pixels at all (e.g. ASTER in Antarctica) gets NaN, not a missing column

    probe = reduce(
        [h3.latlng_to_cell(23.0, 10.0, 4)]
    )  # a Sahara hex: every dataset covers it, so a missing column means a wrong output name
    miss = [c for c in EE_RAW if c not in probe.columns]
    if miss:
        raise KeyError(f"Earth Engine reducer output lacks {miss}; got {list(probe.columns)}")
    print(finish(probe).T.round(3))
    ck = OUT / "ee_batches"
    ck.mkdir(exist_ok=True)
    parts = []
    nb = -(-len(cells) // batch)
    for k in range(0, len(cells), batch):
        f = ck / f"{k // batch:04d}.parquet"
        hx = list(cells[k : k + batch])
        if f.exists() and set(pd.read_parquet(f).index) == set(hx):
            parts.append(pd.read_parquet(f))
            continue  # finished before a disconnect
        part = finish(reduce(hx)).reindex(hx)
        part.to_parquet(f)
        parts.append(part)
        print(f"batch {k // batch + 1}/{nb} done")
    return pd.concat(parts).rename_axis("h3").reset_index()


O = ["mafic_volcanic", "felsic_feldspathic", "carbonate", "siliciclastic", "evaporite", "ice"]
# GLiM first-level class -> ontology fractions (rows sum to 1, or all 0 for nd/wb). PROPOSAL for human review: config/ontology_crosswalk.csv is human-owned
GLIM = {
    "vb": [1, 0, 0, 0, 0, 0],
    "pb": [1, 0, 0, 0, 0, 0],
    "py": [0.5, 0.5, 0, 0, 0, 0],
    "va": [0, 1, 0, 0, 0, 0],
    "vi": [0, 1, 0, 0, 0, 0],
    "pa": [0, 1, 0, 0, 0, 0],
    "pi": [0, 1, 0, 0, 0, 0],
    "mt": [0, 0.5, 0, 0.5, 0, 0],
    "sc": [0, 0, 1, 0, 0, 0],
    "ss": [0, 0, 0, 1, 0, 0],
    "su": [0, 0, 0, 1, 0, 0],
    "sm": [0, 0, 0.3, 0.7, 0, 0],
    "ev": [0, 0, 0, 0, 1, 0],
    "ig": [0, 0, 0, 0, 0, 1],
    "nd": [0] * 6,
    "wb": [0] * 6,
}
GLIM_W = {
    **dict.fromkeys(GLIM, 1.0),
    "su": 0.5,
    "sm": 0.5,
    "mt": 0.5,
    "py": 0.5,
}  # low weight for unconsolidated/mixed (used when a cell holds several classes)
xw = load_crosswalk()


def crosswalk(source, codes, proposal):
    """Ontology fractions (n x 6, columns LITH_COLS) for unit codes. Rows of config/ontology_crosswalk.csv with this `source` win (human-owned); else `proposal`.
    Codes not in the table and all-zero rows (water, no data) give NaN."""
    rows = xw[xw["source"].str.lower() == source]
    table = rows.set_index("unit_code")[O].astype(float) if len(rows) else proposal
    out = np.array(table.reindex(list(codes)), float)
    out[~(np.nansum(out, axis=1) > 0)] = np.nan
    return pd.DataFrame(out, columns=LITH_COLS)


xyz = lambda la, lo: np.c_[
    np.cos(np.radians(la)) * np.cos(np.radians(lo)),
    np.cos(np.radians(la)) * np.sin(np.radians(lo)),
    np.sin(np.radians(la)),
]


def earth_local(cells):
    """GLiM lithology, permafrost, volcano tag and land fraction at the hex centres, from files under DATA.
    ponytail: centre sampling (GLiM 0.5 deg cell, permafrost 1 km pixel); upgrade = zonal mean over the hex polygon."""
    import h3
    import rasterio
    import shapely
    from pyproj import Transformer
    from scipy.spatial import cKDTree

    ll = np.array([h3.cell_to_latlng(c) for c in cells]).reshape(-1, 2)
    lat, lon = ll[:, 0], ll[:, 1]
    # GLiM: row 0 = +90, col 0 = -180, no .prj (EPSG:4326); value -> 2-letter code through Classnames.txt
    with zipfile.ZipFile(get("glim")) as zf:
        grid = np.loadtxt(zf.open("glim_wgs84_0point5deg.txt.asc"), skiprows=6, dtype=int)
        names = pd.read_csv(zf.open("Classnames.txt"), sep=";").set_index("Value_")["xx"]
    v = grid[
        np.clip(((90 - lat) / 0.5).astype(int), 0, 359),
        np.clip(((lon + 180) / 0.5).astype(int), 0, 719),
    ]
    lith = crosswalk(
        "glim", pd.Series(v).map(names), pd.DataFrame(GLIM, index=O).T
    )  # -9999 (no polygon) -> NaN
    # permafrost probability: unzip the 1.9 GB GeoTIFF to scratch once (reading inside the zip is too slow), polar stereographic EPSG:3995
    with zipfile.ZipFile(get("perprob")) as zf:
        tif = next(n for n in zf.namelist() if n.endswith(".tif"))
        if not (WORK / tif).exists():
            zf.extract(tif, WORK)
    perma = np.full(len(cells), np.nan)
    with rasterio.open(WORK / tif) as ds:
        x, y = Transformer.from_crs(4326, ds.crs.to_wkt(), always_xy=True).transform(lon, lat)
        col, row = (x - ds.transform.c) / ds.transform.a, (y - ds.transform.f) / ds.transform.e
        ok = (
            (col >= 0) & (col < ds.width) & (row >= 0) & (row < ds.height)
        )  # outside the grid (south of about 25 N) stays NaN
        band = ds.read(1)
        perma[ok] = band[row[ok].astype(int), col[ok].astype(int)]
    perma = np.where(
        (perma >= 0) & (lat >= 25), perma, np.nan
    )  # nodata is -3.4e38 (and NaN); the product's domain is north of 25 N (grid corners below hold 0, not data)
    # GVP: any Holocene volcano within 25 km of the centre (chord on the unit sphere)
    vol = json.loads(get("gvp").read_text(encoding="utf-8"))["features"]
    vll = np.array([f["geometry"]["coordinates"][:2] for f in vol])
    d, _ = cKDTree(xyz(vll[:, 1], vll[:, 0])).query(xyz(lat, lon))
    # land fraction: centre + 6 points 60% of the way to each vertex, inside the Natural Earth land polygon. ponytail: 7-point stencil; upgrade = polygon intersection area
    bnd = [list(h3.cell_to_boundary(c)) for c in cells]
    vtx = np.array([b + [b[0]] * (6 - len(b)) for b in bnd]).reshape(
        len(cells), 6, 2
    )  # pentagons repeat a vertex
    s_lat = lat[:, None] + 0.6 * (vtx[..., 0] - lat[:, None])
    s_lon = lon[:, None] + 0.6 * ((vtx[..., 1] - lon[:, None] + 180) % 360 - 180)
    land = load_land()
    ins = (
        shapely.contains_xy(land, ((s_lon + 180) % 360 - 180).ravel(), s_lat.ravel())
        .reshape(-1, 6)
        .sum(1)
    )
    land_frac = (ins + shapely.contains_xy(land, lon, lat)) / 7
    out = pd.DataFrame(
        {
            "h3": list(cells),
            "permafrost_prob": perma,
            "tag_volcanic": d <= 2 * np.sin(25 / (2 * EARTH_R_KM)),
            "land_frac": land_frac,
            "lat": lat,
            "lng": lon,
        }
    )
    return pd.concat([out, lith], axis=1)


def disc_terrain(dem, ppd, lat, lon, body, lon0=0.0, scale=1.0, r_km=R_KM):
    """Terrain stats for one disc. dem: int16 DN (rows, cols), row 0 = +90, col 0 = lon0 deg E; height = DN * scale; -32768 = nodata.
    ponytail: polar discs use a capped lon window (the 2 discs nearest each pole are mildly distorted)."""
    R = BODY_R_M[body]
    dth = np.radians(1.0 / ppd)
    dy = R * dth
    dx = max(R * np.cos(np.radians(lat)) * dth, dy * 0.05)
    hw_r = int(np.ceil(r_km * 1000 / dy)) + 1
    hw_c = min(int(np.ceil(r_km * 1000 / dx)) + 1, 2000)
    r0 = int((90 - lat) * ppd)
    c0 = int(((lon - lon0) % 360) * ppd)
    rows = np.clip(np.arange(r0 - hw_r, r0 + hw_r + 1), 0, dem.shape[0] - 1)
    cols = np.arange(c0 - hw_c, c0 + hw_c + 1) % dem.shape[1]
    raw = dem[np.ix_(rows, cols)]
    z = np.where(raw == -32768, np.nan, raw * scale).astype(np.float64)
    ry, rx = np.mgrid[-hw_r : hw_r + 1, -hw_c : hw_c + 1]
    mask = np.hypot(ry * dy, rx * dx) <= r_km * 1000
    return {
        **terrain_stats(z, horn_slope_deg(z, dx, dy), mask),
        "vf_dem": float(np.isfinite(z[mask]).mean()),
    }


def gcp_reduce(tab):
    """One 10-degree Diviner GCP table -> (first lat row, (4, n_lat, 720) float32): T(10:30), T(22:30), mean T, fraction < 273.15 K, per 0.5 deg bin.
    Table rows: clon, clat, ltim (bin centre, h), ..., tbol (col 10); -9999 = no observation."""
    d = pd.read_csv(tab, usecols=[0, 1, 2, 10], skipinitialspace=True)
    ix = np.floor((d.iloc[:, 0].to_numpy() + 180) / 0.5).astype(int)
    iy = np.floor((90 - d.iloc[:, 1].to_numpy()) / 0.5).astype(int)
    k = np.floor(d.iloc[:, 2].to_numpy() / 0.25).astype(
        int
    )  # centres 0.125, 0.375, ... -> bins 0..95
    assert ix.min() >= 0 and ix.max() < 720 and k.min() >= 0 and k.max() < 96, (
        "unexpected GCP layout"
    )
    t = d.iloc[:, 3].to_numpy(np.float32)
    ok = t != -9999
    iy0 = int(iy.min())
    A = np.full((iy.max() - iy0 + 1, 720, 96), np.nan, np.float32)
    A[(iy - iy0)[ok], ix[ok], k[ok]] = t[ok]
    n = np.isfinite(A).sum(-1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN slices are the honest gaps
        t1030 = np.nanmean(A[..., [41, 42]], -1)
        t2230 = np.nanmean(
            A[..., [89, 90]], -1
        )  # 10.5 h and 22.5 h sit between bins 41/42 and 89/90
    mean = np.where(n > 0, np.nansum(A, -1) / np.maximum(n, 1), np.nan)
    frac = np.where(n > 0, (A < 273.15).sum(-1) / np.maximum(n, 1), np.nan)
    return iy0, np.stack([t1030, t2230, mean, frac]).astype(np.float32)


def diviner_lt_grid():
    """All GCP bands -> (4, 360, 720) grid (see gcp_reduce). Each band: download to WORK, reduce, checkpoint OUT/gcp_lt/<band>.npz, delete the table.
    With FETCH_DIVINER False, bands without a checkpoint stay NaN (warning)."""
    ck = OUT / "gcp_lt"
    ck.mkdir(exist_ok=True)
    grid = np.full((4, 360, 720), np.nan, np.float32)
    for band in GCP_BANDS:
        f = ck / f"{band}.npz"
        if not f.exists():
            if not FETCH_DIVINER:
                warnings.warn(
                    f"Diviner band {band} not reduced and FETCH_DIVINER is False: thermal NaN there"
                )
                continue
            tab = fetch(f"gcp_{band}", GCP_URL.format(band), GCP_SHA[band], WORK / f"{band}.tab")
            iy0, r = gcp_reduce(tab)
            np.savez_compressed(f, iy0=iy0, r=r)
            tab.unlink()
        z = np.load(f)
        grid[:, int(z["iy0"]) : int(z["iy0"]) + z["r"].shape[1]] = z["r"]
    return grid


def win3(g):
    """NaN-mean over the 3x3 neighbouring 0.5 deg bins (about the 47 km disc). ponytail: lon bins shrink poleward, so the window is narrower there; upgrade = distance-weighted."""
    p = np.pad(g, ((0, 0), (1, 1), (1, 1)), constant_values=np.nan)
    p[:, :, 0], p[:, :, -1] = p[:, :, -2], p[:, :, 1]  # wrap longitude
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(
            [p[:, i : i + 360, j : j + 720] for i in range(3) for j in range(3)], axis=0
        )


def moon_lith_from_feo(feo):
    """PROXY. FeO wt% -> mafic vs feldspathic fraction (linear 6-16 wt%); other classes 0."""
    m = np.clip((np.asarray(feo, float) - 6) / 10, 0, 1)
    return pd.DataFrame(0.0, index=range(len(m)), columns=LITH_COLS).assign(
        lith_mafic_volcanic=m, lith_felsic_feldspathic=1 - m
    )


# Mars geologic unit suffix (age prefix e/m/l and A/H/N letters stripped) -> ontology fractions. PROPOSAL for human review, not a published crosswalk:
# volcanic/impact/dune sand -> basaltic crust; highland = basaltic crust + sedimentary cover; transition/lowland/basin/apron/outflow = sedimentary; polar = ice-rich layered deposits.
MARS_ONTO = {
    **dict.fromkeys(["v", "ve", "vf", "i", "pd"], [1, 0, 0, 0, 0, 0]),
    **dict.fromkeys(["h", "hu", "he", "hm"], [0.7, 0, 0, 0.3, 0, 0]),
    **dict.fromkeys(["t", "tu"], [0.4, 0, 0, 0.6, 0, 0]),
    "to": [0, 0, 0, 1, 0, 0],
    "l": [0.5, 0, 0, 0.5, 0, 0],
    "b": [0.3, 0, 0, 0.7, 0, 0],
    "a": [0, 0, 0, 1, 0, 0],
    **dict.fromkeys(["p", "pu", "pe"], [0, 0, 0, 0.3, 0, 0.7]),
    "pc": [0, 0, 0, 0, 0, 1],
}
mars_suffix = lambda u: re.sub(r"^[eml]?(AH|HN|AN|A|H|N)", "", u)
mars_proposal = lambda units: (
    pd.DataFrame({u: MARS_ONTO.get(mars_suffix(u), [0] * 6) for u in units}, index=O).T
)  # unknown suffix -> all 0 -> NaN lithology


def disc_frame(ids, lat, lon, feats, lith, vf_dem):
    """C2 disc table: every feature float32 (NaN where the body has no source); aridity 0.0 by definition (profiles.yaml assumption)."""
    df = pd.DataFrame({"disc_id": np.asarray(ids, np.int32), "lat": lat, "lon": lon})
    for name in EXPECTED_FEATURES:
        df[name] = np.asarray(feats.get(name, np.full(len(df), np.nan)), np.float32)
    df["aridity_index"] = np.zeros(len(df), np.float32)
    for col in LITH_COLS:
        df[col] = lith[col].to_numpy(np.float32)
    df["vf_dem"] = np.asarray(vf_dem, np.float32)
    return df


def moon_discs_real(lat, lon, ids):
    dem = np.fromfile(get("ldem"), "<i2").reshape(
        11520, 23040
    )  # 530 MB read once (Drive random access is slow); col 0 = 0 deg E
    t = pd.DataFrame(
        [disc_terrain(dem, 64, la, lo, "moon", lon0=0.0, scale=0.5) for la, lo in zip(lat, lon)]
    )
    del dem
    f = {c: t[c].to_numpy() for c in EXPECTED_FEATURES[:4]}
    # Diviner: the 0.5 deg bin containing the disc centre, NaN-mean over the 3x3 bins around it
    g = win3(diviner_lt_grid())[
        :,
        np.clip(((90 - lat) / 0.5).astype(int), 0, 359),
        np.clip(((lon + 180) / 0.5).astype(int), 0, 719),
    ]
    f["lst_mean_K"], f["diurnal_range_K"], f["frac_below_0C"] = g[2], g[0] - g[1], g[3]
    # LP GRS FeO (equal-area pixels, nearest pixel centre; ~5 deg true resolution). Columns: 1-4 = min/max lat/lon, 12 = W_FEO (g/g)
    p = pd.read_csv(get("lpgrs"), sep=r"\s+", header=None, usecols=list(range(13)))
    from scipy.spatial import cKDTree

    _, j = cKDTree(xyz((p[1] + p[2]) / 2, (p[3] + p[4]) / 2)).query(xyz(lat, lon))
    lith = moon_lith_from_feo(100 * p[12].to_numpy()[j])
    return disc_frame(ids, lat, lon, f, lith, t["vf_dem"])


def mars_discs_real(lat, lon, ids):
    import geopandas as gpd
    import rasterio

    with rasterio.open(get("mola")) as ds:
        dem = ds.read(1)  # 2.1 GB int16, metres above the areoid; col 0 = -180 deg E
    t = pd.DataFrame(
        [disc_terrain(dem, 128, la, lo, "mars", lon0=-180.0, scale=1.0) for la, lo in zip(lat, lon)]
    )
    del dem
    f = {
        c: t[c].to_numpy() for c in EXPECTED_FEATURES[:4]
    }  # thermal and permafrost stay NaN: no temperature product (TES TI is not converted)
    # TES thermal inertia side columns: 3600x7200 big-endian int16 after a 7200 B header, stored south-up/west-lon; [::-1, ::-1] gives north-up, 0..360 E at 0.05 deg
    ti = np.fromfile(get("tes_ti"), ">i2", offset=7200).reshape(3600, 7200)[::-1, ::-1]
    mk = np.fromfile(get("tes_mask"), "u1", offset=7200).reshape(3600, 7200)[
        ::-1, ::-1
    ]  # 1 = TES data, 0 = no data or interpolated
    r, c = (
        np.clip(((90 - lat) / 0.05).astype(int), 0, 3599),
        np.clip(((lon % 360) / 0.05).astype(int), 0, 7199),
    )
    v = ti[r, c].astype(np.float32)
    ok = (v >= 24) & (v <= 800)  # 0 = nodata
    # Tanaka 2014 unit at the centre (geographic degrees, same sphere); first match if polygons touch
    geo = gpd.read_file(mars_shapefile())
    pts = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(np.clip(lon, -179.99, 179.99), lat), crs=geo.crs
    )  # polygon edges stop up to ~0.01 deg short of +-180
    unit = gpd.sjoin(pts, geo[["Unit", "geometry"]], how="left", predicate="intersects")["Unit"]
    unit = unit[~unit.index.duplicated()].reindex(pts.index)
    lith = crosswalk("mars_tanaka2014", unit, mars_proposal(geo["Unit"].unique()))
    out = disc_frame(ids, lat, lon, f, lith, t["vf_dem"])
    out["tes_ti"] = np.where(ok, v, np.nan).astype(np.float32)
    out["tes_ti_measured"] = np.where(ok, mk[r, c], np.nan).astype(np.float32)
    out["geo_unit"] = unit.to_numpy()  # kept so the proposal can be reviewed unit by unit
    return out


def targets_real(moon, mars):
    """Target features = the nearest disc to each landmark in config/landmarks.yaml (human-owned). While that file is empty: the nearest real disc to the synthetic target
    positions, ids prefixed placeholder_. ponytail: the nearest disc is up to about 60 km (Moon) / 120 km (Mars) from the point; upgrade = run the disc builders at the landmark."""
    lm = load_landmarks()
    if not len(lm):
        t = targets_table(moon, mars)
        return t.assign(
            target_id=t["target_id"].str.replace("synthetic_", "placeholder_"),
            name="PLACEHOLDER (nearest real disc) " + t["name"].str.replace("Synthetic ", ""),
        )
    cols = [*EXPECTED_FEATURES, *LITH_COLS]
    rows = []
    for r in lm.itertuples():
        d = moon if r.body == "moon" else mars
        disc = d.iloc[
            int(np.argmin(haversine_km(d["lat"].to_numpy(), d["lon"].to_numpy(), r.lat, r.lon)))
        ]
        rows.append(
            {
                "target_id": r.id,
                "name": r.name,
                "body": r.body,
                "lat": r.lat,
                "lon": r.lon,
                **{c: disc[c] for c in cols},
            }
        )
    return pd.DataFrame(rows).astype({c: np.float32 for c in cols})


def earth_table_real(cells):
    e = earth_remote(cells).merge(earth_local(cells), on="h3", how="left")
    if "pit_cave_density_per_1000km2" not in e:
        # TODO(verify): catalogue ingestion needs earth_caves + a survey-coverage rule (datasets.yaml).
        # NaN means "not catalogued / not surveyed", never 0 (science-invariant 1).
        e["pit_cave_density_per_1000km2"] = np.nan
    e["vf_dem"] = e["slope_p50_deg"].notna()
    e["vf_lst"] = e["lst_mean_K"].notna()
    e["vf_lith"] = e["lith_mafic_volcanic"].notna()
    m = prof.params[
        "mask"
    ]  # keep hex if barren+ice >= min OR ndvi <= max; NaN cover/NDVI counts as masked
    e["masked"] = ~(
        ((e["barren_frac"] + e["snow_ice_frac"]) >= m["barren_plus_ice_min"])
        | (e["ndvi_mean"] <= m["ndvi_max"])
    )
    e["tag_periglacial"] = e["frac_below_0C"].fillna(0) > 0.5
    e["tag_evaporitic"] = e["lith_evaporite"].fillna(0) > 0.3
    num = [
        *EXPECTED_FEATURES,
        *LITH_COLS,
        "barren_frac",
        "snow_ice_frac",
        "ndvi_mean",
        "aster_mafic_idx",
        "land_frac",
        "vf_dem",
        "vf_lst",
        "vf_lith",
    ]
    e[num] = e[num].astype(np.float32)
    return e[
        ["h3", *num, "tag_volcanic", "tag_periglacial", "tag_evaporitic", "masked", "lat", "lng"]
    ]


NEED = {
    "earth_features": [
        "h3",
        *EXPECTED_FEATURES,
        *LITH_COLS,
        "barren_frac",
        "snow_ice_frac",
        "ndvi_mean",
        "aster_mafic_idx",
        "land_frac",
        "vf_dem",
        "vf_lst",
        "vf_lith",
    ],
    "moon_discs": ["disc_id", "lat", "lon", *EXPECTED_FEATURES, *LITH_COLS, "vf_dem"],
    "mars_discs": ["disc_id", "lat", "lon", *EXPECTED_FEATURES, *LITH_COLS, "vf_dem"],
    "targets": ["target_id", "name", "body", "lat", "lon", *EXPECTED_FEATURES, *LITH_COLS],
}


def build_tables(limit: int | None = None, use_ee: bool = True) -> dict[str, pd.DataFrame]:
    """Real C2 tables. limit: smoke test on N evenly spaced hexes and discs. use_ee False: Earth EE columns stay NaN."""
    global earth_remote
    cells = select_land_cells()
    lat, lon = fibonacci_lattice(N_DISCS)
    ids = np.arange(N_DISCS)
    if limit:
        cells = cells[:: max(1, len(cells) // limit)][:limit]
        sel = np.linspace(0, N_DISCS - 1, limit).astype(int)
        lat, lon, ids = lat[sel], lon[sel], ids[sel]
    if not use_ee:

        def earth_remote(cells):  # noqa: F811 - offline stand-in: no Earth Engine, every EE column NaN (all hexes end up masked)
            return pd.DataFrame({"h3": list(cells), **{c: np.nan for c in EE_COLS}})

    earth, moon, mars = (
        earth_table_real(cells),
        moon_discs_real(lat, lon, ids),
        mars_discs_real(lat, lon, ids),
    )
    return {
        "earth_features": earth,
        "moon_discs": moon,
        "mars_discs": mars,
        "targets": targets_real(moon, mars),
    }


def write_tables(tables: dict[str, pd.DataFrame], out: Path = OUT, source: str = "real") -> None:
    out.mkdir(parents=True, exist_ok=True)
    for k, cols in NEED.items():
        assert set(cols) <= set(tables[k].columns), k
        assert all(tables[k][c].dtype == np.float32 for c in [*EXPECTED_FEATURES, *LITH_COLS]), k
        tables[k].to_parquet(out / f"{k}.parquet", index=False)
    (out / "tables_source.txt").write_text(source)
    pd.DataFrame(GLIM, index=O).T.assign(weight=pd.Series(GLIM_W)).rename_axis("code").to_csv(
        out / "glim_ontology_proposal.csv"
    )


def main(argv=None) -> int:
    global EE_PROJECT, OUT, FETCH_DIVINER
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument(
        "--ee-project", default="", help="Google Cloud project with Earth Engine enabled"
    )
    p.add_argument(
        "--no-ee", action="store_true", help="skip Earth Engine (smoke test / Moon+Mars only)"
    )
    p.add_argument("--limit", type=int, default=None, help="smoke test: N hexes and N discs")
    p.add_argument(
        "--no-diviner-fetch", action="store_true", help="do not download missing Diviner bands"
    )
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args(argv)
    if not a.no_ee and not a.ee_project:
        p.error("give --ee-project (and run `earthengine authenticate` once) or pass --no-ee")
    EE_PROJECT, OUT, FETCH_DIVINER = a.ee_project, a.out, not a.no_diviner_fetch
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    tables = build_tables(a.limit, use_ee=not a.no_ee)
    write_tables(tables, OUT, "real" if not (a.no_ee or a.limit) else "real-partial")
    for k, v in tables.items():
        print(f"{k}: {len(v)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
