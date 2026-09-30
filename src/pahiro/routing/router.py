"""The decision layer: which institution must act, and why.

Architecture, and the reason for it. Asked to name the responsible authority from
its own knowledge, an open-weight model invented Indian institutions for a Nepali
road ("National Highway Authority of India", "Ministry of Housing and Urban
Affairs"). That raw response is kept in evidence/hallucination-ungrounded.json.

So the model is never asked what it knows. It is asked to **choose among rules
retrieved from a cited ontology**, and a JSON-schema `enum` restricts its answer to
the identifiers of those retrieved rules. The institution, office and legal basis
are then read from the ontology record - never from the model. If the model's
choice is invalid, missing, or numbers a measurement, we fall back to a
deterministic decision and say so.

This is the split that makes the AI load-bearing without making it a liability:
deterministic code owns retrieval, geometry, thresholds and every number; the model
owns the judgement of which cited duty applies.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field

from pahiro.ontology import (ANY, EMERGENCY, MAINTENANCE, AuthorityRule, Ontology)

HIGH, MEDIUM, LOW = "high", "medium", "low"
DIGITS = re.compile(r"\d")


@dataclass
class RoutingDecision:
    case_id: str | None
    priority: str
    institution: str | None
    office: str | None
    legal_basis: str | None
    escalation: list[str] = field(default_factory=list)
    confidence: str = "none"
    rationale: str = ""
    candidates: list[str] = field(default_factory=list)
    used_model: bool = False
    fallback_used: bool = False
    numeric_claim_withheld: bool = False
    notes: list[str] = field(default_factory=list)

    def describe(self) -> str:
        who = self.institution or "unresolved"
        src = "model-selected from cited rules" if self.used_model else "deterministic fallback"
        return f"{who} [{self.confidence}] via {src}"


class RuleRetriever:
    """Deterministic retrieval. No model, no network, fully reproducible."""

    def retrieve(self, ontology: Ontology, asset_type: str, role: str = MAINTENANCE,
                 jurisdiction: str | None = None,
                 hazard_type: str | None = None, k: int = 4) -> list[AuthorityRule]:
        scored: list[tuple[int, AuthorityRule]] = []
        for r in ontology.rules:
            if not r.citable or r.role != role:
                continue
            score = 0
            if r.asset_type == asset_type:
                score += 8
            elif r.asset_type == ANY:
                score += 2
            else:
                continue
            if jurisdiction and r.jurisdiction == jurisdiction:
                score += 4
            if hazard_type and r.hazard_type == hazard_type:
                score += 3
            scored.append((score, r))
        scored.sort(key=lambda t: (-t[0], t[1].case_id))
        return [r for _, r in scored[:k]]


class LlamaServerBackend:
    """Open-weight model over llama-server's OpenAI-compatible endpoint.

    Always call with threads=6. Measured on this machine, generation collapses
    from ~16 tok/s at 6 threads to 1-3.5 tok/s at 12 (6 physical cores; SMT
    oversubscription).
    """

    def __init__(self, url: str = "http://127.0.0.1:8081", timeout: int = 240):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/health", timeout=5) as r:
                return json.load(r).get("status") == "ok"
        except Exception:
            return False

    def decide(self, prompt: str, schema: dict) -> dict:
        body = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 400,
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "routing", "schema": schema}},
        }
        req = urllib.request.Request(
            f"{self.url}/v1/chat/completions", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.load(resp)
        return json.loads(payload["choices"][0]["message"]["content"])


def build_schema(candidates: list[AuthorityRule]) -> dict:
    """Constrain the answer to the retrieved identifiers. Inlined - never $ref."""
    return {
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "enum": [c.case_id for c in candidates]},
            "priority": {"type": "string", "enum": [HIGH, MEDIUM, LOW]},
            "rationale": {"type": "string"},
        },
        "required": ["case_id", "priority", "rationale"],
        "additionalProperties": False,
    }


def build_prompt(asset_type: str, role: str, hazard_type: str, jurisdiction: str | None,
                 candidates: list[AuthorityRule], evidence_state: str) -> str:
    lines = [
        "You are routing a slope-hazard report in Nepal to the office legally responsible.",
        "Choose exactly ONE case_id from the options below. Do not invent any other.",
        "Every option carries its governing legal provision. You may not add an institution.",
        "",
        f"Asset: {asset_type}   Role: {role}   Hazard: {hazard_type}"
        + (f"   Jurisdiction: {jurisdiction}" if jurisdiction else ""),
        f"Evidence state: {evidence_state}",
        "",
        "OPTIONS:",
    ]
    for c in candidates:
        lines.append(f"- case_id: {c.case_id}")
        lines.append(f"  institution: {c.institution}")
        lines.append(f"  office: {c.office}")
        lines.append(f"  legal basis: {c.legal_basis}")
        if c.notes:
            lines.append(f"  note: {c.notes}")
    lines += ["", "Return JSON with case_id, priority (high/medium/low) and a short rationale.",
              "Do not state any number - measurements are computed elsewhere."]
    return "\n".join(lines)


class Router:
    def __init__(self, backend: LlamaServerBackend | None = None, threshold: float = 0.30):
        self.retriever = RuleRetriever()
        self.backend = backend
        self.threshold = threshold

    def route(self, ontology: Ontology, asset_type: str, role: str = MAINTENANCE,
              jurisdiction: str | None = None, hazard_type: str = "slope-instability",
              evidence_state: str = "", evidence_quality: float = 1.0,
              allow_model: bool = True) -> RoutingDecision:
        candidates = self.retriever.retrieve(ontology, asset_type, role, jurisdiction, hazard_type)
        ids = [c.case_id for c in candidates]

        decision: RoutingDecision | None = None
        if allow_model and self.backend is not None and candidates:
            try:
                if self.backend.available():
                    raw = self.backend.decide(
                        build_prompt(asset_type, role, hazard_type, jurisdiction, candidates,
                                     evidence_state),
                        build_schema(candidates))
                    decision = self._from_model(raw, candidates, ids)
            except Exception as exc:
                decision = None
                self._last_error = f"{type(exc).__name__}: {exc}"

        if decision is None:
            decision = self._deterministic(candidates, evidence_quality)
        decision.candidates = ids
        return decision

    # -- model path ---------------------------------------------------------
    def _from_model(self, raw: dict, candidates: list[AuthorityRule],
                    ids: list[str]) -> RoutingDecision | None:
        case_id = raw.get("case_id")
        if case_id not in ids:
            return None                       # invalid choice -> caller falls back
        rule = next(c for c in candidates if c.case_id == case_id)
        priority = raw.get("priority") if raw.get("priority") in (HIGH, MEDIUM, LOW) else MEDIUM
        rationale = str(raw.get("rationale") or "").strip()

        withheld = bool(DIGITS.search(rationale))
        if withheld:
            # Enforce the rule that the model never states a measurement.
            rationale = ("model rationale withheld: it contained a numeric claim "
                         "(measurements are computed in code, never by the model)")

        return RoutingDecision(
            case_id=rule.case_id, priority=priority, institution=rule.institution,
            office=rule.office, legal_basis=rule.legal_basis, escalation=list(rule.escalation),
            confidence=rule.confidence, rationale=rationale, used_model=True,
            numeric_claim_withheld=withheld,
            notes=[n for n in (rule.notes, rule.legal_gap) if n],
        )

    # -- deterministic path -------------------------------------------------
    def _deterministic(self, candidates: list[AuthorityRule],
                       evidence_quality: float) -> RoutingDecision:
        if len(candidates) != 1:
            return RoutingDecision(
                case_id=None, priority=MEDIUM, institution=None, office=None, legal_basis=None,
                confidence="none", fallback_used=True,
                rationale=("no unique citable rule matched; routing withheld for human review"),
                notes=["ambiguity is treated as failure, not as a guess"],
            )
        rule = candidates[0]
        priority = HIGH if evidence_quality >= 0.6 else (MEDIUM if evidence_quality >= 0.3 else LOW)
        return RoutingDecision(
            case_id=rule.case_id, priority=priority, institution=rule.institution,
            office=rule.office, legal_basis=rule.legal_basis, escalation=list(rule.escalation),
            confidence=rule.confidence, fallback_used=True,
            rationale="deterministic selection: exactly one citable rule matched",
            notes=[n for n in (rule.notes, rule.legal_gap) if n],
        )

    def route_emergency(self, ontology: Ontology, asset_type: str,
                        jurisdiction: str | None = None) -> RoutingDecision:
        return self.route(ontology, asset_type, role=EMERGENCY, jurisdiction=jurisdiction,
                          hazard_type="road-blockage")
