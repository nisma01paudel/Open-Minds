# Evaluation v0 — gap-state calibration (contribution C, measured)

Date: 2026-09-30 · status: **first real measurement** · reproducible with one command each.

```bash
python -m pahiro.ingest.screen --bbox 84.95 27.75 85.10 27.90 \
    --from 2024-01-01 --to 2024-12-31 --out evidence/screen-dhading-2024
python -m pahiro.eval.gap --obs evidence/screen-dhading-2024.jsonl \
    --radar evidence/s1-radar-dates.jsonl --year 2024 --out evidence/gap-2024.csv
```

## 1. Per-AOI optical usable fraction — Dhading corridor, 2024 (150 scenes)

`eo:cloud_cover` is not used: it describes the whole ~110 km tile. Clear ground here means
SCL ∈ {4,5,6,7} measured **over the study patch**.

| Month | scenes | median clear | %>50 clear | %>80 clear |
|---|---|---|---|---|
| Jan | 12 | 0.83 | 100.0 | 75.0 |
| Feb | 14 | 0.64 | 57.1 | 21.4 |
| Mar | 12 | 0.85 | 83.3 | 75.0 |
| Apr | 12 | 0.99 | 83.3 | 83.3 |
| May | 12 | 0.86 | 100.0 | 58.3 |
| Jun | 12 | 0.44 | 50.0 | 25.0 |
| **Jul** | 12 | **0.00** | **0.0** | **0.0** |
| **Aug** | 12 | **0.01** | 16.7 | 16.7 |
| **Sep** | 12 | **0.02** | 33.3 | 16.7 |
| Oct | 14 | 0.83 | 100.0 | 57.1 |
| Nov | 14 | 0.90 | 85.7 | 78.6 |
| Dec | 12 | 0.66 | 83.3 | 16.7 |

**JJAS pooled: 48 scenes — 25.0% >50% clear, 14.6% >80% clear. July: 0.0% >80% clear.**

## 2. Gap-state calibration — how often can the system actually speak?

For every day of 2024 we ask the staleness gate whether an advisory could be issued with the evidence
then available. Positive = may issue.

| Policy | Days issuable | Longest blind streak |
|---|---|---|
| **Optical only** (150 observations) | **328 / 366 = 89.6%** | **34 days** |
| Optical + radar (150 + 431 acquisitions) | 366 / 366 = 100.0%* | 0 days |

**Radar adds +10.4 percentage points of coverage overall — and +58 points in July, +52 in August.**

| Month | optical | +radar | delta |
|---|---|---|---|
| Jan | 87% | 100% | +13 |
| Feb–Jun | 100% | 100% | 0 |
| **Jul** | **42%** | **100%** | **+58** |
| **Aug** | **48%** | **100%** | **+52** |
| Sep–Dec | 100% | 100% | 0 |

The 42% July figure is not a contradiction of the 0%-clear table: the 20-day freshness window carries
late-June looks into the first days of July, and a handful of July scenes clear the 0.30 usability floor.

## 3. Limitations — stated, not buried

- **\*Radar is an upper bound.** Acquisition times are known (4–6 passes every month, 431 in 2019–2025);
  per-pixel usability is **not yet measured**. Steep-terrain layover and shadow will reduce the real
  figure. The Sentinel-1 GRD products also carry a known geolocation trap (`crs=None`, global affine
  fit 1.3 km RMS wrong) that must be fixed before any radar result is trusted.
- **Single AOI.** One 2 km patch in Dhading. The method transfers; the numbers must be re-measured per site.
- **2024 only** in this report; the 11-year SCL screen (933 scenes) is in `docs/DATA.md`.
- **This is not validation of detection.** No claim is made that the system would have predicted any
  landslide. This measures **whether the system can speak at all**, which is the honesty layer.

## 4. Why this matters for the pitch

Most entries will show a dashboard. This is a **measured, reproducible number about our own blind spots**:
under an optical-only policy a hidden 34-day silence falls exactly across the monsoon, and adding radar
closes it. It is the quantitative version of contribution C, and it is the ablation promised in the plan.
