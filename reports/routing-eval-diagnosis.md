# E1 diagnosis — why 38.1%, and what to fix

First honest measurement of the routing layer, 21 expert-labelled scenarios, all 21 answered by the
open-weight model. **Case accuracy 38.1% (44.4% on routable scenarios).** Not good enough. Here is
exactly how it fails, because the failure pattern is completely systematic.

## The failure pattern

| Predicted asset | Count | Expected distribution |
|---|---|---|
| local-road | **8** | 4 |
| strategic-road | 2 | 3 |
| any | 2 | 3 |
| private-land | 2 | 2 |
| public-building | 2 | 2 |
| province/riverbank | **0** | 4 |
| none | **0** | 3 |

Four defects, all diagnosable:

1. **A strong default to the first-listed option.** `local-road` was predicted 8 times against an
   expected 4, and `provincial-road` and `riverbank` were **never** predicted at all (0/4). The model is
   anchoring on the head of the candidate list rather than reasoning about the report.
2. **Systematic maintenance-vs-emergency confusion.** `highway-crack` (a crack, road open) was routed as
   *emergency*; `simaltal-01` was routed as *emergency* when the question was who owns the failing asset.
   The prompt never defined the two roles, so the model treats "something happened" as emergency.
3. **Abstention never happens.** 0/3. Three deliberately under-specified reports ("a road is affected by
   something") were all routed confidently. **Abstention recall 0%, precision 0%.** For a routing system
   this is the worst class of error: a confident wrong authority is worse than silence.
4. **The number guard fires constantly** — 8 of 21 rationales contained a numeric claim despite an
   explicit instruction not to state numbers. The guard worked, but it shows a 1.5B model ignoring
   negative instructions.

## The fix: do not ask a 1.5B model to do four things at once

The single-call design asked the model to pick one of 14 rules directly — which silently requires
resolving the asset, the role, the jurisdiction and the citation in one step. That is a hard task even
for a large model.

**Decomposition instead:** the model classifies **(asset, role)** from small, well-defined, few-shot
enumerations, and the ontology maps that deterministically to the cited rule. This is not a retreat from
"AI is load-bearing" — the model still makes the decision that determines everything downstream — it is
matching the task to the model's actual capability.

Concretely:
- **define the roles** in the prompt (maintenance = who owns and must fix it; emergency = who responds
  now), with the Simaltal rule stated explicitly: *the failing asset is the road on the slope, not the
  highway it damaged*;
- **few-shot exemplars**, including one that abstains, so `none` becomes a reachable answer;
- **stage two is deterministic**, so an answer cannot invent an authority;
- keep the **single-call implementation** as an ablation arm, so the improvement is measured, not claimed.

This is the honest research loop: measure, diagnose, change one thing, measure again.
