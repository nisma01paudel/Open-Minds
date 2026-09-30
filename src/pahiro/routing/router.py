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
    asset_type: str | None = None
    role: str | None = None
    institution: str | None = None
    office: str | None = None
    legal_basis: str | None = None
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

    # -- triage from an unstructured report ---------------------------------
    def triage_route_single_call(self, ontology: Ontology, facts: str, evidence_state: str = "",
                                priority_hint: str = MEDIUM) -> RoutingDecision:
        """Turn an unstructured report into a routing decision in one constrained call.

        This is where the AI is genuinely load-bearing: without the model, a free-text
        report cannot be triaged into an asset and a duty at all, so nothing can be
        routed and nothing is dispatched. The model's answer is still locked to the
        cited case identifiers, and the institution is read from the ontology.
        """
        candidates = [r for r in ontology.rules if r.citable]
        ids = [c.case_id for c in candidates]
        if not candidates:
            return RoutingDecision(case_id=None, priority=priority_hint, confidence="none",
                                   fallback_used=True,
                                   rationale="no citable rules loaded; nothing can be routed")

        if self.backend is None or not self.backend.available():
            return RoutingDecision(
                case_id=None, priority=priority_hint, confidence="none", fallback_used=True,
                candidates=ids,
                rationale=("free-text triage requires the open-weight model; without it an "
                           "unstructured report cannot be resolved to an asset and a duty, "
                           "so nothing is routed"),
                notes=["the decision layer is load-bearing: remove it and the product stops"])

        try:
            raw = self.backend.decide(
                build_triage_prompt(facts, candidates, evidence_state),
                build_triage_schema(candidates))
        except Exception as exc:
            return RoutingDecision(case_id=None, priority=priority_hint, confidence="none",
                                   fallback_used=True, candidates=ids,
                                   rationale=f"model call failed ({type(exc).__name__}); routed nothing")

        case_id = raw.get("case_id")
        if case_id == "none" or case_id not in ids:
            return RoutingDecision(
                case_id=None, priority=priority_hint,
                asset_type=raw.get("asset_type"), role=raw.get("role"),
                confidence="none", used_model=True, candidates=ids,
                rationale=f"abstained: {str(raw.get('rationale') or '')[:200]}",
                notes=["the model chose to abstain rather than guess an authority"])

        rule = next(c for c in candidates if c.case_id == case_id)
        priority = raw.get("priority") if raw.get("priority") in (HIGH, MEDIUM, LOW) else priority_hint
        rationale = str(raw.get("rationale") or "").strip()
        withheld = bool(DIGITS.search(rationale))
        if withheld:
            rationale = ("model rationale withheld: it contained a numeric claim "
                         "(measurements are computed in code, never by the model)")
        notes = [n for n in (rule.notes, rule.legal_gap) if n]
        chosen_asset, chosen_role = raw.get("asset_type"), raw.get("role")
        if chosen_asset and rule.asset_type not in (chosen_asset, ANY):
            notes.append(f"model labelled the asset {chosen_asset!r} but chose a rule for "
                         f"{rule.asset_type!r} - the rule was applied and the mismatch recorded")
        if chosen_role and rule.role != chosen_role:
            notes.append(f"model labelled the role {chosen_role!r} but chose a {rule.role!r} rule")

        return RoutingDecision(
            case_id=rule.case_id, priority=priority, asset_type=rule.asset_type, role=rule.role,
            institution=rule.institution, office=rule.office, legal_basis=rule.legal_basis,
            escalation=list(rule.escalation), confidence=rule.confidence, rationale=rationale,
            used_model=True, numeric_claim_withheld=withheld, candidates=ids, notes=notes)

    # -- two-stage triage (the default) -------------------------------------
    def triage_route(self, ontology: Ontology, facts: str, evidence_state: str = "",
                     priority_hint: str = MEDIUM) -> RoutingDecision:
        """Classify (asset, duty) with the model, then map deterministically to a rule.

        The single-call version asked a 1.5B model to resolve asset, duty, jurisdiction
        and citation at once and scored 38.1%. Here the model answers a small, defined
        classification - which asset is failing, and which duty applies - and the
        ontology maps that to the cited rule. The model still makes the decision that
        determines the outcome; it is no longer asked to also recall the law.
        """
        candidates = [r for r in ontology.rules if r.citable]
        ids = [c.case_id for c in candidates]
        assets = sorted({c.asset_type for c in candidates})
        roles = sorted({c.role for c in candidates})

        if self.backend is None or not self.backend.available():
            return RoutingDecision(
                case_id=None, priority=priority_hint, confidence="none", fallback_used=True,
                candidates=ids,
                rationale=("free-text triage requires the open-weight model; without it an "
                           "unstructured report cannot be resolved to an asset and a duty, "
                           "so nothing is routed"),
                notes=["the decision layer is load-bearing: remove it and the product stops"])

        try:
            raw = self.backend.decide(
                build_classify_prompt(facts, assets, roles, evidence_state),
                build_classify_schema(assets, roles))
        except Exception as exc:
            return RoutingDecision(case_id=None, priority=priority_hint, confidence="none",
                                   fallback_used=True, candidates=ids,
                                   rationale=f"model call failed ({type(exc).__name__}); routed nothing")

        asset = raw.get("asset_type")
        role = raw.get("role")
        if role in (None, "none"):
            role = "maintenance"   # a known asset always carries at least its ownership duty
        rationale = str(raw.get("rationale") or "").strip()
        withheld = bool(DIGITS.search(rationale))
        if withheld:
            rationale = ("model rationale withheld: it contained a numeric claim "
                         "(measurements are computed in code, never by the model)")

        if asset in (None, "none"):
            return RoutingDecision(
                case_id=None, priority=priority_hint, asset_type=asset, role=role,
                confidence="none", used_model=True, candidates=ids,
                rationale=f"abstained: {rationale[:220]}",
                notes=["the model chose to abstain rather than guess an authority"])

        # Deterministic mapping from (asset, duty) to the cited rule.
        matched = [c for c in candidates if c.asset_type == asset and c.role == role]
        if not matched:
            return RoutingDecision(
                case_id=None, priority=priority_hint, asset_type=asset, role=role,
                confidence="none", used_model=True, candidates=ids,
                rationale=f"no cited rule exists for asset={asset!r} duty={role!r}; nothing routed",
                notes=["the report fell outside the cited routing key - a real gap, recorded"])
        if len(matched) > 1:
            return RoutingDecision(
                case_id=None, priority=priority_hint, asset_type=asset, role=role,
                confidence="none", used_model=True, candidates=ids,
                rationale=f"ambiguous: {len(matched)} rules match asset={asset!r} duty={role!r}",
                notes=["ambiguity abstains rather than guessing"])

        rule = matched[0]
        priority = raw.get("priority") if raw.get("priority") in (HIGH, MEDIUM, LOW) else priority_hint
        notes = [n for n in (rule.notes, rule.legal_gap) if n]
        return RoutingDecision(
            case_id=rule.case_id, priority=priority, asset_type=asset, role=role,
            institution=rule.institution, office=rule.office, legal_basis=rule.legal_basis,
            escalation=list(rule.escalation), confidence=rule.confidence, rationale=rationale,
            used_model=True, numeric_claim_withheld=withheld, candidates=ids, notes=notes)

    def route_emergency(self, ontology: Ontology, asset_type: str,
                        jurisdiction: str | None = None) -> RoutingDecision:
        return self.route(ontology, asset_type, role=EMERGENCY, jurisdiction=jurisdiction,
                          hazard_type="road-blockage")


