# The slope-change agent

This is the layer the competition's first operational criterion is about — *"real autonomy, tool use, or
multi-step reasoning rather than a single prompt dressed up."* Every step below is a **recorded tool call**
with its arguments, result and duration. The trace is the evidence, and it is emitted with every run.

```
python scripts/agent_demo.py --report "..." --lon 85.05 --lat 27.76 --as-of 2024-07-20
```

## The loop

| # | Tool | What it does | Real source |
|---|---|---|---|
| 1 | `resolve_location` | coordinate → ward, municipality, district | BIPAD GeoServer WFS |
| 2 | `rainfall_trigger` | antecedent rainfall vs a published intensity–duration threshold | CHIRPS daily |
| 3 | `ground_evidence` | screens recent Sentinel-2 (SCL) and Sentinel-1 passes → staleness state | anonymous STAC, live |
| 4 | `route_report` | triage the free-text report, then choose among cited rules | open-weight model + cited ontology |
| 5 | `compose_advisory` | constrained Nepali advisory | template + model-selected slots |
| 6 | `emit_dispatch` | validated dispatch object, priority, register payload | deterministic |

The trace is not decoration. It is how a reviewer can check that the agent took a defensible path, and how
a failure is debugged without guessing.

## The decision is multi-signal

Two independent signals — the rainfall trigger and the state of ground evidence — combine into four states:

| Rainfall | Ground evidence | State | Priority |
|---|---|---|---|
| exceeded | fresh | **primed-confirmed** | high |
| exceeded | **not available** | **primed-unobserved** | high |
| below / approaching | fresh | monitored | medium |
| below | not available | abstain — nothing issued | — |

## `primed-unobserved` is the state that matters

In July, optical imagery is blind (measured: **zero usable Sentinel-2 scenes in July and August across
eleven years** over two independent areas) and radar gives only a handful of looks a month. A system that
stays silent then is indistinguishable from a system reporting safety.

So when the rain says the slope is primed and nothing can see it, the agent says exactly that, in Nepali:

> **पहिरो जोखिम सूचना — वर्षाका कारण ढलान संवेदनशील बनेको छ, तर पछिल्लो अवलोकन उपलब्ध छैन।**
> *"Landslide risk notice — the slope has been made sensitive by rainfall, but no recent observation is
> available."*

and it states plainly that the notice is **a signal of risk, not a confirmation of it**. This is more
useful than an all-clear and more honest than a guess, and no prior work in `docs/DIFERENTIATION.md`
surfaces a runtime state like it.

## The litmus test, at the agent level

`tests/test_agent.py::test_without_the_model_the_agent_still_runs_but_routes_nothing` runs the whole agent
with **no model** and asserts that the free-text report yields **no authority and no addressee** — the
dispatch is produced but marked `needs_review`. The agent still gathers evidence; it cannot route it.
That is the honest boundary of what the AI owns.
