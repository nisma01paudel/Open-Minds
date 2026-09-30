"""The agent must decide on multiple signals, and show its work."""
from datetime import date

from pahiro.agent import (ABSTAIN, MONITORED, PRIMED_CONFIRMED, PRIMED_UNOBSERVED,
                          SlopeChangeAgent, decide_state, priority_for)
from pahiro.ontology import Ontology
from pahiro.routing.abstain import OPTICAL, Observation, staleness_gate

AS_OF = date(2025, 7, 20)
ONTOLOGY = "ontology/nepal-slope-routing.json"


# --- the decision matrix ------------------------------------------------------
def test_trigger_up_with_evidence_is_confirmed():
    assert decide_state("exceeded", True) == PRIMED_CONFIRMED


def test_trigger_up_without_evidence_is_the_blindness_state():
    """The state no optical system can produce, and the most useful one in July."""
    assert decide_state("exceeded", False) == PRIMED_UNOBSERVED


def test_evidence_without_a_trigger_is_monitored():
    assert decide_state("below", True) == MONITORED


def test_nothing_to_say_abstains():
    assert decide_state("below", False) == ABSTAIN
    assert decide_state("approaching", False) == ABSTAIN


def test_priority_reflects_blindness_as_a_concern():
    assert priority_for(PRIMED_CONFIRMED, "exceeded") == "high"
    assert priority_for(PRIMED_UNOBSERVED, "exceeded") == "high", \
        "primed ground we cannot see is not a low priority"
    assert priority_for(MONITORED, "below") == "medium"


# --- the loop -----------------------------------------------------------------
class FakeContext:
    ward, municipality, district, province, centre = "11", "Thakre", "DHADING", "3", None
    source = "fake"
    def describe(self): return "Ward 11, Thakre, DHADING"


def build_agent(*, trigger_state, evidence_ok, model=None):
    agent = SlopeChangeAgent(ontology=Ontology.load(ONTOLOGY))
    from pahiro.routing.router import Router
    agent.router = Router(model)

    def fake_resolve(run):
        run.ctx = FakeContext()
        run.trace.append(_ok("resolve_location"))
        return run.ctx

    def fake_rain(run):
        run.rainfall_state = trigger_state
        run.rainfall_banner = f"rainfall trigger {trigger_state.upper()}"
        run.trace.append(_ok("rainfall_trigger"))
        return run.rainfall_banner

    def fake_evidence(run):
        obs = [Observation(OPTICAL, AS_OF, quality=0.9)] if evidence_ok else \
              [Observation(OPTICAL, AS_OF.replace(month=4), quality=0.1)]
        run.staleness = staleness_gate(obs, AS_OF)
        run.trace.append(_ok("ground_evidence"))
        return run.staleness

    agent.tool_resolve_location = fake_resolve
    agent.tool_rainfall_trigger = fake_rain
    agent.tool_ground_evidence = fake_evidence
    return agent


def _ok(name):
    from pahiro.agent import ToolCall
    return ToolCall(name, {}, "fake", True, 1)


def test_run_records_every_step_in_order():
    agent = build_agent(trigger_state="exceeded", evidence_ok=True)
    run = agent.run("a slope above a road has cracked", 85.05, 27.76, AS_OF)
    names = [t.name for t in run.trace]
    assert names == ["resolve_location", "rainfall_trigger", "ground_evidence",
                     "route_report", "compose_advisory", "emit_dispatch"]
    assert run.state == PRIMED_CONFIRMED
    assert run.priority == "high"


def test_blind_but_primed_produces_an_advisory_that_admits_it():
    agent = build_agent(trigger_state="exceeded", evidence_ok=False)
    run = agent.run("report", 85.05, 27.76, AS_OF)
    assert run.state == PRIMED_UNOBSERVED
    assert "छैन" in run.advisory_ne, "the advisory must say it cannot see"
    assert run.dispatch is not None


def test_nothing_to_say_produces_no_dispatch():
    agent = build_agent(trigger_state="below", evidence_ok=False)
    run = agent.run("report", 85.05, 27.76, AS_OF)
    assert run.state == ABSTAIN
    assert run.dispatch is None


def test_without_the_model_the_agent_still_runs_but_routes_nothing():
    """The litmus test at the agent level: no model, no authority, no addressee."""
    agent = build_agent(trigger_state="exceeded", evidence_ok=True, model=None)
    run = agent.run("a rural road on a slope above a highway has failed", 85.05, 27.76, AS_OF)
    assert run.routing is not None and run.routing.case_id is None
    assert run.dispatch is not None and run.dispatch.needs_review is True


def test_trace_serialises_for_the_demo():
    import json
    agent = build_agent(trigger_state="exceeded", evidence_ok=True)
    run = agent.run("report", 85.05, 27.76, AS_OF)
    payload = json.loads(run.to_json())
    assert payload["state"] == PRIMED_CONFIRMED
    assert len(payload["trace"]) == 6
    assert payload["as_of"] == AS_OF.isoformat()


def test_a_hung_tool_times_out_and_the_agent_carries_on():
    """A single blocked network read must never hang the whole run."""
    import time as _time
    agent = build_agent(trigger_state="exceeded", evidence_ok=True)
    agent.tool_timeout = 1

    def hang(run):
        _time.sleep(10)
        return "never returned"

    agent.tool_rainfall_trigger = hang
    run = agent.run("report", 85.05, 27.76, AS_OF)
    rain = next(t for t in run.trace if t.name == "rainfall_trigger")
    assert rain.ok is False and "timed out" in rain.result
    # The evidence tool still succeeded, so the agent has something to say and says
    # only that: fresh evidence, no trigger reading. It does not invent a trigger.
    assert run.state == MONITORED
    assert len(run.trace) == 6, "the remaining steps still ran"


def test_a_tool_exception_is_recorded_not_swallowed():
    agent = build_agent(trigger_state="exceeded", evidence_ok=True)

    def boom(run):
        raise RuntimeError("upstream 502 after retries")

    agent.tool_ground_evidence = boom
    run = agent.run("report", 85.05, 27.76, AS_OF)
    step = next(t for t in run.trace if t.name == "ground_evidence")
    assert step.ok is False and "502" in step.result
    # The trigger says primed and the observation step failed. That IS the
    # primed-unobserved condition: we know the slope is primed and we could not look.
    # Reporting it is the whole point; silently downgrading to "nothing to say" would
    # be the failure mode this project exists to avoid.
    assert run.state == PRIMED_UNOBSERVED
