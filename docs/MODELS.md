# Pinned model stack

Every entry was verified for existence and licence against the HuggingFace API, and every latency was
**measured on this laptop** (Ryzen 5 8645HS, 6 physical cores, ~3 GB free RAM). Full numbers:
`research/ai-stack-benchmarks.md`.

## The stack

| Slot | Model | Size | Licence | Measured on this machine |
|---|---|---|---|---|
| Change detection | **DINOv2-S/14 int8** (ONNX) | 24.5 MB | Apache-2.0 | 30.4 ms per 224px |
| — alternative | CLIP ViT-B/32 int8 | 89 MB | MIT | 17.0 ms per 224px |
| Decision head | LightGBM / logistic regression over embeddings + SSIM + index deltas | <5 MB | BSD/MIT | trains in seconds, CPU |
| Before/after description | **SmolVLM-256M Q8_0** | 279 MB | Apache-2.0 | **3.2 s per image pair** |
| Routing + advisory text | **Qwen2.5-1.5B-Instruct Q4_K_M** | 1117 MB | Apache-2.0 | 6.1 s / 88 tokens, **5/5 valid JSON** |
| Nepali speech | **Piper `ne_NP` chitwan medium** | 63 MB (62,950,044 bytes, verified) | MIT | **7.3 s of Nepali in 2.3 s (RTF 0.32)**, best of 3 one-shot CLI runs; ~1.3 s of that is process start and model load |

Total ≈ **1.7 GB** on disk. Peak RAM with all five resident ≈ 3.0 GB — equal to our free RAM, so
**load one model at a time and unload between stages.**

## Rejected, with reasons

| Rejected | Why |
|---|---|
| `facebook/mms-tts-npi` | **does not exist.** The similar `mms-tts-npl` is **Nahuatl**, a Mexican language. Meta MMS has no Nepali, and is CC-BY-NC-4.0 |
| Qwen2.5-**3B**-Instruct | **not Apache-2.0** — Qwen Research Licence (non-commercial). Use Qwen3-1.7B/4B or Qwen2.5-1.5B |
| DINOv3 | gated (`401 must log in`), licence `other` |
| moondream2 GGUF | f16 only → 3.75 GB, does not fit |
| Qwen3-VL | not in llama.cpp's supported list; a crash issue is filed |
| FastSAM | **AGPL-3.0** — copyleft risk for a graded submission |
| NLLB-200 | CC-BY-NC-4.0 (IndicTrans2 is MIT instead) |
| `nvidia/segformer-b0/b1` | licence tag `other`, LICENSE file 404s — unresolved |

## Rules that matter more than model choice

1. **Never pass `-t 12`.** Measured generation with Qwen2.5-1.5B Q4_K_M:
   **15.8 tok/s @ 4 threads · 15.3–17.3 @ 6 · 11.4 @ 8 · 1.0–3.5 @ 12.** Six physical cores; SMT
   oversubscription collapses throughput 5–15×. Same in ONNX (CLIP int8: 17.0 ms @ 6 vs 67.1 ms @ 12).
   **Always `-t 6`.**
2. **Inline JSON schemas.** `$ref`/`$defs` silently fails in llama.cpp (`MAX_REPETITION_THRESHOLD`).
   With an inlined `response_format: json_schema`: 5/5 valid. Without any grammar: 0/3.
3. **Grammar fixes syntax, not truth.** One valid run wrote *"the slope has increased by 31 degrees"* —
   echoing `mean_slope_deg` rather than a delta. **The model never emits a measured number.** Code
   computes; the model may only echo after parsing. Validate with a real schema plus range asserts, and
   fall back to a deterministic template rather than retrying.
4. **Batch hurts.** CLIP int8 single image 17.0 ms vs 23.4 ms/image at batch-16. Use a process pool.
5. **The ONNX vision exports are 224-fixed** despite dynamic-looking signatures; 518×518 throws. Treat
   512×512 as a tiling problem, not one forward pass.

## Nepali

A purpose-built 1.04B English–Nepali model scores **0.240 against a 0.250 chance baseline** — even a
specialist is at chance. Therefore: **the model never writes Nepali prose.** It selects among
pre-written, human-reviewed Nepali sentences and fills a deterministic template. A fluent speaker
reviews every template line before submission. (Optional MIT fallback for free text: IndicTrans2.)
