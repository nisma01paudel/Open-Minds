# E5 — does rainfall ranking find the slopes that fail?

## The claim being tested

The whole design rests on an assumption that is easy to state and had never been
tested against outcomes: **that ranking slopes by rainfall load puts the slopes that
actually fail near the top.** This is the central assumption of every rainfall-threshold
warning system, including ours. So we tested it against our own benchmark.

Method: for each day with recorded failures, rank all 613 documented slopes by the same
multi-window rainfall load the system uses (24/48/72 h, each against its own threshold),
then look at where the slopes that *actually failed that day* landed in that ranking.

## Result

| Event day | Slopes that failed | Median rank (of 613) | Percentile | Crossed the threshold | All-slope median load |
|---|---|---|---|---|---|
| 2024-09-28 | 14 | **337** | **55%** | 4/14 | 1.00 |
| 2024-07-07 | 8 | **322** | **53%** | 0/8 | 0.40 |

On both days the slopes that failed ranked in the **bottom half** of the rainfall
ranking — 53rd and 55th percentile. A coin toss would do as well. On the peak day, of
the 14 documented failures, **only 4 had crossed the threshold at all**, and the median
load of the slopes that failed (0.97) was **below** the median load of all 613 (1.00).

The fourteen, in the order rainfall ranked them:

| Rank | Load | 24 h rainfall | Slope that failed |
|---|---|---|---|
| 222 | 1.12 | 59.4 mm | Landslide at Mandandeupur , Mandandeupur Municipalit |
| 232 | 1.11 | 78.7 mm | Landslide at Takhel , Lalitpur Metropolitan City-10 |
| 233 | 1.11 | 78.7 mm | Landslide at T.U.  & ward 8 Gaushala , Kathmandu Met |
| 282 | 1.03 | 83.7 mm | Landslide at Thumki /Ladkepauwa , Panauti Municipali |
| 317 | 0.99 | 60.2 mm | Landslide at Banepa Municipality-10 |
| 320 | 0.99 | 77.7 mm | Landslide at Hurlang , Diktel Rupakot Majhuwagadhi M |
| 335 | 0.97 | 78.5 mm | Landslide at Manebhanjyang Rural Municipality-9 |
| 339 | 0.96 | 78.2 mm | Landslide at Singe , Panauti Municipality-1 |
| 358 | 0.94 | 59.4 mm | Landslide at Temal Rural Municipality-1 |
| 363 | 0.92 | 74.5 mm | Landslide at Lele, Godawari_Lalitpur Municipality-5 |
| 384 | 0.89 | 90.7 mm | Landslide at Balting , Roshi Rural Municipality-10 |
| 385 | 0.89 | 72.4 mm | Landslide at Dhulikhel Municipality-10 |
| 408 | 0.83 | 26.3 mm | Landslide at Shreekhumba , Deumai Municipality-9 |
| 446 | 0.57 | 50.8 mm | Landslide at Katari Municipality-10 |

## What this means

**Rainfall load does not identify which slope fails.** It identifies that a region is
primed, which is real and useful, but at 0.05° (~5 km) it cannot distinguish one
hillside from its neighbour. Local slope, material, drainage, road cutting and
antecedent soil moisture decide which slope goes, and none of those are in the rainfall
field.

This is consistent with the two other measurements in this project:

- the event-vs-control test found a **3-point** difference (13.6% vs 10.6%), reported in
  `reports/trigger-discrimination.md`;
- on 2018-08-08, thirty-plus landslides were recorded on a day whose maximum 24-hour
  rainfall across those sites was **51 mm**, against a 118.8 mm threshold.

Three independent measurements, one conclusion. It is a negative result about the
approach the whole sector uses, including us.

## What it does NOT mean

It does **not** mean the system is useless, and it does not mean the warning is wrong.
It means the value is somewhere other than prioritisation by rain:

1. **The honest state.** `primed-unobserved` — *this slope is loaded and we cannot see
   it* — is information no existing Nepali tool produces, and this result makes it more
   valuable, not less: if rainfall cannot tell you which slope, then knowing that you
   are blind across a whole district is the thing worth acting on.
2. **The dispatch.** Naming the office and the section of law is unaffected by any of this.
3. **The observability record.** Knowing where the satellite cannot see is a precondition
   for anyone else's warning, and we now measure it nationally.

And it says what would actually help: per-slope evidence — radar change, terrain, and
citizen reports — precisely because the rainfall field has already given everything it has.

## Limitations of this test

- **Two event days.** Only 2024-07-07 and 2024-09-28 had eight or more documented
  failures inside the season that was built. This is a small sample and it is the main
  weakness of the result.
- **The date may be a report date.** BIPAD records `incidentOn`, but if some records carry
  the date an incident was reported rather than the date it happened, the failure set is
  noisy and the measured ranking would be understated.
- **The negatives are not clean.** Every site in the benchmark failed on *some* day, so a
  slope ranked above a failing slope is not necessarily a slope that stayed put.

None of these rescue the result: an effect this small cannot be hidden by a noisy set, it
would have to be invented by one.
