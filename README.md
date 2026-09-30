# Pahiro (पहिरो) — from detection to dispatch

> **Nepal can already *detect*. Nepal cannot *dispatch*.**
> Pahiro is the missing last metre: it turns a slope signal into a specific, readable,
> authority-addressed inspection request in Nepali — and says so when it cannot see.

A detection is not an instruction. A ward chair cannot act on a raster; a division road engineer cannot
act on "elevated hazard probability". Pahiro takes a slope signal — satellite change, radar, rainfall, or
a citizen's report — and produces a **dispatch object**: what changed, how stale the evidence is, which
named office is responsible under which cited legal provision, what to inspect first, and whether to
repair in place or relocate the asset above the deformation zone.

## What runs today

Not a plan — running code, verified against live services:

| Component | State |
|---|---|
| Free satellite ingest (Sentinel-2, Sentinel-1, DEM, CHIRPS) | **working**, anonymous, no keys |
| Per-AOI cloud screening (the honest measure) | **working** — 457 scenes screened at the corrected pilot, July = 0.0% clear |
| Staleness gate (issue / degraded / **abstain**) | **working**, measured: 34-day monsoon blind streak |
| Dispatch object with validation | **working** — an authority without a cited section is structurally invalid |
| Nepali advisory renderer | **working** — fully Nepali, including the evidence state |
| **AI routing / triage** (open-weight, on CPU) | **working** — real model, citation-locked |
| Rainfall trigger on published thresholds | **working** — validated on the 2024-09-28 event |
| **Siting advice** (repair here, or move above the source zone) | **working** — Copernicus DEM, live |
| BIPAD government integration | **working** — coordinate → ward; real road-blockage register |
| Evaluation harnesses (routing accuracy, kappa, gap calibration) | **working** |
| **Offline hiking trails** (20,176 OSM ways, four regions of Nepal) | **working** — 4.49 MB, bundled, no network |
| **Trip planning + bus access** (which park, what fare) | **working** — Rs 24 Bagmati minimum, April 2026, DOTM |
| **Ask in your own words** (open-weight model → deterministic engine) | **working** — the model reads, the engine decides |

The full test suite passes. Every claim in this repo is reproducible from the commands below.

## The other half: it is not only for the day the mountain moves

**Nobody opens a landslide tool on a clear Saturday** — and a tool nobody opens is not installed on
the Tuesday the mountain moves. So the same offline engine answers the ordinary question: which
hiking trail, and which bus, from where I am standing.

```bash
python scripts/plan_trip.py --near 27.7750 85.3620 --origin 27.7047 85.3146
```

    trails within 3.0 km of 27.7750, 85.3620:
        4.02 km  +833 m  2h12   Shiva puri peak trek (stairs)
    from 27.7047, 85.3146:
        bus to Budhanilkantha Stop (~9.3 km, about Rs 37), then 4.8 km on foot

*"an easy walk, maybe a view, under forty rupees on the bus"* becomes `easy · under 1h00 · bus
under Rs 40 · wants view` — read by the open-weight model, then planned by a deterministic engine
that validates every field the model returns. It works with no model server too, and says which
reader answered.

**20,176 mapped footpaths, 141 bus stops, all of it offline** — on the web app and on the phone.
Trail data © OpenStreetMap contributors, ODbL 1.0. Coverage is incomplete, the terrain grid is
1 km, and bus schedules are not known here: all three are stated in the output rather than hidden.

## Start here

New to the repo? Read **[SUBMISSION.md](SUBMISSION.md)** — it lists the five required submission items,
where each lives, the one command that runs the whole pipeline, and every measured result with its own
weakness attached. Reserve ten minutes.

## Quickstart

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e '.[geo,dev,crypto]'

python scripts/verify_data_access.py          # the founding evidence, live from anonymous STAC
python -m pytest -q                            # the full suite

# end-to-end: a real coordinate, real observations, a real Nepali advisory
python scripts/demo_end_to_end.py --lon 85.0575 --lat 27.7620 --as-of 2024-07-20 \
    --obs evidence/screen-dhading-2024.jsonl --radar evidence/s1-radar-dates.jsonl

# with the open-weight decision model (see scripts/serve_model.sh)
python scripts/demo_end_to_end.py --lon 85.0575 --lat 27.7620 --as-of 2024-07-20 \
    --obs evidence/screen-dhading-2024.jsonl --report "a rural road above a national highway has failed"
