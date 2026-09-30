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


# The monsoon case: rain has primed the slope but nothing can see it. This is the
# most honest and most useful thing the product can say in July.
PRIMED_UNOBSERVED = (
    "पहिरो जोखिम सूचना — वर्षाका कारण ढलान संवेदनशील बनेको छ, तर पछिल्लो अवलोकन उपलब्ध छैन। "
    "स्याटेलाइटले यो ढलान हेर्न सकेको छैन, त्यसैले परिवर्तनको पुष्टि गर्न सकिँदैन।"
)

LABELS_PRIMED = {
    "rain": "वर्षाको अवस्था",
    "why": "किन महत्त्वपूर्ण",
    "inspect": "पहिले जाँच्नुहोस्",
    "authority": "जिम्मेवार निकाय",
    "legal_basis": "कानुनी आधार",
}


def primed_unobserved_text(
    *,
    location: str,
    as_of: str,
    rainfall_state: str,
    inspect_first: list[str],
    authority_institution: str | None = None,
    authority_office: str | None = None,
    legal_basis: str | None = None,
    needs_review: bool = False,
) -> str:
    """Advisory for: the rainfall trigger is up, but ground evidence is not available.

    Saying this out loud is the point. In July an optical system has nothing to show,
    and silence is indistinguishable from safety. Rain says the slope is primed; we
    say we cannot see it; a human decides.
    """
    lines = [PRIMED_UNOBSERVED, "", f"{LABELS['location']}: {location}",
             f"{LABELS['date']}: {as_of}", "",
             f"{LABELS_PRIMED['rain']}: {rainfall_state}"]
    lines.append(f"{LABELS_PRIMED['why']}: यो अवस्थामा ढलान अस्थिर हुन सक्छ, तर हामीसँग "
                 "पछिल्लो उपग्रह प्रमाण छैन — त्यसैले यो सूचना जोखिमको संकेत हो, पुष्टि होइन।")
    if inspect_first:
        lines.append(f"{LABELS_PRIMED['inspect']}: " + "; ".join(inspect_first))
    if authority_institution and legal_basis:
        office = f" ({authority_office})" if authority_office else ""
        lines.append(f"{LABELS_PRIMED['authority']}: {authority_institution}{office}")
        lines.append(f"{LABELS_PRIMED['legal_basis']}: {legal_basis}")
    elif needs_review:
        lines.append(f"{LABELS_PRIMED['authority']}: यकिन गर्न बाँकी — प्रमाणित भएपछि मात्र पठाइनेछ।")
    return "\n".join(lines)


TRIGGER_STATE_NE = {
    "below": "थ्रेसहोल्डभन्दा तल",
    "approaching": "थ्रेसहोल्ड नजिक",
    "exceeded": "थ्रेसहोल्ड नाघ्यो",
}


def rainfall_state_ne(assessment) -> str:
    """Render the rainfall trigger in Nepali.

    The same defect class as the evidence line: an advisory that drops into English
    at its most important sentence is not a Nepali advisory. The threshold name is
    rendered in Nepali too, not transliterated from the English label.
    """
    if assessment is None:
        return "वर्षाको तथ्याङ्क उपलब्ध छैन।"
    state = TRIGGER_STATE_NE.get(assessment.state, assessment.state)
    name = getattr(assessment.threshold, "name_ne", None) or assessment.threshold.name
    parts = [f"{w.duration_hours} घण्टामा {w.accumulation_mm:.0f}/{w.threshold_mm:.0f} मिमि"
             for w in assessment.windows]
    return f"{state} ({name})" + (" — " + ", ".join(parts) if parts else "")
