# Pahiro (पहिरो)

**Nepal can already detect. Nepal cannot dispatch.**

Nepal has world-class landslide science and several working detection efforts. What it does not have is
the last metre: a slope signal turned into a specific, readable, authority-addressed inspection request,
in Nepali, that names who is responsible and under which section of law.

Pahiro is that last metre.

---

## What it does

A report arrives — *"a rural road built by a municipality runs across the slope above the national
highway; cracks have appeared and debris is falling onto the highway."*

Pahiro returns an advisory that names the **failing asset** rather than the asset it damaged, the
**responsible office**, and the **legal basis** for that office's duty — and it says so, plainly, when
the evidence does not support a claim at all.

The distinction it is built around: the upslope road belongs to a municipality; the highway below
belongs to the federal government. A system that routes on the damage rather than the cause sends the
inspection to the wrong office. That is not a hypothetical — it is the Simaltal failure of
12 July 2024, where two buses carrying 62 people went into the Trishuli, 40 of them never recovered,
and the fatal slope was a rural road built by Bharatpur Metropolitan City.

## Status

**The implementation has landed.** This file was the placeholder README from when the repository
carried only a description; it is kept because the step-by-step publication was deliberate, and
because deleting a file that once explained the plan is how a project loses the record of having
had one.

It is superseded by [README.md](../README.md). What it promised is now here:

- the agent loop and its step-by-step trace — [docs/AGENT.md](AGENT.md), `src/pahiro/agent.py`
- the cited routing key, 14 rules each with its statutory basis —
  [ontology/nepal-slope-routing.json](../ontology/nepal-slope-routing.json)
- measured evaluation results with their weaknesses attached —
  [reports/eval-v1.md](../reports/eval-v1.md), [reports/routing-ablation.md](../reports/routing-ablation.md)
- a one-command demo that runs offline on a laptop CPU — [SUBMISSION.md](../SUBMISSION.md)

Two things this file used to say that are **no longer true**, corrected here rather than quietly
deleted:

- *"this repository currently carries only this description"* — it carries 513 tracked files (counted, not remembered — see the test that derives it).
- *"when the code arrives"* — it arrived.

What it promised, and where each promise now lives, is listed in **Status** above.
## Principles

- **Open-weight models only**, running locally. Free and anonymous data sources; no API keys.
- **The model never invents a fact.** Numbers, geometry and thresholds are deterministic; the model
  chooses among cited rules, and the institution is read from the ontology record, never generated.
- **Abstention is a feature.** When the evidence is not there, the system says so rather than going
  quiet — because silence is indistinguishable from safety.
- **Honest about limits.** Nothing here claims to predict a landslide, and the documentation says which
  numbers are assumed rather than measured.

## Licence

MIT.

---

*Submitted to Frogtoberfest 2026 — Leapfrog Technology, Nepal.*
