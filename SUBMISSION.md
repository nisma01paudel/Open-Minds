# Submission — Pahiro (पहिरो)

**Nepal can already detect. Nepal cannot dispatch.** Pahiro is the missing last metre: it turns a slope
signal into a specific, readable, authority-addressed inspection request in Nepali — and says so when it
cannot see.

Read this file and you have everything. Ten minutes end to end.

---

## If you have sixty seconds

**The gap nobody builds.** Nepal has world-class detection science and several working detection
efforts. What does not exist is the *last metre*: a slope signal turned into a specific,
authority-addressed inspection request, in Nepali, that names who is responsible and under which
section of law. Everyone builds the detector. Nobody builds the dispatch, because it is a legal and
organisational problem rather than a modelling one — which is exactly why it is still open.

**It is anchored to a real event.** 12 July 2024, Simaltal: two buses, 62 people, 40 never
recovered. **The fatal slope was a rural road built by a municipality**, above the national highway.
Nobody was looking at the asset that failed.

**The result that should make you sceptical of every other entry.** Everyone assumes rainfall tells
you which slope will fail. We tested it and **it does not** — failing slopes sat at the
**53rd/55th percentile** of rainfall load, and only 4 of 14 crossed the threshold. So this system
**ranks, routes and recommends. It never predicts.** Said on the first slide, not buried in a
limitations section.

**It measures its own blindness.** July, August and September returned **0.0%** of whole scenes with
more than 80% of the frame clear; site-level usability in August was **16.8%**, and **17 of 142
documented sites were never seen at all**. The system says *"I cannot see this"* and **abstains**,
rather than going quiet and looking like *all clear*.

**It is a product, not a demo.** Nobody opens a landslide tool on a clear Saturday, and a tool nobody
opens is not installed on the Tuesday the mountain moves. So the same engine answers the ordinary
question too — which hiking trail, and which bus, from where I am standing. **23,726 mapped footpaths
across six regions of Nepal, offline, on the web and on the phone.**

**Open weights only, as the brief requires.** Qwen2.5-1.5B-Instruct on CPU through llama.cpp. No API
key, no hosted service, nothing that stops working when the credit runs out. And when the model is not
running, the planner still works on a deterministic reader — **one code path for choosing a trail,
not two.**

**Everything is checkable.** A clean clone builds, tests and verifies itself; the release APK carries
its own map data; every file in `web/public/data/` records what produced it; and the suite has been
**mutation-tested** — ten load-bearing constants broken on purpose, ten caught.

### What this does NOT claim

Stated here so you do not have to find it:

- **Nothing has run on a physical handset.** The release APK is installed and running on an Android emulator (see reports/device/), which shows the UI, the bundled trail data and the Nepali-first gate all work. An emulator cannot measure a radio, so every range figure below is still unverified hardware. Every radio range figure is somebody else's measurement or
  modelled from one. The logic is tested; the radios are not.
- **Duty identification is the weak axis at 52.4%** — routing is 61.9% exact and 76.2% on the right
  asset, but it abstains rather than guesses.
- **No cryptographer has reviewed the sealing layer.**
- Nepali footpath coverage is incomplete; the terrain grid is ~1 km; bus schedules are not known here.

---

## The five required items

