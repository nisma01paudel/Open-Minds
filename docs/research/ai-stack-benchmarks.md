# Open-Weight, CPU-Only AI Stack — Frogtoberfest 2026 (Leapfrog, Nepal)

**Target hardware (measured on this machine):** AMD Ryzen 5 8645HS — **6 physical cores / 12 threads**, 14 GB RAM (~3 GB free, load avg ~21), no usable NVIDIA GPU, Radeon 760M iGPU. 181 GB free disk.

**Rules (read from `/home/logic/win/guidelines.txt`):** "This challenge is built on open, self-hostable AI." Approved: local/self-hosted inference (Ollama/LM Studio/vLLM), **open-weight models run locally *or through a hosted inference provider***, open-source agent frameworks. Banned: "OpenAI/ChatGPT, Anthropic/Claude, Google Gemini, Azure OpenAI, and similar closed, paid services" — *"It covers the whole pipeline, including smaller auxiliary calls like embeddings or a secondary classification step."*

---
## 0. Environment findings that change the plan

| Finding | Evidence | Impact |
|---|---|---|
| **An NVIDIA RTX 4050 Max-Q IS physically present** (`01:00.0 AD107M`) but has **no kernel module loaded**; `nvidia-smi` → "Unable to determine the device handle … Unknown Error", no `nvidia` in `lsmod` | `lspci`, `nvidia-smi`, `lsmod` | The brief's "no NVIDIA GPU" is **true in practice**, but this is a *fixable* upside, not a hardware absence. If a 4050 can be made to work, every latency below drops 20–50×. Worth 30 min of driver investigation before accepting CPU-only limits. |
| **Only Python 3.14 system-wide, and `pip` is missing** (`No module named pip`) | `python3 -m pip --version` | Python 3.14 is too new for most ML wheels. Use `uv` (already installed at `/home/logic/.local/bin/uv`) to pin **Python 3.12**: `uv venv --python 3.12`. This worked. |
| **`/usr/bin/time` absent**; gcc 16.2.1 + cmake + make present | — | llama.cpp builds fine from source; don't shell out to `/usr/bin/time`. |
| **System is heavily oversubscribed** (load avg 21 on 12 threads; browsers resident) | `uptime`, `ps` | All numbers below are *pessimistic real-world* figures, which is what a live demo will look like. |

### 0.1 THE MOST IMPORTANT FINDING: never use all 12 threads

llama.cpp, Qwen2.5-1.5B-Instruct Q4_K_M, measured repeatedly:

| threads | prefill (pp256) t/s | **generation (tg64) t/s** |
|---|---|---|
| 4 | 187 | **15.8** |
| **6** | **218** | **15.3 – 17.3** |
| 8 | 190 | 11.4 |
| 12 | 115 | **1.0 – 3.5** |

**12 threads is 5–15× SLOWER than 6.** The chip has 6 physical cores; SMT oversubscription plus a loaded machine destroys generation throughput. A naive `-t 12` ("use all my threads") turns a 15 tok/s stack into a 1 tok/s stack. **Always pass `-t 6`.** The same effect appeared in ONNX Runtime (CLIP int8: 17.0 ms at 6 threads vs 67.1 ms at 12).

---
## 1. IMAGE CHANGE DETECTION / VISUAL SIMILARITY

**Measured** (ONNX Runtime 1.30.0, CPU EP, **6 threads**, 224×224, idle-ish machine):

| Model | Disk | 1×224 | batch16 /img | img/s (single) | License |
|---|---|---|---|---|---|
| **CLIP ViT-B/32 int8** | **89 MB** | **17.0 ms** | 23.4 ms | **~59** | MIT (OpenAI CLIP) |
| CLIP ViT-B/32 fp32 | 352 MB | 55.7 ms | 41.5 ms | ~18 | MIT |
| DINOv2-S/14 int8 | 24.5 MB | 30.4 ms | 40.8 ms | ~33 | Apache-2.0 |
| DINOv2-S/14 fp32 | 88.5 MB | 54.3 ms | 68.2 ms | ~18 | Apache-2.0 |
| SigLIP2-base int8 | 94.6 MB | 53.3 ms | 112.3 ms | ~19 | Apache-2.0 |
| SigLIP2-base fp32 | 372 MB | 120.1 ms | 159.7 ms | ~8 | Apache-2.0 |

