"""The slope-change agent: plan, call tools, decide, act, and show its work.

This is the layer the competition's first operational criterion is about - "real
autonomy, tool use, or multi-step reasoning rather than a single prompt dressed up".
Every step is a recorded tool call with its arguments, its result, and how long it
took. The trace is the evidence.

The decision is genuinely multi-signal, and the most important state it can produce
is the one no optical system can:

    rain says the slope is primed  +  nothing can see it
    ->  "primed, unobserved" - a warning about our own blindness

Silence in July is indistinguishable from safety. Saying "the slope is primed and I
cannot see it" is more useful than either a false all-clear or a confident guess.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from pahiro.advisory.nepali import (evidence_state_ne, primed_unobserved_text,
                                    refusal_text, render)
from pahiro.dispatch import authority_from_decision, build_dispatch
from pahiro.ingest import stac
from pahiro.ingest.rainfall import fetch_series
from pahiro.ingest.screen import screen_scene
from pahiro.ontology import Ontology
from pahiro.routing.abstain import Observation, staleness_gate
from pahiro.routing.resolve import RoutingContext, resolve
from pahiro.routing.router import Router
from pahiro.trigger import EXCEEDED, PANCHPOKHARI, assess

# Decision states.
PRIMED_CONFIRMED = "primed-confirmed"     # trigger up AND fresh ground evidence
PRIMED_UNOBSERVED = "primed-unobserved"   # trigger up, but we cannot see
MONITORED = "monitored"                   # fresh evidence, no trigger
ABSTAIN = "abstain"                       # nothing to say

SITE_PAD = 0.01
RAIN_PAD = 0.05              # ~5 km: rainfall is an area signal, not a point


@dataclass
class ToolCall:
    name: str
    args: dict
    result: str
    ok: bool = True
    ms: int = 0


@dataclass
class AgentRun:
    report: str
    lon: float
    lat: float
    as_of: date
    trace: list[ToolCall] = field(default_factory=list)
    state: str = ABSTAIN
    ctx: RoutingContext | None = None
    rainfall_state: str | None = None
    rainfall_banner: str | None = None
    staleness: object | None = None
    routing: object | None = None
    dispatch: object | None = None
    advisory_ne: str | None = None
    register_payload: dict | None = None
    priority: str | None = None

    def to_json(self) -> str:
        d = asdict(self)
        d["as_of"] = self.as_of.isoformat()
        d["trace"] = [asdict(t) for t in self.trace]
        return json.dumps(d, ensure_ascii=False, indent=2, default=str)

    def summary(self) -> str:
        lines = [f"state: {self.state}   priority: {self.priority}"]
        for t in self.trace:
            mark = "ok " if t.ok else "ERR"
            lines.append(f"  [{mark}] {t.name:22} {t.ms:>6} ms  {t.result}")
        return "\n".join(lines)


def decide_state(trigger_state: str, evidence_may_issue: bool) -> str:
    """The multi-signal decision. Order matters: blindness is its own finding."""
    if trigger_state == EXCEEDED and evidence_may_issue:
        return PRIMED_CONFIRMED
    if trigger_state == EXCEEDED:
        return PRIMED_UNOBSERVED
    if evidence_may_issue:
        return MONITORED
    return ABSTAIN


def priority_for(state: str, trigger_state: str) -> str:
    if state == PRIMED_CONFIRMED:
        return "high"
    if state == PRIMED_UNOBSERVED:
        return "high"            # primed ground we cannot see is a high concern
    if state == MONITORED or trigger_state == "approaching":
        return "medium"
    return "low"


class SlopeChangeAgent:
    """Runs the whole pipeline for one report, recording every tool call."""

    def __init__(self, ontology: Ontology | None = None, router: Router | None = None,
                 threshold=PANCHPOKHARI, rain_days: int = 10,
                 evidence_days: int = 45, max_scenes: int = 24):
        self.ontology = ontology if ontology is not None else Ontology([])
        self.router = router if router is not None else Router(None)
        self.threshold = threshold
        self.rain_days = rain_days
        self.evidence_days = evidence_days
        self.max_scenes = max_scenes

    # -- tools -------------------------------------------------------------
    def _record(self, run: AgentRun, name: str, args: dict, fn):
        start = time.time()
        try:
            result = fn()
            summary = result[0] if isinstance(result, tuple) else str(result)
            payload = result[1] if isinstance(result, tuple) else result
            run.trace.append(ToolCall(name, args, summary, True,
                                      int((time.time() - start) * 1000)))
            return payload
        except Exception as exc:
            run.trace.append(ToolCall(name, args, f"{type(exc).__name__}: {exc}", False,
                                      int((time.time() - start) * 1000)))
            return None

    def tool_resolve_location(self, run: AgentRun) -> RoutingContext | None:
        ctx = self._record(run, "resolve_location", {"lon": run.lon, "lat": run.lat},
                           lambda: (lambda c: (c.describe() + f"  [{c.source}]", c))(
                               resolve(run.lon, run.lat, cache_path="cache/ward-cache.json")))
        if ctx is not None:
            run.ctx = ctx
        return ctx

    def tool_rainfall_trigger(self, run: AgentRun):
        bbox = (run.lon - RAIN_PAD, run.lat - RAIN_PAD, run.lon + RAIN_PAD, run.lat + RAIN_PAD)
        start = run.as_of - timedelta(days=self.rain_days)

        def call():
            series = fetch_series(bbox, start, run.as_of)
            if not series:
                raise RuntimeError("no CHIRPS days available")
            rain = {r.day: r.max_mm for r in series}
            a = assess(rain, run.as_of, self.threshold)
            return a.banner(), a

        a = self._record(run, "rainfall_trigger",
                         {"days": self.rain_days, "threshold": self.threshold.name}, call)
        if a is not None:
            run.rainfall_state = a.state
            run.rainfall_banner = a.banner()
        return a

    def tool_ground_evidence(self, run: AgentRun):
        bbox = (run.lon - SITE_PAD, run.lat - SITE_PAD, run.lon + SITE_PAD, run.lat + SITE_PAD)
        start = run.as_of - timedelta(days=self.evidence_days)

        def call():
            scenes = stac.search(stac.OPTICAL, bbox, start.isoformat(), run.as_of.isoformat(),
                                 cloud_lt=None, max_items=self.max_scenes)
            obs: list[Observation] = []
            usable = 0
            for s in scenes:
                try:
                    rec = screen_scene(s, bbox)
                except Exception:
                    continue
                frac = rec["aoi_clear_fraction"]
                usable += 1 if frac >= 0.30 else 0
                obs.append(Observation(stac.OPTICAL, s.acquired, quality=frac, scene_id=s.id))
            radar = stac.search(stac.RADAR, bbox, start.isoformat(), run.as_of.isoformat(),
                                cloud_lt=None, max_items=self.max_scenes)
            for s in radar:
                # acquisition known, per-pixel usability not yet measured
                obs.append(Observation(stac.RADAR, s.acquired, quality=1.0,
                                       scene_id=s.id, verified=False))
            decision = staleness_gate(obs, run.as_of)
            return (f"{len(scenes)} optical scenes ({usable} usable), {len(radar)} radar "
                    f"-> {decision.status}", decision)

        d = self._record(run, "ground_evidence",
                         {"days": self.evidence_days, "max_scenes": self.max_scenes}, call)
        if d is not None:
            run.staleness = d
        return d

    def tool_route_report(self, run: AgentRun):
        d = self._record(run, "route_report", {"chars": len(run.report)},
                         lambda: self._route(run))
        if d is not None:
            run.routing = d
        return d

    def _route(self, run: AgentRun):
        if not self.ontology.rules:
            return "no ontology loaded; routing withheld", None
        decision = self.router.triage_route(self.ontology, run.report,
                                            evidence_state=run.rainfall_banner or "")
        who = decision.institution or "withheld"
        return f"{who}  [{decision.case_id or 'none'}]", decision

    def tool_compose_advisory(self, run: AgentRun):
        return self._record(run, "compose_advisory", {"state": run.state},
                            lambda: ("nepali advisory composed", self._compose(run)))

    def tool_emit_dispatch(self, run: AgentRun):
        return self._record(run, "emit_dispatch", {"state": run.state},
                            lambda: self._emit(run))

    # -- composition -------------------------------------------------------
    def _compose(self, run: AgentRun) -> str:
        where = run.ctx.describe() if run.ctx else f"{run.lat:.4f}, {run.lon:.4f}"
        as_of = run.as_of.isoformat()
        decision = run.routing
        who = getattr(decision, "institution", None)
        office = getattr(decision, "office", None)
        basis = getattr(decision, "legal_basis", None)
        needs_review = who is None
        inspect = [f"{where} को ढलान", "माथिल्लो ढलानको जल-निकास"]

        if run.state == PRIMED_UNOBSERVED:
            return primed_unobserved_text(
                location=where, as_of=as_of,
                rainfall_state=run.rainfall_banner or "",
                inspect_first=inspect, authority_institution=who,
                authority_office=office, legal_basis=basis, needs_review=needs_review)
        if run.staleness is None or not getattr(run.staleness, "may_issue", False):
            return refusal_text(run.staleness) if run.staleness else (
                "प्रमाण उपलब्ध छैन — सूचना जारी गरिएको छैन।")
        return render(
            location=where, as_of=as_of,
            what_changed="स्याटेलाइट/रडार परिवर्तन संकेत",
            evidence_state=evidence_state_ne(run.staleness),
            why_it_matters="यो ढलानसँग जोडिएको सडक तथा बस्ती जोखिममा पर्न सक्छ।",
            inspect_first=inspect,
            recommendation="मर्मत गर्नुअघि ढलानको अवस्था जाँच्नुहोस्।",
            authority_institution=who, authority_office=office, legal_basis=basis,
            needs_review=needs_review)

    def _emit(self, run: AgentRun):
        state = run.state
        if state == ABSTAIN:
            return "nothing issued: no trigger and no fresh evidence", None
        decision = run.routing
        rule = None
        if getattr(decision, "case_id", None):
            rule = next((r for r in self.ontology.rules if r.case_id == decision.case_id), None)
        priority = priority_for(state, run.rainfall_state or "")
        staleness = run.staleness
        if staleness is None or not getattr(staleness, "may_issue", False):
            # An honest refusal to claim: we have no ground evidence.
            class _Blind:
                may_issue = False
                banner = lambda self: "no fresh observation"      # noqa: E731
            staleness = _Blind()
        d = build_dispatch(
            location=run.ctx.describe() if run.ctx else f"{run.lat:.4f}, {run.lon:.4f}",
            as_of=run.as_of, staleness=staleness, advisory_ne=run.advisory_ne or "",
            findings=[run.rainfall_banner or ""],
            inspect_first=[run.ctx.describe() if run.ctx else ""],
            priority=priority, rule=rule,
            scenes=[], sensors=[],
            ontology_version=self.ontology.version,
        )
        d.routing_context = {
            "ward": getattr(run.ctx, "ward", None),
            "municipality": getattr(run.ctx, "municipality", None),
            "district": getattr(run.ctx, "district", None),
            "state": state,
        }
        run.dispatch = d
        run.priority = priority
        return f"dispatch {d.status} priority={priority} problems={d.validate() or 'none'}", d

    # -- the loop ----------------------------------------------------------
    def run(self, report: str, lon: float, lat: float, as_of: date) -> AgentRun:
        run = AgentRun(report=report, lon=lon, lat=lat, as_of=as_of)

        self.tool_resolve_location(run)
        trigger = self.tool_rainfall_trigger(run)
        evidence = self.tool_ground_evidence(run)
        run.state = decide_state(run.rainfall_state or "", bool(
            getattr(evidence, "may_issue", False)))
        self.tool_route_report(run)
        run.advisory_ne = self.tool_compose_advisory(run)
        self.tool_emit_dispatch(run)
        return run