| # | Required | Where | State |
|---|---|---|---|
| 1 | Public GitHub repository | `nisma01paudel/Open-Minds` | ✅ |
| 2 | Documentation — README, architecture, tech, **limitations/future work** | [README.md](README.md) · [docs/AGENT.md](docs/AGENT.md) · [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | ✅ |
| 3 | Working demo | **`./scripts/fetch_model.sh` once, then `./scripts/demo.sh`** | ✅ runs offline after the one-time fetch |
| 4 | 2–3 minute demo video | [reports/video/pahiro-narrated-web.mp4](reports/video/pahiro-narrated-web.mp4) — **2:36**, 1920×1080, continuous Nepali narration; shot list in [docs/DEMO-SCRIPT.md](docs/DEMO-SCRIPT.md) | **recorded ✅** |
| 5 | **AI usage disclosure** naming the exact file/function where AI output is consumed | [docs/AI-USAGE.md](docs/AI-USAGE.md) | ✅ |

## Run it

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e '.[geo,dev,crypto]'
.venv/bin/python -m pytest -q             # the whole suite, no skips
.venv/bin/python scripts/verify_repo.py   # submission readiness: files, references, tests

# ONE-TIME: 1.1 GB of weights and a compiled server. Deliberately not in the repo.
./scripts/fetch_model.sh

# ONE COMMAND AFTER THAT: starts the model, runs the whole pipeline, prints the
# trace and the Nepali advisory.
./scripts/demo.sh

# a mid-monsoon date instead, to see the abstain state
./scripts/demo.sh --as-of 2024-07-20
```

`demo.sh` starts the model server itself (6 threads - 12 collapses throughput on this CPU).
It needs `fetch_model.sh` to have run once: the weights are 1.1 GB and the server is a
compiled binary, so neither is in the repository, and a clone without them gets a clear
message naming both and the command that fetches them.

Without the model, geometry, thresholds and routing still work - only the decision step
needs it. `tests/test_router.py::test_without_the_model_nothing_is_routed` holds that line. Add `--stop` to shut the server down afterwards.
Pass `--as-of`, `--lon`, `--lat` or `--report` to interrogate any slope you like.

## See it in a browser

```bash
python scripts/build_demo_page.py        # renders reports/demo.html from the real JSON
python3 -m http.server 8099 --bind 127.0.0.1
# open http://127.0.0.1:8099/reports/demo.html
```

Nothing on that page is hand-written. The trace, the advisory, the siting figures and
the monthly observability table are all read out of the JSON the system actually
produced, so the page either matches the data or it is wrong.

## The other half — it is not only for the day the mountain moves

Nothing in a landslide tool gets opened on a clear Saturday. A tool nobody opens is a tool nobody
has installed when the ground gives way, and that is a real argument against building only the
disaster half.

So the same offline engine answers the ordinary question: **which hiking trail, and which bus,
from where I am standing.**

```bash
.venv/bin/python -m pahiro.api --port 8080        # then open the map and use Plan a walk
.venv/bin/python scripts/plan_trip.py --near 27.7750 85.3620 --origin 27.7047 85.3146
```

    trails within 3.0 km of 27.7750, 85.3620:
        4.02 km  +833 m  2h12   Shiva puri peak trek (stairs)
        3.59 km  +267 m  1h10   easy valley path

    from 27.7047, 85.3146:
        bus to Budhanilkantha Stop (~9.3 km, about Rs 37), then 4.8 km on foot

### What it is built on

| | |
|---|---|
| Hiking trails | **23,726 walkable ways, 153,480 vertices, 979 named**, 5.42 MB — OpenStreetMap over the six regions of Nepal |
| Bus access | **335 mapped bus stations** (76 named), from OSM |
| Fare | **Rs 24** valley minimum, April 2026, set by the Department of Transport Management. The distance component is a labelled approximation |
| Ask in words | The **open-weight model reads the request**; a deterministic engine chooses the trail, the stop and the fare |
| Offline | **4.2 MB precached** — the map, terrain, trails, advisories and observability layer, all of it |

### The model reads. The engine decides.

*"I have a free morning in Kathmandu and want an easy walk, maybe with a view, and I do not want
to spend more than 40 rupees on the bus"* becomes:

    understood as  easy; under 1h00; bus under Rs 40; wants view

Every field the model returns is **validated and clamped** before the engine sees it — a difficulty
of `extreme` is dropped, a 100,000-minute walk is dropped, an invented want is dropped, and each
refusal is reported rather than swallowed. The failure this prevents is a language model quietly
sending somebody up a mountain.

**Without the model server it still works.** The keyword reader handles the same sentence and the
planner is the same code — there is one code path for choosing a trail, not two. The answer says
which reader produced it, because those are different qualities of evidence.

### Stated rather than hidden

- **Nepali footpath coverage is incomplete.** A trail missing here is one nobody has drawn yet.
  Most mapped paths carry no difficulty tag, and the planner keeps them and says so rather than
  returning nothing.
- **Climb comes from a 1.2 km terrain grid** and is indicative — it will miss a 40 m knoll.
- **Bus schedules are not known.** Not the timetable, not whether it runs today, not bandha, not
  whether the route changed. The output says so and tells you to confirm at the park.
- Two OSM footpaths often meet without sharing a node, so junctions are snapped at **25 m**; the
  alternative was refusing to plan walks a person can plainly walk.
- **The whole feature has never run on a phone.** It is verified from a clean checkout, in a
  browser build, and over HTTP — not on a device in a valley.

## The demo, in seven auditable steps

Every step is a recorded tool call with its arguments, result and duration. The trace is the evidence.

```
1. resolve_location   BIPAD   Ward 11, Thakre, DHADING, Province 3
2. rainfall_trigger   CHIRPS  EXCEEDED — 48h 190/142mm, 240h 245/215mm
3. ground_evidence    STAC    18 optical scenes (8 usable), 8 radar -> abstain
4. siting_advice      DEM     relocate 195 m upslope (+75 m); source zone 135 m up, 29°
5. route_report       model   Rural/Urban Municipality [local-road-maintenance]
6. compose_advisory           Nepali
7. emit_dispatch              validates OK
```

The advisory, produced for real on that date:

> **पहिरो जोखिम सूचना** — वर्षाका कारण ढलान संवेदनशील बनेको छ, तर पछिल्लो अवलोकन उपलब्ध छैन।
> **वर्षाको अवस्था:** थ्रेसहोल्ड नाघ्यो (पाँचपोखरी थाङपाल, सिन्धुपाल्चोक) — ४८ घण्टामा १९०/१४२ मिमि
> **सिफारिस (स्थान):** सोही ठाउँमा मर्मत नगर्नुहोस् — नयाँ लाइन करिब १९५ मिटर माथि सार्नुहोस् (+७५ मिटर)
> **जिम्मेवार निकाय:** Rural/Urban Municipality (Ward Chair) — LGOA 2074 s.12(2)(c)(23)

Four defensible claims at once: the slope is primed, we cannot currently see it, do not rebuild in the
same place, and here is the office that owns it under the cited section.

## What the AI actually does — the eligibility test

> *"if you deleted the AI call from your codebase, would the product still do its job? If yes, it doesn't qualify."*

**It does not.** Geometry and thresholds stay deterministic. The open-weight model owns the decision
chain: which asset is failing, which duty applies, which cited rule governs, the addressed advisory.
Delete it and a free-text report yields **no authority and no addressee** — asserted, not claimed, in
`tests/test_router.py::test_without_the_model_nothing_is_routed`.

And the model is never asked what it knows. Asked to name the responsible authority from its own
knowledge, it invented **Indian** ministries for a Nepali road. It is therefore constrained to choose
among cited rules, and the institution is read from the ontology. Both responses are kept in
[evidence/grounding-contrast.md](evidence/grounding-contrast.md).

## Measured results, with their own weaknesses attached

| Result | Value | Source | Weakness |
|---|---|---|---|
| Routing accuracy (exact case) | **61.9%** | [reports/routing-ablation.md](reports/routing-ablation.md) | duty axis only 52.4%; labels debatable |
| Asset identification | 76.2% | same | 1.5B model is the ceiling |
| Confident misroutes across road tiers | **0** | same | — |
| Abstention precision | **100%** | same | 7 under-routes remain |
| Optical-only days issuable | 90.4% | [reports/eval-v1.md](reports/eval-v1.md) | one region |
| Longest optical blind streak | **34 days** | same | **replicates in a second area** |
| Scenes >80% clear, Jun/Jul/Aug | **0.0 / 0.0 / 0.0 %** | same | 2024, one AOI |
| Rainfall trigger on the 2024-09-28 event | EXCEEDED at 48/72/240 h | [docs/DATA.md](docs/DATA.md) | threshold fit rests on 43 events |
| Event benchmark | 613 sites | `benchmark/events.csv` | 1,650 distinct coordinates from 6,579 records |
| **Does rainfall ranking find the slopes that fail?** | **No — 55th percentile** | [reports/rainfall-ranking.md](reports/rainfall-ranking.md) | two event days only |
| Controls | 1,839 matched sites | `benchmark/controls.csv` | absence of a record is not stability |

## What this project does NOT claim

No prediction. No better detection. No first Nepali hazard app. Detection is solved and published, and
we credit it — including two 2026 papers that already use open-weight LLMs to write priority-ranked
landslide reports ([docs/PRIOR-ART.md](docs/PRIOR-ART.md), [docs/DIFERENTIATION.md](docs/DIFERENTIATION.md)).
Full list of limitations and honest gaps: [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## The phone app builds and installs

```bash
cd mobile && flutter build apk --release
# -> an APK under mobile/build/app/outputs/flutter-apk/   (48.5 MB, generated, not committed)
```

Verified, not asserted: the release APK builds and is a valid Android package. That is the only
check in this repository that proves the product exists as something a person can hold, and it is
the one to run first if you have half an hour.

**The APK is NOT in this repository**, deliberately: `mobile/build/` is gitignored, and fifty
megabytes of build output does not belong in git beside the source that generates it. So an
installable binary requires a Flutter toolchain - clone, one command, half an hour cold. If a
downloadable binary matters for demo day, attach the built APK to a GitHub **Release** rather than
committing it; that is what releases are for and it keeps the repository clean.

**What it does not prove is that it has run on a handset.** No radio figure has been measured on a
device, and every radio number in this repository is somebody else's measurement or modelled from
one. Installing this APK on a phone is the next real step.

## Where things are

The daily-use half: `src/pahiro/trails.py` (the network and routing), `src/pahiro/access.py` (bus
stops and fares), `src/pahiro/trip_agent.py` (the model reader), `src/pahiro/api.py`
(`/api/v1/plan`), `scripts/build_trails.py` (OSM → the offline bundle). Trail data © OpenStreetMap
contributors, ODbL 1.0, and the attribution travels inside the bundle.


| | |
|---|---|
| The routing key (who is responsible, under which section) | [ontology/nepal-slope-routing.json](ontology/nepal-slope-routing.json) · [docs/AUTHORITY-MAP.md](docs/AUTHORITY-MAP.md) |
| The spoken pitch, with a fact sheet citing every number | [docs/SPEECH.md](docs/SPEECH.md) |
| The agent loop | [docs/AGENT.md](docs/AGENT.md) · `src/pahiro/agent.py` |
| Model choices, sizes, licences, measured latencies | [docs/MODELS.md](docs/MODELS.md) |
| Verified data access and the traps | [docs/DATA.md](docs/DATA.md) |
| Prior art and the gap | [docs/DIFERENTIATION.md](docs/DIFERENTIATION.md) |
| The competitive field | [docs/COMPETITION.md](docs/COMPETITION.md) |
| How inspection actually reaches a road in Nepal | [docs/research/nepal-slope-reporting-chain.md](docs/research/nepal-slope-reporting-chain.md) |
| Who is legally responsible, statute by statute | [docs/research/nepal-slope-responsibility-map.md](docs/research/nepal-slope-responsibility-map.md) |

## Licence

MIT. Model licences in [docs/MODELS.md](docs/MODELS.md). Not legal advice; the routing key requires
review by a Nepal-based legal reviewer before operational use.
