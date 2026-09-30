# Why the model may only choose from cited rules — measured

Same open-weight model (Qwen2.5-1.5B-Instruct Q4_K_M, llama.cpp, `-t 6`), same task, two prompts.

## Ungrounded — asked to name the responsible authority from its own knowledge

> "A rural road built by a municipality on a slope above a national highway has failed and
> blocked the highway. Which institutions must be notified?"

```json
{"responsible_institution": "Municipality, National Highway Authority of India (NHAI),
 Ministry of Road Transport and Highways, Ministry of Home Affairs, Ministry of Urban
 Development, Ministry of Housing and Urban Affairs, ..."}
```

Raw response: `hallucination-ungrounded.json`.

**It invented Indian federal ministries for a Nepali road.** NHAI does not exist in Nepal. The
answer was also syntactically valid JSON — grammar constrains form, not truth.

## Grounded — same model, choosing among retrieved cited rules

The router retrieves candidate rules from `ontology/nepal-slope-routing.json` (deterministic,
no model), passes them as an enumerated option list, and constrains `case_id` to their
identifiers with a JSON-schema `enum`. The institution is then read from the ontology record,
never from the model.

| Report | Model's selection | Institution applied | Legal basis applied |
|---|---|---|---|
| Failing asset: municipal rural road (Simaltal) | `local-road-maintenance` | Rural/Urban Municipality (Ward Committee) | LGOA 2074 s.12(2)(c)(23) |
| Affected asset: national highway | `strategic-road-maintenance` | Department of Roads (DoR), MoPIT | Constitution 2072 Sch. 5 item 20 |
| Road already blocked (emergency role) | `strategic-road-emergency` | District Disaster Management Committee | DRRM Act 2074 s.16(2) |

The model's rationale (unedited):

> "The slope-hazard report indicates a critical issue with local roads… The municipality has the
> legal responsibility to address such issues, and the Ward Committee is the first level of
> authority to address such matters."

## The design rules that follow

1. **The model never decides what it knows** — only which of the retrieved, cited duties applies.
2. **The `enum` is the guardrail**: any `case_id` outside the retrieved set is rejected and the
   router falls back to a deterministic decision.
3. **Institutions, offices and legal citations come from the ontology**, so they cannot be invented.
4. **The model never states a number.** A rationale containing a digit is withheld and flagged
   (`numeric_claim_withheld`), because in an earlier run the model echoed `mean_slope_deg` as
   "the slope has increased by 31 degrees".
5. **Ambiguity abstains.** Two equally good rules produce no routing and a human-review marker,
   not a coin flip.
