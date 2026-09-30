# The field we are competing against (verified intelligence)

Researched 2026-09-30. Sources cited inline. This file exists so we make decisions on evidence,
not on how good our own idea feels.

## 1. This is the first year of the format

Frogtoberfest ran 2019–2024 as a **Hacktoberfest-style PR-count challenge** with a public leaderboard
(`frogtoberfest-leaderboard.lftechnology.com`, weighted score of PRs opened/reviewed/issues/comments).
2024 rules: 8 PRs in October, ≥5 outside your own repos, top 20 got SWAG. **No cash grand prize, no jury,
no product.**

2025 has no trace of running (repo dormant 2024-11-04 → 2026-09-16, no Wayback captures, leaderboard
never regenerated). **2026 is a 2026-only reboot** into a product challenge — confirmed by the site's own
copy: *"For years, Frogtoberfest was about making contributions. This year, it's about creating something
of your own."*

**Consequence:** there is no previous winner's playbook to copy. Nobody has won this format before.

## 2. The prize is undisclosed

The site names only "**Best AI Project — Grand Prize**". No amount, no sponsor, no details published
anywhere. Second tier: Top 5 Teams get to demo. Third: all eligible participants get a digital certificate.

**Consequence:** we cannot optimise for a prize we can't see. We optimise for the published criteria and
for Leapfrog's demonstrated taste (§4).

## 3. The real field (partially enumerated)

Registration required submitting a **public GitHub repo**, so entries are discoverable. GitHub-wide search
returns ~18 repos matching "frogtoberfest" — all participant projects or the event site. **There is no
2026 leaderboard and no submission tracker**; tracking is by observing the repos.

Confirmed 2026 entries seen so far:

