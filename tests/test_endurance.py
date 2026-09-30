"""Wet, flat, cracked, or switched off: what the software does, and what it admits it cannot.

The tests that matter are the ones about the last 5% of a battery and about treating silence as
evidence rather than as absence of harm.
"""
from __future__ import annotations

import pytest

from pahiro import endurance as E


# ---- the mode ladder ---------------------------------------------------------------------------

def test_a_healthy_charged_phone_sheds_nothing():
    p = E.plan(E.State(battery_pct=90, charging=True))
    assert p.mode is E.Mode.NORMAL
    assert p.model_enabled and p.screen_on
    assert p.shed == []


def test_an_unknown_battery_is_treated_as_conserve_not_as_normal():
    """A phone that cannot say how much power it has may be at 3%. Assuming the best loses it."""
    assert E.choose_mode(E.State(battery_pct=None)) is E.Mode.CONSERVE
    assert E.choose_mode(E.State()) is E.Mode.CONSERVE


def test_the_model_is_the_first_thing_to_die():
    """Nothing that saves a life depends on it, so shedding it is free. That is the ordering."""
    conserve = E.plan(E.State(battery_pct=20))
    assert conserve.model_enabled is False
    assert "on-device model" in conserve.shed[0]
    # and the radio is still on: the thing that carries the message survives the thing that
    # prettifies it
    assert conserve.radios


def test_capabilities_are_shed_in_a_published_order():
    normal = E.plan(E.State(battery_pct=90))
    conserve = E.plan(E.State(battery_pct=20))
    gasp = E.plan(E.State(battery_pct=4))
    silent = E.plan(E.State(battery_pct=0.5))
    # Each rung keeps fewer radios than the one above. Not a strict subset, and that is a
    # design decision rather than an oversight: at the last gasp you keep SMS - the one rung
    # that crosses any distance with no chain - and drop Wi-Fi Aware, which needs strangers in
    # a line. One transmission left is worth more spent on the rung that does not need help.
    assert len(gasp.radios) < len(conserve.radios) < len(normal.radios), \
        "the ladder must shed monotonically or it is not a ladder"
    assert silent.radios == ()
    assert gasp.radios == ("sms",), "one rung left, and it is the one that needs no chain"
    assert len(conserve.shed) < len(gasp.shed) < len(silent.shed)


def test_the_mode_boundaries():
    assert E.choose_mode(E.State(battery_pct=26)) is E.Mode.NORMAL
    assert E.choose_mode(E.State(battery_pct=25)) is E.Mode.CONSERVE
    assert E.choose_mode(E.State(battery_pct=6)) is E.Mode.CONSERVE
    assert E.choose_mode(E.State(battery_pct=5)) is E.Mode.LAST_GASP
    assert E.choose_mode(E.State(battery_pct=1.5)) is E.Mode.LAST_GASP
    assert E.choose_mode(E.State(battery_pct=1)) is E.Mode.SILENT


def test_charging_overrides_a_flat_battery():
    """Plugged in is plugged in, whatever the percentage says."""
    assert E.choose_mode(E.State(battery_pct=3, charging=True)) is E.Mode.NORMAL


def test_duty_cycling_is_where_the_hours_come_from():
    """A continuous scan is the most expensive thing this app does, and it is optional."""
    assert E.plan(E.State(battery_pct=90)).scan_duty_cycle == 1.0
    assert E.plan(E.State(battery_pct=20)).scan_duty_cycle == 0.25
    assert E.plan(E.State(battery_pct=4)).scan_duty_cycle == 0.0
    assert E.plan(E.State(battery_pct=0.5)).scan_duty_cycle == 0.0


def test_conserve_mode_buys_measurable_hours():
    """Rough numbers, but the RATIO is the point and it is large."""
    normal = E.estimated_hours(E.Mode.NORMAL, 20.0)
    conserve = E.estimated_hours(E.Mode.CONSERVE, 20.0)
    assert conserve > normal * 5, f"conserving bought only {conserve / normal:.1f}x"


