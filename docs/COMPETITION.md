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
