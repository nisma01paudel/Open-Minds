"""The mesh must survive a flood, a dead phone and an encounter that lasts one second."""
from __future__ import annotations

import pytest

from pahiro.mesh import LoopbackRadio, LossyRadio, MeshMessage, MeshNode, MeshRunner


def test_frame_round_trips_through_the_wire_format():
    m = MeshMessage(kind="sos", body="buried, two of us", origin="d1", origin_name="Sita",
                    lat=27.762, lon=85.0575, accuracy_m=8.5, people=2, battery=14)
    back = MeshMessage.from_bytes(m.to_bytes())
    assert back.id == m.id and back.kind == "sos" and back.body == m.body
    assert back.origin == "d1" and back.origin_name == "Sita"
    assert (back.lat, back.lon, back.accuracy_m, back.people, back.battery) == \
           (27.762, 85.0575, 8.5, 2, 14)
    assert back.created_at == m.created_at


def test_a_malformed_frame_raises_rather_than_being_guessed_at():
    with pytest.raises(ValueError):
        MeshMessage.from_bytes(b"not json")
    with pytest.raises(ValueError):
        MeshMessage.from_bytes(b'{"k":"chat"}')          # no id, no origin
    with pytest.raises(ValueError):
        MeshMessage(kind="gossip", body="x", origin="d1")


def test_an_overlong_message_is_truncated_and_says_so():
    m = MeshMessage(kind="chat", body="x" * 900, origin="d1")
    assert len(m.body) <= 480
    assert m.body.endswith("[truncated]")


def test_the_same_message_arriving_twice_is_stored_once():
    """The flood means duplicates are normal, not exceptional."""
    node = MeshNode("d2")
    m = MeshMessage(kind="sos", body="help", origin="d1")
    relayed = m.relay(via="d3")
    assert node.receive(relayed) is True
    assert node.receive(relayed) is False
    assert node.stats.duplicates == 1
    assert len(node.store) == 1


def test_a_message_crosses_a_chain_of_phones():
    """A -> B -> C -> D, where each pair is only in range of its neighbour.

    Modelled by attaching and detaching, because that is what a chain physically is: the
    nodes at the ends never share a radio.
    """
    radio = LoopbackRadio()
    nodes = {n: MeshNode(n, name=n.upper()) for n in "abcd"}
    runners = {n: MeshRunner(nodes[n], radio) for n in "abcd"}

    # Only a and b are in range of each other.
    for n in "cd":
        radio.detach(n)

    msg = nodes["a"].sos("trapped under the slide", lat=27.7, lon=85.0)
    runners["a"].send(msg)
    runners["b"].pump()

    # b HEARD it directly, so no relay has happened yet: zero hops, empty path.
    assert nodes["b"].store[msg.id].hops == 0
    assert nodes["b"].store[msg.id].path == []

    # Now b carries it to c, which was never in range of a.
    radio.attach("c")
    runners["b"].meet(runners["c"])
    carried = nodes["c"].store[msg.id]
    assert carried.hops == 1
    assert carried.path == ["b"], "the path records who relayed it"
    assert carried.origin == "a", "the sender never changes as a message is carried"

    # And c carries it to d.
    radio.detach("b")
    radio.attach("d")
    runners["c"].meet(runners["d"])
    final = nodes["d"].store[msg.id]
    assert final.hops == 2
    assert final.path == ["b", "c"]
    assert final.id == msg.id
    assert len(nodes["d"].distress()) == 1


def test_ttl_stops_the_flood():
    """Without this a mesh becomes a broadcast storm on the radio you need for rescue."""
    m = MeshMessage(kind="chat", body="hello", origin="a", ttl=1)
    one = m.relay(via="b")
    assert one.ttl == 0
    assert one.alive() is False
    with pytest.raises(ValueError):
        one.relay(via="c")


def test_an_expired_message_is_dropped_not_stored():
    node = MeshNode("z")
    dead = MeshMessage(kind="chat", body="stale", origin="a", ttl=0)
    assert node.receive(dead) is False
    assert node.store == {}
    assert node.stats.expired == 1


def test_chat_is_evicted_before_an_sos():
    """A phone is not a server. When it is full, the joke goes and the person stays."""
    node = MeshNode("n", capacity=6)
    sos = node.sos("buried", lat=27.7, lon=85.0)
    for i in range(20):
        node.compose("chat", f"chatter {i}")
    assert sos.id in node.store, "a distress message must survive chat pressure"
    assert node.stats.evicted > 0
    assert len(node.store) <= 6


def test_sos_is_sent_before_chat_when_the_encounter_is_brief():
    """Two people walking past each other: the SOS goes, the chat may not."""
    node = MeshNode("carrier")
    node.compose("chat", "nice weather")
    node.sos("two people under the debris", lat=27.7, lon=85.0)
    order = [m.kind for m in node.relayable()]
    assert order[0] == "sos"


def test_store_and_forward_reaches_a_phone_that_arrived_later():
    """The difference between a mesh and a walkie-talkie: the listener need not be there
    when the message was sent."""
    radio = LoopbackRadio()
    carrier = MeshRunner(MeshNode("carrier"), radio)

    sender = MeshRunner(MeshNode("sender"), radio)
    msg = sender.node.sos("need help at the culvert", lat=27.7, lon=85.0)
    sender.send(msg)
    carrier.pump()
    assert msg.id in carrier.node.store

    # Hours later, a phone with signal walks up.
    gateway = MeshRunner(MeshNode("gateway"), radio)
    handed, taken = carrier.meet(gateway)
    assert msg.id in gateway.node.store
    assert msg.id in gateway.node.distress()[0].id


def test_a_lossy_radio_still_delivers_because_of_repetition():
    """Half the frames lost, and the message still arrives - that is the point of a mesh."""
    radio = LossyRadio(loss=0.5, seed=7,
                       in_range=lambda a, b: not (a == "a" and b == "d"))
    a = MeshRunner(MeshNode("a"), radio)
    b = MeshRunner(MeshNode("b"), radio)
    c = MeshRunner(MeshNode("c"), radio)
    d = MeshRunner(MeshNode("d"), radio)

    msg = a.node.sos("trapped", lat=27.7, lon=85.0)
    for _ in range(6):                            # several passes, as people move
        a.send(msg)
        b.pump()
        b.meet(c)
        c.meet(d)

    assert msg.id in d.node.store
    assert radio.dropped > 0, "the test is only meaningful if frames were actually lost"


def test_the_distress_board_shows_a_person_once():
    """A panicking person sends several. A board that shows them five times hides someone
    else."""
    node = MeshNode("ops")
    for i in range(4):
        node.receive(MeshMessage(kind="sos", body=f"help {i}", origin="victim1").relay("r1"))
    node.receive(MeshMessage(kind="sos", body="help", origin="victim2").relay("r1"))
    board = node.distress()
    assert len(board) == 2
    assert {m.origin for m in board} == {"victim1", "victim2"}


def test_messages_with_a_position_rank_above_those_without():
    node = MeshNode("ops")
    node.receive(MeshMessage(kind="sos", body="no fix", origin="v1").relay("r"))
    node.receive(MeshMessage(kind="sos", body="fixed", origin="v2",
                             lat=27.7, lon=85.0).relay("r"))
    assert node.distress()[0].origin == "v2"
