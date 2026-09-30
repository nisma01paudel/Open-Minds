"""The dispatch object: the artefact the whole product exists to produce.

A finding is not an instruction. This object is the instruction - and it is
self-validating, so an advisory that cannot cite an authority cannot be issued.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone

from pahiro.ontology import AuthorityRule
from pahiro.routing.abstain import StalenessDecision

HIGH, MEDIUM, LOW = "high", "medium", "low"


@dataclass
class Provenance:
    """Everything needed to audit a claim back to its evidence."""
    scenes: list[str] = field(default_factory=list)
    sensors: list[str] = field(default_factory=list)
    ontology_version: str = "0.0.0"
    model: str | None = None
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


@dataclass
class DispatchObject:
    location: str
    as_of: date
    status: str                      # ok | degraded | abstain
    confidence: str                  # high | medium | low | none
    evidence_state: str              # human-readable staleness banner
    priority: str | None = None      # high | medium | low | None when abstaining
    authority: dict | None = None    # institution/office/legal_basis/escalation/source
    findings: list[str] = field(default_factory=list)
    inspect_first: list[str] = field(default_factory=list)
    recommendation: str | None = None
    advisory_ne: str | None = None   # Nepali advisory, the user-facing output
    needs_review: bool = False       # set when routing could not be justified
    provenance: Provenance = field(default_factory=Provenance)

    # --- invariants -------------------------------------------------------
    def validate(self) -> list[str]:
        """Return the list of reasons this dispatch may NOT be issued."""
        problems: list[str] = []

        if self.status not in ("ok", "degraded", "abstain"):
            problems.append(f"unknown status {self.status!r}")
        if self.confidence not in ("high", "medium", "low", "none"):
            problems.append(f"unknown confidence {self.confidence!r}")

        if self.status == "abstain":
            if self.advisory_ne and "छैन" not in self.advisory_ne:
                problems.append("abstaining dispatch must carry a refusal advisory")
            if self.priority is not None:
                problems.append("abstaining dispatch must not carry a priority")
            return problems

        # A dispatch that may be issued has hard requirements.
        if not self.advisory_ne:
            problems.append("non-abstaining dispatch requires an advisory")
        if self.priority not in (HIGH, MEDIUM, LOW):
            problems.append("non-abstaining dispatch requires a valid priority")
        if not self.provenance.scenes:
            problems.append("non-abstaining dispatch requires at least one source scene")

        if self.authority is None:
            if not self.needs_review:
                problems.append(
                    "no authority: either supply a citable rule or set needs_review"
                )
        else:
            for key in ("institution", "office", "legal_basis", "source"):
                if not self.authority.get(key):
                    problems.append(f"authority missing {key!r} (never invent a mandate)")
        return problems

    def to_json(self) -> str:
        d = asdict(self)
        d["as_of"] = self.as_of.isoformat()
        return json.dumps(d, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "DispatchObject":
        d = json.loads(text)
        d["as_of"] = date.fromisoformat(d["as_of"])
        d["provenance"] = Provenance(**d.get("provenance", {}))
        return cls(**d)


def authority_from_rule(rule: AuthorityRule) -> dict:
    """Turn a citable ontology rule into the authority block of a dispatch."""
    if not rule.citable:
        raise ValueError(f"rule {rule.case_id} is not citable (no legal basis or source)")
    return {
        "institution": rule.institution,
        "office": rule.office,
        "legal_basis": rule.legal_basis,
        "escalation": list(rule.escalation),
        "source": rule.source_url,
        "case_id": rule.case_id,
        "confidence": rule.confidence,
    }


def build_dispatch(
    *,
    location: str,
    as_of: date,
    staleness: StalenessDecision,
    advisory_ne: str,
    findings: list[str] | None = None,
    inspect_first: list[str] | None = None,
    recommendation: str | None = None,
    priority: str | None = None,
    rule: AuthorityRule | None = None,
    scenes: list[str] | None = None,
    sensors: list[str] | None = None,
    ontology_version: str = "0.0.0",
    model: str | None = None,
) -> DispatchObject:
    """Assemble a dispatch, defaulting to a safe refusal when evidence is stale."""
    if not staleness.may_issue:
        return DispatchObject(
            location=location, as_of=as_of, status="abstain",
            confidence="none", evidence_state=staleness.banner(),
            advisory_ne=advisory_ne,
            provenance=Provenance(scenes=scenes or [], sensors=sensors or [],
                                  ontology_version=ontology_version, model=model),
        )

    authority = authority_from_rule(rule) if rule is not None else None
    return DispatchObject(
        location=location, as_of=as_of, status=staleness.status,
        confidence=staleness.confidence, evidence_state=staleness.banner(),
        priority=priority, authority=authority,
        findings=findings or [], inspect_first=inspect_first or [],
        recommendation=recommendation, advisory_ne=advisory_ne,
        needs_review=authority is None,
        provenance=Provenance(scenes=scenes or [], sensors=sensors or [],
                              ontology_version=ontology_version, model=model),
    )