```

## Why this matters — with numbers we measured

**In July, 0.0% of Sentinel-2 scenes over eleven years had more than 80% clear ground at our study slope.**
Not few — zero. July is when Nepal's landslides kill. Optical-only monitoring is blind exactly when it
matters, and radar is the only thing still looking (4–6 passes every month of every year).

Measured consequence: under an optical-only policy the system can speak on **90.4%** of days, with a
**hidden 34-day silence** across the monsoon. Adding radar closes it — **+58 points in July**.

And the intake side is broken too: BIPAD holds **7,081 citizen hazard reports of which zero are
verified**, 323 are uncleaned SQL-injection probes, and genuine reports (`सडकमा क्षति`, damage to the
road, ×46) were never actioned. Nepal's own 2020 review recommended the missing function and it was
never built.

## What the AI actually does

The guidelines' test: *"if you deleted the AI call from your codebase, would the product still do its
job? If yes, it doesn't qualify."*

**It does not.** Geometry, thresholds and every number stay deterministic. The open-weight model owns the
decision chain: severity triage, which asset is failing, which duty applies, which cited rule governs,
and the addressed advisory. Delete it and a free-text report yields no authority, no priority and no
dispatch — asserted in `tests/test_router.py::test_without_the_model_nothing_is_routed`.

Crucially, **the model is never asked what it knows.** Asked to name the responsible authority from its
own knowledge, it invented *Indian* ministries for a Nepali road. So it is constrained to **choose among
cited rules retrieved from the ontology**, and the institution and legal basis are read from the ontology
record — never from the model. Both responses are kept in `evidence/grounding-contrast.md`.

## The whole pipeline on the day of a real disaster

```bash
./scripts/demo.sh                                        # one command: starts the model, runs everything
./scripts/demo.sh --as-of 2024-07-20                     # a mid-monsoon date: the abstain state
./scripts/demo.sh --lon 85.30 --lat 27.70 --report "..."  # any slope you like
```

**2024-09-28 is the day BIPAD records 167 landslides.** Seven recorded steps, all live:

```
1. resolve_location     BIPAD      Ward 11, Thakre, DHADING, Province 3
2. rainfall_trigger     CHIRPS     EXCEEDED — 48h 190/142mm, 240h 245/215mm
3. ground_evidence      STAC       18 optical scenes (8 usable), 8 radar -> abstain
4. siting_advice        DEM        relocate 195 m upslope (+75 m): source zone at 135 m, 29 deg
5. route_report         model      Rural/Urban Municipality [local-road-maintenance]
6. compose_advisory                Nepali
7. emit_dispatch                   abstain, priority HIGH, validates OK
```

The advisory it produced:

> **पहिरो जोखिम सूचना** — वर्षाका कारण ढलान संवेदनशील बनेको छ, तर पछिल्लो अवलोकन उपलब्ध छैन।
> **वर्षाको अवस्था:** थ्रेसहोल्ड नाघ्यो (पाँचपोखरी थाङपाल, सिन्धुपाल्चोक) — ४८ घण्टामा १९०/१४२ मिमि
> **सिफारिस (स्थान):** सोही ठाउँमा मर्मत नगर्नुहोस् — नयाँ लाइन करिब १९५ मिटर माथि सार्नुहोस् (+७५ मिटर उचाइ)
> **जिम्मेवार निकाय:** Rural/Urban Municipality (Ward Chair) — LGOA 2074 s.12(2)(c)(23)

Four things at once, all of them defensible: the slope is primed, we cannot currently see it, do
not rebuild in the same place, and here is the office that owns it under the cited section.

## When it has already failed: the mesh, the API, and finding people

The half above warns that a slope is loaded and names the office on the hook. The other half
is what happens after it goes — no road, no tower, and people under the slide.

**A landslide takes the network with it**, so everything here works without one.

```bash
python scripts/demo_mesh_rescue.py     # SOS -> carried by hand -> located -> on the board
python -m pahiro.api --port 8080       # the API a mobile client is built against
```

* **Bluetooth mesh chat** (`src/pahiro/mesh/`) — messages travel phone to phone, carried by
  whoever walks within range. Real frames, real TTL and hop counts, real store-and-forward:
  the listener does not have to be there when the message was sent. Chat is evicted before a
  distress message when storage fills.
* **A field API** (`src/pahiro/api.py`) — not another screen. A common place for things to
  land, so a village phone, a rescuer's phone and the district desk see one picture. Every
  write is idempotent, reads take `?since=`, and there are no sessions, because a session is
  a thing that expires while you are under a rock.
* **Locating a buried handset** (`src/pahiro/locate.py`) — from RSSI alone, when GPS cannot
  see the sky. It answers with a **search radius, not a point**, and with two receivers it
  refuses to triangulate rather than invent one.

Measured: the estimator recovers a placed target to **under 25 m**, and the end-to-end demo
lands **20 m** off with a 15 m search radius. Full design, including the trade-offs and what
is *not* implemented: **[docs/MESH.md](docs/MESH.md)**.

## What this project does NOT claim

We do not claim to detect landslides better, to predict failure, or to be first at anything except a
machine-readable routing key. Detection is solved and published; we use it and credit it
(`docs/PRIOR-ART.md`, `docs/DIFERENTIATION.md`). Our contribution is the translation and dispatch layer.

## Architecture

```
INPUTS (borrowed, credited)                THE LAST METRE (ours)
  Sentinel-2 / Sentinel-1  ──┐
  CHIRPS rainfall            │   ingest tools → structured change features
  Copernicus DEM             ├─▶ (+ per-sensor observation age and verification state)
  susceptibility (Kincey)    │            │
  citizen reports (photo)  ──┘            ▼
                              TRIAGE + ROUTING (AI)  choose among cited rules from
                                             ontology/nepal-slope-routing.json
                              ADVISORY (AI)  constrained Nepali template
                              ABSTAIN (AI)   refuses when evidence is stale
                                             │
                                             ▼
                              ★ DISPATCH OBJECT (schema-validated JSON) ★
                                             │
                    ranked queue · Nepali advisory · work order · BIPAD register payload
                    alerts · append-only provenance (scene IDs, model, ontology version)