def build_triage_schema(candidates: list[AuthorityRule]) -> dict:
    """Every answer - including abstention - is an enum value. Schemas are inlined."""
    assets = sorted({c.asset_type for c in candidates})
    roles = sorted({c.role for c in candidates})
    return {
        "type": "object",
        "properties": {
            "asset_type": {"type": "string", "enum": assets + ["none"]},
            "role": {"type": "string", "enum": roles + ["none"]},
            "case_id": {"type": "string", "enum": [c.case_id for c in candidates] + ["none"]},
            "priority": {"type": "string", "enum": [HIGH, MEDIUM, LOW]},
            "rationale": {"type": "string"},
        },
        "required": ["asset_type", "role", "case_id", "priority", "rationale"],
        "additionalProperties": False,
    }


def build_triage_prompt(facts: str, candidates: list[AuthorityRule], evidence_state: str) -> str:
    lines = [
        "You are routing a slope-hazard report in Nepal to the office legally responsible.",
        "First identify WHICH ASSET is failing, then WHICH DUTY applies, then choose ONE case_id.",
        "The failing asset may not be the asset that is damaged: if a road on the slope above a",
        "highway fails onto the highway, the failing asset is the road on the slope.",
        "Choose case_id from the options only. If the report does not identify an asset and a",
        "duty well enough to route safely, choose \"none\" and explain what is missing.",
        "Do not state any number - measurements are computed elsewhere.",
        "",
        f"REPORT: {facts}",
    ]
    if evidence_state:
        lines.append(f"EVIDENCE STATE: {evidence_state}")
    lines += ["", "OPTIONS:"]
    for c in candidates:
        lines.append(f"- case_id: {c.case_id} | asset: {c.asset_type} | role: {c.role}")
        lines.append(f"  institution: {c.institution}")
        lines.append(f"  legal basis: {c.legal_basis}")
    lines += ["", "Return JSON: asset_type, role, case_id, priority, rationale."]
    return "\n".join(lines)


