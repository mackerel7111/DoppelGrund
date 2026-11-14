# Earth Engine check: what we need from you

The Earth fusion in `earth_remote()` (`pipeline/doppelgrund/real.py`) has never been run. It now averages
**Copernicus GLO-30 + NASADEM** (terrain) and **MOD11A2 + MOD21A1D/N** (thermal), using the mean where
both have a pixel and whichever has data otherwise. We can't run Earth Engine, so please run it and send back the
results below. Please do not send credentials, tokens or your project id.

## 0. Get the right code
These changes are not on `main` yet. Ask the repo owner which branch or commit to use, and check out exactly that.
Do not edit `real.py`; if something fails, send us the error instead.

## 1. Setup (once)
```powershell
.venv\Scripts\python.exe -m pip install -e "pipeline[dev,ee]"
.venv\Scripts\python.exe -m pip show earthengine-api      # send us the Version line
mkdir data\interim\real                                   # earth_remote() needs this folder
```
Log in with `earthengine authenticate` if you have not. The Earth Engine project needs the API enabled.

## 2. Save a baseline (old code) next to the new code
This lets us compare fused values with the old GLO-30-only / MOD11A2-only values.
```powershell
git show HEAD~0:pipeline/doppelgrund/real.py > NUL   # sanity check that git works
```
Use the commit that is the parent of the fusion change (the owner will tell you its hash, call it `OLD`):
```powershell
git show OLD:pipeline/doppelgrund/real.py > pipeline\doppelgrund\real_baseline.py
```
Do not commit `real_baseline.py`. Delete it when done.

## 3. Probe five hexes with both versions
Save as `probe.py` in the repo root and run `.venv\Scripts\python.exe probe.py`. Set `PROJECT` to your project id.
```python
import h3, pandas as pd
import doppelgrund.real as new
import doppelgrund.real_baseline as old

PROJECT = "YOUR_PROJECT_ID"          # do not paste this into messages
POINTS = {                           # name: (lat, lon)
    "sahara": (23.0, 10.0),
    "atacama": (-24.0, -69.0),
    "himalaya": (30.5, 85.0),
    "arctic_70N": (70.0, 20.0),      # poleward of NASADEM's likely +-60 deg limit
    "antarctica": (-80.0, 0.0),
}
cells = [h3.latlng_to_cell(la, lo, 4) for la, lo in POINTS.values()]
for mod in (new, old):
    mod.EE_PROJECT = PROJECT
    mod.OUT.mkdir(parents=True, exist_ok=True)

out = {}
for tag, mod in (("NEW", new), ("OLD", old)):
    df = mod.earth_remote(cells, batch=5).set_index("h3")
    df.index = list(POINTS)
    out[tag] = df
cols = ["slope_p50_deg", "slope_p90_deg", "relief_std_m", "frac_slope_lt_10deg",
        "lst_mean_K", "diurnal_range_K", "annual_range_K", "frac_below_0C"]
pd.set_option("display.width", 200)
print("NEW\n", out["NEW"][cols].round(3))
print("OLD\n", out["OLD"][cols].round(3))
print("NEW - OLD\n", (out["NEW"][cols] - out["OLD"][cols]).round(3))
```
Both versions checkpoint to `data/interim/real/ee_batches/`. If the second run reuses the first run's files
(you see no `batch 1/1 done`), delete that folder between runs.

## 4. Check that the new asset IDs resolve and how far NASADEM reaches
```python
import ee; ee.Initialize(project=PROJECT)
print(ee.Image("NASA/NASADEM_HGT/001").bandNames().getInfo())                         # expect ['elevation']
for lat in (45, 59, 61, 65, 70, 80):
    v = ee.Image("NASA/NASADEM_HGT/001").reduceRegion(ee.Reducer.mean(), ee.Geometry.Point([20, lat]), 30).getInfo()
    print("NASADEM", lat, v)                       # None / null = no data at that latitude
for a in ("MODIS/061/MOD21A1D", "MODIS/061/MOD21A1N"):
    ic = ee.ImageCollection(a).filterDate("2010-01-01", "2020-01-01")
    print(a, ic.size().getInfo(), ic.first().bandNames().getInfo())   # expect ~3,600 images each and LST_1KM
```

## 5. What to send back (paste text, not screenshots)
1. The three tables printed by `probe.py` (NEW, OLD, NEW - OLD).
2. The output of section 4, including the `earthengine-api` version.
3. Any error or traceback, in full, and any message like "Computation timed out" or "User memory limit exceeded".
4. How long the NEW run took for the 5 hexes (rough wall-clock is fine).
5. Whether the project is a standard or a noncommercial/research tier, if you know.

## What we will look for
- `slope_*`, `relief_std_m`: NEW within a few percent of OLD in Sahara, Atacama and Himalaya; **identical** (diff 0) at
  `arctic_70N` and `antarctica` if NASADEM has no data there.
- `lst_mean_K`, `diurnal_range_K`, `annual_range_K`, `frac_below_0C`: NEW within about 1-2 K (or a few hundredths
  for the fraction) of OLD; a large gap means one product is masked or mis-scaled.
- No all-NaN column, and the daily MOD21 collections finish without timeouts. If they time out we switch to monthly
  composites.

## If you were already running the full build
Tell us the exact command and when it started. The full run touches about 82,000 hexes and downloads several GB into
`data/raw/`, so please do not start another one until we have the probe results.
