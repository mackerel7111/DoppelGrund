# Section C review: landmarks, known sites, cave lists (DRAFT for human review)

Written 2026-11-15 for gap tasks G11 and G12 (`gap-resolution-tasks.md`). **Nothing in `config/` was changed.**
All three config files are human-owned: copy approved rows across yourself, or tell an agent which rows to copy.

How this was checked:
- References came from web searches (abstracts, bibliographic records, NASA/USGS pages). **No full paper text was
  read.** "Verify DOI" means the DOI came from one listing and was not opened at doi.org.
- Land-mask column: how many of the site's H3 res-4 hex plus its 6 ring-1 neighbours have their centre on Natural Earth
  1:110m land (same rule as `select_land_cells()` and `validation.candidate_rows()`). `0/7` means validation can never
  evaluate the site.
- Second-source coordinates came from OpenStreetMap (Nominatim) and the LROC 2016 coordinate table.

Decisions already made (2026-11-15): add landmarks that the literature actually pairs with Earth sites; set
`documented_target_id` only where a source names that place; keep Mars subsurface NaN; grow the lava-tube list.

---

## 1. Proposed new landmarks (`config/landmarks.yaml`)

Six new targets make spec-mode pairs possible. Apollo coordinates are landing-module (LM) positions, not feature
centres, because the training and simulant literature refers to the landing sites.

| id | name | body | lat | lon | source | why it is needed |
|---|---|---|---|---|---|---|
| apollo14_fra_mauro | Apollo 14 landing site (Fra Mauro formation) | moon | -3.64589 | -17.47194 | LROC 2016 coordinates of human features, Apollo 14 LM (342.52806 E) | Ries training (§2) |
| apollo15_hadley | Apollo 15 landing site (Hadley-Apennine) | moon | 26.13239 | 3.63330 | LROC 2016, Apollo 15 LM | Rio Grande Gorge, Kilbourne Hole (§2) |
| apollo16_descartes | Apollo 16 landing site (Descartes highlands) | moon | -8.9734 | 15.5011 | LROC 2016, Apollo 16 LM | Sudbury training, NU-LHT simulant (§2) |
| meridiani_planum | Opportunity landing site, Eagle crater (Meridiani Planum) | mars | -1.9462 | -5.5266 | Eagle crater, 354.4734 E (Wikipedia, several agreeing copies). TODO(verify) against a NASA/USGS source | Rio Tinto (§2) |
| phoenix_landing | Phoenix landing site (Vastitas Borealis) | mars | 68.2188 | -125.7492 | NASA/JPL: 68.2188 N, 234.2508 E, IAU 2000 areocentric | Beacon Valley (§2) |
| nili_fossae | Nili Fossae | mars | 22.02 | 76.69 | USGS Gazetteer Feature 4271, MDIM 2.1 control net | Pilbara (§2) |