def test_a_silent_phone_lasts_at_least_as_long_as_one_still_transmitting():
    """Once scanning stops, the difference between the two is the transmission burst - which this
    deliberately rough model does not capture. So the assertion is >=, and the caveat is here
    rather than hidden: the useful output of `estimated_hours` is the RATIO between modes, not
    the absolute number."""
    silent = E.estimated_hours(E.Mode.SILENT, 5.0)
    gasp = E.estimated_hours(E.Mode.LAST_GASP, 5.0)
    assert silent >= gasp
    assert gasp > 0


def test_zero_battery_is_zero_hours_and_does_not_divide_by_zero():
    assert E.estimated_hours(E.Mode.SILENT, 0.0) == 0.0


# ---- wet, cracked, spoken ----------------------------------------------------------------------

def test_a_wet_screen_forces_a_spoken_interface():
    """Touches do not register on a wet screen, so the interface must stop needing them."""
    wet = E.plan(E.State(battery_pct=80, wet=True))
    assert wet.spoken_only is True
    dry = E.plan(E.State(battery_pct=80, wet=False))
    assert dry.spoken_only is False


def test_a_cracked_display_also_falls_back_to_voice():
    cracked = E.plan(E.State(battery_pct=80, screen_usable=False))
    assert cracked.spoken_only is True
    assert cracked.screen_on is False


def test_a_wet_phone_still_transmits_even_when_it_cannot_be_touched():
    """Ingress does not stop the radio. The message must keep going out."""
    wet = E.plan(E.State(battery_pct=80, wet=True))
    assert wet.radios, "a wet phone is still a working relay"


# ---- the last gasp, in order -------------------------------------------------------------------

def test_the_position_is_written_to_disk_before_anything_is_transmitted():
    """A durable write survives a shutdown. A transmission does not, and can die mid-frame."""
    steps = E.last_gasp_steps((28.21, 83.98), b"sealed")
    assert steps[0]["action"] == "persist_position"
    assert "survives a shutdown" in steps[0]["why"]
    assert [s["action"] for s in steps].index("persist_position") < \
           [s["action"] for s in steps].index("emit_final_beacon")


def test_a_phone_that_never_got_a_fix_records_that_fact():
    """So nobody later reads the absence of a position as refusal or as a bug."""
    steps = E.last_gasp_steps(None, b"sealed")
    assert steps[0]["action"] == "persist_no_fix"
    assert "refusal" in steps[0]["why"]


def test_the_last_gasp_ends_waiting_for_a_charger_not_transmitting():
    steps = E.last_gasp_steps((1.0, 2.0), b"sealed")
    assert steps[-1]["action"] == "await_charger"
    assert "dies doing it" in steps[-1]["why"]


def test_a_final_beacon_is_emitted_once_and_only_if_there_is_one():
    assert any(s["action"] == "emit_final_beacon"
               for s in E.last_gasp_steps((1.0, 2.0), b"sealed"))
    assert not any(s["action"] == "emit_final_beacon"
                   for s in E.last_gasp_steps((1.0, 2.0), None))


# ---- silence is evidence, not absence of harm --------------------------------------------------

def test_a_missed_interval_or_two_is_not_yet_an_escalation():
    late = E.quiet_is_a_signal(25.0, expected_interval_min=15.0)
    assert late["state"] == "late"
    assert "Not yet a reason to escalate" in late["note"]


def test_prolonged_silence_is_labelled_not_confirmed_alive_never_not_alive():
    quiet = E.quiet_is_a_signal(120.0, expected_interval_min=15.0)
    assert quiet["state"] == "quiet"
    assert "not confirmed alive" in quiet["note"]
    assert "not alive" in quiet["note"], "the phrase it must avoid is named explicitly"
    assert "uninformative" in quiet["note"]


def test_never_heard_is_not_treated_as_harm():
    never = E.quiet_is_a_signal(None)
    assert never["state"] == "never_heard"
    assert "not evidence of harm" in never["note"]


def test_recent_contact_reads_as_current():
    assert E.quiet_is_a_signal(5.0, expected_interval_min=15.0)["state"] == "current"


