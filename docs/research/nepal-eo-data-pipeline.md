# Nepal Multi-Temporal EO / Environmental Data Pipeline — Verified Technical Path

**Verified live on 2026-09-30** from a CPU-only Linux box (the target machine class: Ryzen 5 8645HS, 12 threads, 14 GB RAM, ~3 GB free, no NVIDIA GPU).

Every endpoint below was actually called. Where a number is given it was **measured**, not estimated. Where I could not verify something it is listed in §9.

**Test AOI** (used throughout): `2 km × 2 km`, EPSG:4326 polygon
`85.89,27.69 → 85.91,27.71` (centre **27.70 N, 85.90 E**).
OSM data shows this sits on the **Sun Koshi / Khadichaur–Jiri corridor (NH23 near Charikot–Dolakha Road)** on the Sindhupalchok–Dolakha border — the same mid-hill terrain class as Melamchi and Jhyaple Khola. It lies in MGRS tile **45RUL**, UTM zone 45N easting ≈ 391,500 m.
If your site is Jhyaple Khola proper (~27.87 N, 84.87 E, Dhading) it falls in a different MGRS tile; the *method* below is unchanged, only the tile ID differs.

---

## 0. Headline conclusions

| Question | Verdict |
|---|---|
| Sentinel-2 L2A COG, anonymous, no account? | **YES** — Element84 Earth Search v1 is live, no auth, no requester-pays. Verified 200/206. |
| Optical change detection in the monsoon? | **NO.** Measured: in July, **0.0 %** of 11 years of scenes had >80 % clear pixels over this AOI. |
| Sentinel-1 GRD free/anonymous? | **YES**, as real COGs on AWS — with a serious georeferencing gotcha (§3.2). |
| Run InSAR on CPU? | **Do not.** ~8 GB/SLC scene, ~16 GB per pair. But you don't need to — **LiCSAR already pre-computed 10 years of InSAR + coherence for Nepal**, free and anonymous. |
| Is InSAR useful here? | **Marginal.** Measured mean 12-day coherence at the AOI = **0.16**. C-band is largely decorrelated on this slope. |
| Rainfall thresholds exist for this exact district? | **YES** — Practical Action (2025) thresholds for Helambu / Panchpokhari Thangpal, Sindhupalchok. |
| Everything free, no paid AI API? | **YES.** CHIRPS, Copernicus DEM, SRTM, OSM, LiCSAR need no account. CDSE/ERA5/IMERG/SMAP need *free* accounts only. |

**Bottom line: the viable 4-week CPU-only pipeline is rainfall + terrain + Sentinel-1 GRD amplitude change + LiCSAR coherence *as a screening layer*, with Sentinel-2 used only as an opportunistic dry-season supplement.** Optical-only landslide detection in the Nepal monsoon does not work, and this is now measured, not asserted.

---

## 1. Sentinel-2 optical time series (highest priority)

### 1.1 Catalogue-by-catalogue verdict (all tested anonymously)

| Option | Status 2026-09-30 | Auth | Requester-pays? |
|---|---|---|---|
| **(a) Earth Search v1** `https://earth-search.aws.element84.com/v1` | **LIVE — use this** | **None** | **No** |
| (b) AWS `sentinel-cogs` bucket | **LIVE** | None | No |
| (b) AWS `sentinel-s2-l2a` (JP2) | **LIVE but hrefs in STAC are stale** | None | No |
| (c) Copernicus Data Space (CDSE) | STAC/OData metadata anonymous, **download 401** | Free account + OAuth | No |
| (d) Planetary Computer STAC | `/search` anonymous, **assets need SAS token** | API key (free tier) | No |
| (e) Google Earth Engine | **Proprietary hosted — EXCLUDED** per your constraints | Google account + project | n/a |

#### Earth Search — collections actually returned
```
sentinel-2-l2a            Sentinel-2 Level-2A            <- use this
sentinel-2-c1-l2a         Sentinel-2 Collection 1 L2A    <- alias, same 23 items for 2026 Q3
sentinel-2-pre-c1-l2a     pre-Collection-1 archive       <- 0 items for 2026 Q3 (legacy)
sentinel-2-l1c            Sentinel-2 Level-1C
sentinel-1-grd            Sentinel-1 IW GRD (COG)
cop-dem-glo-30 / cop-dem-glo-90
landsat-c2-l2
naip
```
`sentinel-2-l2a` and `sentinel-2-c1-l2a` are both populated through **2026-09-28** with identical counts for the AOI — these are the same data. Note the collection `license` field literally reads `"proprietary"`; that is an artifact of the Element 84 STAC metadata, not a data restriction — Sentinel data is free and open under the Copernicus licence, but **have counsel confirm before commercial redistribution**.

**Anonymous access proven:**
```bash
# search: 200 OK, no key
curl -s -X POST "https://earth-search.aws.element84.com/v1/search" \
  -H "Content-Type: application/json" -d '{
   "collections":["sentinel-2-l2a"],
   "intersects":{"type":"Polygon","coordinates":[[[85.89,27.69],[85.91,27.69],[85.91,27.71],[85.89,27.71],[85.89,27.69]]]},
   "datetime":"2024-06-01T00:00:00Z/2024-09-30T23:59:59Z","limit":100}'

# COG range read: 206 Partial Content, no key, no requester-pays
curl -s -r 0-1023 "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/45/R/UL/2024/9/S2A_45RUL_20240928_0_L2A/B04.tif"
# -> HTTP/1.1 206 Partial Content
#    Content-Range: bytes 0-1023/98232824
#    Content-Type: image/tiff; application=geotiff; profile=cloud-optimized
```
Pagination needs the **`next` token inside `links[rel=next].body.next`** (not `merge`) — this trips people up.