```

## Documentation

| Document | What it holds |
|---|---|
| `docs/AI-USAGE.md` | the required disclosure, naming the exact file/function where AI output is consumed |
| `docs/MODELS.md` | the pinned stack with measured latencies and licences |
| `docs/DATA.md` | verified data access, measured monsoon climatology, and the traps |
| `docs/PRIOR-ART.md` · `docs/DIFERENTIATION.md` | what exists, what we add, and the evidence |
| `docs/AUTHORITY-MAP.md` · `ontology/nepal-slope-routing.json` | who is responsible, under which section |
| `docs/COMPETITION.md` | the field, and what winning requires |
| `reports/eval-v0.md` · `reports/routing-eval.md` | measurements: gap calibration, routing accuracy |
| `docs/DEMO-SCRIPT.md` | the 2–3 minute demo video script |
| `docs/SPEECH.md` | the spoken pitch, a 90-second cut, Q&A armour, and a fact sheet citing every number |
| `docs/OFFLINE-RANGE.md` | how far software can actually reach, with measured ranges and the open-source projects that already solve parts of it |
| `docs/SEALING.md` | what a phone that carries your message is allowed to see, and why the crypto is not wired yet |

## Limitations — stated, not buried

- **Not validated for prediction.** This is a retrospective prototype on pilot corridors; no claim is
  made that it would have predicted any landslide. It measures whether the system can *speak*, and how
  accurately it *routes*.
- **Radar usability is unmeasured**, so radar-derived confidence is capped and labelled.
- **Single pilot AOI** for the monsoon numbers. The method transfers; the numbers must be re-measured.
- **The ontology is cited but not yet legally reviewed.** A Nepal-based legal reviewer must check every
  row before operational use. Where the law is silent we say so — e.g. no provision was found letting a
  municipality compel a landowner to stabilise a *bare slope*.
- **Nepali is template-based, not free-generated.** A purpose-built 1B English–Nepali model scores at
  chance, so the model selects among human-reviewed sentences rather than writing prose.
- **InSAR compliance is out of scope**; LiCSAR products are available for slow-creep validation.

## Licence

MIT — see `LICENSE`. Model licences are documented in `docs/MODELS.md`. This is not legal advice.
