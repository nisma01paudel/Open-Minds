"""The authority-routing ontology: who is responsible, and on what legal basis.

Design rule that the code enforces: **a routing rule without a citation is not a
rule.** Anything unverified is either absent or explicitly marked, so the system
can never state an institution it cannot justify.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Asset classes we route on.
LOCAL_ROAD = "local-road"
STRATEGIC_ROAD = "strategic-road"
PROVINCIAL_ROAD = "provincial-road"
PRIVATE_LAND = "private-land"
PUBLIC_BUILDING = "public-building"
RIVERBANK = "riverbank"

ASSET_TYPES = (LOCAL_ROAD, STRATEGIC_ROAD, PROVINCIAL_ROAD,
               PRIVATE_LAND, PUBLIC_BUILDING, RIVERBANK)

# Confidence a rule can carry.
VERIFIED = "verified"
PARTIAL = "partial"
UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class AuthorityRule:
    """One routing rule, with the legal basis that makes it citable."""
    case_id: str
    asset_type: str
    jurisdiction: str          # e.g. 'municipality', 'federal', 'province'
    hazard_type: str           # e.g. 'slope-instability', 'road-blockage'
    institution: str           # e.g. 'Division Road Office'
    office: str                # the specific office / level
    legal_basis: str           # act name + year + section where known
    escalation: list[str] = field(default_factory=list)
    confidence: str = UNCERTAIN
    source_url: str | None = None
    notes: str | None = None

    @property
    def citable(self) -> bool:
        """A rule may only be used if it carries a legal basis and a source."""
        return bool(self.legal_basis.strip()) and bool(self.source_url)


class Ontology:
    """A versioned, citable set of routing rules."""

    def __init__(self, rules: list[AuthorityRule] | None = None, version: str = "0.0.0"):
        self.rules: list[AuthorityRule] = list(rules or [])
        self.version = version

    def __len__(self) -> int:
        return len(self.rules)

    @classmethod
    def load(cls, path: str | Path) -> "Ontology":
        data = json.loads(Path(path).read_text())
        rules = [AuthorityRule(**r) for r in data.get("rules", [])]
        return cls(rules, data.get("version", "0.0.0"))

    def save(self, path: str | Path) -> None:
        payload = {
            "version": self.version,
            "rules": [asdict(r) for r in self.rules],
        }
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def lookup(self, asset_type: str, jurisdiction: str | None = None,
               hazard_type: str | None = None) -> AuthorityRule | None:
        """Return the single best citable rule, or None.

        Ambiguity is treated as failure, not as a guess: if more than one rule
        matches equally well, we return None and the caller must abstain.
        """
        matches = [r for r in self.rules if r.asset_type == asset_type and r.citable]
        if jurisdiction:
            narrowed = [r for r in matches if r.jurisdiction == jurisdiction]
            matches = narrowed or matches
        if hazard_type:
            narrowed = [r for r in matches if r.hazard_type == hazard_type]
            matches = narrowed or matches
        if len(matches) == 1:
            return matches[0]
        return None   # zero matches, or ambiguous -> no routing
