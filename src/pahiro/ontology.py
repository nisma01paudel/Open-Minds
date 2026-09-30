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

# ANY is the wildcard asset class, used by cross-cutting roles (warning,
# assessment, coordination) that are not tied to a single kind of asset.
ANY = "any"

ASSET_TYPES = (LOCAL_ROAD, STRATEGIC_ROAD, PROVINCIAL_ROAD,
               PRIVATE_LAND, PUBLIC_BUILDING, RIVERBANK, ANY)

# A slope sits in TWO chains that are routinely confused, so a routing key that
# ignores role will misroute. "Have the hazard fixed" is a capital/maintenance
# duty with a budget cycle; "respond now" is an emergency duty triggered by an
# event. A blocked road sits in both.
MAINTENANCE = "maintenance"     # fix it: the asset owner
EMERGENCY = "emergency"         # respond now: LDMC/DDMC
WARNING = "warning"             # issue a public warning
ASSESSMENT = "assessment"       # technical/geological opinion
COORDINATION = "coordination"   # multi-agency response

ROLES = (MAINTENANCE, EMERGENCY, WARNING, ASSESSMENT, COORDINATION)

# Confidence a rule can carry.
VERIFIED = "verified"
PARTIAL = "partial"
UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class AuthorityRule:
    """One routing rule, with the legal basis that makes it citable.

    A rule states a *duty*, not just an owner: who must act, in which role, and
    under which section. Where the law is genuinely silent we say so through
    `confidence` and `notes` rather than filling the gap with a guess.
    """
    case_id: str
    asset_type: str
    jurisdiction: str          # e.g. 'municipality', 'federal', 'province'
    hazard_type: str           # e.g. 'slope-instability', 'road-blockage'
    role: str                  # maintenance | emergency | warning | assessment | coordination
    institution: str           # e.g. 'Division Road Office'
    office: str                # the specific office / level
    legal_basis: str           # act name + year + section where known
    escalation: list[str] = field(default_factory=list)
    confidence: str = UNCERTAIN
    source_url: str | None = None
    citation: str | None = None      # document title + section, when no stable URL
    notes: str | None = None
    legal_gap: str | None = None     # where the law does not actually reach

    @property
    def citable(self) -> bool:
        """A rule may only be used if it carries a legal basis AND a source."""
        return bool(self.legal_basis.strip()) and bool(self.source_url or self.citation)


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

    def lookup(self, asset_type: str, role: str = MAINTENANCE,
               jurisdiction: str | None = None,
               hazard_type: str | None = None) -> AuthorityRule | None:
        """Return the single best citable rule, or None.

        Ambiguity is treated as failure, not as a guess: if more than one rule
        matches equally well, we return None and the caller must abstain.
        """
        matches = [
            r for r in self.rules
            if r.citable and r.role == role
            and r.asset_type in (asset_type, ANY)
        ]
        if not matches:
            return None
        if jurisdiction:
            narrowed = [r for r in matches if r.jurisdiction == jurisdiction]
            matches = narrowed or matches
        if hazard_type:
            narrowed = [r for r in matches if r.hazard_type == hazard_type]
            matches = narrowed or matches
        exact = [r for r in matches if r.asset_type == asset_type]
        if len(exact) == 1:
            return exact[0]
        if len(matches) == 1:
            return matches[0]
        return None   # zero matches, or ambiguous -> no routing

    def route_incident(self, causer_asset: str, affected_asset: str | None = None,
                       jurisdiction: str | None = None,
                       hazard_type: str = "slope-instability") -> dict:
        """Route a slope incident across the two assets that always exist.

        The lesson of Simaltal (12 July 2024, Narayanghat-Muglin, 62 passengers):
        a rural road built by Bharatpur Metropolitan City on the slope above a
        FEDERAL highway failed onto it. Routing by the affected asset alone -
        "national highway = Department of Roads, full stop" - names the wrong
        actor for the cause. Asset-anchored routing must name both.
        """
        responsible = self.lookup(causer_asset, MAINTENANCE, jurisdiction, hazard_type)
        emergency = self.lookup(causer_asset, EMERGENCY, jurisdiction, hazard_type)
        affected = (self.lookup(affected_asset, MAINTENANCE, jurisdiction, hazard_type)
                    if affected_asset else None)
        caveats = []
        if responsible is None:
            caveats.append("no citable maintenance duty found for the failing asset")
        if affected_asset and affected is None:
            caveats.append(f"no citable maintenance duty found for {affected_asset}")
        if responsible is not None and affected is not None \
                and responsible.institution != affected.institution:
            caveats.append(
                "the failing asset and the affected asset belong to different "
                "institutions: notifying only the road owner misroutes this case")
        return {
            "responsible": responsible,
            "emergency": emergency,
            "affected_authority": affected,
            "caveats": caveats,
        }
