# AI usage disclosure

**Required for eligibility.** Names the exact file/function where AI output is consumed
programmatically, as the guidelines demand.

## Models and the rule we operate under

Open-weight only, end to end: Llama / Mistral / Qwen / DeepSeek class models, self-hosted (llama.cpp,
Ollama, vLLM) or via a hosted provider for open-weight models. **No proprietary AI API is called
anywhere** — not for the core logic, not for embeddings, not for auxiliary classification.
Model names, sizes and licences are pinned in `docs/MODELS.md`.

## The split that makes the AI load-bearing

The guidelines' test: *"if you deleted the AI call from your codebase, would the product still do its
job? If yes, it doesn't qualify."*

We answer that with an explicit division of labour, because the honest answer depends on it:

| Layer | Owner | Why |
|---|---|---|
| Imagery reads, cloud masking, spectral indices, thresholds, geometry, hydrology | **deterministic code** | must be reproducible, auditable and identical every run |
| **Asset and duty classification, severity triage, request composition and addressing, acknowledgement tracking** | **the open-weight models** | this is a judgement over messy real-world evidence — not a lookup |
| Mapping (asset, duty) → the cited rule, escalation path and institution | **deterministic** | the law is not a judgement call once the facts are classified; the citation must be reproducible |

Delete the AI layer and you delete the entire right-hand column: no authority is selected, no escalation
path is derived, no Nepali advisory is composed and addressed, and no acknowledgement can be tracked.
What remains is a viewer with numbers on it. **Nothing is dispatched** — and dispatch is the product.

**This is asserted in the test suite, not just claimed.** `tests/test_router.py::test_without_the_model_nothing_is_routed`
constructs the router with no model and shows that a free-text report yields **no authority, no priority
and no dispatch** — the honest boundary being that a report which *already names* its asset can still be
routed by the deterministic path (`test_structured_routing_still_works_without_the_model`). Free text is
where the AI is irreplaceable.

## Where each model's output is consumed programmatically

| File / function | Model class | What its output drives |
|---|---|---|
| `src/pahiro/routing/router.py::triage_route()` | open-weight instruct, JSON-schema constrained | **the load-bearing call.** Turns an unstructured hazard report into *(which asset is failing, which duty applies)* — the judgement that determines everything downstream. The ontology then maps that pair deterministically to the cited rule, so the institution and legal basis are read from the ontology record and can never be invented |
| `src/pahiro/routing/router.py::triage_route_single_call()` | same | the ablation arm: one call choosing directly among 14 cited rules. Measured at 38.1% case accuracy versus the two-stage design — the improvement is an ablation, not a claim (`reports/routing-eval-diagnosis.md`) |
| `src/pahiro/routing/router.py::route()` | open-weight instruct, JSON-schema constrained | reads the retrieved cited rules from `ontology/nepal-slope-routing.json` and returns the responsible institution, office, escalation path and priority. Consumed to address and order the dispatch queue |
| `src/pahiro/routing/router.py::route_incident()` | same | decides, for an incident with a failing asset and an affected asset, **which institutions must each be notified** |
| `src/pahiro/advisory/nepali.py::render()` | open-weight instruct, slot-constrained | composes the Nepali advisory and work-order text consumed by the dispatch object and the register payload |
| `src/pahiro/routing/abstain.py::staleness_gate()` | rules + model | decides whether an advisory may be issued at all, from per-sensor observation age and verification state |
| `src/pahiro/reports/classify.py::classify_report()` | open-weight vision/text | turns a citizen report into structured hazard fields consumed by the queue |

## Language discipline

Following the strongest entry in the field, outputs are **items to verify**, never accusations:

- the advisory says **"पहिले जाँच्नुहोस्"** (inspect first), never "this is unsafe";
- where routing cannot cite a governing section, the dispatch is marked **`needs_review`** and the
  advisory states that the responsible body is **"यकिन गर्न बाँकी"** (to be confirmed);
- every advisory carries a confidence value and, where relevant, routes to human review;
- where an observation is unvalidated we say so — *"रडारको उपयोगिता अझै नापिएको छैन"*.
