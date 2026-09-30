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

**The implementation is complete and being prepared for publication.** This repository currently carries
only this description; the source, the evaluation harness, the cited routing key and the full
documentation land here before the showcase.

Static READMEs are cheap. When the code arrives it will be accompanied by:

- the agent loop and its step-by-step trace, so every conclusion is auditable;
- a cited routing key — 14 rules, each with its statutory basis;
- measured evaluation results, each reported with the weakness that qualifies it;
- a one-command demo that runs offline on a laptop CPU.

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
