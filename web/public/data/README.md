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
| `seasons.json` | `scripts/build_seasons.py` | **yes** - Open-Meteo ERA5; `--fetch` |
| `terrain-texture.jpg` | `scripts/build_terrain_texture.py` | **in kind** - exact geometry, reconstructed palette |

## seasons.json is mostly valid and says so

Twelve-month climate normals per trail region, so the app can answer "when should I go". ERA5 is a
~28 km reanalysis and the Himalaya is its worst case: it gives Manaslu **8,228 mm a year** against a
real figure nearer 1,000-1,900, and calls April its wettest month.

So the file carries a cross-check against this repository's own CHIRPS measurement, and it does not
flatter all six regions:

| region | ERA5 ÷ CHIRPS, Jun-Sep | verdict |
|---|---|---|
| Kathmandu | **1.89** | **not reliable - should not be quoted** |
| Manaslu | 1.54 | passes the monsoon check, annual total still wrong |
| Annapurna | 1.13 | reliable |
| Upper Mustang | 1.06 | reliable |
| Langtang | 0.83 | reliable |
| Khumbu | 0.71 | reliable |

Only **June to September** could be checked, because that is the window CHIRPS covers here. The
other eight months are marked `validated: false`. The guide reports what the model says and states
which parts of it have been tested - it does not label a month good or bad, because a farmer, a
trekker and a paraglider want different weather from the same month.

## Every file here now has a recipe

Round 28 found four files with no generator: the bus stops, and the two observability files, and the
flythrough backdrop. All four have one now.

### terrain-texture.jpg is reconstructed, not reproduced

It is 2048x1260, and 2048/1260 is 1.625 - exactly the 832x512 aspect of the bundled DEM - so it is
a colour-shaded render of that same grid. `scripts/build_terrain_texture.py` renders it from
`terrain.bin` and produces the **same dimensions and the same geography**. What it cannot reproduce
is the original's **palette**: the colormap that made the committed file was not kept, so this draws
its own hypsometric ramp.

**The served file is therefore left alone.** Regenerating it would change how the 3D flythrough
looks, and replacing a working backdrop with a differently-shaded one to make a table tidier is the
same class of mistake as the observability attempt that would have silently swapped two quoted
figures. The script writes to a scratch path by default; the served path is opt-in.

### The other three were closed outright

Both observability files, and the bus stops. `scripts/build_observability.py` reproduces them
**exactly** from `reports/observability-monsoon.json` - JSON-equal to the committed files - and
refuses to write if the monsoon total stops matching 2,021 scenes.

## Licence

- Trail and bus-stop data: © OpenStreetMap contributors, **ODbL 1.0**. The attribution is written
  into the data files themselves and is required wherever they are shown.
- Terrain: AWS Terrain Tiles (terrarium), via `build_terrain.py`.
- Everything else: produced by this repository from the open sources listed in
  [docs/DATA.md](../../../docs/DATA.md).
