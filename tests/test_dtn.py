"""The transport ladder and its custody rules.

The properties under test are the ones that decide whether a message survives a valley: a bundle
is never dropped for want of a radio, an SOS never waits for a person to walk, and an
acknowledgement - not a forward - is what releases a copy.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pahiro.mesh import dtn
from pahiro.mesh.protocol import PRIORITY

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


def sos(**kw) -> dtn.Bundle:
    base = dict(id="b1", kind="sos", body="SOS six trapped at KM 42", created_at=NOW)
    base.update(kw)
    return dtn.Bundle(**base)


# ---- the ladder is what it claims to be ----------------------------------------------------------

def test_the_ladder_is_ordered_by_range_nearest_first():
    """The order is the strategy: exhaust the cheap short hop before spending the long one."""
    ranges = [t.range_m for t in dtn.LADDER]
    assert ranges == sorted(ranges)
    assert [t.name for t in dtn.LADDER] == ["ble", "wifi_aware", "sms", "courier"]


def test_only_the_courier_needs_nothing_at_all():
    """The floor of the ladder is a person walking, which is always available."""
    assert dtn.COURIER.needs == "none"
    assert all(t.needs in ("cell", "radio") for t in dtn.LADDER if t.name != "courier")


def test_the_advertisement_seat_carries_exactly_the_beacon_payload():
    """The 20-byte rung must match the frame beacon.py actually emits, or it cannot carry it."""
    from pahiro.mesh import beacon

    assert dtn.BLE.max_payload == beacon.MAX_AD_BYTES - 4
    assert dtn.BLE.max_payload < beacon.ENCODED_BYTES + 4 or beacon.ENCODED_BYTES <= 20


def test_the_ladder_lists_itself_for_documentation():
    rows = dtn.ladder_summary()
    assert [r["name"] for r in rows] == ["ble", "wifi_aware", "sms", "courier"]
    assert rows[-1]["range_m"] is None, "the courier has no range limit and says so"
    assert all(r["note"] for r in rows)


# ---- choosing ------------------------------------------------------------------------------------

def test_an_sos_takes_the_fastest_transport_available_not_the_cheapest():
    """A distress call that arrives in six hours by courier is a record, not a rescue."""
    c = dtn.choose(sos(body="SOS 6 trapped"), available={"ble", "courier"})
    assert c.transport.name == "ble", "2 s beats 6 h regardless of cost"
    assert "SOS" in c.reason


def test_a_full_text_sos_cannot_ride_a_twenty_byte_advertisement():
    """A real constraint, not a bug: this is WHY the beacon codec exists.

    "SOS six trapped at KM 42" is 24 bytes and a BLE advertisement carries 20. The text SOS must
    take a bigger hop; only the packed beacon frame fits on the smallest rung.
    """
    text = sos()
    assert text.size_bytes() > dtn.BLE.max_payload
    c = dtn.choose(text, available={"ble", "wifi_aware", "courier"})
    assert c.transport.name == "wifi_aware"

    packed = sos(body="b:20")   # what the beacon codec actually puts on the wire
    assert packed.size_bytes() <= dtn.BLE.max_payload
    assert dtn.choose(packed, available={"ble", "courier"}).transport.name == "ble"


def test_an_sos_prefers_wifi_over_ble_when_it_needs_the_payload():
    """The body is too big for 20 bytes, so the SOS cannot climb onto the advertisement."""
    b = sos(body="x" * 300)
    c = dtn.choose(b, available={"ble", "wifi_aware"})
    assert c.transport.name == "wifi_aware"
    assert c.transport.max_payload >= b.size_bytes()


def test_ordinary_traffic_climbs_the_ladder_rather_than_reaching_for_sms():
    """A chat message a stranger could carry must not cost the sender money."""
    chat = dtn.Bundle(id="c1", kind="chat", body="we are at the bridge", created_at=NOW)
    c = dtn.choose(chat, available={"ble", "wifi_aware", "sms", "courier"})
    assert c.transport.name == "ble"


def test_an_acknowledgement_rides_the_cheapest_thing_that_fits():
    ack = dtn.Bundle(id="a1", kind="ack", body="ok", created_at=NOW)
    c = dtn.choose(ack, available={"ble", "wifi_aware", "sms"})
    assert c.transport.name == "ble", "acks are not cargo"
    assert "lowest ladder rung" in c.reason


def test_no_transport_at_all_raises_and_never_returns_a_plan_to_discard():
    with pytest.raises(dtn.NoTransport):
        dtn.choose(sos(), available=set())


def test_a_bundle_too_large_for_every_available_carrier_says_so_precisely():
    big = sos(body="x" * 400)
    with pytest.raises(dtn.NoTransport) as exc:
        dtn.choose(big, available={"ble"})
    assert "400 bytes" in str(exc.value)
    assert "at most 20" in str(exc.value)


def test_a_short_hop_is_preferred_even_when_it_cannot_span_the_distance():
    """A 30 m hop that works beats a 200 m hop that does not exist yet: that is what relays are."""
    chat = dtn.Bundle(id="c2", kind="chat", body="hello", created_at=NOW)
    c = dtn.choose(chat, available={"ble", "courier"}, distance_m=9000)
    assert c.transport.name == "ble"
    # the courier spans it; the honest note is that this relies on relays
    assert not c.reachable
    assert "relies on relays" in c.reason


def test_a_bundle_with_no_hops_left_is_refused():
    with pytest.raises(dtn.NoTransport) as exc:
        dtn.choose(sos(), available={"ble"}, hops_left=0)
    assert "no hops left" in str(exc.value)


# ---- custody -------------------------------------------------------------------------------------

def test_a_bundle_is_not_dropped_without_an_acknowledgement():
    """The failure this prevents: forward, drop, and the next hop fails. That is Tuesday."""
    store = dtn.Custody("dev-a")
    store.accept(sos())
    store.hand_off("b1", dtn.BLE, "dev-b", NOW)
    with pytest.raises(PermissionError) as exc:
        store.release("b1")
    assert "nobody has acknowledged" in str(exc.value)
    assert "b1" in store, "the copy must still be here"


def test_an_acknowledgement_is_what_releases_the_copy():
    store = dtn.Custody("dev-a")
    store.accept(sos())
    store.hand_off("b1", dtn.BLE, "dev-b", NOW)
    assert store.acknowledge("b1", "dev-b") is True
    assert store.release("b1") is True
    assert "b1" not in store


def test_an_acknowledgement_that_arrives_late_is_a_no_op_not_an_error():
    """Acks cross paths and arrive after a copy is gone. That is normal, not a fault."""
    store = dtn.Custody("dev-a")
    assert store.acknowledge("never-seen", "dev-b") is False


def test_the_same_bundle_over_two_transports_is_accepted_once():
    """This is what stops one SOS arriving by BLE and then again by SMS being two people."""
    store = dtn.Custody("dev-a")
    assert store.accept(sos()) is True
    assert store.accept(sos()) is False, "same id over a second transport"


def test_a_delivered_bundle_is_not_re_accepted_by_a_third_path():
    store = dtn.Custody("dev-a")
    store.accept(sos())
    store.hand_off("b1", dtn.BLE, "dev-b", NOW)
    store.acknowledge("b1", "dev-b")
    store.release("b1")
    assert store.accept(sos()) is False
    assert "b1" in store.delivered


def test_handing_off_records_the_path_and_spends_a_hop():
    store = dtn.Custody("dev-a")
    store.accept(sos())
    held = store.hand_off("b1", dtn.BLE, "dev-b", NOW)
    assert held.bundle.hops == 1
    assert held.bundle.path == ["dev-a"]
    assert store.offered_to("b1") == "dev-b"


def test_a_full_store_drops_chat_to_keep_an_sos():
    """A store that refuses an SOS because it is holding gossip has failed at its only job."""
    store = dtn.Custody("dev-a", capacity=1)
    store.accept(dtn.Bundle(id="chat-1", kind="chat", body="rumours", created_at=NOW))
    assert store.accept(sos()) is True
    assert "chat-1" not in store
    assert "b1" in store


def test_a_full_store_of_equally_urgent_work_says_it_cannot_take_more():
    """Dropping an SOS to store another SOS is not an improvement, so it refuses loudly."""
    store = dtn.Custody("dev-a", capacity=1)
    store.accept(sos())
    with pytest.raises(MemoryError):
        store.accept(sos(id="b2", body="SOS second group"))


def test_priority_order_comes_from_the_protocol_not_from_here():
    """One definition of what outranks what, or the radio and the store will disagree."""
    assert PRIORITY["sos"] < PRIORITY["chat"]
    assert sos().priority == PRIORITY["sos"]


def test_expiry_is_the_only_other_way_a_bundle_leaves():
    store = dtn.Custody("dev-a", max_age=timedelta(hours=48))
    store.accept(sos(created_at=NOW - timedelta(hours=60)))
    assert store.expire(NOW) == ["b1"]
    assert "b1" not in store


def test_the_offer_queue_is_urgent_first_then_oldest_first():
    store = dtn.Custody("dev-a")
    store.accept(dtn.Bundle(id="chat-1", kind="chat", body="a", created_at=NOW))
    store.accept(dtn.Bundle(id="chat-2", kind="chat", body="b", created_at=NOW - timedelta(minutes=5)))
    store.accept(sos(id="sos-1", created_at=NOW - timedelta(minutes=1)))
    queue = [b.id for b in store.pending(NOW)]
    assert queue[0] == "sos-1", "the distress call leads regardless of arrival order"
    # within a priority, the older one goes first: it has waited longest
    assert queue[1:] == ["chat-2", "chat-1"]


def test_an_acknowledged_bundle_leaves_the_offer_queue_without_being_dropped():
    store = dtn.Custody("dev-a")
    store.accept(sos())
    store.acknowledge("b1", "dev-b")
    assert store.pending(NOW) == []
    assert "b1" in store, "held until release, but no longer offered"


# ---- the relay decision -------------------------------------------------------------------------

def test_the_plan_holds_rather_than_drops_when_nothing_is_available():
    """The single most important property: no transport means held, never discarded."""
    store = dtn.Custody("dev-a")
    store.accept(sos())
    plans = dtn.plan_offers(store, available=set())
    assert len(plans) == 1
    assert plans[0].transport is None
    assert plans[0].held is True
    assert "b1" in store, "the message is still here for the next transport that appears"
    assert "no transport is available" in plans[0].reason


def test_the_plan_uses_the_courier_when_that_is_all_there_is():
    """Somebody is always walking out. That is the floor of the ladder and it never fails."""
    store = dtn.Custody("dev-a")
    store.accept(sos())
    plans = dtn.plan_offers(store, available={"courier"})
    assert plans[0].transport == "courier"
    assert plans[0].held is True


def test_the_plan_offers_every_held_bundle_in_priority_order():
    store = dtn.Custody("dev-a")
    store.accept(dtn.Bundle(id="chat-1", kind="chat", body="a", created_at=NOW))
    store.accept(sos(id="sos-1", created_at=NOW))
    plans = dtn.plan_offers(store, available={"ble"})
    assert [p.bundle_id for p in plans] == ["sos-1", "chat-1"]


def test_an_ordinary_bundle_is_validated_against_the_protocol():
    with pytest.raises(ValueError):
        dtn.Bundle(id="x", kind="picnic", body="hello")


def test_a_body_over_the_protocol_limit_is_truncated_and_says_so():
    b = dtn.Bundle(id="x", kind="chat", body="z" * 900)
    assert b.body.endswith("[truncated]")
    assert len(b.body) <= 480
