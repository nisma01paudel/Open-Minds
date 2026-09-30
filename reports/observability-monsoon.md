# E4 — can the ground actually be seen during the monsoon?

**Interim: 122 of 142 documented sites** - the run is still completing. Every number below is computed only from sites that have finished.

Sites are stratified by year-month so that one wet season cannot dominate the sample, which is what happened on the first attempt at this evaluation (it reported 100% because it was sampling only post-monsoon events).

## Headline

- **Optical usability across the monsoon: 33.1%** (549 usable of 1,661 screened observations)
- **August, the worst month: 16.6%**
- **15 of 122 sites (12%) have ZERO usable optical observations** in their window - completely blind, not merely degraded
- **Radar delivers regardless: median 7 acquisitions per site** (min 4, max 12)

This is the measurement behind the project's central data claim. It is not that the monsoon is cloudy in general - it is that an optical-only system is blind at a specific share of specific slopes, and that gap is what the satellite layer has to be honest about.

## By year-month

| Year-month | Sites | Optical usable | Best clear fraction (median) | Radar obs (median) |
|---|---|---|---|---|
| 2019-08 | 2 | 15.4% | 0.91 | 8 |
| 2019-09 | 4 | 32.4% | 0.99 | 8 |
| 2020-06 | 4 | 40.7% | 1.00 | 6 |
| 2020-07 | 4 | 18.1% | 0.72 | 7 |
| 2020-08 | 4 | 18.5% | 0.90 | 8 |
| 2020-09 | 4 | 8.3% | 0.35 | 7 |
| 2021-06 | 4 | 41.9% | 0.99 | 6 |
| 2021-07 | 4 | 11.8% | 0.99 | 8 |
| 2021-08 | 4 | 10.7% | 0.88 | 5 |
| 2021-09 | 1 | 0.0% | 0.01 | 8 |
| 2021-10 | 4 | 59.8% | 1.00 | 7 |
| 2022-06 | 4 | 62.5% | 0.81 | 8 |
| 2022-07 | 4 | 47.2% | 0.99 | 8 |
| 2022-08 | 3 | 31.8% | 1.00 | 5 |
| 2022-09 | 4 | 10.0% | 0.23 | 4 |
| 2022-10 | 4 | 40.6% | 0.98 | 6 |
| 2023-06 | 4 | 74.4% | 1.00 | 8 |
| 2023-07 | 4 | 29.6% | 1.00 | 6 |
| 2023-08 | 4 | 14.0% | 0.52 | 5 |
| 2024-06 | 4 | 72.5% | 1.00 | 8 |
| 2024-07 | 4 | 33.3% | 0.89 | 4 |
| 2024-08 | 4 | 13.9% | 0.32 | 8 |
| 2024-09 | 4 | 59.2% | 1.00 | 8 |
| 2025-06 | 4 | 37.5% | 1.00 | 7 |
| 2025-07 | 4 | 40.0% | 0.89 | 4 |
| 2025-08 | 4 | 21.3% | 0.54 | 8 |
| 2025-09 | 4 | 33.3% | 0.62 | 8 |
| 2025-10 | 4 | 39.5% | 0.99 | 8 |
| 2026-06 | 4 | 56.4% | 1.00 | 7 |
| 2026-07 | 4 | 52.3% | 0.89 | 10 |
| 2026-08 | 4 | 10.0% | 0.36 | 8 |
| 2026-09 | 4 | 31.1% | 0.86 | 5 |

August is the worst month in **every** year sampled except one, and the worst single month observed is 2021-08 at 10.7%.

## What this does and does not show

- It **does** show that a large share of documented slope sites cannot be observed optically for most of the monsoon, and that some cannot be observed at all.
- It **does not** show a dry-season comparison: the sample is deliberately stratified across June-October, so there are no dry-season sites here and none is claimed.
- It **does not** measure radar usability at the pixel level. Radar acquisitions are counted, not verified; every radar-derived confidence in the system is capped and labelled as an upper bound because of exactly this.

## Method

For each documented site and month: search Sentinel-2 L2A scenes over a 3-month window centred on the event month, then screen each scene per-AOI using the SCL band only (~0.05 MB per scene instead of a full granule). `eo:cloud_cover` is deliberately **not** used - it describes the whole ~110 km tile, not the site, and using it would overstate clear ground substantially.
