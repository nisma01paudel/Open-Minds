"""The missing link: mesh -> gateway phone -> district board.

Everything before this carried a message between phones. Nothing handed it to anyone who
was not standing there, so an SOS successfully carried across four kilometres was still
invisible to the board.

This is the integration that has to hold at two boundaries:

  1. a frame produced by the JAVASCRIPT mesh must be accepted by the PYTHON api. Field
     names drifting between two implementations is exactly how carried messages vanish
     with no error anywhere.
  2. what the api then shows must be the real thing - the hops it was carried, the position
     if there is one, and one row per person.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from pahiro.api import FieldStore, make_server
from pahiro.mesh.node import MeshNode
from pahiro.mesh.transport import LoopbackRadio, MeshRunner


@pytest.fixture()
def api(tmp_path):
    store = FieldStore(tmp_path / "field.json")
    httpd = make_server(0, "127.0.0.1", store)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown(); httpd.server_close()


def post(base, path, payload):
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode())


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=15) as r:
        return r.status, json.loads(r.read().decode())


def test_a_message_carried_across_a_chain_reaches_the_board(api):
    """Sita's phone has no signal. Ram carries it. Maya has one bar. The board must see it,
    and must know it was carried rather than sent directly."""
    radio = LoopbackRadio()
    phones = {n: MeshNode(n, name=n.title()) for n in ("sita", "ram", "maya")}
    runners = {n: MeshRunner(phones[n], radio) for n in phones}

    radio.detach("maya")                              # Maya is in the bazaar, out of range
    sos = phones["sita"].sos("buried near the culvert, two of us",
                             lat=27.762, lon=85.0575, people=2, battery=11)
    runners["sita"].send(sos)
    runners["ram"].pump()

    radio.attach("maya")
    runners["ram"].meet(runners["maya"])              # Ram walks into the bazaar

    carried = phones["maya"].store[sos.id]
    assert carried.hops >= 1, "the gateway must be handing over a message it carried"

    # THIS is the step that was missing: the gateway phone uploads what it holds.
    status, res = post(api, "/api/v1/mesh/messages",
                       {"messages": [carried.to_dict()]})
    assert status == 202 and res["accepted"] == 1

    _, board = get(api, "/api/v1/trapped")
    assert board["count"] == 1
    row = board["trapped"][0]
    assert row["device_id"] == "sita"
    assert row["people"] == 2
    assert row["lat"] == pytest.approx(27.762)
    assert row["hops"] >= 1, "the board must record that this was carried, not sent"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_a_frame_built_by_the_javascript_mesh_is_accepted_by_the_python_api(api):
    """The cross-language contract. mesh.js produces the frame; api.py consumes it. If the
    field names drift, carried messages vanish with no error on either side."""
    script = """
    var M = require(process.argv[process.argv.length - 1]);
    var n = new M.MeshNode("sita", { name: "Sita" });
    var m = n.sos("buried, two of us", { lat: 27.762, lon: 85.0575, people: 2, battery: 9 });
    // relay it once so the frame carries a hop and a path, as a real carried frame would
    var relayed = m.relay("ram");
    console.log(JSON.stringify(relayed.toDict()));
    """
    proc = subprocess.run(["node", "-e", script, str(ROOT / "web/public/field/mesh.js")],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    frame = json.loads(proc.stdout.strip().splitlines()[-1])

    status, res = post(api, "/api/v1/mesh/messages", {"messages": [frame]})
    assert status == 202, f"the Python API refused a frame the JS mesh produced: {res}"
    assert res["accepted"] == 1 and res["rejected"] == 0, res

    _, board = get(api, "/api/v1/trapped")
    assert board["count"] == 1
    row = board["trapped"][0]
    assert row["device_id"] == "sita"
    assert row["name"] == "Sita"
    assert row["people"] == 2
    assert row["hops"] == 1
    assert row["path"] == ["ram"]


def test_a_gateway_that_uploads_twice_does_not_invent_a_second_victim(api):
    """A phone with one bar of signal will retry. The retry must be absorbed."""
    radio = LoopbackRadio()
    a = MeshRunner(MeshNode("a", name="A"), radio)
    b = MeshRunner(MeshNode("b", name="B"), radio)
    sos = a.node.sos("trapped", lat=27.7, lon=85.0)
    a.send(sos); b.pump()

    first, r1 = post(api, "/api/v1/mesh/messages",
                     {"messages": [b.node.store[sos.id].to_dict()]})
    second, r2 = post(api, "/api/v1/mesh/messages",
                      {"messages": [b.node.store[sos.id].to_dict()]})
    assert first == 202 and r1["accepted"] == 1
    assert second == 202 and r2["duplicates"] == 1 and r2["accepted"] == 0

    _, board = get(api, "/api/v1/trapped")
    assert board["count"] == 1


def test_housekeeping_frames_are_not_put_on_the_board(api):
    """The mesh exchanges `status` hellos between phones. Those are not incidents."""
    radio = LoopbackRadio()
    a = MeshRunner(MeshNode("a"), radio)
    b = MeshRunner(MeshNode("b"), radio)
    a.send(a.node.compose("status", "hello"))
    b.pump()
    status_frame = list(b.node.store.values())[0].to_dict()

    _, res = post(api, "/api/v1/mesh/messages", {"messages": [status_frame]})
    assert res["accepted"] == 1
    _, board = get(api, "/api/v1/trapped")
    assert board["count"] == 0, "a hello must never appear as a person"


def test_an_sos_on_the_mesh_becomes_a_board_row_the_api_can_locate(api):
    """The whole chain: carried SOS, uploaded by a gateway, then located from sightings."""
    radio = LoopbackRadio()
    a = MeshRunner(MeshNode("victim"), radio)
    gw = MeshRunner(MeshNode("gateway"), radio)
    sos = a.node.sos("under the slide", lat=27.762, lon=85.0535, people=1)
    a.send(sos); gw.pump()
    post(api, "/api/v1/mesh/messages",
         {"messages": [gw.node.store[sos.id].to_dict()]})

    for lat, lon, rssi in [(27.76227, 85.05350, -86.5), (27.76160, 85.05350, -95.0),
                           (27.76200, 85.05406, -92.3)]:
        post(api, f"/api/v1/track/victim", {"lat": lat, "lon": lon, "rssi_dbm": rssi})

    _, board = get(api, "/api/v1/trapped")
    row = board["trapped"][0]
    assert row["located"] is not None
    assert row["located"]["radius_m"] > 0
    assert row["located"]["receivers"] == 3


def test_the_upload_reports_which_frames_were_duplicates_and_which_were_refused(api):
    """The gateway needs PER-ID outcomes, not counts.

    It must not re-send its whole backlog forever, and it must not mark a frame delivered
    when the server refused it. With counts alone the client has to guess, and the obvious
    guess - "anything not accepted, when there was at least one duplicate, was a duplicate" -
    silently discards refused messages and tells nobody.
    """
    radio = LoopbackRadio()
    a = MeshRunner(MeshNode("a", name="A"), radio)
    b = MeshRunner(MeshNode("b", name="B"), radio)
    good = a.node.sos("trapped", lat=27.7, lon=85.0)
    a.send(good)
    b.pump()
    frame = b.node.store[good.id].to_dict()

    # First upload: everything new.
    _, first = post(api, "/api/v1/mesh/messages", {"messages": [frame]})
    assert first["accepted"] == 1
    assert first["ids"] == [frame["id"]]
    assert first["duplicate_ids"] == [] and first["rejected_ids"] == []

    # Second upload mixes a duplicate WITH a malformed frame. The response must name each
    # one, so the client can mark the duplicate delivered and still flag the bad frame.
    _, second = post(api, "/api/v1/mesh/messages",
                     {"messages": [frame, {"id": "broken-1", "k": "chat"}]})
    assert second["accepted"] == 0
    assert second["duplicates"] == 1 and second["duplicate_ids"] == [frame["id"]]
    assert second["rejected"] == 1 and second["rejected_ids"] == ["broken-1"]
    assert second["ids"] == []


def test_counts_alone_would_have_lost_the_refused_frame(api):
    """The exact shape of the bug this replaces.

    A batch of one duplicate and one refusal reports `duplicates > 0`, so the old client rule
    marked BOTH as delivered - and the refused frame was never retried and never mentioned.
    Per-id outcomes make that impossible: the duplicate is named, the refusal is named.
    """
    radio = LoopbackRadio()
    a = MeshRunner(MeshNode("a"), radio)
    b = MeshRunner(MeshNode("b"), radio)
    known = a.node.sos("already sent", lat=27.7, lon=85.0)
    a.send(known)
    b.pump()
    frame = b.node.store[known.id].to_dict()

    post(api, "/api/v1/mesh/messages", {"messages": [frame]})
    _, res = post(api, "/api/v1/mesh/messages",
                  {"messages": [frame, {"id": "bad", "k": "nonsense-kind", "o": "x"}]})

    delivered = set(res["ids"]) | set(res["duplicate_ids"])
    assert frame["id"] in delivered
    assert "bad" not in delivered, "a refused frame must not look delivered"
    assert "bad" in res["rejected_ids"]
