"""Nepali advisory rendering.

The model never free-writes facts. It fills a fixed structure, and the
structure is rendered here - so the output is always parseable, always fluent,
and can never invent a location, an authority or a date.
"""
from __future__ import annotations

from pahiro.routing.abstain import StalenessDecision

REFUSAL = (
    "नयाँ अवलोकन छैन — यो ढलानको पछिल्लो उपलब्ध अवलोकन {detail} अघि थियो। "
    "प्रमाण पर्याप्त नभएकोले सूचना जारी गरिएको छैन।"
)

HEADER = "पहिरो परिवर्तन सूचना"
LABELS = {
    "location": "स्थान",
    "date": "मिति",
    "changed": "के परिवर्तन भयो",
    "evidence": "प्रमाणको अवस्था",
    "why": "किन महत्त्वपूर्ण",
    "inspect": "पहिले जाँच्नुहोस्",
    "recommendation": "सिफारिस",
    "authority": "जिम्मेवार निकाय",
    "legal_basis": "कानुनी आधार",
}

SENSOR_NE = {
    "sentinel-2": "स्याटेलाइट (अप्टिकल)",
    "sentinel-1": "रडार",
    "rainfall": "वर्षा",
    "citizen-report": "नागरिक रिपोर्ट",
}


STATUS_NE = {"ok": "पर्याप्त", "degraded": "सीमित", "abstain": "अपर्याप्त"}
CONFIDENCE_NE = {"high": "उच्च", "medium": "मध्यम", "low": "न्यून", "none": "छैन"}


def evidence_state_ne(staleness: StalenessDecision) -> str:
    """Render the evidence state in Nepali - never leave English inside an advisory."""
    if not staleness.ages:
        return "यो स्थानको कुनै अवलोकन अभिलेख छैन।"
    parts = [f"{SENSOR_NE.get(s, s)} {age} दिन अघि"
             for s, age in sorted(staleness.ages.items(), key=lambda kv: kv[1])]
    status = STATUS_NE.get(staleness.status, staleness.status)
    conf = CONFIDENCE_NE.get(staleness.confidence, staleness.confidence)
    text = f"पछिल्लो अवलोकन: {', '.join(parts)}। प्रमाण {status}, विश्वास {conf}।"
    if any("unverified" in r for r in staleness.reasons):
        text += " रडारको उपयोगिता अझै नापिएको छैन।"
    return text


def refusal_text(staleness: StalenessDecision) -> str:
    if staleness.ages:
        newest_sensor, days = min(staleness.ages.items(), key=lambda kv: kv[1])
        detail = f"{SENSOR_NE.get(newest_sensor, newest_sensor)}को {days} दिन"
    else:
        detail = "कुनै अभिलेख"
    return REFUSAL.format(detail=detail)


def render(
    *,
    location: str,
    as_of: str,
    what_changed: str,
    evidence_state: str,
    why_it_matters: str,
    inspect_first: list[str],
    recommendation: str | None = None,
    authority_institution: str | None = None,
    authority_office: str | None = None,
    legal_basis: str | None = None,
    needs_review: bool = False,
) -> str:
    """Render the advisory. Institutions appear only when cited."""
    lines = [HEADER, ""]
    lines.append(f"{LABELS['location']}: {location}")
    lines.append(f"{LABELS['date']}: {as_of}")
    lines.append("")
    lines.append(f"{LABELS['changed']}: {what_changed}")
    lines.append(f"{LABELS['evidence']}: {evidence_state}")
    lines.append(f"{LABELS['why']}: {why_it_matters}")
    if inspect_first:
        lines.append(f"{LABELS['inspect']}: " + "; ".join(inspect_first))
    if recommendation:
        lines.append(f"{LABELS['recommendation']}: {recommendation}")
    if authority_institution and legal_basis:
        office = f" ({authority_office})" if authority_office else ""
        lines.append(f"{LABELS['authority']}: {authority_institution}{office}")
        lines.append(f"{LABELS['legal_basis']}: {legal_basis}")
    elif needs_review:
        lines.append(
            f"{LABELS['authority']}: यकिन गर्न बाँकी — जिम्मेवार निकायको आधार "
            "प्रमाणित भएपछि मात्र पठाइनेछ।"
        )
    return "\n".join(lines)
