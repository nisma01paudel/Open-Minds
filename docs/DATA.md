# Data pipeline — verified live, with the traps written down

Everything below was confirmed by real requests, not from literature. The full audit is in
`research/nepal-eo-data-pipeline.md`; this file is the operational summary.

Reproduce our own measurements:

```bash
python3 scripts/verify_data_access.py --out evidence/monsoon-gap.csv   # scene availability
python -m pahiro.ingest.screen --bbox 84.95 27.75 85.10 27.90 \
    --from 2024-01-01 --to 2024-12-31 --out evidence/screen-2024      # per-AOI usability
```

## 1. Verified access (no account, no key, no cost)

| Source | Endpoint | Status |
|---|---|---|
| Sentinel-2 L2A, Sentinel-1 GRD, Copernicus DEM 30/90 m, Landsat | anonymous STAC `earth-search.aws.element84.com/v1` | live, current through 2026-09-28, **no requester-pays** |
| Sentinel-2 band windows | `sentinel-cogs` S3 range requests | HTTP 206, cloud-optimized |
| CHIRPS daily rainfall | `data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05/YYYY/...tif.gz` | open, no login |
| Copernicus DEM GLO-30 | `copernicus-dem-30m.s3.amazonaws.com` | anonymous, 44.8 MB/tile |
| SRTM | `elevation-tiles-prod.s3.amazonaws.com/skadi/N27/N27E085.hgt.gz` | anonymous |
| OSM roads/buildings | Overpass API | works, **but requires a User-Agent header (406 without)** |
| **LiCSAR InSAR (Nepal)** | frame `121D_06267_131313`, plain HTTPS | **296 epochs 2014–2025, 2,537 pre-computed interferograms, anonymous** |

**Not usable without an account:** ERA5-Land (401), NASA IMERG/HyP3 (Earthdata login), CDSE download (401),
Planetary Computer assets (SAS token), SMAP (host unreachable).

## 2. Trap 1 — `eo:cloud_cover` is the whole tile, not your slope

Sentinel-2 STAC metadata reports cloud cover for the **~110 km tile**. A scene reporting 99.95% cloud was
**100% cloud over the AOI**; the converse also happens. Scene-level filtering on this field is therefore
wrong, and it is why our first pass used the wrong metric.

**The honest measure is the SCL band read over the actual area of interest.** SCL only, windowed, costs
**~0.05 MB per scene**, so screening an entire archive for a site is tens of megabytes, not hundreds of
gigabytes.

Clear ground = SCL ∈ {4 vegetation, 5 not-vegetated, 6 water, 7 unclassified}. Class 2 (topographic shadow)
is *excluded* — on a steep Himalayan slope it can cover a large part of a patch.

## 3. The monsoon finding — measured, and stronger than the scene counts

Per-AOI measurement over a 2 km site on the Sindhupalchok–Dolakha border (27.70 N, 85.90 E), reading the SCL
window for **933 Sentinel-2 scenes, 2016-01 → 2026-09**:

| Month | median AOI clear | %>50 clear | %>80 clear |
|---|---|---|---|
| Jan | 0.80 | 72.9 | 47.1 |
| Mar | 0.88 | 71.6 | 58.1 |
| Jun | 0.00 | 20.5 | 13.3 |
| **Jul** | **0.00** | **5.7** | **0.0** |
| Aug | 0.00 | 20.2 | 8.3 |
| Sep | 0.05 | 24.7 | 14.8 |
| Nov | 0.90 | 78.1 | 65.8 |
| Dec | 0.82 | 85.1 | 60.8 |

**JJAS pooled: 335 scenes → 17.6% >50% clear, 9.0% >80% clear** — roughly one usable frame per 20 days,
clustered in late September. **In July, 0.0% of scenes across eleven years had >80% clear pixels at the AOI.**

A usable optical *pair* bracketing a July landslide essentially never exists. Optical-only monsoon change
detection is not degraded — it is **structurally absent**.

## 4. Trap 2 — Sentinel-1 GRD ships with no CRS

The `sentinel-1-grd` COG has `crs=None` and an identity transform; geolocation lives in 210 GCPs. A global
affine fit to those GCPs has **1.3 km RMS / 3.3 km max error** — a pipeline will run cleanly and read the
**wrong hillside**.

