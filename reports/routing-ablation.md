# E1 — routing accuracy, three arms (an ablation, not a claim)

21 expert-labelled scenarios (`benchmark/routing-scenarios.jsonl`), all answered by the open-weight model
(Qwen2.5-1.5B-Instruct Q4_K_M, llama.cpp, `-t 6`, CPU only). Ground truth is the expert reading of each
report against the cited provisions — deliberately **not** derived from the ontology, because a test whose
answers come from the system under test measures nothing.

| Arm | Design | Case accuracy | Asset ID | Abstention precision | Over-routes | **Tier misroutes** | Under-routes |
|---|---|---|---|---|---|---|---|
| v1 | single call, choose among 14 rules | 38.1% | 52.4% | 0% | 3 | **1** | 0 |
| v2 | two-stage + aggressive abstention | 38.1% | 42.9% | 100% | 0 | **0** | 13 |
| **v3** | **two-stage, abstain only on an unknown asset, few-shot** | **61.9%** | **76.2%** | **100%** | **0** | **0** | **7** |

## What each change bought

**v1 → v2 (decomposition).** The single call asked a 1.5B model to resolve asset, duty, jurisdiction and
citation at once. It anchored on the head of the candidate list (`local-road` predicted 8 times against an
expected 4; `provincial-road` and `riverbank` never predicted at all) and **never once abstained** — three
deliberately unidentifiable reports were all routed confidently. Decomposing to *(asset, duty)* + a
deterministic mapping to the cited rule did not move the headline, but it **eliminated every dangerous
error**: tier misroutes 1 → 0, over-routes 3 → 0, abstention precision 0% → 100%.

**v2 → v3 (calibrating abstention).** v2 over-corrected: the instruction to abstain whenever the duty was
"unclear" made silence the default and cost 13 under-routes. Restricting abstention to *"the report names
no kind of asset at all"*, requiring a duty once an asset is known, and adding few-shot exemplars for the
asset classes the model was missing moved case accuracy **38.1% → 61.9%** and asset identification
**42.9% → 76.2%**, with the dangerous-error profile unchanged at zero.

**The flagship case now works.** `simaltal-01` — the July 2024 configuration where a municipal rural road
failed onto a *federal* highway — routes to the **municipality**, not the highway authority. In v1 it was
wrong.

## What is still weak, stated plainly

- **Duty identification is the weak axis (52.4%).** Maintenance vs emergency remains genuinely hard from
  brief reports, and it is the axis where the labelling is most debatable — `simaltal-01` is labelled
  *maintenance* (who owns the failing asset) while a reader could defensibly answer *emergency* (an event
  has occurred). Some of the measured error is label ambiguity, and a second annotator would be needed to
  separate the two. That is exactly why E2 reports inter-rater agreement.
- **7 under-routes remain.** The system still abstains on routable reports — safe, but it costs coverage.
- **A 1.5B model is the constraint.** With the GPU revived (the RTX 4050 is present but stuck post-suspend)
  a larger model is affordable and this number should rise again.

## Reproduce

```bash
scripts/serve_model.sh start
python -m pahiro.eval.routing --mode two-stage   --out reports/routing-eval.json      # v3
python -m pahiro.eval.routing --mode single-call --out reports/routing-single.json    # v1
```

Full per-scenario outputs: `reports/routing-eval-v3.md`, `reports/routing-eval.md`,
`reports/routing-eval-diagnosis.md`.