# ---- the honest ledger -------------------------------------------------------------------------

def test_the_physical_limits_are_stated_and_include_the_ones_that_hurt():
    limits = E.limits_summary()
    names = {x["name"] for x in limits}
    for required in ("powered_off", "wet_touchscreen", "cracked_display", "battery_empty",
                     "wet_speaker", "bluetooth_through_rock"):
        assert required in names, f"{required} must be admitted, not hidden"
    assert "transmits nothing" in E.PHYSICAL_LIMITS["powered_off"]


def test_every_admitted_limit_names_the_design_choice_it_forced():
    """A limit with no consequence is decoration. Each one must point at what was built for it."""
    assert "physical button" in E.PHYSICAL_LIMITS["wet_touchscreen"]
    assert "spoken" in E.PHYSICAL_LIMITS["wet_touchscreen"]
    assert "persisted" in E.PHYSICAL_LIMITS["no_gps_indoors"]
    assert "RSSI" in E.PHYSICAL_LIMITS["no_gps_indoors"]


def test_the_plan_serialises_for_the_panel():
    d = E.plan(E.State(battery_pct=4)).as_dict()
    assert d["mode"] == "last gasp"
    assert d["emit_final_beacon"] is True
    assert isinstance(d["radios"], list)
    assert d["why"]


# ---- the total blackout ------------------------------------------------------------------------

def test_with_no_sim_no_tower_and_no_charge_the_radio_is_gone_but_the_courier_is_not():
    plan = E.blackout_plan(has_sim=False, has_signal=False, battery_pct=0.5,
                           last_known=(28.21, 83.98))
    assert "courier" in plan["remaining_transports"], "the rung that needs nothing"
    assert "ble" not in plan["remaining_transports"]
    assert any("no SIM" in x for x in plan["unrecoverable"])
    assert any("no cell signal" in x for x in plan["unrecoverable"])


def test_the_blackout_names_what_software_cannot_bring_back():
    """Four of the five things are gone and none of them is recoverable from code."""
    plan = E.blackout_plan(has_sim=False, has_signal=False, battery_pct=None, last_known=None)
    assert len(plan["unrecoverable"]) >= 2
    assert "cannot reach anybody" in plan["honest_summary"]


def test_with_a_charged_phone_but_no_sim_the_radios_still_work():
    """People forget this: BLE and Wi-Fi Aware need neither a SIM nor a tower."""
    plan = E.blackout_plan(has_sim=False, has_signal=False, battery_pct=60, last_known=None)
    assert "ble" in plan["remaining_transports"]
    assert "wifi_aware" in plan["remaining_transports"]
    assert not any("1%" in x for x in plan["unrecoverable"])


def test_a_moment_of_power_is_spent_on_the_message_not_the_interface():
    plan = E.blackout_plan(has_sim=True, has_signal=True, battery_pct=0.4,
                           last_known=(1.0, 2.0), charge_available=True)
    actions = [s["action"] for s in plan["steps"]]
    assert "persist_position" in actions
    assert "boot_on_charge" in actions
    assert actions.index("persist_position") < actions.index("boot_on_charge"), \
        "the durable write comes first because a transmission can be interrupted"
    assert "tracker and a toy" in plan["steps"][1]["why"]


def test_when_the_phone_is_dead_the_answer_is_a_piece_of_paper():
    plan = E.blackout_plan(has_sim=False, has_signal=False, battery_pct=0.0,
                           last_known=(28.20961, 83.98561))
    written = [s for s in plan["steps"] if s["action"] == "write_it_down"]
    assert written, "a phone that will not switch on is a note waiting to be written"
    assert "28.20961" in written[0]["why"]


def test_the_blackout_always_records_the_silence_as_a_fact():
    for kwargs in (dict(has_sim=False, has_signal=False, battery_pct=None, last_known=None),
                   dict(has_sim=True, has_signal=True, battery_pct=90, last_known=(1, 2))):
        plan = E.blackout_plan(**kwargs)
        assert any(s["action"] == "radio_silence_is_a_recorded_fact" for s in plan["steps"])
