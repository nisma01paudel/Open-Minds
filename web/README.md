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
| Basemap | **Sentinel-2 cloudless (EOX/ESA)** — real satellite imagery | none |
| Alt basemap | Esri World Imagery — real high-res satellite | none |
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

## Why there is no 3D terrain layer

Two approaches were tried and both were **measured**, not assumed:

| Approach | Result |
|---|---|
| `terrain` key inside the style object | map renders completely blank |
| `map.setTerrain({source:"dem"})` in `load` | map renders completely blank |
| a `raster-dem` source + `hillshade` layer present | the map's `load` event never fires, so no layer is ever added |

No error event, nothing in the console, nothing on the error surface. It was isolated by
rendering the style one piece at a time until the imagery came back. The DEM tiles
themselves are fine (HTTP 200, `Access-Control-Allow-Origin: *`), so this is almost
certainly the software GL in the headless capture environment failing the shading pass.

It may work on a real GPU. But it could not be verified here, and a layer that silently
blanks the map is worse than no layer — so what ships is the real satellite imagery,
which is verified. To try terrain, re-add a `raster-dem` source and uncomment the
`setTerrain` line in `components/SlopeMap.tsx`; if the map goes black, that is the cause.

## A warning about screenshotting this app

A cold Chromium profile with a short `--virtual-time-budget` captures the map **before
the satellite tiles arrive**, producing an apparently blank map. This cost an hour of
bisecting a bug that did not exist. Warm the profile, or allow a long budget.

## The 3D flythrough (`/fly/`)

Real elevation, real satellite imagery, real rainfall. Nothing is invented.

- **Terrain**: AWS terrarium tiles, decoded to metres. `scripts/build_terrain.py` stitches
  and decimates them to an Int16 grid (`public/data/terrain.bin`, 852 KB, 832×512, 18 m to
  8,461 m — the Everest massif is in there).
- **Drape**: the Esri World Imagery export for the terrain's exact extent, fetched to match
  so the imagery lines up with the geometry.
- **Slopes**: the same 613 sites, placed by their real coordinates, floating at the real
  terrain height, coloured by the same multi-window trigger rule.

`?step=` controls mesh density (default 4). Lower is finer; the software GL used for
automated screenshots cannot render step 2 in reasonable time, which is why the default is
4 rather than the finest possible.

### Bugs this cost, all found by running it

1. `makePoints()` returns `{ geo, mat }` and `paint()` read `pts.geometry` — a typo that
   threw at runtime and blanked the whole view.
2. The scene is built when the *terrain* arrives, which is before the *timeline* does. The
   day-setter was guarded on a `tl` closure captured as `null`, so it returned immediately
   on every call: the date advanced and the colours and counts stayed frozen on the first
   frame. Guarded on the sites instead.
3. Calling `paint()` from inside a `setState` updater is a side effect in a pure function.
   The day now drives the scene from its own effect.
4. Square point sprites. A shared radial-gradient canvas texture makes them round.
5. The camera started inside a ridge face. Pulled back and up.