| Repo | Domain | AI | Note |
|---|---|---|---|
| [krishi-sahayak](https://github.com/Nirvik-49/krishi-sahayak) | agriculture decision support | Llama 3.3 / Qwen 2.5 | smallholder farmers |
| [Shikshak-sahayog](https://github.com/AayushGyawali-tech/Shikshak-sahayog) | handwritten exam grading | Ollama + Llama 3.2 vision | Nepali schools |
| [karmi](https://github.com/amgainprabesh/karmi) | Nepali housing design→build | — | "design-to-built-reality compiler" |
| [bca-buddy](https://github.com/Narankhadka/bca-buddy) | study companion | — | education |
| [Syncra](https://github.com/nikajr10/Syncra) | — | — | |
| [mockina](https://github.com/O-OzwalBK/mockina) | — | — | |
| [Mohar_FrogtoberFest](https://github.com/aayushmak/Mohar_FrogtoberFest) | — | — | |

**Domains already taken: agriculture, education/grading, housing, study tooling.**
**Our lane — disaster risk and infrastructure dispatch — is not among them.**

## 4. What Leapfrog actually celebrates

Their other events do publish named winners, and the pattern is consistent:

- **Hackathon 2026 "From Insight to Action"** (agentic AI): winner **Project Aegis** — *incident management*;
  runner-up **ALICE** (Jira→PR agent); *Agents the Edge* — **Agent M2E**.
- **Hackathon 2025** ("AI Ignite with AWS"): winner **φolice** — PHI detection (health-data privacy).
- **Open Source DevOps Challenge 2025**: winner **Terraform Analyzer**, runner-up **Finleap**.

Read across: **agentic AI, incident/response management, production-readiness, security and compliance,
developer tooling, and civic/health impact.** They reward systems that *act*, and they reward problems with
institutional weight.

**Consequence:** a dispatch/incident-response system for a public-safety problem sits squarely inside
Leapfrog's demonstrated taste. That is a tailwind, and it should shape the framing: this is an
**incident-management system for slopes**, not a mapping tool.

## 5. The eligibility gate is where entries die

Every submission must clear: public repo · README (architecture, tech, **limitations**) · working demo ·
demo video · qualifies as "Build with AI" · **AI Usage Disclosure naming the exact file/function where AI
output is consumed programmatically**.

"Strong entry" guidance adds: open-weight AI used as an important part; a clear problem; substantial
technical work; **source, licence, model and dependencies easy to verify**; working demo + clear
explanation.

**Consequence:** treat documentation and the disclosure as *gate items*, written as we build, not at the
end.

## 6. Our differentiation, stated plainly

Detection, susceptibility mapping and even LLM-written landslide reports are published (see
`PRIOR-ART.md`). What is absent across the entire field is the **last metre**: a finding converted into a
named authority, a cited mandate, a Nepali advisory, an inspection priority, and an honest statement of
when we cannot see at all.

We are the only entry in the field addressing disaster risk, and the only one addressing the
reporting-to-action gap that every published system stops short of.

---

# Addendum — confirmed field intelligence (2026-09-30)

Verified by screening ~6,000 repos and full-text grepping ~60 candidate clones for
`frogtoberfest|leapfrog|lftechnology`.

## The field is 14 confirmed entries, and 11 of them are empty

| Substance | Count |
|---|---|
| 100% empty repo (registration placeholder) | 5 |
| README only, no code | 6 |
| Real files, still no working pipeline | 3 |
| Working end-to-end demo | **0** |

Domains taken: education (2), construction/AEC (2), agriculture (2), plus singletons in civic/legal
safety, network tooling, document intelligence. **DRR / landslide / geospatial: EMPTY — zero confirmed
entries.** The 1,113 "landslide" repos created in Sep 2026 are **Smart India Hackathon 2026**, a
different competition; they are not our rivals.

## The entry to beat: `amgainprabesh/karmi`

A Nepali housing *naksa*-conformance compiler (MIT). Architecturally the **same pattern as ours** —
detection → diff → authority-addressed verify-list — just for buildings instead of slopes.

- Open-weight only: Qwen2.5-VL for drawings/photos, an open-weight LLM for diff reasoning and Nepali
  narration, bge-m3 embeddings.
- The only entry that quotes Leapfrog's own litmus test and states the renderer is
  *"deliberately dumb… infers nothing."*
- Ships its own AI usage file, an architecture document, a component table, a failure-mode table, a privacy
  policy, and honest "known limitations".
- Language discipline: outputs are **"items to verify"**, never "violates".
- **Weakness: one commit, no pipeline code, no dataset, no demo.** Everything AI is *planned*; the only
  running artefact is a hand-authored 2D→3D prototype containing **no AI calls**.

## The operational rubric — this is what actually scores

Beyond the four marketing criteria, the Guidelines page carries three operational criteria:

1. **Agentic Depth** — *"Real autonomy, tool use, or multi-step reasoning rather than a single prompt
   dressed up."*
2. **Demo Credibility** — *"Does it actually complete the task it claims to, end to end?"*
3. **Repo & Doc Clarity** — *"Could a stranger understand what it does in under 5 minutes?"*

Submission is **five items**: public repo · documentation (README, architecture, tech, limitations) ·
working demo · **2–3 minute pre-recorded demo video** · AI disclosure.

## The litmus test is our single biggest risk

> *"If you deleted the AI call from your codebase, would the product still do its job? If yes, it
> doesn't qualify."*

If detection is deterministic geospatial code and the LLM merely drafts a Nepali letter, **the product
still works without the AI** — and we score near zero on Agentic Depth.

**Our answer** is the split `karmi` also makes, stated explicitly: **geometry and thresholds stay
deterministic; the AI owns the decision chain** — severity triage, which authority and jurisdiction the
request must reach, composition and addressing of the request, and acknowledgement tracking. Delete the
routing step and no institution is selected, no escalation path is derived and nothing is dispatched.

## To beat `karmi`

1. **Ship a working end-to-end demo** — `karmi` has none. This is the single largest available win
   because Demo Credibility is explicitly scored.
2. Ship `AI_USAGE.md` naming the **exact file/function** where each model's output is consumed (Leapfrog
   demands this verbatim; `karmi` is the only entry that complies).
3. Cite the real instruments — DRRM Act 2074, LGOA 2074 — the way `karmi` cites Building Act 2055.
4. Keep the "items to verify" discipline: never accuse, always attach a confidence and a review path.
5. Release a **reusable open-source artefact** — our cited routing key plus the evaluation harness and
   the screened per-AOI dataset.
6. Match the documentation standard, and **remember the 2–3 minute demo video is mandatory**.
