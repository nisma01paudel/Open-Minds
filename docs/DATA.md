# Data feasibility — verified, not assumed

All of the following was confirmed by live requests. Reproduce with:

```bash
python3 scripts/verify_data_access.py --out evidence/monsoon-gap.csv
```

## Verified access (no account, no API key, no cost)

| Source | Endpoint | Verified result |
|---|---|---|
| Sentinel-2 L2A | anonymous STAC `earth-search.aws.element84.com/v1` | 58 scenes over Dhading in 2024 (cloud < 20%) |
| Sentinel-2 band windows | `sentinel-cogs` S3, HTTP range request | `206 Partial Content`, `profile=cloud-optimized` → fetch only the needed window |
| Sentinel-1 GRD | same STAC, collection `sentinel-1-grd` | 4–6 scenes **every month**, 36/36 months |
| Copernicus DEM 30 m | same STAC, `cop-dem-glo-30` | slope / aspect / curvature derivable |
| CHIRPS daily rainfall | `data.chc.ucsb.edu` | global daily GeoTIFF, anonymous |

## The founding finding

Usable (cloud < 20%) Sentinel-2 scenes over the Dhading corridor, by month, 2019–2025:

```
year     J    F    M    A    M    J    J    A    S    O    N    D
2019    10    8   12    8   14    6    0    0    0    5   19   10
2020     3    8   18   12    4    2    0    0    0   14   16   23
2021     6   20   21   17    4    0    0    0    7    8   18   21
2022     1    6   14    6    3    0    0    0    0    6   12   11
2023     4    8    8    6    9    4    0    0    0    5    9    6
2024     4    8    7   10    5    1    0    0    0    4   11    8
2025     5    9   11    9    3    0    0    0    2   11   13   10
TOTAL   33   67   91   68   42   13    0    0    9   53   98   89
```

**Zero usable optical scenes in July and August across seven years; nine in September** — the months
Nepal's landslides kill. Sentinel-1 radar gives 4–6 looks every month of every year.

This is why the product ships a per-sensor **staleness state** and can **abstain** rather than guess.

## Known data risks
- Optical blackout during the monsoon (above) — mitigated by radar, not solved by it.
- Sentinel-1 revisit ≈ 6–12 days plus terrain geometry: latency, not real-time.
- Historical event labels for the benchmark are still being sourced (see `benchmark/`).
