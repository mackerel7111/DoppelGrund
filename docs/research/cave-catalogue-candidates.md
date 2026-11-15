# Cave / lava-tube catalogue candidates (DRAFT, nothing here is verified)

Written 2026-11-14 for the `pit_cave_density_per_1000km2` feature. **Nothing in `config/` was changed.** Every coordinate
and count below was read from a web page by an automated reader and must be checked by a human (`TODO(verify)`) before
it goes into `config/datasets.yaml` or any catalogue file. Wikipedia is a convenience source, not an authority.

## Moon: LROC pit catalogue (`moon_pits`)
- Page: https://data.lroc.im-ldi.com/lroc/view_rdr/SHAPEFILE_LUNAR_PIT_LOCATIONS (read, HTTP 200)
- Files (folder `https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/EXTRAS/SHAPEFILE/LUNAR_PIT_LOCATIONS/`):
  `LUNAR_PIT_LOCATIONS.CSV` (163.5 KB, only file with the full Description field), `LUNAR_PIT_LOCATIONS_180.ZIP`,
  `LUNAR_PIT_LOCATIONS_360.ZIP` (1.19 MB each), `LUNAR_PIT_LOCATIONS_README.TXT`.
- Columns include Name, Terrain (Mare / Highland / Impact melt), Type (Fracture / Large Bowl / Uncertain), Latitude, Longitude.
  Updated 2021-03-09. Cite Wagner & Robinson (2021), LPSC abstract #2530 (ADS: 2021LPI....52.2530W).
- **Licence: not stated on the page.**
- **Count:** the page gives none. A secondary source reports 281 impact-melt pits, 15 mare pits, 5 non-impacted-terrain
  pits; unconfirmed.
- **Survey coverage: no statement found.** The page has no search-area or completeness text. The abstract PDF at
  hou.usra.edu returned 404, and only the ADS record page was found. Treat the catalogue as **positive-only**.
- Optional extra: Zenodo 20516852 (CC-BY-4.0, June 2026, Losarcos and Dombard): lunar lava-tube evidence shapefiles
  (rille lines, gravity-anomaly polygons, points, pit locations). Feature counts not stated.

## Mars: Mars Global Cave Candidate Catalog, MGC3 (`mars_caves`)
- USGS page returned 403 to the reader, and both data.gov mirrors returned 404. Search results only (unverified):
  - ZIP (about 1.77 MB, includes README.TXT): `astropedia.astrogeology.usgs.gov/download/Mars/MarsCaveCatalog/mars_cave_catalog.zip`
  - PDS4 bundle `urn:nasa:pds:mars_cave_catalog`; release folder `pds.nasa.gov/data/pds4/releases/img/mars_cave_catalog-20191121/`
    (lists `collection_cave_inventory.csv`; contents not opened).
  - Fields reportedly: lat, lon, feature type, priority (confidence) rating, comment. Cite G. E. Cushing (2015).
  - Counts differ by source (about 1,000 candidates, mostly Tharsis). Search snippets say most CTX-identified
    candidates later proved false positives; **verify before using it as a scored input**.
- Verified derived set (read): Zenodo 8308454, "PITS apparent depth profiles for MGC3 features", CC-BY-4.0. Covers only
  88 atypical pit craters, so it is not the catalogue.

## Earth: no open global catalogue found
Candidates that were found but not usable as-is:
- ASU Lava Tube Database (https://rgcps.asu.edu/ltdb/): the page failed on a certificate error; unread. Entries for lava
  tubes in 34 countries (from a search snippet); no confirmed bulk download or licence.
- UIS WikiCaves / GrottoCenter: general cave data (60,000+ caves, 126 countries per a snippet); not lava-tube specific;
  licence and coordinate access unchecked.
- NASA Ames Planetary Pits and Caves Analog Dataset: rejected. Four Earth sites as local x/y/z point clouds, **no
  lat/lon**, research-use-only terms.

### Hand-curated starter list (coordinates as displayed on Wikipedia; unverified)
| Name | Type | Country | Lat, lon as displayed | Note |
|---|---|---|---|---|
| Surtshellir | lava tube | Iceland | 64.7842, -20.72771 | coordinates tagged `source:dewiki`, no citation |
| Raufarholshellir | lava tube | Iceland | 63.9397, -21.4008 | no location source cited |
| Vidgelmir | lava tube | Iceland | 64.750283, -20.8017 | cites fljotstunga.is for the description |
| Cueva del Viento | lava tube | Spain (Tenerife) | 28.34667, -16.72222 | page has a "needs more citations" tag |
| Manjanggul | lava tube | South Korea (Jeju) | 33.5282, 126.7701 | UNESCO list 1264 for the heritage listing |
| Undara lava tubes | lava tube field | Australia | -18.20111, 144.59611 | park coordinates, not one tube |
| Lava Beds National Monument | lava tube field | USA | 41.71389, -121.50833 | monument centre, not one tube; USGS Bulletin 1673 is the usual cave-list source (unverified) |
| Kazumura Cave | lava tube | USA (Hawaii) | none on its page | do not fill from the island or monument |
| Ape Cave | lava tube | USA (Washington) | none on its page (only the monument's) | do not fill from the monument |
| Deer Cave | karst | Malaysia (Sarawak) | 4.1319, 114.9189 | limestone, **not** a lava tube |
| Niah Caves | karst | Malaysia (Sarawak) | 3.81389, 113.78139 | limestone, **not** a lava tube |

Rules this list must respect: karst caves (Mulu, Niah) are never presented as structural lava-tube analogues
(`.kiro/steering/product.md`), so each row needs a `type` column and the feature should count lava tubes and karst
separately or only lava tubes. About ten point locations cannot form a density surface: a hex either holds one or it
does not.

## Decisions still needed from the user
1. Moon survey-coverage rule (none is documented): positive-only (NaN unless a pit exists) vs a rule you define.
2. Which Earth entries to accept, and whether karst caves count toward the same feature.
3. Whether to use the Mars catalogue now, given the false-positive caveat.

## Decisions (user, 2026-11-14: "go with your recommendation for all three")
1. **Moon:** positive-only. A disc has a value only where an LROC pit is catalogued inside it; otherwise NaN. Pits typed `Uncertain` (12 of 278) are dropped by me, because the catalogue README says it is unclear they qualify as pits.
2. **Earth:** lava tubes only, from `config/earth_lava_tubes.csv` (5 single tubes). The two field-scale entries (Undara, Lava Beds) and all karst caves are left out. Coordinates are still unverified.
3. **Mars:** left empty (NaN). The MGC3 catalogue has not been read.

Result on the real grids (`caves.py`): 266 pits fall in 12 of the 3,000 Moon discs, and the list yields values in only 2 of 81,772 Earth hexes (the 5 tubes fall in 4 distinct hexes; the Tenerife and Jeju hex centres are not on the land mask, and Surtshellir and Vidgelmir share one hex, leaving 2). The subsurface feature is therefore almost always "not measured".
