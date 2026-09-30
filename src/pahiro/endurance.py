"""What the phone does when it is wet, flat, cracked, or switched off.

WHY THIS EXISTS
---------------
Every design above assumes a working handset. In an actual landslide the handset is in a pocket
that has been under water, or on 4% battery because the power went three days ago, or face-down in
mud with a cracked screen. A system that only works on a charged, dry, undamaged phone has quietly
excluded the circumstances it was built for.

This module is the honest ledger of those failures, split into two columns: **what software can
do about it**, implemented here, and **what software cannot do**, stated rather than papered over.

WHAT SOFTWARE CANNOT FIX
------------------------
These are physics and materials, and no amount of code changes them:

    a powered-off phone transmits nothing, at any power level, on any band
    a wet capacitive touchscreen does not register touches
    a cracked display does not show anything, whatever is rendered
    a battery at 0% is not running a background scan
    water in a speaker makes speech unintelligible

Stating them is not defeatism. It is what stops the design from depending on any of them - which
is why the SOS is reachable from a **physical button**, why the instructions are **spoken** as
well as shown, why the last known position is **persisted to disk**, and why a phone that has gone
quiet is treated as a data point rather than as a gap.

THE FOUR MODES
--------------
Battery is the binding constraint, so the radio and the processor are spent in a strict order and
shed in the reverse one:

    NORMAL      everything: mesh, beacon, map, model, screen
    CONSERVE    the model goes first, then the map, then the screen dims
    LAST_GASP   one job only - get the final position out, sealed, and stop
    SILENT      radio off. Persist, and wait for a charger.

The ordering is the opinion: **the model is the first thing to die**, because nothing that
matters depends on it. That is the same rule `offline_ai.py` enforces from the other direction -
nothing life-saving is behind the AI - and it is what makes shedding it free.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum


class Mode(IntEnum):
    """Lower is more capable. The ladder is shed in reverse order, cheapest capability first."""

    NORMAL = 0
    CONSERVE = 1
    LAST_GASP = 2
    SILENT = 3

    @property
    def label(self) -> str:
        return self.name.lower().replace("_", " ")


# Battery thresholds, as percentages.
CONSERVE_AT_PCT = 25.0
LAST_GASP_AT_PCT = 5.0
SILENT_AT_PCT = 1.0

# Discharge the radio itself causes. Measured-ish from BLE scanning behaviour on handsets: a
# continuous scan is the single most expensive thing this app can do, and duty-cycling it is the
# largest saving available.
SCAN_CONTINUOUS_MW = 90.0
SCAN_DUTY_MW = 12.0
RADIO_IDLE_MW = 2.0


@dataclass
class State:
    """What the phone knows about itself. Anything unknown is None, never a guess."""

    battery_pct: float | None = None
    charging: bool = False
    wet: bool = False                 # ingress detected, or the user said so
    screen_usable: bool = True
    has_fix: bool = True
    minutes_since_uplink: float | None = None

    def unknown(self) -> list[str]:
        out = []
        if self.battery_pct is None:
            out.append("battery level unknown")
        return out


@dataclass
class Plan:
    """What this mode does, and what it has given up."""

    mode: Mode
    radios: tuple[str, ...]
    scan_duty_cycle: float            # 0..1 - fraction of time listening
    model_enabled: bool
    screen_on: bool
    spoken_only: bool
    persist_position: bool
    emit_final_beacon: bool
    shed: list[str] = field(default_factory=list)
    why: str = ""

    def as_dict(self) -> dict:
        return {
            "mode": self.mode.label,
            "radios": list(self.radios),
            "scan_duty_cycle": round(self.scan_duty_cycle, 3),
            "model_enabled": self.model_enabled,
            "screen_on": self.screen_on,
            "spoken_only": self.spoken_only,
            "persist_position": self.persist_position,
            "emit_final_beacon": self.emit_final_beacon,
            "shed": self.shed,
            "why": self.why,
        }


def choose_mode(state: State) -> Mode:
    """Pick the least destructive mode that keeps the phone useful.

    An unknown battery is treated as **CONSERVE, not NORMAL**. A phone that cannot tell us how much
    power it has may be at 3%, and assuming the best is how the last beacon is lost.
    """
    if state.charging:
        return Mode.NORMAL
    if state.battery_pct is None:
        return Mode.CONSERVE
    if state.battery_pct <= SILENT_AT_PCT:
        return Mode.SILENT
    if state.battery_pct <= LAST_GASP_AT_PCT:
        return Mode.LAST_GASP
    if state.battery_pct <= CONSERVE_AT_PCT:
        return Mode.CONSERVE
    return Mode.NORMAL


def plan(state: State) -> Plan:
    """Translate a state into behaviour, shedding capabilities in a fixed, published order."""
    mode = choose_mode(state)
    wet = state.wet
    # A wet screen means touches do not register, so the interface has to stop needing them.
    spoken_only = wet or not state.screen_usable

    if mode is Mode.NORMAL:
        return Plan(
            mode=mode, radios=("wifi_aware", "ble", "sms"), scan_duty_cycle=1.0,
            model_enabled=True, screen_on=state.screen_usable, spoken_only=spoken_only,
            persist_position=False, emit_final_beacon=False,
            shed=[], why="charged or healthy: everything runs",
        )

    if mode is Mode.CONSERVE:
        return Plan(
            mode=mode, radios=("wifi_aware", "ble"), scan_duty_cycle=0.25,
            model_enabled=False, screen_on=False, spoken_only=True,
            persist_position=True, emit_final_beacon=False,
            shed=["on-device model", "map rendering", "screen"],
            why=("the model dies first because nothing that saves a life depends on it; then the "
                 "map goes, then the screen. Listening drops to a quarter duty cycle, which is "
                 "the single largest saving available to this app."),
        )

    if mode is Mode.LAST_GASP:
        # ONE rung, and it is SMS. With a single transmission left, spending it on a 30 m
        # advertisement that needs a stranger standing in the right place is waste: SMS crosses
        # any distance in one hop with no chain and no help. The ladder is meant to shed
        # monotonically, and keeping two radios here broke that.
        return Plan(
            mode=mode, radios=("sms",), scan_duty_cycle=0.0,
            model_enabled=False, screen_on=False, spoken_only=True,
            persist_position=True, emit_final_beacon=True,
            shed=["wifi_aware", "ble", "model", "map", "screen", "scanning"],
            why=("one job left: write the last position to disk and get it out sealed. A phone "
                 "that reports where it was and then dies is worth more than one that dies "
                 "announcing that it is still alive."),
        )

    return Plan(
        mode=mode, radios=(), scan_duty_cycle=0.0,
        model_enabled=False, screen_on=False, spoken_only=True,
        persist_position=True, emit_final_beacon=False,
        shed=["all radios", "the last radio", "model", "map", "screen", "scanning",
              "everything"],
        why=("radio off. A handset at 1% that transmits burns the reserve that would have "
             "restarted it. Persist, and wait for a charger."),
    )


# ---- the failures software cannot fix -----------------------------------------------------------

PHYSICAL_LIMITS: dict[str, str] = {
    "powered_off": "a phone that is switched off transmits nothing, on any band, at any power",
    "wet_touchscreen": "a wet capacitive screen does not register touches - hence the physical "
                       "button and the spoken instruction",
    "cracked_display": "a broken display shows nothing, whatever is rendered",
    "battery_empty": "a battery at 0% runs no scan",
    "wet_speaker": "water in a speaker makes speech unintelligible",
    "no_gps_indoors": "a buried or indoor handset may get no fix at all - hence RSSI-only "
                      "locating and a persisted last-known position",
    "bluetooth_through_rock": "Bluetooth does not go through rock or saturated soil",
}


def limits_summary() -> list[dict]:
    return [{"name": k, "statement": v} for k, v in PHYSICAL_LIMITS.items()]


# ---- the last gasp, in order -------------------------------------------------------------------

def last_gasp_steps(last_known: tuple[float, float] | None,
                    sealed_payload: bytes | None) -> list[dict]:
    """What to do, in this order, when the phone is about to die.

    Order is the whole point. Writing the position to disk survives a shutdown; a radio
    transmission does not, and can be interrupted by the phone dying mid-frame. So the durable
    write happens **first** and the transmit second, and a failure to transmit still leaves a
    record for whoever finds the handset.
    """
    steps: list[dict] = []
    if last_known is not None:
        steps.append({
            "action": "persist_position",
            "lat": last_known[0], "lon": last_known[1],
            "why": "survives a shutdown; a transmission does not",
        })
    else:
        steps.append({
            "action": "persist_no_fix",
            "why": "no fix ever obtained - record that, so nobody reads the silence as a refusal",
        })
    steps.append({
        "action": "stop_everything_else",
        "why": "the model, the map and the screen cost power and add nothing now",
    })
    if sealed_payload is not None:
        steps.append({
            "action": "emit_final_beacon",
            "bytes": len(sealed_payload),
            "why": "one frame, sealed, then the radio goes quiet",
        })
    steps.append({
        "action": "await_charger",
        "why": "a 1% phone that keeps transmitting dies doing it",
    })
    return steps


def quiet_is_a_signal(minutes_since_last_contact: float | None,
                      expected_interval_min: float = 15.0) -> dict:
    """What silence means.

    A phone that has stopped calling has not necessarily stopped needing help - but a phone with a
    flat battery also cannot tell us it went flat. So absence is measured, never assumed, and it is
    labelled with the reason it might be benign. This is the honest half of "is the person still
    alive": the evidence is the last beacon, and the absence of the next one.
    """
    if minutes_since_last_contact is None:
        return {"state": "never_heard", "note": "no contact at any point - not evidence of harm"}
    missed = minutes_since_last_contact / expected_interval_min
    if missed < 1.5:
        return {"state": "current", "missed_intervals": round(missed, 1)}
    if missed < 4:
        return {"state": "late", "missed_intervals": round(missed, 1),
                "note": "could be terrain, could be battery. Not yet a reason to escalate."}
    return {
        "state": "quiet",
        "missed_intervals": round(missed, 1),
        "note": ("the handset has been silent for several intervals. The last beacon is the "
                 "evidence; the silence is uninformative. Do not record this as 'not alive' - "
                 "record it as 'not confirmed alive'."),
    }


# ---- spend, and how long it lasts ---------------------------------------------------------------

def estimated_hours(mode: Mode, battery_pct: float, capacity_mah: float = 3000.0,
                    nominal_v: float = 3.85) -> float:
    """Rough remaining life in this mode. Rough is the honest word for it.

    Handset discharge depends on the screen, the age of the cell and the temperature, none of which
    this knows. The useful output is not the number but the *ratio* between modes: it is what shows
    that duty-cycling the scan buys hours, which is the whole reason CONSERVE exists.
    """
    if battery_pct <= 0:
        return 0.0
    plan_for_mode = plan(State(battery_pct=battery_pct, charging=False))
    if plan_for_mode.mode is not mode:
        plan_for_mode = _plan_for(mode)
    draw_mw = RADIO_IDLE_MW + SCAN_CONTINUOUS_MW * plan_for_mode.scan_duty_cycle
    if plan_for_mode.screen_on:
        draw_mw += 350.0
    if plan_for_mode.model_enabled:
        draw_mw += 1500.0
    if draw_mw <= 0:
        return math.inf
    remaining_mwh = capacity_mah * nominal_v * (battery_pct / 100.0)
    return remaining_mwh / draw_mw


def _plan_for(mode: Mode) -> Plan:
    """The behaviours for a mode, independent of the battery level that would select it."""
    return {
        Mode.NORMAL: Plan(Mode.NORMAL, ("wifi_aware", "ble", "sms"), 1.0, True, True, False,
                          False, False),
        Mode.CONSERVE: Plan(Mode.CONSERVE, ("wifi_aware", "ble"), 0.25, False, False, True,
                            True, False),
        Mode.LAST_GASP: Plan(Mode.LAST_GASP, ("sms",), 0.0, False, False, True,
                             True, True),
        Mode.SILENT: Plan(Mode.SILENT, (), 0.0, False, False, True, True, False),
    }[mode]


# ---- the total blackout -------------------------------------------------------------------------

def blackout_plan(*, has_sim: bool, has_signal: bool, battery_pct: float | None,
                  last_known: tuple[float, float] | None,
                  charge_available: bool = False) -> dict:
    """What is left when there is no tower, no SIM, no network and no charge.

    This is not a hypothetical in the districts this is built for. It is a Tuesday in a monsoon.

    The honest answer is that **four of the five things are gone and software cannot bring any of
    them back**: no SIM means no SMS, no tower means the same, a dead cell runs no radio. What
    software controls is the fifth thing, and it is the one that decides whether the person is
    found:

        what the person carries out, and whether a phone that gets 60 seconds of power uses them
        well enough to be worth carrying.

    So this returns what remains, in the order it should be done, and names what is unrecoverable
    rather than pretending otherwise.
    """
    gone: list[str] = []
    if not has_sim:
        gone.append("no SIM: the SMS rung does not exist")
    if not has_signal:
        gone.append("no cell signal: SMS is unavailable even with a SIM")
    if battery_pct is not None and battery_pct <= 1.0:
        gone.append("a handset at 1% transmits nothing useful and burns its own reserve trying")

    if battery_pct is None:
        usable_radio = True
        note = "battery unknown, so assume it works until it does not"
    else:
        usable_radio = battery_pct > 1.0
        note = "radio usable" if usable_radio else "radio is gone"

    remaining: list[str] = []
    if usable_radio:
        remaining.append("ble")
        remaining.append("wifi_aware")
    # A courier needs nothing: not a SIM, not a tower, not a charge, not a radio.
    remaining.append("courier")

    steps: list[dict] = []
    steps.append({
        "action": "persist_position",
        "why": "the only thing that survives the phone. A durable write outlives a transmission.",
        "have_position": last_known is not None,
    })
    if charge_available:
        steps.append({
            "action": "boot_on_charge",
            "why": ("60 seconds of power is enough to write the position and emit one sealed "
                    "frame before the phone dies again. Doing that FIRST, before anything the "
                    "user might want to look at, is the difference between a tracker and a toy."),
        })
    steps.append({
        "action": "hand_to_a_person",
        "why": ("the rung that never fails. Somebody is already walking out, and the handset - "
                "or a written note - is what they carry."),
    })
    if last_known is not None and not usable_radio:
        steps.append({
            "action": "write_it_down",
            "why": (f"{last_known[0]:.5f}, {last_known[1]:.5f} on paper. A phone that will not "
                    f"switch on is a note waiting to be written."),
        })
    steps.append({
        "action": "radio_silence_is_a_recorded_fact",
        "why": ("record that the handset went quiet and why it might have, so nobody later reads "
                "the silence as a decision not to call."),
    })

    return {
        "unrecoverable": gone,
        "battery_note": note,
        "remaining_transports": remaining,
        "steps": steps,
        "honest_summary": (
            "With no SIM, no tower and no charge, software cannot reach anybody. What it can do "
            "is make the last known position durable, make a phone that gets a moment of power "
            "spend it on the message rather than the interface, and hand the person something "
            "worth carrying."
        ),
    }
