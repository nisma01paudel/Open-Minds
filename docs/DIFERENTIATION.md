# Differentiation matrix — what is actually empty

Built 2026-09-30 from full texts where obtainable. This is the evidence behind every novelty claim we
make. If a claim is not supported here, we do not make it.

**Columns:** Q1 output · Q2 localisation · Q3 named institution + mandate per finding ·
Q4 runtime per-sensor staleness state · Q5 citizen-report fusion · Q6 maturity · Q7 openness · Q8 own limitations

| Work | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 |
|---|---|---|---|---|---|---|---|---|
| **A** Alruqimi 2026, RS 18(11):1821 | per-slide structured report (4 sections, priority, outlook, velocity class) | No | No | No | No | research prototype | partial (paper CC-BY; data on request; no code) | yes |
| **B** MAS-LAND 2026, IJDRR 143:106263 | interactive map + per-landslide report, machine-readable stages | No | **Partial** — "civil protection authorities", generic/unnamed | UNVERIFIED | No | prototype, minutes-scale | partial (CC-BY; no repo) | UNVERIFIED |
| **C** Sen12Landslides 2025 | dataset + benchmarks (39,556 patches) | No | No | partial (invalid-pixel handling) | No | research dataset | yes (CC-BY-4.0) | yes |
| **D** HR-GLDD 2023 | patches + masks + shapefiles | No | No | partial (cloud/haze documented) | No | research dataset | yes (CC-BY-4.0 + code) | yes |
| **E** LhamNepal 2025 | national susceptibility + GEE nowcast app | No | **Partial** — "communities and authorities", unspecified | No | No | *claimed* operational (2-page abstract) | partial (no repo/licence) | none |
| **F** Kincey 2024, Earth's Future 12, 10.1029/2023EF004102 | 30 m national susceptibility raster + exposure | No | **Partial** — hosted on government BIPAD portal, no per-finding routing | partial (record-length bias) | No | research → gov-hosted | yes (CC-BY-4.0) | yes |
| **G** TerraTrack 2026, NHESS 26:2305 | masks, velocity maps, displacement series, inverse-velocity failure time | No | No | partial (decorrelation/snow documented) | No | open tool / Colab | yes (MIT + CC-BY) | yes |
| **H** Leder 2024, EGU24-10697 | multi-component displacement + DSM change (single landslide) | No | No | partial — monsoon cloud named as the obstacle | No | research only | partial/UNVERIFIED | UNVERIFIED |

**Totals:** Q2 = 0/8 · Q3 = 0/8 Yes (3 partial, all generic) · Q4 = 0/8 Yes (5 partial, all analytical not runtime) · Q5 = 0/8.

## The empty cells — our contribution is their intersection

1. **Citizen/community report fusion — 8/8 No.**
2. **Any non-English / Nepali localisation — 8/8 No.**
3. **Named responsible institution + mandate citation per finding — 0/8 Yes.**
4. **Runtime, user-facing, per-sensor "no fresh observation" state — 0/8 Yes.**

**Claim, precisely:** the intersection of 1–4, evaluated with inter-rater reliability (which A explicitly deferred) and with routing-correctness axes that no work reports.

## What we must NOT claim (each is pre-empted)

| Tempting claim | Pre-empted by |
|---|---|
| "LLM-generated landslide reporting for response" | **A and B** (same six authors, same event — treat as one research line, expect them named first) |
| "No one has an operational Nepal landslide warning" | **E** claims exactly this (though evidence is a 2-page abstract) |
| "We deliver findings to government" | **F** already reaches the official BIPAD/NDRRMA portal |
| "Nobody addresses monsoon data gaps" | **H** names optical cloud as the core obstacle and solves it with radar+optical fusion |
| "Open + failure-time forecasting" | **G** (MIT) already occupies it |
| "We are open source" (as novelty) | **C, D, F, G** are all open — table stakes, not a differentiator |
| "We are aware of data-quality limits" | **C, D, F, G** all document them — ours must be **runtime, per-sensor, user-facing** |

## Evaluation: where A left the door open

A's protocol is the bar: **100 stratified tiles, 3 experts (one rating, two verifying by consensus), 3 metrics
per section, reported 58% Very Good / 30% Good / 8% Acceptable / 4% Poor.**
Their own stated gap, verbatim: *"Future evaluations could also further quantify expert consistency using
independent ratings and inter-rater reliability metrics such as Cohen's or Fleiss' kappa."*
And their rubric text still says "caption" in the definition of Very Good — inherited from image captioning.

**So we report what they did not:** Cohen's/Fleiss' kappa across independent raters, plus three axes nobody
reports — **institution-routing correctness**, **Nepali-comprehension by last-mile readers**, and
**gap-state correctness** (does the system abstain when it should?).

## Two design requirements these findings force

1. **Citizen-report confidence design.** Nepal's official records already come from police and local
   officials; a judge will attack unverified community input. Every citizen report must carry provenance,
   a confidence tier, corroboration requirements, and an explicit "unverified report" state — and it must
   never be sufficient on its own to issue an advisory (already enforced in `src/pahiro/routing/abstain.py`).
2. **Justify Nepali for the *last mile*.** E and F are Nepal-focused yet English, because their readers are
   agency officials. Our Nepali targets the **ward chair and the household**, not the ministry. Say that
   explicitly or the choice looks unmotivated.