**Fix:** parse `annotation/iw-vv.xml`, read the `geolocationGridPointList` (10 lines × 21 points), and
interpolate **locally**. Assert a known landmark lands within ~1 px before trusting any result. Warning sign
for silent failure: SAR signal correlating with tile boundaries instead of terrain. Also fetch
`calibration-iw-vv.xml` for sigma0.

Radar is genuinely usable: **4–6 GRD passes every month through the monsoon**, ~5–10 s per scene on CPU.
GRD backscatter change over 50–100 scenes ≈ 10–20 minutes, under 1 GB RSS. **No SNAP needed.**

## 5. InSAR: download it, do not compute it

Raw Sentinel-1 SLC is **7.7–8.2 GB per scene** (~16 GB per pair, 16–32 GB RAM) — impossible here, and a trap.

But **LiCSAR has already computed it for Nepal**: frame `121D_06267_131313` covers 85.02–87.96 E,
26.08–28.55 N with **296 epochs (2014-10-14 → 2025-02-18) and 2,537 interferograms**, all anonymous.
Products readable via `/vsicurl`: `geo.vlos_eur.tif` (19 MB — **+19.5 mm/yr at the AOI**),
`geo.meancoh.12.tif` (7.6 MB), plus E/N/U, height, landmask.

**But the physics is weak:** measured mean 12-day coherence at the AOI is **0.16** (range 0.08–0.32), below
usable C-band range on this vegetated steep slope. Use VLOS for slow creep and `meancoh` as a *validity mask*;
**gate on meancoh > 0.3 before promising any InSAR result.** Never stake the deliverable on it.

## 6. Rainfall — the always-available signal, with district-specific thresholds

CHIRPS verified live (2024-07-15 over the AOI = 45.3 mm). Published intensity–duration thresholds for
**Sindhupalchok, the same district as Melampchi** (Practical Action 2025):

| Catchment | Threshold | 24 h equivalent |
|---|---|---|
| Helambu | `I = 41.029 · D^(-0.651)` | **124.4 mm/24 h** |
| Panchpokhari Thangpal | `I = 52.476 · D^(-0.743)` | **118.8 mm/24 h** |
| Dahal (2008), regional | — | ≈145 mm/24 h |
| Dahal & Hasegawa (2008) | `I = 73.90 · D^(-0.79)` | — |

Also triggering: <10 h at ~10 mm/h, or >100 h of sustained >2 mm/h.
**Caveat we will state:** those R² ≈ 0.998 fits rest on only **44 and 43 landslide events**.

**This is why the trigger layer leads with rainfall**: it is available every day of the monsoon, unlike
optical imagery. Rainfall proposes; ground evidence (radar, dry-season optical, LiCSAR creep, citizen
reports) disposes.

## 7. Download economics — two-tier screening wins decisively

| Approach | Volume |
|---|---|
| SCL screening pass, all scenes for one site | **47 MB** (~1 min) |
| One scene, all 11 bands, 2 km AOI | 9.69 MB / 22 range requests |
| One scene, SCL only | 0.05 MB |
| Clear-only scenes, one site, full archive | 4.27 GB |
| Full tiles (never do this) | 543 GB |

**Pattern: (1) SCL-screen every scene per site; (2) fetch only the passing scenes, only B02/B03/B04/B08.**
Cache extracted arrays keyed `(site, item, band)`. Disk: ~10 GB for 1–3 sites.

## 8. Resulting pipeline order (lowest risk first)

1. **Terrain + assets + rainfall baseline** — Copernicus DEM, Overpass, CHIRPS 2016–2026. Zero accounts, zero risk.
2. **SCL screening** → a per-site, per-date clear table. The single most valuable derived artefact.
3. **Dry-season optical** — 10 m NDVI/brightness series (Oct–Nov scar mapping).
4. **Radar through the monsoon** — GRD windows, correctly geolocated, sigma0 change.
5. **Rainfall trigger** — 24 h + 3–10 day antecedent against the district thresholds above.
6. **LiCSAR creep** — VLOS + coherence mask, gated on meancoh > 0.3.

## 9. What we could not verify
ERA5-Land latency (no account) · SMAP (host unreachable) · HyP3 Nepal coverage/latency (401) · accuracy of
the annotation-grid local geolocation residual (the *global affine* is proven bad; the local method's
residual is unverified — validate against a landmark) · LiCSAR individual unwrapped-phase pairs (the
aggregated products are verified, the per-pair directory 404'd) · whether an ascending LiCSAR frame covers
Nepal (none found) · **all cloud and coherence statistics are from one AOI — the method transfers, the numbers
must be re-measured per site.**
