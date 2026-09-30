# Prior art we build on (and credit publicly)

The pitch names these *before* a judge can. Detection is solved; we do not claim it.
Citations verified 2026-09-30; see `DIFERENTIATION.md` for the full matrix and evidence.

| Work | What it gives us | Naming correction |
|---|---|---|
| **Kincey et al. 2024**, *Earth's Future* 12, `10.1029/2023EF004102` — national 30 m rainfall-triggered susceptibility for Nepal; dataset CC-BY on Zenodo 8307964; hosted on the government BIPAD/NDRRMA portal | prior-risk input; we do not recompute susceptibility | the widely cited "2023" is the **dataset** year |
| **LhamNepal / Pradhan & Kim 2025**, AJEG 2(Sp):381–382 | national hazard + IMERG rainfall thresholds, Google Earth Engine app | it is a **2-page extended abstract with no DOI**, claiming deployment rather than reporting an operational evaluation — we call the claim unverified, never disproved |
| **Practical Action → DHM** (May 2025) — rainfall intensity–duration thresholds integrated into DHM's operational forecasting | the warning that already exists; we are not competing with it | |
| **Alruqimi et al. 2026**, *Remote Sensing* 18(11):1821, `10.3390/rs18111821` — SegFormer detection → geo-attributes → **Mistral-7B-Instruct-v0.3** → structured reports with intervention-priority indicators; 100 stratified tiles, 3 experts, 58/30/8/4 | the closest work; our rubric source | **no inter-rater reliability is reported** (kappa explicitly deferred) and no refusal/abstain mode exists |
| **MAS-LAND 2026**, *IJDRR* 143:106263, `10.1016/j.ijdrr.2026.106263` — SegFormer + Llama-3.3-70B + interactive map, "LLM-enhanced automated reporting for civil protection" | shows the multi-agent response framing is taken | **shares six authors with Alruqimi and the same Emilia-Romagna event** — treat A+B as one research line. Its reports address "civil protection" generically, with no named institution |
| **Sen12Landslides 2025**, `10.1038/s41597-025-06167-2` — 39,556 NetCDF patches, Sentinel-1 + Sentinel-2 + DEM, event dates | detection dataset; per-modality invalid-pixel handling | a dataset, not a product |
| **HR-GLDD 2023**, ESSD 15:3283, Zenodo 7189381 — PlanetScope patches, **includes Rasuwa, Nepal** | a Nepal tile set already exists; we do not claim a first benchmark | |
| **TerraTrack 2026**, NHESS 26:2305 (MIT) — optical feature tracking, velocity maps, inverse-velocity failure time | change detection is a commodity; we call or reproduce it | already occupies "open + failure-time" |
| **Leder et al.** EGU24-10697 — radar + optical monitoring of a Nepali slow-moving landslide during monsoon | the sensing is published | they already name monsoon cloud as the core obstacle and fuse radar — we must not claim to have discovered it |
| **Prakop Alert** (ICIMOD) — free Nepali + English hazard app | the localisation lane has a credible occupant for *weather* | not per-slope advisories |

## The gap — measured, not asserted

Across all ten works above: **citizen-report fusion 0/8 reviewed · Nepali localisation 0/8 ·
per-finding institution routing with a mandate citation 0/8 Yes · runtime per-sensor staleness state 0/8 Yes.**

Every work ends at a **finding** — a mask, a map, a report, a probability. None ends at a **named
institution, under a cited mandate, in Nepali, with the evidence age stated and a refusal to guess when
blind.** That intersection is what Pahiro builds.