- Verified ONNX repos: [`Xenova/clip-vit-base-patch32`](https://huggingface.co/Xenova/clip-vit-base-patch32) (`onnx/vision_model_quantized.onnx` = 89.1 MB), [`Xenova/dinov2-small`](https://huggingface.co/Xenova/dinov2-small) (`model_quantized.onnx` = 24.5 MB), [`onnx-community/siglip2-base-patch16-224-ONNX`](https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX) (`vision_model_quantized.onnx` = 94.6 MB).
- Licenses verified via the HF API: [`google/siglip2-so400m-patch14-384`](https://huggingface.co/google/siglip2-so400m-patch14-384) and `google/siglip-so400m-patch14-384` = **apache-2.0**; `facebook/dinov2-small` / `dinov2-base` = **apache-2.0**.
- ⚠️ **DINOv3 is NOT usable**: [`facebook/dinov3-vits16-pretrain-lvd1689m`](https://huggingface.co/facebook/dinov3-vits16-pretrain-lvd1689m) returns **HTTP 401 / "Access to model … is restricted. You must log in"** and its license tag is `other`. Avoid it. (A satellite-pretrained `dinov3-vit7b16-pretrain-sat493m` also exists — same gating problem.)
- ⚠️ **These ONNX exports are 224-fixed.** Despite input signatures reading `['batch_size','num_channels','height','width']`, a 518×518 input **fails**: `Add` node broadcasting `257 by 1370` (DINOv2), `Reshape` `{1,768,32,32}` → `{-1,768,196}` (CLIP/SigLIP). The position embeddings are baked in. For 512×512 you must either **tile into 224 crops** or re-export with interpolated pos-embeds.

**Batching does NOT help here** — CLIP int8 single-image (17.0 ms) beats batch-16 (23.4 ms/img). Process single images in a pool rather than batching.

**Is cosine distance between bi-temporal patch embeddings defensible?** Yes as a *candidate generator*, **no as a final verdict**. It is a real, published approach (frozen-feature / training-free change detection; see [DynamicEarth: How Far are We from Open-Vocabulary Change Detection?](https://arxiv.org/abs/2501.12931) and [Make Some Noise: Unsupervised Remote Sensing Change Detection Using Latent Space Perturbations](https://arxiv.org/pdf/2602.19881)). But cosine distance conflates *changed* with *semantically different*, and is corrupted by:
- **mis-registration** (1–2 px shift produces large pseudo-change along edges),
- **illumination / shadow / seasonal vegetation phenology**, and
- **sensor/ORTHO differences between dates**.

**A supervised head is the right call, not fine-tuning.** Fine-tuning a ViT needs GPU-scale compute and thousands of labelled patch pairs you do not have. A logistic regression / LightGBM head on `[DINOv2 or CLIP embedding (both dates) ‖ cosine distance ‖ SSIM ‖ spectral index deltas (NDVI/NDWI) ‖ gradient/slope features]` trains in seconds on CPU and is auditable. Use cosine distance as **one input feature**, never as the decision.

- **PRIMARY:** DINOv2-S/14 int8 (24.5 MB, Apache-2.0, ~33 img/s) — best licence:size:latency ratio; strong dense features.
- **FALLBACK:** CLIP ViT-B/32 int8 (89 MB, MIT, ~59 img/s) — nearly 2× faster, weaker fine-grained spatial detail. Add SigLIP2-base int8 only if you need its stronger zero-shot text alignment.

## 2. SEGMENTATION OF SLOPES / ROADS / SCARS

| Model | Disk | License | CPU verdict |
|---|---|---|---|
| **SAM 2.1 hiera-tiny** [`facebook/sam2.1-hiera-tiny`](https://huggingface.co/facebook/sam2.1-hiera-tiny) | ~150 MB | **Apache-2.0** | Best SAM-family choice. **Prompted** (point/box) is cheap — sub-second. Full automatic mask generation (AMG) is *many* decoder passes; batch-only. |
| SAM 2.1 hiera-small | ~180 MB | Apache-2.0 | Fallback if tiny under-segments. |
| SAM ViT-B [`facebook/sam-vit-base`](https://huggingface.co/facebook/sam-vit-base) | 375 MB | Apache-2.0 | Okay; SAM2 tiny is better. |
| **MobileSAM** [`PulpCut/mobilesam-onnx`](https://huggingface.co/PulpCut/mobilesam-onnx) | encoder 28.2 MB + decoder 16.5 MB (**quant 8.8 MB**) ≈ **44 MB** | Apache-2.0 | Lightest promptable option; genuinely CPU-friendly. |
| **SegFormer-B0** [`Xenova/segformer-b0-finetuned-ade-512-512`](https://huggingface.co/Xenova/segformer-b0-finetuned-ade-512-512) | **15.3 MB** fp32 / **4.4 MB** quantized | ⚠️ NVIDIA tag = `other` | Fastest path to a dense class map (ADE20K = 150 classes incl. road/ground). **Check the licence** — `nvidia/segformer-b0/b1-*` are tagged `other`, not Apache-2.0 (the LICENSE file 404s). |
| FastSAM-X/S | ~70–140 MB | AGPL-3.0 (Ultralytics) | ⚠️ **AGPL** — copyleft; risky for a graded open-source submission. |
| SAM ViT-H | ~2.4 GB | Apache-2.0 | ❌ Not viable on 3 GB RAM / CPU. |

Honest caveat: **there is no credible open landslide-segmentation checkpoint.** Searches surfaced only near-zero-download, undocumented repos (`Suchit037/Landslide-Segmentation`, `rangerhkai/ranger-landslide-detection-model`, etc. — all <10 downloads). Do **not** depend on them. Road segmentation has one semi-credible option (`kishan4444/upernet-swin-openearthmap-road-segmentation`, 352 downloads) but nothing you should build a demo on.

- **PRIMARY:** SAM 2.1 hiera-tiny (`facebook/sam2.1-hiera-tiny`, Apache-2.0) — **prompted** on change-detection hotspots from §1. Cheap because you only decode a few prompts, not the whole grid.
- **FALLBACK:** MobileSAM ONNX (44 MB, Apache-2.0) if SAM2 is too heavy; or SegFormer-B0 quantized (4.4 MB) if you only need a coarse class map and you accept the `other` licence.

## 3. SMALL VISION-LANGUAGE MODEL

**Verified supported** by llama.cpp `libmtmd` — its own [`docs/multimodal.md`](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/docs/multimodal.md) lists SmolVLM/2, Qwen2-VL, Qwen2.5-VL (3B/7B/32B/72B), InternVL2.5 (1B/4B), InternVL3 (1B/2B/8B/14B), moondream2, Gemma 3/4, Pixtral-12B, Llama-4-Scout. Use `--no-mmproj-offload` for CPU.

**⚠️ Qwen3-VL is NOT in that official list.** A `ggml-org/Qwen3-VL-2B-Instruct-GGUF` repo *does* exist but ships **only Q8_0** (LM 1834 MB + mmproj 445 MB = **2.28 GB** — too big for 3 GB free with KV cache), and there is a filed crash report for Qwen3-VL/Qwen3.5 on serve: [llama.cpp issue #21750](https://github.com/ggml-org/llama.cpp/issues/21750). Treat Qwen3-VL as experimental.

**Measured on this machine (llama.cpp 0.5.0-dev build `eae11d2`, `-t 6`, `--no-mmproj-offload`, before/after image pair):**

| Model | LM + mmproj | Total | **2 images, wall** | Output quality |
|---|---|---|---|---|
| **SmolVLM-256M-Instruct Q8_0** | 175 + 104 MB | **279 MB** | **3.18 s** | Terse but **correct**: *"A landslide occurred."* |
| InternVL3-2B Q4_K_M | 1117 + 337 MB | 1.45 GB | **50.25 s** | Detailed & accurate: *"The hillside in Image 2 has a large, dark brown area where the soil has slid away, creating a visible gap…"* |

Logs showed 9 image chunks encoded at ~500–910 ms each. Other sizes (verified via HF API):
- SmolVLM-500M: 437 + 109 = 546 MB
- SmolVLM2-2.2B: 1113 + 593 = 1.71 GB
- Qwen2.5-VL-3B: 1930 + 845 = **2.78 GB** → too big at 3 GB free
- moondream2 GGUF: 2840 + 910 = **3.75 GB (f16 only)** → ❌ does not fit
- gemma-4-E2B Q4_0: 2841 + 557 = 3.4 GB → ❌ does not fit
- Phi-3.5-vision (MIT) has no ggml-org GGUF; not on the supported list

**Verdict: a CPU VLM IS practical — at the 256M scale.** 3.2 s per image pair is demo-safe. But note the quality/latency cliff: going from 256M to 2B costs **16× latency** for better prose. For a graded demo, **use the VLM only to phrase a change you already detected numerically**, and always show the numbers next to its sentence.

- **PRIMARY:** SmolVLM-256M-Instruct Q8_0 (279 MB, Apache-2.0) — 3.2 s, fits anywhere.
- **FALLBACK:** InternVL3-2B Q4_K_M (1.45 GB) for a pre-recorded "detailed description" mode — 50 s is **too slow for live interaction**; use it in batch or on a cached example.
- **If RAM is ever tighter than ~500 MB:** drop the VLM entirely and have the text LLM (§4) phrase the advisory from structured numeric change features. This is **more defensible for judging** — it is verifiable, reproducible, and has no hallucination surface.

## 4. TEXT LLM FOR STRUCTURED ADVISORY GENERATION

**Measured** — Qwen2.5-1.5B-Instruct Q4_K_M (1117 MB) via `llama-server`, `-t 6`:

| Condition | Result |
|---|---|
| **No grammar constraint, 3 runs** | **0/3 valid JSON** — emitted markdown prose ("Based on the provided parameters…") |
| **`response_format: json_schema`, 5 runs** | **5/5 VALID**, correct required keys and types |
| Latency | **6.1 s wall** for 88 completion tokens ≈ **14.6 tok/s** |

**Grammar fixes syntax, NOT meaning.** In the 5 valid runs the model still wrote *"the slope has increased by 31 degrees"* (31 was `mean_slope_deg`, not a delta) and *"the landslide area has increased by 12.4%"*. Constrained decoding eliminates *parse* failures; it does **not** eliminate semantic error. Validate numbers against your own computed features and overwrite them deterministically — never let the LLM be the source of a measurement.

**⚠️ llama.cpp gotcha:** [`json_schema` with `$ref`/`$defs` silently fails — "grammar rule count exceeds MAX_REPETITION_THRESHOLD" (issue #21228)](https://github.com/ggml-org/llama.cpp/issues/21228). **Inline your schema; do not use `$ref`/`$defs`.** Pass the schema in `response_format` (`llama-server` supports `json_schema` natively); GBNF via `--grammar-file` is the lower-level equivalent.

**⚠️ Licensing trap in the brief's own candidate list:** `Qwen/Qwen2.5-3B-Instruct` is **not Apache-2.0** — it ships the **Qwen RESEARCH LICENSE AGREEMENT** (non-commercial). Verified: `Qwen2.5-0.5B/1.5B/7B` = `apache-2.0`, **`Qwen2.5-3B` = `other` = research-only**. **Use Qwen3-1.7B / Qwen3-4B-Instruct-2507 instead — both verified `apache-2.0`.**

**RAM/size:** Q4_K_M of a 1.5B ≈ 1.1 GB; 3B ≈ 1.9 GB; 7–8B ≈ 4.4–4.9 GB. llama.cpp **mmaps** weights, so the 1.1 GB model loaded fine with 1.1 GB "free" (page cache is reclaimable) — but a 7B will thrash under memory pressure. **Stay ≤3B.**

- **PRIMARY:** **Qwen3-4B-Instruct-2507 Q4_K_M** (~2.5 GB, **Apache-2.0**) — if RAM allows; strongest reasoning/JSON discipline in the Apache-2.0 small class.
- **FALLBACK:** **Qwen2.5-1.5B-Instruct Q4_K_M** (1117 MB, Apache-2.0) — **measured working end-to-end here** at 6.1 s/88 tokens with 5/5 schema-valid output. This is the safe, proven choice at 3 GB free.
- Avoid: Qwen2.5-3B (research licence), Llama-3.2-3B (`llama3.2` community licence + weakest JSON behaviour), Gemma (`gemma` licence), moondream2/Phi-3.5-vision (no viable CPU path).

## 5. NEPALI LANGUAGE CAPABILITY

**Honest answer: small open models are weak at Nepali generation. Do not build the plan on it.**

Evidence:
- **A purpose-built 1B English–Nepali model still fails.** [Arkios (arXiv 2608.30092)](https://huggingface.co/papers/2608.30092) — 1.04B params trained from scratch on 150B bilingual tokens with a **Devanagari-aware tokenizer** — scores **0.240 Nepali / 0.236 English against a 0.250 chance baseline** under standard multiple-choice-letter prompting. Scoring answer text directly gives only **0.306 Nepali / 0.387 English**. Weights: [`sajalregmi4/arkios-1b-base`](https://huggingface.co/sajalregmi4/arkios-1b-base) / [`arkios-1b-chat`](https://huggingface.co/sajalregmi4/arkios-1b-chat), **Apache-2.0**. The abstract also warns that a naive harness run *"would lead a naive benchmark run to conclude the model has no Nepali ability."* Even the specialists are near chance at 1B.
- **Llama 3.2's official languages are English, German, French, Italian, Portuguese, Hindi, Spanish, Thai.** **Hindi ≠ Nepali** — shared Devanagari script, different grammar and vocabulary. Script transfer is not language competence.
- **Devanagari tokenizes expensively** in mostly-English BPE vocabularies — materially more tokens per word than English, so a 2–4B model burns its small context on fewer Nepali words and degrades faster.
- The Nepali-specific fine-tunes that exist are **unproven**: [`mradermacher/Qwen-0.6b-nepali-instruct-GGUF`](https://huggingface.co/mradermacher/Qwen-0.6b-nepali-instruct-GGUF) (629 downloads), [`shivam9980/NEPALI-LLM-INSTRUCT-Q4_K_M-GGUF`](https://huggingface.co/shivam9980/NEPALI-LLM-INSTRUCT-Q4_K_M-GGUF) (14 downloads), `vhab10/Llama-3.2-3B-Instruct_Nepali_gguf_q4_k_m` (42 downloads). **Three orders of magnitude below what would justify trusting them**; no eval is published.

**Recommended workaround (the honest one):** the LLM emits **structured JSON with English/latin keys and numeric values** (which §4 proved it does reliably), and a **deterministic Nepali template** fills slots. The LLM's *only* Nepali job is selecting among pre-written, human-reviewed Nepali sentences.

- Template + slots, LLM picks the variant and supplies numbers → **no Nepali generation risk at all.** Best choice.
- For the free-text `summary` slot, **translate** English→Nepali with **[IndicTrans2](https://huggingface.co/ai4bharat/indictrans2-en-indic-1B)** — verified **MIT** licence (also `indictrans2-en-indic-dist-200M` = 200M params, MIT, and `ai4bharat/indictrans2-indic-en-1B`). Prefer this over NLLB: [`facebook/nllb-200-distilled-600M`](https://huggingface.co/facebook/nllb-200-distilled-600M) is **CC-BY-NC-4.0 (non-commercial)**.
- **Have a fluent Nepali speaker read every template sentence before submission.** No benchmark substitutes for this, and the rules reward a verifiable, honest pipeline.

## 6. HOSTED OPEN-WEIGHT ACCELERATION

Permitted by the rules ("run locally **or through a hosted inference provider**"). Verified free tiers ([OpenRouter's 2026 comparison](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/), [Cloudflare Workers AI pricing, updated 2026-09-17](https://developers.cloudflare.com/workers-ai/platform/pricing/)):

| Provider | Free tier | Card | Notable open-weight models | Vision? | Embeddings? | Notes |
|---|---|---|---|---|---|---|
| **Cloudflare Workers AI** | **10,000 neurons/day**, resets 00:00 UTC | No | llama-3.2-1b/3b, llama-4-scout, gemma-3-12b, qwen3-30b-a3b, glm-4.7-flash, granite-4.0-h-micro | ✅ `@cf/meta/llama-3.2-11b-vision-instruct`, **`@cf/moondream/moondream3.1-9B-A2B`** | ✅ `@cf/qwen/qwen3-embedding-0.6b`, `@cf/baai/bge-m3` (1075 neurons/M) | **Also hosts `@cf/ai4bharat/indictrans2-en-indic-1B`** — Nepali translation as a service. Best single fit for this project. |
| **Groq** | 30 RPM, 1,000 req/day | No | Llama 3.3 70B, Mixtral (~320 tok/s) | Limited | — | No data-training. Fastest, good emergency demo path. |
| **Cerebras** | 30 RPM, ~1M tok/day | No | Llama 3.3 70B | — | — | No data-training. Best batch volume. |
| **OpenRouter** | 20 RPM, **only 50 req/day** (1,000/day after a $10 top-up) | No | 20+ `:free` open-weight models (Llama/Qwen/gpt-oss) | Some | — | No data-training. **50/day is too tight to rely on.** |
| **Mistral** | ~1B tok/month | No | Mistral Small/Large, Codestral | Pixtral | Mistral embed | ⚠️ **Requires data-training opt-in.** |
| **GitHub Models** | 15 RPM, 150–1,000/day | No | Llama, Phi | — | — | ⚠️ Also serves **GPT-4o / Claude 3.5 Sonnet — using those would violate the rules.** High judge-visibility risk. |
| **HuggingFace Inference Providers** | Community / rate-limited | No | 100k+ OSS models via Together/Cerebras/SambaNova/Novita | Some | Some | Successor to the old free Inference API; quota varies by backing provider. |
| **NVIDIA NIM** · **Chutes** | ~1,000/day · community | No | Nemotron, Llama · various OSS | — | — | Lower confidence; verify before relying. |
| Trial credits (Fireworks $1, Nebius $1, SambaNova $5, Baseten $30, DeepSeek 10M tok) | Expiring | Varies | — | — | — | **Evaluation only — never demo-critical.** |

**Demo risk — my recommendation: use hosted inference as a disclosed FALLBACK, never the primary path.** The rules explicitly allow it, so it is not a *rule* violation. But it carries three real risks a judge can *see*: (1) a third-party network dependency in the demo path looks like a paid-API shortcut even when it isn't; (2) free tiers have no SLA and rate-limit without warning — a mid-demo 429 is fatal; (3) **Demo Day is in-person at Leapfrog's Kathmandu office** on an unknown network — if the venue wifi blocks or throttles, a network-dependent demo dies. Design so the **entire critical path runs offline** and hosted inference only *upgrades* quality. If you use it, disclose it in the README exactly as the rules demand: name the model, the provider, and the line of code where its output is consumed.

## 7. NEPALI TEXT-TO-SPEECH

**Verified negatively and positively:**

- ❌ **Meta MMS-TTS has NO Nepali.** `facebook/mms-tts-npi` → **HTTP 401 (does not exist)**; likewise `mms-tts-nep` and `mms-tts-ne_NP`. The only near-match, `facebook/mms-tts-npl`, is "**Nahuatl, Southeastern Puebla**" — a Mexican language, **not** Nepali. (MMS-TTS is also **CC-BY-NC-4.0**, non-commercial.) **The brief's hypothesis is wrong; do not plan on MMS for Nepali.**
- ✅ **Piper HAS Nepali, and I verified it end-to-end on this CPU.** Voices under [`rhasspy/piper-voices`](https://huggingface.co/rhasspy/piper-voices) `ne/ne_NP/`, repo licence **MIT**:

| Voice | File | Size |
|---|---|---|
| **chitwan (medium)** — recommended | `ne/ne_NP/chitwan/medium/ne_NP-chitwan-medium.onnx` | **63.0 MB** |
| google (medium) | `ne/ne_NP/google/medium/ne_NP-google-medium.onnx` | 76.8 MB |
| google (x_low) — smallest | `ne/ne_NP/google/x_low/ne_NP-google-x_low.onnx` | 27.7 MB |

**Measured:** `piper-tts` 1.8.0, Chitwan voice, `-t` default. Synthesised a realistic 4-sentence Nepali advisory →
**1.24–1.44 s wall to produce 9.53 s of 22,050 Hz audio (RTF ≈ 0.14, including model load).** Output was valid WAV. **This is comfortably real-time and the single most solid Nepali component in the whole stack.**

Other Nepali TTS exists but is **immature** — treat as experimental only: [`mlwiseyak/omnivoice-nepali-tts-v2`](https://huggingface.co/mlwiseyak/omnivoice-nepali-tts-v2) (Apache-2.0, 65 dl), [`mradermacher/qwen-nepali-tts-v1-GGUF`](https://huggingface.co/mradermacher/qwen-nepali-tts-v1-GGUF) (Apache-2.0, 178 dl), `multilingual-tts/VITS-OpenBible-Nepali` (CC-BY-SA-4.0, 29 dl), `himalaya-ai/indic-parler-tts-nepali-finetuned-*` (licence unstated). All are double-digit downloads with no evaluation.

- **PRIMARY:** **Piper + `ne_NP-chitwan-medium.onnx` (63 MB, MIT)** — verified working, real-time, permissive.
- **FALLBACK:** Piper `ne_NP-google-x_low.onnx` (27.7 MB) if disk/RAM is tight; or **espeak-ng** (GPL) as a robotic last resort. **Do not use MMS-TTS** — no Nepali.

---
## FINAL RECOMMENDED STACK

| Slot | PRIMARY | Size | RAM | License | CPU latency (measured, 6 threads) | Why |
|---|---|---|---|---|---|---|
| 1. Change detection | **DINOv2-S/14 int8** (`Xenova/dinov2-small`) | 24.5 MB | ~0.3 GB | **Apache-2.0** | **30.4 ms**/224px (~33 img/s) | Best licence/size/quality balance; strong dense features |
| | *fallback*: CLIP ViT-B/32 int8 | 89 MB | ~0.4 GB | MIT | **17.0 ms** (~59 img/s) | ~2× faster, coarser |
| 1b. Decision head | **LightGBM / logistic regression** on embeddings + SSIM + index deltas | <5 MB | ~0.2 GB | BSD/MIT | trains in seconds | Beats fine-tuning at this data scale; auditable |
| 2. Segmentation | **SAM 2.1 hiera-tiny**, *prompted* | ~150 MB | ~0.5 GB | **Apache-2.0** | sub-second per prompt | Cheap when prompted, not AMG |
| | *fallback*: MobileSAM ONNX | 44 MB | ~0.3 GB | Apache-2.0 | sub-second | Lightest promptable option |
| 3. VLM | **SmolVLM-256M-Instruct Q8_0** | **279 MB** | ~0.6 GB | **Apache-2.0** | **3.2 s / image pair** | Verified correct on a real before/after pair |
| | *fallback*: InternVL3-2B Q4_K_M | 1.45 GB | ~1.9 GB | Apache-2.0 | **50.3 s** — batch only | Much better prose, too slow to be live |
| 4. Text LLM | **Qwen3-4B-Instruct-2507 Q4_K_M** | ~2.5 GB | ~3 GB | **Apache-2.0** | ~10–15 tok/s | Best Apache-2.0 small model |
| | *fallback (verified)*: **Qwen2.5-1.5B-Instruct Q4_K_M** | 1117 MB | ~1.4 GB | **Apache-2.0** | **6.1 s / 88 tok**; **5/5** schema-valid | Proven end-to-end on this machine |
| 4b. Constrained decode | `llama-server` `response_format: json_schema` | — | — | MIT | same | **5/5 valid vs 0/3 unconstrained**; inline schemas (no `$ref`) |
| 5. Nepali text | **Deterministic Nepali template + slots**, LLM fills JSON | — | — | yours | instant | Zero Nepali-generation risk |
| | *fallback*: **IndicTrans2** en→indic | ~1B / 200M | ~1.5 GB | **MIT** | seconds | Verified MIT (NLLB is non-commercial) |
| 6. Hosted (optional) | **Cloudflare Workers AI** (10k neurons/day) | — | — | — | network | Only provider with open-weight LLM + **vision + embeddings + IndicTrans2** in one free tier |
| 7. Nepali TTS | **Piper `ne_NP-chitwan-medium.onnx`** | **63 MB** | ~0.2 GB | **MIT** | **1.3 s for 9.5 s audio** | Verified real-time on CPU |
| | *fallback*: Piper `ne_NP-google-x_low.onnx` | 27.7 MB | ~0.1 GB | MIT | faster | Smaller |

**Peak concurrent RAM (primary path):** DINOv2 (~0.3) + SAM2 (~0.5) + SmolVLM (~0.6) + Qwen 1.5B (~1.4) + Piper (~0.2) ≈ **3.0 GB** — right at the limit. **Load models sequentially / lazily and free them between stages**; do not hold all five resident. With the Qwen3-4B primary, you exceed 3 GB and must swap stages.

**Total disk: ≈ 1.7 GB** for the whole primary stack.

---
## TOP 3 RISKS + MITIGATIONS

**1. RAM pressure (only ~3 GB free; 11 GB already used by the desktop).**
- Make **Qwen2.5-1.5B (1.1 GB)** the shipped default, not Qwen3-4B; keep 4B as an opt-in flag.
- **Load one model at a time** and `del`/unload between stages; never hold embedding + SAM + VLM + LLM together.
- Rely on llama.cpp **mmap** (verified: a 1.1 GB model loaded with 1.1 GB "free" because page cache is reclaimable) — but never exceed ~60% of free RAM for weights, because KV cache and the vision encoder are *not* mmappable.
- **Pre-compute embeddings offline** into a cache; the live demo should never re-embed the full tile set. This alone removes the largest RAM/time spike.
- Add a startup guard: check `psutil.virtual_memory().available` and print the chosen tier ("lite/full") so a failure is legible rather than a crash.

**2. Latency during a live demo.**
- **Pass `-t 6`, never `-t 12`** — measured 15–17 tok/s vs 1.0–3.5 tok/s, a 5–15× difference. This is the single highest-leverage line of code in the project.
- **Pre-record the heavy path.** InternVL3-2B's 50 s belongs in a cached video, not a live click.
- Bound latency explicitly: small VLM for live use (3.2 s), big VLM for batch; cap `max_tokens`; cache the demo inputs (same two tiles every run) so the demo is deterministic.
- **Assume the venue network is unreliable** — run the whole critical path offline, with the hosted provider as an optional, disclosed upgrade.
- Keep a pre-rendered "known-good" run as a fallback video if the machine is under load (load avg was 21 during my measurements — this is a real, observed condition).

**3. JSON reliability.**
- **Always** use `response_format: json_schema` (measured **5/5 valid** vs **0/3 unconstrained**), and **inline the schema — `$ref`/`$defs` silently fails** in llama.cpp ([issue #21228](https://github.com/ggml-org/llama.cpp/issues/21228)).
- **Grammar guarantees syntax, not truth.** I observed *"the slope has increased by 31 degrees"* from valid JSON. **Never let the LLM emit a measured number.** Compute all metrics in code and either (a) pass them as fixed slots the model may only echo, or (b) overwrite the model's numbers after parsing.
- Validate with a real `jsonschema` check + range asserts (e.g. `0 ≤ changed_pct ≤ 100`); on failure, **fall back to a deterministic template**, not a retry loop.
- Keep the schema flat and small — nesting and long enums inflate the GBNF grammar and risk the rule-count limit.
- Add a 2–3 example regression set (golden JSON) run in CI so a model/quant change cannot silently break the contract.

---
## COULD NOT VERIFY / OPEN ITEMS
1. **Whether the RTX 4050 can be revived.** It is present (`AD107M`) but has no kernel module. ~30 min of investigation could replace this entire CPU-only premise. **Highest-value unresolved item.**
2. **No credible open landslide-segmentation checkpoint found** — only near-zero-download undocumented repos. Landslide/scar segmentation would need your own labels.
3. **Nepali generation quality of Qwen3/Gemma on Nepali** — no published Nepali-specific eval for these families. The Arkios result at 1B is the only hard number I found, and it is near chance.
4. **The Nepali fine-tunes' quality** (mradermacher/NEPALI-LLM-INSTRUCT/vhab10) is unassessed; download counts (14–629) are far too low to trust.
5. **Exact HuggingFace Inference Providers free quota** — the free-credit structure has changed repeatedly; verify on the day.
6. **Groq/Cerebras/Nebius current vision-model line-ups** — vision availability on these free tiers was not confirmed.
7. **SigLIP2/CLIP 518×518 latency** — not measurable with these exports (position embeddings are baked to 224; 518 throws). 512×512 behaviour is a **tiling** question, not a single-forward-pass one.
8. **Absolute tok/s on an idle machine** — every number here was taken under load average ~21. On an idle laptop expect **materially better** throughput; treat my figures as a conservative floor, which is the right direction for demo planning.
9. **`nvidia/segformer` licence terms** — tagged `other`, LICENSE file 404s. Resolve before shipping.