ASSET_DEFINITION = (
    "asset_type = WHICH ASSET IS FAILING OR AT RISK. This is not always the asset that is "
    "damaged: if a road on the slope above a highway fails and debris lands on the highway, "
    "the FAILING asset is the road on the slope, not the highway."
)

ROLE_DEFINITION = (
    "role = WHICH DUTY the report is asking about:\n"
    "  maintenance = who OWNS and must repair/maintain that asset (a budget-holding duty)\n"
    "  emergency   = who RESPONDS NOW to an event that has already happened (rescue, clearance, "
    "traffic control, relief)\n"
    "  warning     = who issues a public warning\n"
    "  assessment  = who provides a technical or geological opinion\n"
    "  coordination= who coordinates a multi-agency response"
)

ABSTAIN_RULE = (
    "Choose asset_type=\"none\" ONLY when the report names no kind of asset at all - for example "
    "\"a road is affected by something\" or \"there is a problem near a river\". If you can tell "
    "what kind of asset is involved, you MUST choose that asset and the most likely duty; do not "
    "abstain merely because the report is brief. Abstention exists to prevent naming the wrong "
    "authority, not to avoid a decision. A brief but specific report is routable."
)

FEWSHOT = [
    ("A rural road built by a municipality crosses the slope above a national highway. The road has "
     "failed and debris has come down onto the national highway.",
     "local-road", "maintenance"),
    ("A national highway is blocked by debris from a slope failure. Traffic is stopped.",
     "strategic-road", "emergency"),
    ("A tension crack has opened beside a rural road; the road is still passable.",
     "local-road", "maintenance"),
    ("A state highway under the provincial government has a slope failure on one side.",
     "provincial-road", "maintenance"),
    ("A river is eroding its bank and threatening a settlement; earlier check dams have failed.",
     "riverbank", "maintenance"),
    ("A steep privately owned hillside above a house has developed cracks.",
     "private-land", "maintenance"),
    ("The slope behind a community school is unstable and cracks are appearing in the playground.",
     "public-building", "maintenance"),
    ("A municipality wants an independent geological opinion on whether a slope is safe to build on.",
     "any", "assessment"),
    ("The district authorities need to warn the public that landslides are likely.",
     "any", "warning"),
    ("A road is affected by something.", "none", "maintenance"),
]


def build_classify_prompt(facts: str, assets: list[str], roles: list[str],
                          evidence_state: str = "") -> str:
    lines = [
        "You are routing a slope-hazard report in Nepal.",
        ASSET_DEFINITION,
        ROLE_DEFINITION,
        ABSTAIN_RULE,
        "",
        f"Allowed asset_type values: {', '.join(assets)}",
        f"Allowed role values: {', '.join(roles)}",
        "",
        "EXAMPLES:",
    ]
    for text, a, r in FEWSHOT:
        lines.append(f'- report: "{text}"')
        lines.append(f'  answer: asset_type="{a}", role="{r}"')
    lines += [
        "",
        f'REPORT TO ROUTE: "{facts}"',
    ]
    if evidence_state:
        lines.append(f"EVIDENCE STATE: {evidence_state}")
    lines += ["", "Do not state any number. Reply with JSON only."]
    return "\n".join(lines)


def build_classify_schema(assets: list[str], roles: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "asset_type": {"type": "string", "enum": assets + ["none"]},
            "role": {"type": "string", "enum": roles + ["none"]},
            "priority": {"type": "string", "enum": [HIGH, MEDIUM, LOW]},
            "rationale": {"type": "string"},
        },
        "required": ["asset_type", "role", "priority", "rationale"],
        "additionalProperties": False,
    }
