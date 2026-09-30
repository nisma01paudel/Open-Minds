# AI usage disclosure

**Required for eligibility.** Must name the exact file/function where AI output is consumed programmatically.

Rules we operate under: open-weight / self-hostable models only (Ollama, LM Studio, vLLM; Llama, Mistral,
Qwen, DeepSeek), locally or via a hosted inference provider for open-weight models. **No proprietary AI
API anywhere** — not for the core logic, not for embeddings, not for auxiliary classification.

## Where AI output is consumed programmatically

| File / function | Model class | What its output feeds |
|---|---|---|
| `src/pahiro/routing/router.py::route` | open-weight instruct (JSON-schema constrained) | retrieved mandate ontology → responsible institution, escalation path, priority; consumed to address and order the dispatch queue |
| `src/pahiro/advisory/nepali.py::render` | open-weight instruct | constrained Nepali advisory template; consumed by the dispatch object and work-order export |
| `src/pahiro/routing/abstain.py::staleness_gate` | rules + model | decides whether an advisory may be issued at all |
| `src/pahiro/reports/classify.py::classify_report` | open-weight vision/text | citizen report → structured hazard fields consumed by the queue |

## The Core Test

Delete the AI layer and there is no institution selection, no escalation path, no Nepali advisory, and no
ability to abstain. What remains is a viewer with numbers on it. Nothing gets dispatched.
