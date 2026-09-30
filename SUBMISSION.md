# Submission — Pahiro (पहिरो)

**Nepal can already detect. Nepal cannot dispatch.** Pahiro is the missing last metre: it turns a slope
signal into a specific, readable, authority-addressed inspection request in Nepali — and says so when it
cannot see.

Read this file and you have everything. Ten minutes end to end.

---

## The five required items

| # | Required | Where | State |
|---|---|---|---|
| 1 | Public GitHub repository | `nisma01paudel/Open-Minds` | ✅ |
| 2 | Documentation — README, architecture, tech, **limitations/future work** | [README.md](README.md) · [docs/AGENT.md](docs/AGENT.md) · [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | ✅ |
| 3 | Working demo | **`./scripts/demo.sh`** — one command, verified cold | ✅ runs offline after first warm-up |
| 4 | 2–3 minute demo video | [reports/video/pahiro-narrated-web.mp4](reports/video/pahiro-narrated-web.mp4) — **2:34**, 1920×1080, continuous Nepali narration; shot list in [docs/DEMO-SCRIPT.md](docs/DEMO-SCRIPT.md) | **recorded ✅** |
| 5 | **AI usage disclosure** naming the exact file/function where AI output is consumed | [docs/AI-USAGE.md](docs/AI-USAGE.md) | ✅ |

## Run it

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e '.[geo,dev]'
python -m pytest -q                       # 120 tests
python scripts/verify_repo.py             # submission readiness: files, references, tests

# ONE COMMAND: starts the open-weight model, runs the whole pipeline, prints the
# trace and the Nepali advisory. Verified from a cold start.
./scripts/demo.sh

# a mid-monsoon date instead, to see the abstain state
./scripts/demo.sh --as-of 2024-07-20
```

`demo.sh` starts the model server itself (6 threads - 12 collapses throughput on this
CPU), so there is nothing to do first. Add `--stop` to shut the server down afterwards.
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

## Where things are

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
