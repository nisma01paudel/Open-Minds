# Pilot area — corrected after the event benchmark was built

**The correction.** The first pilot AOI (Dhading, `84.95, 27.75, 85.10, 27.90`) was chosen before the
documented-event benchmark existed. When BIPAD's landslide incidents were fetched and deduplicated, that
box turned out to contain **2** documented sites. The audit's Jhyaple Khola 2024 event
(28.00638 N, 84.94688 E) is **outside** it — the same class of mistake the whole project exists to prevent:
choosing the area before looking at where the events actually are.

## The evidence

Ranking every 0.15° cell of the 613-site benchmark by site count:

| Cell centre | Sites | Box (lon0-0.30, lat0-0.30, lon0+0.30, lat0+0.30) | Sites in box |
|---|---|---|---|
| **27.750, 85.350** | **15** | `85.050, 27.450, 85.650, 28.050` | **59** |
| 28.200, 83.400 | 8 | `83.100, 27.900, 83.700, 28.500` | — |
| 27.300, 86.400 | 8 | — | — |
| 27.600, 85.500 | 7 | — | — |
| *(old pilot)* | 2 | `84.950, 27.750, 85.100, 27.900` | **2** |

## The new pilot

**`85.050, 27.450, 85.650, 28.050`** — the Kathmandu-rim / Kavre–Sindhupalchok corridor.
**59 documented landslide sites**, against 2 in the old box.

Two strategic bonuses:

1. **It contains Panchpokhari Thangpal Rural Municipality, Sindhupalchok** — the exact municipality for
   which published rainfall intensity–duration thresholds exist
   (`I = 52.476 · D^(-0.743)`, 118.8 mm/24 h). Our rainfall trigger layer can be evaluated against a real
   local threshold instead of a generic one.
2. It is close to Kathmandu, so the terrain in the demo is terrain the judges know.

## Data availability, verified

| | Old box | **New box** |
|---|---|---|
| Sentinel-2 (cloud<20), 2024 | 58 scenes | **193 scenes** |
| Sentinel-1 GRD, 2024 | 58 scenes | **173 scenes** |
| Scenes in July / August 2024 | **0 / 0** | **0 / 0** |

**The monsoon finding replicates independently in the new area.** Two different boxes, different tiles,
same result: zero usable optical scenes in July and August. That is now a confirmed regional pattern
rather than a single-site curiosity, and it strengthens the case rather than weakening it.

## What this costs

The per-AOI screening (`pahiro.ingest.screen`) must be re-run for the new box — roughly 40–60 minutes of
background work for the same monthly table. The method and scripts are unchanged; only the bbox differs.
Until it is re-run, the monsoon numbers in `reports/eval-v0.md` remain those of the old box and are
labelled as such.

## What does not change

- The routing ontology, the triage router, the dispatch object and the BIPAD integration are all
  location-independent.
- The event benchmark itself (`benchmark/events.csv`, 613 sites) covers the whole country and is
  unaffected by the pilot choice.
- The ablation and routing-accuracy results (E1) do not depend on the pilot area at all.