Sources: [LROC 2016 coordinates PDF](https://www.lroc.asu.edu/data/support/downloads/2016_LROC_Coordinates_of_Human_Features.pdf),
[Phoenix site](https://an.rsl.wustl.edu/phx2008/help/landing_site.htm), [Eagle crater](https://en.wikipedia.org/wiki/Eagle_(crater)),
[Nili Fossae gazetteer](https://planetarynames.wr.usgs.gov/Feature/4271).

Notes for review:
- The existing `descartes` landmark is the crater centre (-11.74, 15.67), about 84 km from the Apollo 16 LM. That puts
  it outside a 23.7 km disc, so the Apollo 16 pairs need `apollo16_descartes`. Keep `descartes` or replace it: your call.
- Nili Fossae is about 700 km long, so a disc at its centroid is an arbitrary patch. The Brown et al. (2010) carbonates
  lie in the wider Nili Fossae region. If a paper gives a study-area point, use that instead.
- The LROC table uses mean Earth/polar axis coordinates, the same system as the gazetteer points already in the file.
- Optional, not proposed: Apollo 17 (20.1911, 30.7723). Its crew also trained at Sudbury (USGS training record,
  May 1972), but the CSV holds one target per site, and Sudbury is listed under Apollo 16 below.

## 2. Known sites (`config/known_sites.csv`)

Strength: **A** = a source ties the Earth site to that exact landmark; **B** = the tie is through crew training or
simulant design for that mission, not a published similarity claim; **body** = a whole-body analogue only (leave
`documented_target_id` empty, so it counts in body mode).

### 2a. Proposed spec-mode pairs (11; there is 1 today)

| site_id | target | dim | strength | evidence | reference |
|---|---|---|---|---|---|
| cinder_lake *(new)* | statio_tranquillitatis | terrain | A | USGS blasted a crater field in 1967 replicating part of Mare Tranquillitatis at the Apollo 11 site | Bailey (1967) USGS OFR 67-7 ([USGS](https://pubs.usgs.gov/publication/ofr677)); [LROC](https://www.lroc.asu.edu/images/1107) |
| nordlinger_ries | apollo14_fra_mauro | terrain | A | After the switch to Fra Mauro, Apollo 14 training moved to crater sites; Ries field trip 10–15 Aug 1970 | [ALSJ Apollo 14 Ries](https://www.nasa.gov/wp-content/uploads/static/history/alsj/a14/a14ries.html) |
| rio_grande_gorge *(new)* | apollo15_hadley | terrain | A | Scott and Irwin ran a Hadley-like traverse there in March 1971; the gorge is about the same width as Hadley Rille | [BLM 2021](https://www.blm.gov/blog/2021-08-04/when-public-land-new-mexico-stood-moon) (cites Schaber 2002) |
| kilbourne_hole *(new)* | apollo15_hadley | terrain | B | Apollo 15 training in January 1971 | same BLM page |
| sudbury_basin | apollo16_descartes | composition | B | Apollo 16 crew trained there in July 1971 for impact breccias. The crew expected volcanic rocks at Descartes, but the samples turned out to be impact breccias | [NASA, Apollo 16 site](https://www.nasa.gov/history/50-years-ago-nasa-selects-landing-site-for-apollo-16/); [USGS training schedule](https://www.usgs.gov/data/apollo-16-training-schedule-19711230) |
| stillwater_complex *(new)* | apollo16_descartes | composition | A | NU-LHT highland simulants are built from Stillwater anorthosite and norite to match average Apollo 16 regolith | Stoeser, Rickman & Wilson (2010) NASA/TM-2010-216438; [NASA ARES](https://ares.jsc.nasa.gov/projects/simulants/nu-lht.html) |
| rio_tinto *(new)* | meridiani_planum | composition | A | Acid-sulfate, jarosite system argued as an analogue for the Meridiani outcrop rocks | Fernández-Remolar et al. (2005) EPSL 240:149–167, doi:10.1016/j.epsl.2005.09.043 (verify DOI) |
| beacon_valley | phoenix_landing | cold_ice | B | Phoenix landing-area polygons compared to Antarctic sublimation polygons; Beacon Valley is the classic sublimation-polygon site | Levy et al. (2008) GRL, doi:10.1029/2007GL032813. TODO(verify) the paper names Beacon Valley; otherwise body |
| pilbara_north_pole_dome *(new)* | nili_fossae | composition | A | Warrawoona Group clay-carbonate assemblage proposed as the Earth analogue of the Nili Fossae carbonate units | Brown et al. (2010) EPSL 297:174–182, doi:10.1016/j.epsl.2010.06.018 |
| lake_salda | jezero | composition | A | Hydromagnesite microbialites, described as an analogue for the Jezero paleolake | Güneş et al. (2024) Geobiology 22(5):e12619, doi:10.1111/gbi.12619 (replaces the Wikipedia link) |
| dumont_dunes *(new)* | gale | terrain | A | Full-scale Curiosity mobility tests for the Gale megaripple crossings | Arvidson et al. (2017) J. Field Robotics 34(3):495–518, doi:10.1002/rob.21647 |

### 2b. Existing rows: proposed edits

| site_id | change | reference | land mask |
|---|---|---|---|
| haughton_crater | keep body (Mars). Better ref: Osinski et al. (2010) PSS 58:646–657, doi:10.1016/j.pss.2009.10.004 (verify). That paper calls Haughton a *lunar* analogue: consider a second Moon row | [record](https://www.research.ed.ac.uk/en/publications/field-geology-on-the-moon-some-lessons-learned-from-the-explorati/) | 6/7 |
| mcmurdo_dry_valleys | keep body. Ref TODO: Marchant & Head (2007) Icarus "Antarctic dry valleys: microclimate zonation…" (not searched; from memory, verify) | | 7/7 |
| beacon_valley | see 2a | | 7/7 |
| atacama_yungay | keep body (the Viking comparison is general, not tied to one landing site) | Navarro-González et al. (2003) Science 302:1018–1021, doi:10.1126/science.1089143 | 7/7 |
| bockfjorden_svalbard | keep body | Treiman et al. (2002) EPSL 204:323–332, carbonate analogue of ALH84001 (DOI not found yet) | 6/7 |
| mdrs_utah | **decide**: a habitat chosen for crew operations, not for measured similarity. Keep it only as `well_known` context, or drop it from validation | | 7/7 |
| hi_seas | **decide**: same issue as MDRS (an isolation study) | | 5/7 |
| askja | keep body: 1965 and 1967 general Apollo training, not tied to one mission | Phinney (2015) NASA SP-2015-626, *Science Training History of the Apollo Astronauts* | 7/7 |
| mauna_kea_isru | keep body; current NTRS link is fine | [NTRS 20100033667](https://ntrs.nasa.gov/citations/20100033667) adds the 2010 test report | 5/7 |
| kilauea | keep body. Ref TODO (only a Wikipedia link today) | | 5/7 |
| meteor_crater | keep body: general Apollo training | Phinney (2015) | 7/7 |
| nordlinger_ries | see 2a | | 7/7 |
| sudbury_basin | see 2a | | 7/7 |
| craters_of_the_moon | keep body | FINESSE overview, Heldmann et al., [NTRS 20190031834](https://ntrs.nasa.gov/citations/20190031834) | 7/7 |
| lonar_lake | keep body. Dimension `composition` → maybe `terrain` (cited as an analogue for simple craters in basalt) | Maloof et al. (2010) GSA Bulletin 122:109–126, doi:10.1130/B26474.1 (verify) | 7/7 |
| teide_np | **cannot be evaluated** (island not in the 110m mask). Keep for the map layer only, or drop | | 0/7 |
| lanzarote_pangaea | **cannot be evaluated**, same reason | | 0/7 |

### 2c. New body-mode rows (no matching landmark)

| site_id | name | lat | lon | body | dim | reference | land mask |
|---|---|---|---|---|---|---|---|
| black_point_lava_flow | Black Point Lava Flow, Arizona (Desert RATS 2010) | 35.67 | -111.45 | moon | terrain | Eppler et al. (2013) Acta Astronautica 90(2):224–241, doi:10.1016/j.actaastro.2012.03.009 | 7/7 |
| merriam_crater | Merriam Crater, Arizona (JSC-1 lunar simulant quarry) | 35.33640 | -111.28904 | moon | composition | McKay et al. (1994) "JSC-1: A new lunar soil simulant", ASCE Space '94 | 7/7 |
| mistastin_lake | Mistastin Lake impact structure, Labrador | 55.89015 | -63.24738 | moon | composition | Mader & Osinski (2018) MAPS, doi:10.1111/maps.13173 (anorthosite target, like the lunar highlands) | 7/7 |
| don_juan_pond | Don Juan Pond, Wright Valley | -77.56314 | 161.18767 | mars | cold_ice | Dickson et al. (2013) Sci. Rep. 3:1166, doi:10.1038/srep01166 | 7/7 |
| qaidam_dalangtan | Dalangtan playa, Qaidam Basin | TODO | TODO | mars | composition | Xiao et al. (2017) Earth-Sci. Rev. 164:84–101, doi:10.1016/j.earscirev.2016.11.003 | 7/7 at the rough point 38.5, 91.4 |
| puu_nene | Pu'u Nene cinder cone, Hawaii (JSC Mars-1 simulant) | TODO | TODO | mars | composition | Allen et al. (1997/1998) JSC Mars-1 (LPSC XXVIII abstract; year differs between sources) | 5/7 at the rough point 19.68, -155.42 |

Coordinates: OSM for Merriam, Mistastin, Don Juan Pond, Dumont Dunes (35.68106, -116.22480), Kilbourne Hole
(31.97166, -106.96322) and Minas de Riotinto (37.69346, -6.59578). Cinder Lake 35.32805, -111.52305 (Atlas Obscura;
TopoQuest puts the lake 1 km away). Rio Grande Gorge 36.33607, -105.73377 is the Taos Junction Bridge, which only
stands in for the March 1971 traverse point. Black Point is a sample latitude from the BP-1 simulant report. Stillwater
(about 45.38, -109.88 near Nye, Montana) and Pilbara (about -21.15, 119.4) are **rough values from memory: replace them
from the papers.**

**Count if everything above is accepted:** 18 + 13 new = 31 sites, 29 evaluable, 11 in spec mode. Still at the low end
of the plan's 30–50. Hawaii (4 sites) and the Flagstaff area (4 sites) each cluster within a few hexes, so the sites are not
independent samples. Say so in the validation write-up.

## 3. Earth lava tubes (`config/earth_lava_tubes.csv`)

### 3a. Cross-check of the 6 existing rows

| name | CSV | OSM | gap | land mask |
|---|---|---|---|---|
| Surtshellir | 64.7842, -20.72771 | 64.78318, -20.72283 (cave entrance) | ~0.3 km | 7/7 |
| Raufarholshellir | 63.9397, -21.4008 | 63.94024, -21.39718 (cave entrance) | ~0.2 km | 4/7 |
| Vidgelmir | 64.750283, -20.8017 | 64.75022, -20.80190 (cave entrance) | ~0.01 km | 7/7 |
| Cueva del Viento | 28.34667, -16.72222 | 28.34404, -16.70138 (nature-reserve centroid) | ~2 km | **0/7** |
| Manjanggul | 33.5282, 126.7701 | 33.52825, 126.77013 (cave entrance) | ~0.01 km | **0/7** |
| Lava River Cave | 43.895396, -121.368917 | 43.89485, -121.36954 (cave entrance) | ~0.08 km | 7/7 |

All six agree with a second source to within 2 km, far below the ~45 km hex size. **But Tenerife and Jeju are not on
the 110m land mask, so 2 of the 6 tubes never reach any Earth hex.** Today the Earth subsurface feature rests on 4 tubes
(3 in Iceland, 1 in Oregon). `docs/submission/project-details.md` lists "Tenerife, Jeju" as data sources and should
say they are display-only.

### 3b. Proposed additions (all on the land mask)

| name | country | lat | lon | coord source | analogue literature | land mask |
|---|---|---|---|---|---|---|
| Ape Cave | USA (Washington) | 46.11385 | -122.21397 | OSM | none found; it is a lava tube, which is all this list needs | 7/7 |
| Valentine Cave, Lava Beds NM | USA (California) | 41.70926 | -121.47779 | OSM | Lava Beds has hundreds of tubes; one point undercounts it (the list is positive-only) | 7/7 |
| Undara lava tubes | Australia (Queensland) | -18.29437 | 144.64185 | OSM (national-park centroid) | Atkinson et al. (1975) Bull. Volcanol., doi:10.1007/BF02597832; lunar analogue argued by Atkinson (1991, 2010) | 7/7 |
| Umm Jirsan | Saudi Arabia (Harrat Khaybar) | 25.5889 | 39.7569 | ShowCaves (one source); do not use the Wikipedia Harrat Khaybar point (that is the summit) | Stewart et al. (2024), archaeology ("First evidence for human occupation of a lava tube in Arabia"; journal TODO(verify)) | 7/7 |
| Kazumura Cave | USA (Hawaii) | 19.5726 | -155.0015 | one travel site: weakest | longest known lava tube (Guinness) | 3/7 |

The CSV's `type` column is `lava_tube` for all of these. Set `verified` yourself.

## 4. LROC pit catalogue licence (G12)

The PDS README (`LUNAR_PIT_LOCATIONS_README.TXT`, read 2026-11-15) gives a required citation (Wagner & Robinson 2021,
LPSC 52 #2530) but **no licence statement**. The data are NASA-funded and archived in the PDS, which usually means
no copyright restrictions, but nothing on the page says so. Suggested `datasets.yaml` licence text: "No licence
stated; NASA PDS archive; cite Wagner & Robinson (2021)". Human to confirm.

## 5. Mars caves: limitation text (decision 2026-11-15)

Mars subsurface stays NaN. Suggested sentence for the write-up and the About page:

> Mars subsurface is not scored. The only global catalogue of Mars cave candidates (USGS MGC3, Cushing 2015) has no
> published false-positive rate, and many of its candidates have not been confirmed in higher-resolution images, so
> we leave the feature unmeasured instead of scoring an unvetted list.

The "no published false-positive rate" claim is based on the search done on 2026-11-14. Nobody has read the
literature fully; soften it to "we found no published false-positive rate" if you prefer.

## 6. Open items for a human

1. Approve or reject each landmark in §1 (and decide whether to keep `descartes`).
2. Approve the spec pairs in §2a. B-strength pairs are the judgement calls.
3. Decide MDRS and HI-SEAS (habitats, not similarity sites), and Teide and Lanzarote (cannot be evaluated).
4. Replace the TODO coordinates (Stillwater, Pilbara, Dalangtan, Pu'u Nene) from the papers.
5. Open each "verify DOI" at doi.org.
6. Approve the lava-tube additions and set `verified`.