#### AWS buckets — the important gotcha
`sentinel-s2-l2a` (the JP2 archive) is **anonymously listable and readable** — but the `*-jp2` asset hrefs that Earth Search returns are **wrong**:
```
Earth Search says:  s3://sentinel-s2-l2a/tiles/45/R/UL/2024/9/28/0/B04.jp2          -> 404 over HTTPS
Actually exists:    .../tiles/45/R/UL/2024/9/28/0/R10m/B04.jp2                      -> 206
```
The real layout is `.../<date>/<orbit>/<R10m|R20m|R60m>/<BAND>.jp2`, and **SCL exists only under `R20m/` and `R60m/`**. If you ever fall back to JP2, fix the path. (Practically: don't fall back — the COG path is better.)

### 1.2 Bands, resolutions, cloud masking

**Resolution groups** (all tiles 10980 × 10980 at 10 m; COG internal tiles 1024 × 1024):

| Group | Bands |
|---|---|
| **10 m** | B02 (blue), B03 (green), B04 (red), B08 (NIR) |
| **20 m** | B05, B06, B07, B8A (red edge/NIR), B11, B12 (SWIR), **SCL** |
| **60 m** | B01 (coastal), B09 (water vapour) |
| auxiliary | AOT, WVP, TCI (visual), thumbnail |

**Cloud masking: use `SCL`.** QA60 exists only in L1C; Fmask is unnecessary. SCL is a uint8 classification: `4`=vegetation, `5`=bare, `6`=water, `7`=unclassified are **usable**; `3`=cloud shadow, `8`=cloud med, `9`=cloud high, `10`=thin cirrus, `11`=snow are **mask**. `0`=nodata.
An `scl` mask classifier is baked into the COG, and SCL is **tiny**: the whole 110 km tile at 20 m is **0.2 MB**, and a 2 km windowed read is **50 KB**.

**Measured full-tile COG sizes** (tile 45RUL, 2024-09-28) so you can budget:

| Band | MB | Band | MB |
|---|---|---|---|
| B08 NIR (10 m) | 97.7 | B11 SWIR (20 m) | 31.0 |
| B02 (10 m) | 93.9 | B12 SWIR (20 m) | 31.1 |
| B04 (10 m) | 93.7 | B01 (60 m) | 4.2 |
| B03 (10 m) | 92.8 | B09 (60 m) | 4.1 |
| B8A (20 m) | 37.3 | TCI / WVP / AOT | 0.9 / 0.7 / 0.6 |
| B06 (20 m) | 36.0 | **SCL (20 m)** | **0.2** |
| B07 (20 m) | 35.8 | **TOTAL tile** | **≈ 596 MB** |
| B05 (20 m) | 35.6 | JP2 archive equivalent | 564 MB |

### 1.3 Data volume for a 2 km × 2 km AOI, 2016–2026 — measured

I measured this properly by intercepting GDAL's curl range requests (`CPL_CURL_VERBOSE=YES`) during a real read of all 11 bands:

**One scene, full 11-band read of a 2 km AOI = 9.69 MB across 22 HTTP range requests.**

| Subset | MB / scene |
|---|---|
| SCL only (cloud screening) | **0.05** |
| SCL + 4× 10 m bands (B02,B03,B04,B08) | 5.67 |
| SCL + all 10 m + 20 m bands | **9.69** |

**Scenes intersecting the AOI, 2016-01-01 → 2026-09-30: 934** (117 months ⇒ **7.2 scenes/month**; note S2B retirement cut this from ~8.3 to ~6/month).
451 (48.3 %) have >50 % clear AOI pixels; 317 (34.0 %) have >80 %.

| Strategy | Volume |
|---|---|
| **SCL-only screening pass over all 934 scenes** | **47 MB** |
| All 934 scenes, all 11 bands | **8.84 GB** |
| Only the 451 scenes with >50 % clear pixels, all bands | **4.27 GB** |
| *Naïve: download full 110 km tiles* | ***543 GB*** |

**The 9.69 MB vs 543 MB gap is the single most important engineering fact in this document.** Never download a whole tile for a 2 km AOI.

### 1.4 Working Python (pystac-client + rasterio windowed read)
```python
from pystac_client import Client
import rasterio, numpy as np
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from rasterio.env import Env

catalog = Client.open("https://earth-search.aws.element84.com/v1")   # no auth
items = list(catalog.search(
    collections=["sentinel-2-l2a"],
    intersects={"type":"Point","coordinates":[85.90,27.70]},
    datetime="2024-09-01/2024-09-30").items())

env = Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
          CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
          GDAL_HTTP_MULTIPLEX="YES")
BANDS = ["blue","green","red","nir","rededge1","rededge2","rededge3",
         "nir08","swir16","swir22","scl"]

with env:
    for it in items:
        stack = {}
        for b in BANDS:
            with rasterio.open(it.assets[b].href) as ds:          # HTTPS COG, anonymous
                bb = transform_bounds("EPSG:4326", ds.crs, 85.89,27.69,85.91,27.71)
                stack[b] = ds.read(1, window=from_bounds(*bb, ds.transform))
        usable = np.isin(stack["scl"], [4,5,6,7]).mean()
        print(it.id, it.properties["datetime"][:10],
              f"aoi_clear={usable:.2f}", "eo:cloud_cover=", it.properties.get("eo:cloud_cover"))
```
> **Do not trust `eo:cloud_cover` for a small AOI** — it is the whole 110 km tile's cloud cover. In my data the 2024-09-28 scene reports 99.95 % and is in fact **100 % cloud over the AOI** (11199/11200 px = SCL 8). Always mask with SCL.

---

## 2. Cloud-cover reality — measured, not cited

I read the **SCL window for the AOI for every one of the 933 readable scenes** and computed the true per-AOI clear fraction. This is the most important result in this report.

### 2.1 Monthly climatology (pooled 2016-01 → 2026-09)

| Month | scenes | median tile CC % | **median AOI clear frac** | % scenes >50 % clear | % >80 % clear | **usable/mo (>50 %)** |
|---|---|---|---|---|---|---|
| Jan | 70 | 12.7 | 0.80 | 72.9 | 47.1 | 5.1 |
| Feb | 74 | 13.5 | 0.76 | 66.2 | 43.2 | 4.9 |
| Mar | 74 | 8.9 | 0.88 | 71.6 | 58.1 | 5.3 |
| Apr | 78 | 23.2 | 0.93 | 65.4 | 53.8 | 5.1 |
| **May** | 81 | 60.6 | 0.05 | 40.7 | 29.6 | 3.3 |
| **Jun** | 83 | 76.8 | **0.00** | 20.5 | 13.3 | 1.7 |
| **Jul** | 87 | 88.2 | **0.00** | **5.7** | **0.0** | **0.5** |
| **Aug** | 84 | 81.8 | **0.00** | 20.2 | 8.3 | 1.7 |
| **Sep** | 81 | 63.9 | 0.05 | 24.7 | 14.8 | 2.0 |
| Oct | 74 | 26.3 | 0.43 | 47.3 | 27.0 | 3.9 |
| Nov | 73 | 6.9 | 0.90 | 78.1 | 65.8 | 6.3 |
| Dec | 74 | 5.4 | 0.82 | **85.1** | 60.8 | **7.0** |

### 2.2 The monsoon numbers that decide the design

- **July: in 11 years, 0.0 % of scenes — not one — had >80 % clear pixels over this AOI.** Median clear fraction is exactly **0.00**. Median tile cloud cover 88.2 %.
- **JJAS (Jun–Sep) pooled:** 335 scenes; only **59 (17.6 %)** exceed 50 % clear and **30 (9.0 %)** exceed 80 % clear.
  ⇒ **≈ 6 usable scenes and ≈ 3 good scenes per JJAS season** — roughly **one usable frame every 20 days**, concentrated in late September.
- Dry season is excellent: Dec/Nov/Jan/Mar give 5–7 usable scenes per month.

**Why this kills optical change detection in the landslide season:** landslides in Sindhupalchok cluster in Jun–Aug. To detect one you need a *usable before* and a *usable after* scene bracketing the event. With ~1 usable frame per 20 days, and near-zero availability in Jul, the expected gap between usable observations around any given monsoon failure exceeds the useful detection window. **This is a measured conclusion, and it matches the design intuition — but now it is quantified for your exact AOI rather than assumed.**

**Recommendation:** use Sentinel-2 for (a) dry-season baseline / inventory / pre-monsoon conditioning, and (b) opportunistic post-monsoon (Oct–Nov) scar mapping. **Do not build the real-time trigger on Sentinel-2.**

---

## 3. Sentinel-1 SAR — the monsoon-proof option

### 3.1 Availability — verified

| Product | Where | Auth | Size |
|---|---|---|---|
| **GRD (COG)** | Earth Search `sentinel-1-grd` → `s3://sentinel-s1-l1c/...` | **None** | VV **727 MB**, VH **606 MB** |
| GRD (SAFE) | CDSE OData | Free account | 1.2–1.7 GB each |
| **SLC** | **CDSE only** | Free account | **7.7–8.2 GB each** |

Earth Search `sentinel-1-grd` for the AOI: **20 items Jun–Sep 2024**, **60 items in all of 2024** (31 ascending orbit 85 / 29 descending orbit 121) ⇒ **~5 passes/month through the monsoon**, exactly as required.
*Cross-check / correction:* CDSE OData returns 125 rows for 2024 but only **60 unique acquisitions** — it lists each acquisition twice (legacy SAFE + a new `_COG.SAFE` variant). So **Earth Search is complete**, not missing half the data as a raw count suggests. CDSE's new `_COG.SAFE` products are a notable 2026 development.

Request:
```bash
curl -s -X POST "https://earth-search.aws.element84.com/v1/search" \
 -H "Content-Type: application/json" -d '{
  "collections":["sentinel-1-grd"],
  "intersects":{"type":"Point","coordinates":[85.9,27.7]},
  "datetime":"2024-06-01T00:00:00Z/2024-09-30T23:59:59Z",
  "query":{"sar:polarizations":{"eq":["VV","VH"]}}}'
# assets: "vv" and "vh" -> image/tiff; application=geotiff; profile=cloud-optimized
# e.g. https://sentinel-s1-l1c.s3.amazonaws.com/GRD/2024/9/27/IW/DV/.../measurement/iw-vv.tiff
```
Good news, verified: this **is** a genuine COG — `tiled=True`, internal blocks **1024 × 1024**, **6 overviews**, DEFLATE, uint16, 16748 × 25537. A 100 × 100 px windowed HTTP read took **3.67 s** at **80 MB peak RSS**. Windowed access works.

### 3.2 ⚠ The georeferencing gotcha (this will silently ruin your results)

The GRD measurement COG has **`crs = None` and an identity transform**:
```
crs: None
transform: | 1.00, 0.00, 0.00 |
           | 0.00, 1.00, 0.00 |
bounds: BoundingBox(left=0.0, bottom=16748.0, right=25537.0, top=0.0)
```
Geolocation lives in **210 GCPs in EPSG:4326**. I fitted a global affine to them and measured the residuals:

```
residual lon: max 0.0333 deg   rms 0.0135 deg
residual lat: max 0.0076 deg   rms 0.0032 deg
-> max error ~3.3 km, RMS ~1.3 km
```

**A global affine/GCP fit misplaces your 2 km AOI by ~1.3 km — it will read the wrong hillside.** An affine is simply the wrong model for SAR range/azimuth geometry.

**Correct approach (proven, pure-Python, no SNAP):** fetch `annotation/iw-vv.xml` (1.7 MB, anonymous) and use its `geolocationGridPointList` — verified as a **10 (azimuth) × 21 (range)** grid with `line`, `pixel`, `latitude`, `longitude`, `height` per point. Interpolate **locally** (bilinear on the 4 surrounding grid nodes) to map AOI corners → pixel coords, then read the window. Useful metadata also in that file: `productType=GRD`, `mode=IW`, `pass=Descending`, `rangePixelSpacing=10`, `azimuthPixelSpacing=10`, `incidenceAngleMidSwath≈39.3°`.
The `calibration-iw-vv.xml` (1.0 MB) and `noise-iw-vv.xml` (0.4 MB) are also anonymously fetchable for sigma0 calibration.
> Equivalent, better-tested options: `s1reader` (ISCE3) or `xsar` (CNES/Ifremer) — I did not install-test these here (see §9). Avoid a naive `rasterio.transform.from_gcps`: I measured it returning a degenerate near-zero-scale affine.

### 3.3 CPU cost, honestly

**(a) GRD backscatter change between two dates — cheap and realistic.**
Per scene per 2 km AOI: open + geolocate + windowed read + apply sigma0 calibration ≈ **~5–10 s**. The only heavy download is the two 1–1.4 MB annotation XMLs; the measurement window itself is a few MB.
**50–100 GRD scenes ⇒ ~10–20 minutes of CPU, well under 1 GB RSS.** Comfortably within your 3 GB free RAM and 4 weeks. Tools: `rasterio` (windows + `/vsicurl`), pure-Python XML parse, optionally `pyroSAR`/`sarpy`/`xsar`. **SNAP `gpt` is not required and is a poor fit for 3 GB RAM.**

**(b) InSAR coherence from SLC pairs — do not attempt on this machine.**
- One Sentinel-1 IW SLC = **7.7–8.2 GB** (measured on CDSE). A pair = **~16 GB download** and typically 20–40 GB of scratch.
- ISCE2/`topsStack`, SNAP, GMTSAR all want **16–32 GB RAM** and run for **hours to days per interferogram** even on a GPU-less workstation. With **3 GB free RAM** this is not a matter of tuning — it will swap (you have 29 GB swap; it will thrash) and likely fail.
- **Verdict: yes, running raw InSAR on this box in 4 weeks is a trap.**

### 3.4 The escape hatch: LiCSAR — pre-computed InSAR for Nepal, free, anonymous

**You do not need to compute InSAR. COMET-LiCSAR has already done it for Nepal.**

I searched every LiCSAR frame footprint for the AOI and found exactly one covering it:

> **Frame `121D_06267_131313`** — footprint lon **85.02–87.96**, lat **26.08–28.55** (contains 85.90 E, 27.70 N)
> Descending relative orbit 121, heading −169.6°, incidence ≈ 34°, common master 2016-09-21, applied DEM SRTM 30 m.
> Base: `https://gws-access.jasmin.ac.uk/public/nceo_geohazards/LiCSAR_products/121/121D_06267_131313/`

| Property | Measured value |
|---|---|
| **Epochs** | **296**, from **2014-10-14** to **2025-02-18** (10.3 years) |
| **Pre-computed interferograms** | **2,537** |
| Auth | **None — plain HTTPS, anonymous** |
| Uploaded/updated | 2026-07-22 |

Verified-downloadable derived products (all anonymous, all read successfully with `rasterio` over `/vsicurl`):

| Product | Size | Measured at the AOI |
|---|---|---|
| `…geo.vlos_eur.tif` — LOS velocity | 19 MB | **+19.5 mm/yr** |
| `…geo.meancoh.12.tif` — mean 12-day coherence | 7.6 MB | **40.9/255 = 0.16 coherence** |
| `…geo.meancoh.{6,24,36,48,84,96,108,…}.tif` | 3.6–7.6 MB | — |
| `…geo.E.tif` / `.N.tif` / `.U.tif` (E/N/U displacement) | 23 MB each | — |
| `…geo.hgt.tif`, `.hillshade.nc`, `.landmask.tif` | 24 / 24 / 0.05 MB | height 1825 m |
| `data_summary.txt`, `baselines`, `network.png`, `lackifg.txt` | small | — |

All are **EPSG:4326 at 0.001° (~111 m)**, and a 20 × 20 px AOI window reads in **~2 s** with tiny memory. A full per-frame metadata pull is **~49 MB**.

**Strategic consequence:** your "monsoon-proof" layer can be a *download* rather than a *computation*. `geo.vlos_eur.tif` gives you 10 years of displacement; `meancoh.*.tif` gives you multi-temporal coherence directly. This converts an impossible CPU task into a ~100 MB download.

### 3.5 ⚠ But is coherence actually useful here? — measured answer: marginal

I read the real coherence value at the AOI: **mean 12-day coherence = 41/255 ≈ 0.16** (range across the 20 × 20 window: 21–82 ⇒ 0.08–0.32).

**0.16 is low.** Practical InSAR change detection generally wants >0.3–0.4 sustained. This is the expected C-band result for a steep, vegetated, monsoon-soaked Himalayan slope with rapid decorrelation. So:
- **Do not** plan on InSAR coherence as your primary landslide change signal at this AOI.
- **Do** use LiCSAR VLOS velocity as a slow-moving-creep / preconditioning layer, and mean coherence as a *data-quality map* that tells you where InSAR is even worth reading.
- Check the AOI-specific coherence **before** committing to any InSAR-based claim. The infrastructure exists; the geophysics at this specific slope is the weak link.

### 3.6 Free on-demand InSAR services — status
| Service | Status (verified) | Notes |
|---|---|---|
| **ASF HyP3** `https://hyp3-api.asf.alaska.edu/jobs` | **401 — token required** | Free, needs NASA Earthdata login. Produces InSAR/autoRIFT. **I could not verify Nepal coverage or latency** without an account. |
| **ASF Search API** `https://api.daac.asf.alaska.edu/services/search/param` | **200, anonymous** | Metadata search only; `intersectsWith=POINT(85.9 27.7)` (note: **not** `intersects` — that returns HTTP 400). Downloads need Earthdata login. |
| **COMET-LiCSAR** | **200, anonymous** | **The winner — see §3.4.** |
| **EGMS** | 200 | **Europe only — does not cover Nepal.** |
| Copernicus CDSE on-demand | not verified | Requires account. |

---

## 4. Rainfall and environmental signals

### 4.1 Access matrix (all tested)

| Source | Auth | Verified | Exact endpoint |
|---|---|---|---|
| **CHIRPS** | **NONE** | **206 / 200** | `https://data.chc.ucsb.edu/products/CHIRPS-2.0/…` |
| ERA5-Land (CDS) | **Free account + API key** | **401 anonymous** | `https://cds.climate.copernicus.eu/api/retrieve/v1/processes/reanalysis-era5-land/execute` |
| IMERG (GES DISC) | **Free Earthdata login** | **401 / 302→login** | see below |
| SMAP (NSIDC) | **Free Earthdata login** | **could not verify** | see §9 |
| **Copernicus DEM** | **NONE** | **206** | `https://copernicus-dem-30m.s3.amazonaws.com/…` |
| **SRTM (Skadi)** | **NONE** | **206** | `https://elevation-tiles-prod.s3.amazonaws.com/skadi/N27/N27E085.hgt.gz` |
| **OSM Overpass** | **NONE** (needs User-Agent) | **200** | `https://overpass-api.de/api/interpreter` |

### 4.2 CHIRPS — fully open, recommended
0.05° (~5.5 km) global daily precipitation. No account, no key. Verified working URLs:
```
# daily GeoTIFF, 1981–present (final)      ~3.0 MB gz  /  57.6 MB uncompressed per day (global)
https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05/2024/chirps-v2.0.2024.07.15.tif.gz
# daily NetCDF
https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/netcdf/p05/chirps-v2.0.2024.days_p05.nc
# whole-year NetCDF  (1.36 GB/yr) — better bulk option
https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/netcdf/p05/chirps-v2.0.2024.days_p05.nc
# preliminary / near-real-time (verified live for 2026-08-15)
https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/global_daily/tifs/p05/2026/chirps-v2.0.2026.08.15.tif.gz
```
**Real read verified:** for the AOI on **2024-07-15**, CHIRPS gives **44.3 / 38.8 / 58.2 / 40.0 mm** across the four 0.05° cells, mean **45.3 mm** — a genuine monsoon day. `float32`, EPSG:4326, nodata `None`.

**Volume note:** each daily global file is ~3 MB gzipped regardless of AOI, so **10 years of daily = ~11 GB**. Prefer the **yearly NetCDF (1.36 GB × 11 ≈ 15 GB)**, or better, for 5–20 sites just download the days you need (a few hundred MB).

### 4.3 ERA5-Land — free account required (verified 401)
```
POST https://cds.climate.copernicus.eu/api/retrieve/v1/processes/reanalysis-era5-land/execute
-> {"type":"permission denied","status":401,"detail":"authentication required"}
```
- **Free** CDS account + API key, via the `cdsapi` Python client.
- Grid **0.1° × 0.1°** delivered (native 9 km), **hourly**, 1950 → ~2–3 months ago; **ERA5-Land-T** NRT is **~5 days behind real time**, updated daily at no fixed time.
- **⚠ Accumulation gotcha:** ERA5-Land accumulations (including precipitation) run **from forecast start 00 UTC**, and the convention **differs from ERA5**. CDS `time=00` accumulations cover the *previous* 24 h. Get this wrong and your daily rainfall totals are shifted by a day — which directly corrupts any antecedent-rainfall threshold.
- **Download latency: I could not verify** (needs an account). Reported behaviour for small ERA5-Land area requests is minutes-to-tens-of-minutes in the CDS queue; treat as unverified.

### 4.4 NASA IMERG — free Earthdata login required
```
https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGDL.07/2024/07/3B-DAY-L.MS.MRG.3IMERG.20240715-S000000-E235959.V07B.nc4
-> HTTP 401, redirected to https://urs.earthdata.nasa.gov/oauth/authorize?...  "HTTP Basic: Access denied."
```
Note a **trap I hit**: the OPeNDAP `.dds` metadata endpoint returned **HTTP 200 anonymously** and looks open — but actually **fetching data** (`.ascii` / `.dods`) returns **302 → Earthdata login**. Metadata being public does not mean data is public. **Free Earthdata account required.**

### 4.5 SMAP soil moisture
SMAP L4 (`SPL4SMGP.008`) requires **NASA Earthdata login**. In this environment the NSIDC data host `n5eil01u.ecs.nsidc.org` did **not connect at all** (HTTP 000 — DNS/routing), while `daacdata.apps.nsidc.org` returned 302 (login redirect) and the landing page `nsidc.org/data/spl4smgp` returned 200. **I could not verify a working anonymous or authenticated SMAP download path from here** — see §9.

### 4.6 Empirical rainfall thresholds for Nepal — found, and for your exact district

**The key source: Practical Action (2025), *Developing thresholds for landslides triggered by rainfall in the Helambu–Panchpokhari Thangpal area*, Sindhupalchok.** This is the same district as Melamchi and overlaps the Jhyaple Khola terrain class.

**Local intensity–duration (I–D) thresholds (useable directly in code):**
```
Helambu               I = 41.029 · D^(-0.651)     valid 14 < D < 450 h    R² = 0.9984
Panchpokhari Thangpal I = 52.476 · D^(-0.743)     valid 13 < D < 300 h    R² = 0.9969
        where I = hourly rainfall intensity (mm/h), D = event duration (hours)
```
**24-hour equivalents reported by the same study:** **Helambu 124.38 mm/24 h**, **Panchpokhari Thangpal 118.76 mm/24 h**. The study also notes that for events **<10 h an intensity of ~10 mm/h** is needed, while **<2 mm/h sustained beyond ~100 h** is sufficient to trigger failure.

**Comparison / regional thresholds (from that report's Table 2 — cites verified in the PDF):**

| Scope | Source | Equation | Range |
|---|---|---|---|
| Regional (Nepal) | **Dahal & Hasegawa (2008)** | I = 73.90 D^(−0.79) | 5 < D < 720 h |
| Nepal (24 h) | **Dahal (2008)** | **≈145 mm/24 h** | — |
| World | Guzzetti et al. (2008) | I = 8.70 D^(−0.66) | 0.1 < D < 1000 h |
| World | Caine (1980) | I = 14.82 D^(−0.39) | 0.167 < D < 500 h |
| Regional | Mathew et al. (2014) | I = 58.7 D^(−1.12) | 6 < D < 100 h |
| Local | Harilal et al. (2019) | I = 43.62 D^(−0.78) | 24 < D < 720 h |
| Local | Dikshit et al. (2017) | I = 3.72 D^(−0.48) | — |
| Regional | Kanungo & Sharma (2014) | I = 1.82 D^(−0.23) | 24 < D < 336 h |
| Regional | Aleotti (2004) | I = 19.00 D^(−0.50) | 4 < D < 150 h |

**Methodology you must replicate to use these** (the study is explicit):
1. Daily rainfall from **DHM** (Dept. of Hydrology and Meteorology, Nepal) stations.
2. **A 24 h period with no rainfall is treated as a break** in the cumulative event — this defines event boundaries. Getting this wrong changes every duration.
3. Sub-daily rainfall is *estimated* from daily using a sine transform:
   `P_t / P_24 = sin(π·t / 48)^0.4727` (t in hours, sine in radians).
4. Rainfall is spatially interpolated to each landslide point with **IDW**.
5. Study-area monsoon totals for context: **Helambu 3646.75 mm**, **Panchpokhari Thangpal 3338 mm**.
6. Event example given: daily rainfall 123 mm (24 Jul) and 110 mm (25 Jul), event duration ~35 h, total event rainfall ~213 mm.

**Landslide inventories behind the thresholds:** 755 landslides in Helambu (44 with rainfall-duration data) and 213 in Panchpokhari Thangpal (43 usable). **Note the small effective sample (44 and 43)** — the very high R² (0.998) reflects a fit to few points; treat these thresholds as indicative, not definitive.

**Also relevant** (found, not yet fully extracted — PDF was behind an HTTP 406 for automated fetch): Bhandary et al., *"Physically Validated Rainfall Thresholds for Roadside Landslides Using SMAP Soil Moisture and Antecedent Rainfall Models"*, **Geosciences (MDPI) 16(4):150** — combines **SMAP soil moisture with antecedent rainfall** for roadside landslides; likely Nepal-based given the authorship. This is the natural next read if you want a soil-moisture-conditioned threshold.

---

## 5. Terrain and asset data

### 5.1 Copernicus DEM GLO-30 — recommended, fully open
```
# anonymous bucket listing: 200
https://copernicus-dem-30m.s3.amazonaws.com/?list-type=2&max-keys=3

# 1°×1° tile covering the AOI: 206, Content-Length 44,874,244 (~44.8 MB)
https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N27_00_E085_00_DEM/Copernicus_DSM_COG_10_N27_00_E085_00_DEM.tif
```
Verified: anonymous, range-readable, real COG. Same pattern for `copernicus-dem-90m`. This is the **best** free DEM here: globally consistent, 30 m, radar-derived (better in cloud-prone terrain than SRTM), and already a COG.
Derive slope/aspect/curvature with `gdaldem` or `richdem`/`xarray` — all CPU-friendly.

### 5.2 SRTM — also open via a mirror
```
https://elevation-tiles-prod.s3.amazonaws.com/skadi/N27/N27E085.hgt.gz   -> 206 (verified)
```
(These are the Mapzen/Terrain-Tiles SRTM 30 m tiles, AWS Open Data, anonymous.) The USGS `e4ftl01.cr.usgs.gov` path returned 404 for that directory and requires Earthdata login anyway — prefer the Skadi mirror or GLO-30.

### 5.3 OpenStreetMap via Overpass — works, with caveats
```
POST https://overpass-api.de/api/interpreter   --data-urlencode 'data=<query>'
```
**Must send a User-Agent** — without one, `overpass-api.de` returns **HTTP 406 Not Acceptable** (verified; this is the #1 Overpass gotcha). With a UA it returns 200.

Verified queries and results:
- **Roads** in a 0.25° box around the corridor: 25 hits including **NH23 (Khadichaur–Jiri Highway)**, **NH34 (trunk)**, **NH28 (Charikot–Dolakha Road)**, **Kalinchok Road**, and tertiary refs `23DR023/024/035`.
- **Buildings** in the exact 2 km AOI: **306** ways.

**⚠ Data-freshness differences between mirrors (measured the same minute):**
| Mirror | `osm3s.timestamp_osm_base` | Status |
|---|---|---|
| `overpass-api.de` | **2026-09-30T04:39Z** (current) | **use this** |
| `overpass.kumi.systems` | **2026-07-28T02:16Z** (2 months stale) | failover only |

For road-corridor asset data, OSM is usable and the `highway=*` + `ref=NH*` tagging is good enough to build corridor segments. For **property/parcel** data, OSM is *not* a cadastre — Nepal does not have open parcel boundaries. Use buildings/footprints as an asset proxy, and state that limitation.

---

## 6. Bulk download vs on-demand streaming

**On-demand windowed streaming wins decisively, and I have the numbers.**

| Approach | Volume for the full 2016–2026 archive, 1 site | Time @ 20 Mbps | Time @ 50 Mbps |
|---|---|---|---|
| SCL-only screening (934 scenes) | **47 MB** | ~19 s | ~8 s |
| Only >50 %-clear scenes, all bands (451) | **4.27 GB** | ~29 min | ~12 min |
| All 934 scenes, all bands | **8.84 GB** | ~59 min | ~24 min |
| Full 110 km tiles (never do this) | 543 GB | ~60 hours | ~24 hours |

Per-scene timing: a cold 11-band windowed read runs **~2 s** wall clock for the first band and less thereafter with connection reuse — so **934 scenes ≈ 30–50 min single-threaded, or ~5 min at 10 threads**. That is a rounding error against a 4-week budget.

**Scaling to 5–20 sites:**

| Sites | Screening pass (SCL) | Full archive, all bands | Clear-only, all bands |
|---|---|---|---|
| 5 | 0.24 GB | 44 GB | 21 GB |
| 20 | 0.94 GB | 177 GB | 85 GB |

**Disk needed:** budget **~10 GB** for a comfortable demo (1–3 sites, all bands + CHIRPS + DEM + LiCSAR products), **~120 GB** if you evaluate 20 sites over the full 11-year archive with all bands. A middle path — 20 sites, SCL screening + 10 m bands only (5.67 MB/scene, clear-only) — is **~25 GB**.

**Recommended two-tier pattern:**
1. **Pass 1 (cheap, ~47 MB for 934 scenes):** read only `SCL` windows for every candidate scene at every site. Record per-site clear fraction. This is a ~1-minute job and it *fully determines* which scenes are worth anything.
2. **Pass 2 (targeted):** fetch only the scenes that pass the per-site clear threshold, only the bands you actually use (SCL + B02/B03/B04/B08 covers ~90 % of a landslide-scar NDVI/brightness workflow: 5.67 MB/scene).
3. **Cache aggressively.** A COG window is a deterministic byte range — store the extracted GeoTIFF/NumPy arrays locally keyed by `(site_id, item_id, band)`. Re-runs then cost nothing, and you never re-hit the network for the same window. Do **not** cache whole tiles.

This means **the entire optical archive for one site is a ~1-hour, ~5 GB operation** — not the 543 GB it would be with tiles. Network flakiness is handled by `GDAL_HTTP_MAX_RETRY` + idempotent caching rather than by bulk pre-download.

---

## 7. Recommended lowest-risk pipeline for 4 weeks on CPU-only

**Thesis: lead with rainfall (deterministic, always available), corroborate with Sentinel-1 GRD amplitude change and LiCSAR coherence, and use Sentinel-2 only in the dry season.** Do not make optical the backbone — §2 shows why.

### Week 1 — Foundations, all anonymous, no accounts needed
- **Terrain**: Copernicus DEM GLO-30 tiles for the 5–20 sites → slope, aspect, curvature, TWI with `gdaldem`.
- **Assets**: OSM Overpass (with User-Agent) → road corridors (`ref=NH*`), buildings, settlements; snap sites to the road network.
- **Rainfall baseline**: CHIRPS daily for 2016–2026 at each site (yearly NetCDF, or just the days needed). Build per-site daily series.
- **Build the site table**: site_id, lat, lon, MGRS tile, DEM stats, nearest OSM road, CHIRPS cell id.
- **Deliverable**: a site/asset/terrain table + CHIRPS time series. Zero risk, zero accounts.

### Week 2 — Optical screening and the dry-season archive
- Run the **SCL-only screening pass** over all Sentinel-2 scenes per site (~47 MB/site). Produce a per-site, per-date clear-fraction table. *This single artifact is the project's most valuable derived product* — it tells you (and any reviewer) exactly when optical data exists.
- Fetch 10 m bands (B02/B03/B04/B08) **only** for scenes above the clear threshold. Build a dry-season (Oct–May) NDVI/brightness time series.
- **Deliverable**: honest per-site optical availability, plus a dry-season change series.

### Week 3 — The monsoon-proof layers
- **Sentinel-1 GRD** (Earth Search COGs, anonymous): for each site and each available pass, fetch the 2 km window, geolocate via the **annotation XML geolocation grid** (§3.2), apply sigma0 calibration, and compute per-date backscatter. ~5–10 s/scene; 50–100 scenes in ~20 min.
- Compute **GRD amplitude change / change-detection metrics** between consecutive passes and against a per-site dry-season baseline.
- **LiCSAR** (anonymous): download `geo.vlos_eur.tif` and `geo.meancoh.12.tif` for frame `121D_06267_131313`. Extract site windows. Use VLOS for creep and **mean coherence as an explicit data-quality mask**.
- **Deliverable**: a monsoon-season SAR change series, plus a coherence-validity mask.

### Week 4 — Fusion, validation, and an honest evaluation
- **Trigger logic**: CHIRPS-driven. Compute, per site and day: 24 h rainfall, 3/5/10-day antecedent accumulation, and evaluate against both the **Helambu (124.38 mm/24 h; I = 41.029 D^−0.651)** and **Dahal (≈145 mm/24 h)** thresholds, plus the <10 h → 10 mm/h and >100 h → 2 mm/h regimes.
- **Cross-check** each rainfall trigger against the SAR layers: did backscatter change, and was coherence adequate to even ask?
- **Validate** against a known inventory. Use the landslide inventories referenced in the Practical Action report (755 Helambu / 213 Panchpokhari) or the **Durham fatal landslide database** as an independent event list.
- **Report false positives explicitly.** With ~6 usable optical scenes/JJAS and coherence 0.16, the honest headline is likely "rainfall thresholds give X % hit rate; SAR confirms Y %; optical contributes almost nothing in Jul–Aug."
- **Deliverable**: reproducible pipeline + a feasibility verdict backed by measured availability, not by assertion.

### What to explicitly *not* do
- ❌ Do not download full Sentinel-2 tiles (543 GB for one site).
- ❌ Do not run ISCE2/SNAP InSAR on this box.
- ❌ Do not build the trigger on Sentinel-2 optical — Jul has 0 % usable scenes.
- ❌ Do not trust `eo:cloud_cover` for a small AOI.
- ❌ Do not use a global affine GCP fit for Sentinel-1 GRD.
- ❌ Do not use Google Earth Engine (proprietary hosted) — excluded by your constraints anyway.

---

## 8. Top three data risks

**1. The monsoon makes optical change detection structurally unavailable — not merely degraded.**
Measured: **July has 0.0 % of scenes with >80 % clear pixels over the AOI** across 11 years; JJAS yields ~6 usable and ~3 good scenes per season, clustered in late September. Any design that depends on a usable Sentinel-2 pair *bracketing a July/August landslide* will silently produce no detections in exactly the season landslides occur. **Mitigation:** make rainfall the trigger and SAR the corroborator; treat optical as a dry-season baseline. **Early warning sign:** if your first demo site shows zero optical detections in Jun–Aug, that is the data, not a bug.

**2. InSAR coherence at C-band on these slopes is ~0.16 — the physics may not support the method.**
Measured directly from LiCSAR at the AOI: mean 12-day coherence **0.16**. This is below the usual usable range. Combined with 8 GB SLC scenes and 3 GB free RAM, any InSAR-dependent deliverable is high-risk. **Mitigation:** use the pre-computed LiCSAR products (never compute them yourself), and **verify per-site coherence as the very first gate** before promising any InSAR-derived result. **Early warning sign:** if you cannot find sites with meancoh.12 > 0.3, InSAR is off the table for this AOI set.

**3. Silent geolocation failure in the Sentinel-1 GRD layer.**
The GRD COG ships with `crs = None`, an identity transform, and GCPs whose global affine fit has **~1.3 km RMS / 3.3 km max error**. A pipeline that "works" — opens files, produces rasters, plots maps — can be reading the wrong hillside by more than a kilometre, and nothing will crash. **Mitigation:** geolocate via the annotation XML grid with local interpolation, then **assert** that a known feature (e.g. a DEM landmark or a road intersection) lands within ~1 pixel. **Early warning sign:** your SAR change signal correlates suspiciously well with *tile boundaries* rather than with terrain.

*Runner-up risk:* the Practical Action thresholds rest on only **44 and 43 landslide events** despite R² = 0.998 — validate before operational reliance.

---

## 9. What I could NOT verify

Stated plainly, because these are exactly where the plan could break:

1. **ERA5-Land download latency/queue behaviour** — the endpoint returns 401 without an account, and I have no CDS account. The documented "~5 days behind real time" for ERA5-Land-T is from ECMWF's own documentation; actual per-request queue time is unverified.
2. **SMAP download path** — the NSIDC data host `n5eil01u.ecs.nsidc.org` **did not connect at all** from this environment (HTTP 000, DNS/routing failure). I confirmed only that NSIDC landing pages resolve and that the data-pool host redirects to a login. **I could not verify any working SMAP granule download, anonymous or authenticated.**
3. **ASF HyP3 for Nepal** — returns 401 without an Earthdata token. Free and Earthdata-authenticated in principle, but **I could not verify that it produces InSAR for this Nepal location, nor its latency.** (Note ASF's `intersects` parameter returns 400; the correct parameter is `intersectsWith`.)
4. **CDSE on-demand processing** and CDSE STAC's full collection list — the CDSE STAC exposed only 10 collections (CCM/CLMS), and the OData `/Collections` endpoint returned 404. The main S2/S1 mission data is reachable via OData `Products` (verified), but I did not map the complete collection surface.
5. **`s1reader` / `xsar` installability** on this machine — I proved the *concept* (annotation-XML geolocation grid is fetchable and parseable, 10 × 21 points) but did not install and end-to-end test these libraries. My measured GRD/GCP numbers are from `rasterio` + manual XML parsing.
6. **Accuracy of the annotation-grid bilinear geolocation.** I proved a *global affine* fit is bad (~1.3 km RMS). I did **not** independently validate the local-interpolation approach against ground truth, so the residual error of the recommended method is **unknown** (expected metres-to-tens-of-metres, unverified). **Validate against a known feature before relying on it.**
7. **LiCSAR per-interferogram files.** The parent index lists 2,537 interferogram names, but `GET .../interferograms/<pair>/` returned **404** for the frames I tested, and the epoch entries 404 on the guessed `.tif` filenames. **I verified the aggregated products** (VLOS/E/N/U/meancoh — all read successfully) but **not** individual unwrapped-phase/coherence GeoTIFFs. Confirm the correct inner path before planning per-interferogram work.
8. **LiCSAR frame completeness for descending orbit 121** — I found exactly one frame covering the AOI (`121D_06267_131313`). Whether additional ascending frames cover Nepal (I found none among `085A_*`) needs confirmation from the COMET-LiCS portal.
9. **IMERG Early vs Final latency**, and **SMAP soil-moisture latency** — undocumented here, both behind logins.
10. **Copernicus licence terms for redistribution** — the Earth Search STAC collection declares `license: "proprietary"`, which almost certainly does not reflect the actual Copernicus terms, but I did not verify the authoritative licence text.
11. **The Bhandary / MDPI SMAP + antecedent-rainfall threshold paper** — the publisher PDF was blocked to automated fetch (HTTP 406). I confirmed the paper exists with title, venue and authorship but **could not extract its numeric thresholds.**
12. **Reliability/uptime and rate limits** of Earth Search and CHIRPS — I made hundreds of successful requests with no throttling, but no formal SLA or rate-limit documentation was verified.
13. **Whether the specific AOI I tested is representative.** All cloud and coherence statistics are for **27.70 N, 85.90 E**. A different elevation/aspect (e.g. a north-facing slope, or Jhyaple Khola at 84.87 E) may differ. **The method transfers; the numbers should be re-measured per site.**

---

## Appendix — copy-paste verification commands

```bash
# 1. Sentinel-2 L2A search + confirm anonymous (expect 200)
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "https://earth-search.aws.element84.com/v1/search" -H "Content-Type: application/json" \
  -d '{"collections":["sentinel-2-l2a"],"intersects":{"type":"Point","coordinates":[85.9,27.7]},"limit":1}'

# 2. Anonymous COG range read (expect 206 + Content-Range)
curl -s -r 0-1023 -D- -o /dev/null \
  "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/45/R/UL/2024/9/S2A_45RUL_20240928_0_L2A/SCL.tif" | grep -i content-range

# 3. Sentinel-1 GRD COG (expect 206)
curl -s -r 0-99 -o /dev/null -w "%{http_code}\n" \
  "https://sentinel-s1-l1c.s3.amazonaws.com/GRD/2024/9/27/IW/DV/S1A_IW_GRDH_1SDV_20240927T001134_20240927T001159_055843_06D317_71B5/measurement/iw-vv.tiff"

# 4. CHIRPS daily (expect 200/206)
curl -s -r 0-500 -o /dev/null -w "%{http_code}\n" \
  "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05/2024/chirps-v2.0.2024.07.15.tif.gz"

# 5. Copernicus DEM GLO-30 (expect 206)
curl -s -r 0-100 -o /dev/null -w "%{http_code}\n" \
  "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N27_00_E085_00_DEM/Copernicus_DSM_COG_10_N27_00_E085_00_DEM.tif"

# 6. OSM Overpass (MUST include a User-Agent; without it -> 406)
curl -s -o /dev/null -w "%{http_code}\n" -A "my-research/1.0" -X POST \
  "https://overpass-api.de/api/interpreter" \
  --data-urlencode 'data=[out:json][timeout:25];(way["highway"](27.69,85.89,27.71,85.91););out count;'

# 7. LiCSAR pre-computed InSAR for Nepal (expect 200) — no login
curl -sI -o /dev/null -w "%{http_code}\n" \
  "https://gws-access.jasmin.ac.uk/public/nceo_geohazards/LiCSAR_products/121/121D_06267_131313/metadata/121D_06267_131313.geo.vlos_eur.tif"

# 8. Confirm the paid/login services really do refuse anonymous access
curl -s -o /dev/null -w "CDSE download: %{http_code}\n" -L \
  "https://download.dataspace.copernicus.eu/odata/v1/Products(77a7d589-d523-4d28-9cb8-3c2b17756380)/\$value"
curl -s -w "\nCDS: %{http_code}\n" -X POST \
  "https://cds.climate.copernicus.eu/api/retrieve/v1/processes/reanalysis-era5-land/execute" \
  -H "Content-Type: application/json" -d '{}'
```

---

*All figures measured 2026-09-30. Cloud and coherence statistics cover 2016-01-01 → 2026-09-30 (SCL: 933 scenes; cloud fraction per 2 km AOI). Numbers should be re-measured per site — the method transfers, the values will not.*
