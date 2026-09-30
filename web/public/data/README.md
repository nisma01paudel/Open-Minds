# Where each file here comes from

**Everything in this directory ships with the app and is served offline.** This page records what
produced each file, because a dataset with no recipe is not data - it is an artefact somebody made
once, and `bus-parks.geojson` was exactly that until round 27.

| File | Produced by | Reproducible? |
|---|---|---|
| `trails.geojson` | `scripts/build_trails.py` | **yes** — 4 OSM regions; `--fetch` downloads them |
| `bus-parks.geojson` | `scripts/build_bus_stops.py` | **yes** — `--fetch` |
| `terrain.bin`, `terrain.json` | `scripts/build_terrain.py` | **yes** — AWS Terrain Tiles |
| `advisories.json` | `scripts/build_advisories.py` | **yes** |
| `slopes-live-*.geojson`, `slopes-chirps-*.geojson`, `frames.json` | `scripts/build_watch_geojson.py` | **yes** |
| `timeline.json` | `scripts/build_timeline.py` | **yes** |
| `observability-sites.json` | **no committed generator** | **no** |
| `observability-by-month.json` | **no committed generator** | **no** |
| `terrain-texture.jpg` | **no committed generator** | **no** |

## The three that cannot be rebuilt, stated plainly

`observability-sites.json` and `observability-by-month.json` are **live-demo beat 5b** - the
measured-observability layer, 142 sites, and the figure that August returned 16.8% usable scenes
and 17 of 142 sites were never seen at all. `terrain-texture.jpg` is the backdrop of the 3D
flythrough, beat 6.

They were derived from satellite scene metadata during the evaluation work, and **the pipeline that
produced them was not kept.** The numbers in them are reported in `reports/eval-v1.md` and are
consistent with it, and the files themselves are committed and verified by the tests - but nobody,
including the author, can regenerate them from this repository.

**An attempt to close this gap failed, and the failure is worth recording.** The measurement code is
still here (`src/pahiro/eval/observability.py`) and `reports/observability-monsoon.json` still holds
142 site rows, so the missing piece looked like assembly. A generator was written that rebuilt
`observability-sites.json` from those rows - and produced a **different `by_month` block**: 37
months instead of the 5 the app serves, and August/September percentages that are the whole of
live-demo beat 5b replaced with other numbers.

The report is **not** the source. `observability-by-month.json` says it was measured on **2,021
Sentinel-2 scenes**, against the report's per-site 30-day windows - a different computation over a
different scene set. The generator was deleted rather than shipped, because a script named
`build_observability.py` that silently produces different numbers is worse than no script at all.

What is needed is the seasonal scene inventory, not the per-site report.

That is a real gap, not a stylistic one: it means these two demo beats rest on files whose
derivation cannot be re-run or audited line by line, which is below the standard the rest of this
repository holds itself to. Rebuilding the observability pipeline is the honest fix, and until it
exists this table is the disclosure.

## Licence

- Trail and bus-stop data: © OpenStreetMap contributors, **ODbL 1.0**. The attribution is written
  into the data files themselves and is required wherever they are shown.
- Terrain: AWS Terrain Tiles (terrarium), via `build_terrain.py`.
- Everything else: produced by this repository from the open sources listed in
  [docs/DATA.md](../../../docs/DATA.md).
