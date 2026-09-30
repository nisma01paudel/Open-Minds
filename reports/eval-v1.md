# Evaluation v1 — consolidated, on the corrected pilot area

Supersedes `eval-v0.md`, which reported the original pilot AOI. The pilot was moved after the event
benchmark showed the original box held only 2 documented landslides (`docs/PILOT-AOI.md`).

## E3 — gap-state calibration: can the system speak?

For every day of 2024, could an advisory have been issued with the evidence then available?

| Policy | Days issuable | Longest blind streak |
|---|---|---|
| Optical only (457 observations) | **331 / 366 = 90.4%** | **34 days** |
| Optical + radar (457 + 653 acquisitions) | 366 / 366 = 100.0%* | 0 days |

**Radar adds +9.6 points of coverage overall — and +58 points in July, +52 in August.**

| Month | optical | +radar | delta |
|---|---|---|---|
| Jan | 97% | 100% | +3 |
| Feb–Jun | 100% | 100% | 0 |
| **Jul** | **42%** | **100%** | **+58** |
| **Aug** | **48%** | **100%** | **+52** |
| Sep–Dec | 100% | 100% | 0 |

\* Radar is an **upper bound**: acquisition times are known, per-pixel usability is not yet measured.

### The result replicates across two independent areas

| | Original AOI (Dhading) | Corrected AOI (Kavre–Sindhupalchok) |
|---|---|---|
| Optical-only days issuable | 89.6% | **90.4%** |
| Longest blind streak | **34 days** | **34 days** |
| July / August delta with radar | +58 / +52 | **+58 / +52** |
| Sites in the event benchmark | 2 | **59** |

Two different boxes, different Sentinel-2 tiles, different terrain, same conclusion — and the corrected
area is where the documented landslides actually are.

## Per-AOI optical usability — corrected pilot, 2024 (457 scenes screened)

| Month | scenes | median clear | %>50 clear | %>80 clear |
|---|---|---|---|---|
| Jan | 36 | 0.58 | 63.9 | 27.8 |
| Apr | 36 | 0.87 | 77.8 | 55.6 |
| **Jun** | 36 | 0.18 | 5.6 | **0.0** |
| **Jul** | 36 | **0.00** | **0.0** | **0.0** |
| **Aug** | 36 | 0.05 | 8.3 | **0.0** |
| **Sep** | 37 | 0.09 | 18.9 | 2.7 |
| Nov | 46 | 0.56 | 58.7 | 26.1 |
| Dec | 40 | 0.68 | 77.5 | 32.5 |

**JJAS pooled: 145 scenes — 8.3% >50% clear, 0.7% >80% clear.** June, July and August each have
**0.0%** of scenes above 80% clear. This is stricter than the original AOI, where the equivalent figures
were 25% / 16.7% / 16.7% — the corrected area's monsoon is worse, not better, which is presumably why it
holds so many recorded failures.

## E1 — routing accuracy

**61.9%** exact case accuracy, **76.2%** asset identification, **100%** abstention precision, and **zero**
misroutes across road tiers. Three-arm ablation and diagnosis in `routing-ablation.md`.

## E4a — does the rainfall trigger discriminate?

22 event days against 66 matched controls on identical dates: **13.6% of event sites exceeded the
published local threshold against 10.6% of controls — a three-point edge.** Weak.

The case that explains it: on 2018-08-08, thirty-plus landslide sites were recorded on a day whose
maximum 24-hour rainfall across those sites was **51 mm**, well under the 118.8 mm threshold.

Full analysis and interpretation: `reports/trigger-discrimination.md`.

## E4 — observability at documented sites

**Complete: 142 sites over 37 year-months, 2018-06 to 2026-09**, each screened over the 30 days
before its recorded failure. Two thousand and twenty-one scenes.

| Denominator | Value |
|---|---|
| Sites with at least one usable look | **125 / 142 = 88.0%** |
| Sites with **no usable look at all** | **17 / 142 = 12.0%** |
| Sites with a radar pass | 142 / 142 = 100% |
| Scenes usable (observation level) | **676 / 2,021 = 33.4%** |
| August, the worst month (observation level) | **16.8%** |
| Median usable observations per site | 4 |
| Median days since the last usable look | 8, but **29 sites were over two weeks stale** |

Both denominators matter and neither replaces the other: 88% of sites had *something*
usable, which is why the system does not simply refuse everything; 12% had *nothing*,
which is why it has to say so. Full per-site table and monthly breakdown:
`reports/observability-monsoon.md`.

The unstratified first run reported 100% and that number was an artefact - it sampled the
most recent events, which are post-monsoon, exactly when optical returns. Stratifying by
year-month is what made the result honest.

## Reproduce

```bash
scripts/serve_model.sh start
python -m pahiro.ingest.screen --bbox 85.05 27.45 85.65 28.05 \
    --from 2024-01-01 --to 2024-12-31 --out evidence/screen-kavre-2024
python -m pahiro.eval.gap --obs evidence/screen-kavre-2024.jsonl \
    --radar evidence/s1-radar-dates-kavre.jsonl --year 2024
python -m pahiro.eval.routing --mode two-stage --out reports/routing-eval.json
python -m pahiro.eval.observability --per-month 4 --months 6 7 8 9 10 \
    --out reports/observability-monsoon.json
```
