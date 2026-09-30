# Pahiro (पहिरो) — from detection to dispatch

> **Nepal can already *detect*. Nepal cannot *dispatch*.**
> This is the missing last metre: turning a slope signal into a specific, readable,
> authority-addressed inspection request in Nepali — with the data gap stated honestly.

**Status: Week 0 scaffold.** Under active development for Frogtoberfest 2026 (Oct 1–30, 2026).
Nothing here is a working product yet; this README grows with the build.

## The problem

Nepal has world-class landslide science and operational rainfall-threshold warnings. What it lacks is the
step after detection: a detection is not an instruction. A ward chair cannot act on a raster. A division
road engineer cannot act on "elevated hazard probability".

Pahiro takes a slope signal — satellite change, rainfall accumulation, or a citizen's report — and emits a
**dispatch object**: what changed, how stale the evidence is, which named office is responsible under which
mandate, what to inspect first, and, where the evidence supports it, whether to repair in place or relocate
the asset above the deformation zone.

## What this project does NOT claim

We do not claim to detect landslides better, to predict failure, or to have built the first Nepali hazard
app. Detection is a solved, open, published field and we use it rather than re-derive it. See
`docs/PRIOR-ART.md` for the works we build on and cite — including two 2026 papers that already use
open-weight LLMs to write priority-ranked landslide reports. Our contribution is the translation and
dispatch layer, not the sensing.

## Architecture

```
INPUTS (borrowed, credited)                THE LAST METRE (ours)
  Sentinel-2 / Sentinel-1  ──┐
  CHIRPS rainfall            │   ingest tools → structured change features
  Copernicus DEM             ├─▶ (+ per-sensor observation age)
  susceptibility (Kincey)    │            │
  citizen reports (photo)  ──┘            ▼
                              ROUTING (AI)   RAG over the cited mandate ontology
                                             → institution + escalation + priority
                              ADVISORY (AI)  constrained Nepali template, slot-filled
                              ABSTAIN (AI)   refuses to issue when evidence is stale
                                             │
                                             ▼
                              ★ DISPATCH OBJECT (schema-validated JSON) ★
                                             │
                    ranked queue · Nepali advisory · work order · siting advice
                    alerts · append-only provenance (scene IDs, model, ontology version)
```

## AI usage (open-weight only)

No proprietary AI API is called anywhere in this repository. No OpenAI, Anthropic, Google or Azure AI —
including embeddings and auxiliary classification.

*(Full disclosure naming the exact file/function where AI output is consumed programmatically is required
for eligibility and will be completed as the modules land. Placeholder: `docs/AI-USAGE.md`.)*

## Reproduce the founding evidence

```bash
python3 scripts/verify_data_access.py            # live; needs only the standard library
```

This prints, from live anonymous STAC data, the finding that drives the design: over the Dhading
corridor, **zero usable Sentinel-2 scenes in July and August across seven years**, versus 4–6
cloud-free Sentinel-1 radar looks every month.

## Data sources (all free, no account, no key)

| Source | Access |
|---|---|
| Sentinel-2 L2A, Sentinel-1 GRD, Copernicus DEM 30 m | anonymous STAC — `earth-search.aws.element84.com/v1` |
| CHIRPS daily rainfall | `data.chc.ucsb.edu` |

## Limitations

- Retrospective prototype on pilot corridors; **operational skill is unvalidated.**
- Rapid, shallow failures are out of scope for the satellite path and belong to existing rainfall-threshold
  warning systems.
- Sentinel-1 revisit and terrain geometry mean latency, not real-time coverage.
- *(expanded in `docs/LIMITATIONS.md` before submission)*

## License

MIT — see `LICENSE`. Model licenses documented in `docs/AI-USAGE.md`.
