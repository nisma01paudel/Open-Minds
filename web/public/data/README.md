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
| `observability-sites.json` | `scripts/build_observability.py` | **yes** - from `reports/observability-monsoon.json` |
| `observability-by-month.json` | `scripts/build_observability.py` | **yes** |
| `terrain-texture.jpg` | **no committed generator** | **no** |

## The one that still cannot be rebuilt

`terrain-texture.jpg` is the backdrop of the 3D flythrough, beat 6, and **no committed generator
produces it.** The rest of the file has been rebuilt independently by
`scripts/build_observability.py`, which reproduces the two observability files exactly from
`reports/observability-monsoon.json`.

### How those two were closed, because the way they were closed matters

They were listed here as unreproducible. A first attempt to rebuild them filtered the report to
2024 and produced a `by_month` block of the wrong size - **37 months instead of 5**, with August and
September percentages that would have quietly replaced the two figures live-demo beat 5b turns on.
It ran cleanly and its output looked plausible; the only thing that caught it was diffing against
the committed file.

The correct aggregation is **all years, by calendar month, restricted to the monsoon months**: 415 /
518 / 518 / 403 / 167 scenes, **2,021 in total** - the number the data file itself states, which is
now an assertion in the script. If that total ever stops matching, the script **refuses to write**
rather than overwriting the demo's figures.

## Licence

- Trail and bus-stop data: © OpenStreetMap contributors, **ODbL 1.0**. The attribution is written
  into the data files themselves and is required wherever they are shown.
- Terrain: AWS Terrain Tiles (terrarium), via `build_terrain.py`.
- Everything else: produced by this repository from the open sources listed in
  [docs/DATA.md](../../../docs/DATA.md).
