# Scope freeze — Frogtoberfest 2026

Locked in Week 1 (Oct 1–7). Changes after this require a written reason.

## In scope
- 3 pilot areas: Dhading slope corridor; Sindhupalchok / Melamchi corridor; one strategic-highway corridor.
- Time series 2019–2025, cached locally.
- Mandate ontology (asset × location × hazard) → institution + escalation, **with citations**.
- AI layers: routing (RAG), Nepali advisory (constrained generation), staleness abstain gate,
  citizen-report classification.
- Dispatch object (schema-validated JSON) → ranked queue, work order, alerts, provenance.
- Dashboard: map + change timeline + queue + advisory + staleness banner.
- Evaluation harness: routing accuracy, expert-rated Nepali advisory quality, data-gap calibration, ablation.
- Documentation, demo video, AI-usage disclosure.

## Out of scope (documented as future work)
Training new detection models · drones · IoT sensors · InSAR coherence processing · prospective validation ·
national coverage · carrier SMS gateway · mobile app · live integration with BIPAD/DoR systems (we specify
the interface, we do not build the integration).

## Cut list, in order, if the clock bites
1. Next.js frontend → Streamlit.
2. Vision classifier for citizen reports → text-only classification.
3. Nepali TTS → text-only advisories.
4. Three pilot areas → one hero area plus matched controls.
5. Ontology scope → road assets only (strongest case), other asset classes marked partial.
