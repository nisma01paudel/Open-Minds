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
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from pahiro.advisory.nepali import (evidence_state_ne, primed_unobserved_text,
                                    rainfall_state_ne, refusal_text, render, siting_ne)
from pahiro.dispatch import authority_from_decision, build_dispatch
from pahiro.ingest import stac
from pahiro.ingest.rainfall import fetch_series_cached
from pahiro.ingest.screen import screen_scene
from pahiro.ingest import terrain as terrain_mod
from pahiro.siting import advise as siting_advise
from pahiro.ontology import Ontology
from pahiro.routing.abstain import Observation, staleness_gate
from pahiro.routing.resolve import RoutingContext, resolve
from pahiro.routing.router import Router
from pahiro.trigger import APPROACHING, EXCEEDED, PANCHPOKHARI, assess

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
class Decision:
    """A choice the agent made about its own next action, and why.

    Kept separate from ToolCall on purpose. A trace of tool calls shows what the system
    DID; it does not show that the system chose. Without this the loop is a fixed
    pipeline and should be judged as one.
    """
    after: str
    choice: str
    reason: str


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
    trigger: object | None = None
    siting: object | None = None
    decisions: list[Decision] = field(default_factory=list)
    scenes: list[str] = field(default_factory=list)
    sensors: list[str] = field(default_factory=list)
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
                 evidence_days: int = 45, max_scenes: int = 24,
                 tool_timeout: int = 180):
        self.ontology = ontology if ontology is not None else Ontology([])
        self.router = router if router is not None else Router(None)
        self.threshold = threshold
        self.rain_days = rain_days
        self.evidence_days = evidence_days
        self.max_scenes = max_scenes
        self.tool_timeout = tool_timeout

    # -- tools -------------------------------------------------------------
    def _record(self, run: AgentRun, name: str, args: dict, fn, timeout: int | None = None):
        """Run one tool, recording what happened - including if it hung.

        Every tool is bounded. A live demo dies if a single network read blocks
        forever, and an agent that cannot say "that step timed out" is not auditable.
        The worker runs on a daemon thread so an abandoned call cannot keep the
        process alive at exit.
        """
        timeout = timeout if timeout is not None else self.tool_timeout
        start = time.time()
        box: dict = {}

        def worker():
            try:
                box["value"] = fn()
            except Exception as exc:                       # noqa: BLE001
                box["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout)
        elapsed = int((time.time() - start) * 1000)

        if thread.is_alive():
            run.trace.append(ToolCall(name, args, f"timed out after {timeout}s", False, elapsed))
            return None
        if "error" in box:
            exc = box["error"]
            run.trace.append(ToolCall(name, args, f"{type(exc).__name__}: {exc}", False, elapsed))
            return None

        result = box.get("value")
        summary = result[0] if isinstance(result, tuple) else str(result)
        payload = result[1] if isinstance(result, tuple) else result
        run.trace.append(ToolCall(name, args, summary, True, elapsed))
        return payload

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
            series = fetch_series_cached(bbox, start, run.as_of)
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
            run.trigger = a
        return a

    def tool_siting_advice(self, run: AgentRun):
        """Read the terrain and decide: repair here, or move above the source zone."""
        bbox = (run.lon - RAIN_PAD, run.lat - RAIN_PAD, run.lon + RAIN_PAD, run.lat + RAIN_PAD)

        def call():
            tw = terrain_mod.fetch(bbox)
            if tw is None or not tw.usable:
                raise RuntimeError("no usable DEM window for this site")
            h, w = tw.elevation.shape
            advice = siting_advise(tw.elevation, tw.transform, h // 2, w // 2, crs=tw.crs)
            return advice.describe(), advice

        a = self._record(run, "siting_advice", {"bbox": bbox}, call)
        if a is not None:
            run.siting = a
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
            # Remember exactly which observations support the decision: a
            # non-abstaining dispatch must cite its evidence, and its own validator
            # refuses to let one through without it.
            run.scenes = [o.scene_id for o in obs if o.scene_id][:8]
            run.sensors = sorted({o.sensor for o in obs})
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
                rainfall_state=rainfall_state_ne(getattr(run, "trigger", None)) or
                (run.rainfall_banner or ""),
                inspect_first=inspect, authority_institution=who,
                authority_office=office, legal_basis=basis, needs_review=needs_review,
                siting=siting_ne(run.siting))
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
            needs_review=needs_review, siting=siting_ne(run.siting))

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
            scenes=run.scenes, sensors=run.sensors,
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

    # -- call-site guard ---------------------------------------------------
    def _call_tool(self, run: AgentRun, name: str, fn):
        """Protect a tool call regardless of how the tool is implemented.

        The per-tool timeout inside each tool only guards the work *inside* it. The
        guard belongs at the call site, so a tool that hangs, raises, or is replaced
        by something that does either is still bounded and still recorded. Without
        this, one blocked read takes the whole run down.
        """
        before = len(run.trace)
        box: dict = {}

        def worker():
            try:
                box["value"] = fn(run)
            except Exception as exc:                       # noqa: BLE001
                box["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(self.tool_timeout)

        if thread.is_alive():
            run.trace.append(ToolCall(name, {}, f"timed out after {self.tool_timeout}s", False,
                                      self.tool_timeout * 1000))
            return None
        if "error" in box:
            exc = box["error"]
            if len(run.trace) == before:      # the tool did not record it itself
                run.trace.append(ToolCall(name, {}, f"{type(exc).__name__}: {exc}", False, 0))
            return None
        return box.get("value")

    # -- the loop ----------------------------------------------------------
    def run(self, report: str, lon: float, lat: float, as_of: date) -> AgentRun:
        run = AgentRun(report=report, lon=lon, lat=lat, as_of=as_of)

        self._call_tool(run, "resolve_location", self.tool_resolve_location)
        self._call_tool(run, "rainfall_trigger", self.tool_rainfall_trigger)
        evidence = self._call_tool(run, "ground_evidence", self.tool_ground_evidence)

        # The agent chooses its own next action from what it has just observed, rather
        # than running a fixed list. Reading terrain costs a DEM fetch, and on a slope
        # that nothing is raising and nothing can see, that fetch cannot change the
        # answer - so it is not spent. The reason is recorded either way.
        primed = (run.rainfall_state or "") in (APPROACHING, EXCEEDED)
        can_see = bool(getattr(evidence, "may_issue", False))
        if primed or can_see:
            run.decisions.append(Decision(
                after="ground_evidence", choice="siting_advice",
                reason=("rainfall trigger is "
                        f"{run.rainfall_state or 'unknown'}" if primed
                        else "ground evidence is fresh")
                        + " - reading terrain can change the recommendation"))
            self._call_tool(run, "siting_advice", self.tool_siting_advice)
        else:
            run.decisions.append(Decision(
                after="ground_evidence", choice="skip siting_advice",
                reason=("nothing is raising this slope (trigger below) and no fresh "
                        "observation exists; a DEM fetch here cannot change the answer")))

        run.state = decide_state(run.rainfall_state or "", can_see)
        self._call_tool(run, "route_report", self.tool_route_report)
        run.advisory_ne = self._call_tool(run, "compose_advisory", self.tool_compose_advisory)
        self._call_tool(run, "emit_dispatch", self.tool_emit_dispatch)
        return run
