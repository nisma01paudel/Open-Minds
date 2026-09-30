# Pahiro Watch — web interface

A 3D map of every documented landslide-prone slope in Nepal, with the office legally
responsible for each. Next.js + MapLibre GL.

```bash
npm install
npm run build          # static export into out/  (no server needed on stage)
npx serve out          # or: python3 -m http.server 8100 --directory out
```

Open `http://localhost:8100/`. Add `?f=1` to open straight to the 2024-09-28 event day.

## No API keys

Every source is keyless, deliberately. Demo Day is in person on unknown wifi, and a dead
key on stage is worse than a clean map.

| Layer | Source | Key |
|---|---|---|
| Basemap | OpenFreeMap vector tiles | none |
| 3D terrain | AWS Terrain Tiles (terrarium DEM) | none |
| Live rainfall | Open-Meteo (ICON/ECMWF/GFS) | none |
| Historical rainfall | CHIRPS | none |

## Data

`public/data/*.geojson` is generated, not hand-written:

```bash
cd .. && .venv/bin/python scripts/build_watch_geojson.py --out web/public/data
```

That runs `pahiro.watch` — one Open-Meteo batch covering 613 sites for the live frame, and
CHIRPS for the historical frames — and writes one FeatureCollection per frame plus
`frames.json`. Regenerate and the map matches the data, or the map is wrong.

## Two bugs worth remembering

Both were found by screenshotting the page and looking at it, not by reading the code.

1. The slope source was created with `/data/${frames[activeIndex].file}` inside the map's
   `load` handler. That handler runs **before** the React prop arrives, so it threw and
   silently aborted the rest of the handler — the layers were never added and the map
   rendered empty. The source is now added empty and filled by an effect.
2. The header subtitle ran underneath the panel, and grey dots at 1.6 px were invisible
   on light terrain. Both fixed, but only because the output was inspected.
