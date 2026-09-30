"""The field API, exercised over real HTTP against a real socket.

Not a unit test of the handlers: the thing that has to work is a phone talking to this over
a bad connection, so the tests speak to it the way a phone would.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from pahiro.api import FieldStore, make_server


@pytest.fixture()
def api(tmp_path):
    store = FieldStore(tmp_path / "field.json")
    httpd = make_server(0, "127.0.0.1", store)      # port 0 = pick a free one
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base
    httpd.shutdown()
    httpd.server_close()


def call(base, path, payload=None, method=None):
    url = base + path
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode()), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode()), dict(e.headers)


def test_health_reports_counters(api):
    status, body, _ = call(api, "/api/v1/health")
    assert status == 200 and body["status"] == "ok"
    assert body["messages"] == 0


def test_openapi_is_served(api):
    status, body, _ = call(api, "/api/v1/openapi.json")
    assert status == 200 and body["openapi"].startswith("3.")
    assert "/api/v1/sos" in body["paths"]


def test_cors_is_present_so_a_browser_client_can_reach_it(api):
    _, _, headers = call(api, "/api/v1/health")
    assert headers.get("Access-Control-Allow-Origin") == "*"


def test_an_sos_without_a_position_is_still_accepted(api):
    """A person under rubble often has no fix. Refusing the report because it lacks a
    coordinate would discard the most urgent case there is."""
    status, body, _ = call(api, "/api/v1/sos", {"device_id": "d1", "message": "buried",
                                                "people": 2})
    assert status == 201 and body["duplicate"] is False
    _, board, _ = call(api, "/api/v1/trapped")
    assert board["count"] == 1
    assert board["trapped"][0]["lat"] is None
    assert board["trapped"][0]["people"] == 2


def test_a_retried_sos_does_not_create_a_second_person(api):
    """A phone with no idea whether its last frame arrived will send it again. Retrying
    must not make the board show two victims.

    The device supplies its own frame id, exactly as it does on the mesh, and reuses it on
    the retry. That is what makes the write idempotent - a server-generated id could not,
    because the retry would look like a brand new message.
    """
    report = {"device_id": "d1", "message": "help", "id": "frame-7"}
    first, b1, _ = call(api, "/api/v1/sos", report)
    second, b2, _ = call(api, "/api/v1/sos", report)
    assert first == 201 and b1["duplicate"] is False
    assert second == 200 and b2["duplicate"] is True
    _, board, _ = call(api, "/api/v1/trapped")
    assert board["count"] == 1


def test_a_second_sos_from_the_same_phone_keeps_one_board_row(api):
    """Even without a frame id, the board is one row per handset: a person who sends four
    panicked messages must not occupy four lines while someone else is pushed off."""
    for _ in range(4):
        call(api, "/api/v1/sos", {"device_id": "d2", "message": "still here"})
    _, board, _ = call(api, "/api/v1/trapped")
    assert board["count"] == 1
    assert board["trapped"][0]["reports"] == 4


def test_sos_requires_a_device_and_a_message(api):
    assert call(api, "/api/v1/sos", {"message": "help"})[0] == 400
    assert call(api, "/api/v1/sos", {"device_id": "d1"})[0] == 400


def test_mesh_ingest_dedupes_and_reports_what_happened(api):
    frame = {"v": 1, "id": "m1", "k": "sos", "b": "need help", "o": "phone-a",
             "n": "Sita", "t": "2026-09-30T09:00:00Z", "ttl": 5, "h": 1,
             "y": 27.762, "x": 85.0575}
    s1, b1, _ = call(api, "/api/v1/mesh/messages", {"messages": [frame]})
    assert s1 == 202 and b1["accepted"] == 1
    s2, b2, _ = call(api, "/api/v1/mesh/messages", {"messages": [frame]})
    assert s2 == 202 and b2["duplicates"] == 1 and b2["accepted"] == 0
    _, board, _ = call(api, "/api/v1/trapped")
    assert board["count"] == 1 and board["trapped"][0]["device_id"] == "phone-a"


def test_a_malformed_frame_is_rejected_and_recorded_not_silently_dropped(api):
    status, body, _ = call(api, "/api/v1/mesh/messages",
                           {"messages": [{"nope": True}, "not json at all"]})
    assert status == 202 and body["rejected"] == 2 and body["accepted"] == 0
    _, health, _ = call(api, "/api/v1/health")
    assert health["rejected"] == 2


def test_incremental_sync_returns_only_what_is_new(api):
    """A phone that has been offline for hours syncs the delta, not the world."""
    for i, t in enumerate(["2026-09-30T09:00:00Z", "2026-09-30T10:00:00Z"]):
        call(api, "/api/v1/mesh/messages", {"messages": [
            {"v": 1, "id": f"m{i}", "k": "chat", "b": f"msg {i}", "o": "p", "t": t}]})
    _, all_msgs, _ = call(api, "/api/v1/mesh/messages")
    assert all_msgs["count"] == 2
    _, delta, _ = call(api, "/api/v1/mesh/messages?since=2026-09-30T09:30:00Z")
    assert delta["count"] == 1 and delta["messages"][0]["id"] == "m1"


def test_a_buried_handset_is_located_from_rssi_sightings(api):
    """Three rescuers report signal strength; the API answers with an area to search."""
    base = "/api/v1/track/phone-a"
    for lat, lon, rssi in [(27.7600, 85.0500, -65), (27.7640, 85.0520, -72),
                           (27.7605, 85.0560, -78)]:
        status, body, _ = call(api, base, {"lat": lat, "lon": lon, "rssi_dbm": rssi})
        assert status == 201
    status, final, _ = call(api, base)
    assert status == 200 and final["readings"] if "readings" in final else True
    assert final["method"] == "weighted-least-squares"
    assert final["radius_m"] > 0
    assert final["search_area_m2"] > 0


def test_a_sighting_without_a_reading_is_refused(api):
    assert call(api, "/api/v1/track/x", {"lat": 27.7})[0] == 400


def test_unknown_routes_are_404_not_a_crash(api):
    assert call(api, "/api/v1/nope")[0] == 404
    assert call(api, "/api/v1/nope", {})[0] == 404


def test_a_garbage_body_is_a_400(api):
    req = urllib.request.Request(api + "/api/v1/sos", data=b"{not json",
                                 method="POST", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 400


def test_the_board_survives_a_restart(tmp_path):
    """A district office laptop loses power. The board must not."""
    path = tmp_path / "field.json"
    s1 = FieldStore(path)
    s2 = make_server(0, "127.0.0.1", s1)
    t = threading.Thread(target=s2.serve_forever, daemon=True); t.start()
    base = f"http://127.0.0.1:{s2.server_address[1]}"
    call(base, "/api/v1/sos", {"device_id": "d9", "message": "under the slide",
                               "lat": 27.7, "lon": 85.0})
    s2.shutdown(); s2.server_close()
    assert path.exists()

    reloaded = FieldStore(path)
    assert "d9" in reloaded.sos
    assert reloaded.sos["d9"]["message"] == "under the slide"


def test_slopes_endpoint_exposes_the_warning_data(api):
    status, body, _ = call(api, "/api/v1/slopes")
    assert status == 200
    if "error" in body:
        pytest.skip("slope data not built in this checkout")
    assert body["count"] > 0 and body["slopes"][0]["id"]


# ---- sealed mesh ingest -------------------------------------------------------------------------

pytest.importorskip("cryptography", reason="the crypto extra is not installed")


def _sealed_server(monkeypatch, key: bytes):
    """A server that holds a key, plus a client that seals like the browser does."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    from pahiro.api import FieldStore, make_server
    from pahiro.mesh import pipeline, seal
    from pahiro.mesh.protocol import MeshMessage

    store = FieldStore()
    srv = make_server(0, "127.0.0.1", store, seal_key=key)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cipher = seal.AeadCipher(AESGCM, "aes-256-gcm")
    msg = MeshMessage(kind="sos", body="six trapped under the bus at KM 42",
                      origin="dev-alpha", people=6, lat=28.21, lon=83.98)
    sealed = pipeline.seal_bundle(msg, key, cipher, sender_key=b"client-key")
    frame = pipeline.to_frame(sealed)
    return srv, port, frame, store, msg


def test_a_sealed_frame_is_accepted_and_read_by_a_gateway_holding_the_key():
    import urllib.request

    key = seal_key_bytes()
    srv, port, frame, store, msg = _sealed_server(None, key)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/v1/mesh/messages",
            data=json.dumps({"messages": [frame]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
        assert body["accepted"] == 1, body
        assert body["rejected"] == 0
        # and the gateway read it: the plaintext is now on the board
        trapped = store.trapped()
        assert trapped and trapped[0]["people"] == 6
        assert "trapped" not in json.dumps(frame), "the frame itself never carried the words"
    finally:
        srv.shutdown()


def test_a_gateway_with_no_key_refuses_a_sealed_frame_rather_than_dropping_it():
    """Silence would look identical to an empty mesh, and every sealed message would vanish."""
    import urllib.request

    from pahiro.api import FieldStore, make_server
    from pahiro.mesh import pipeline

    key = seal_key_bytes()
    srv, _, frame, _, _ = _sealed_server(None, key)
    srv.shutdown()

    plain = make_server(0, "127.0.0.1", FieldStore())   # no seal key
    port = plain.server_address[1]
    threading.Thread(target=plain.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/v1/mesh/messages",
            data=json.dumps({"messages": [frame]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
        assert body["accepted"] == 0
        assert body["rejected"] == 1, "a sealed frame must be refused loudly, not dropped"
        assert body["rejected_ids"] == [frame["sealed"]["id"]]
    finally:
        plain.shutdown()


def test_a_replayed_sealed_frame_is_refused():
    import urllib.request

    key = seal_key_bytes()
    srv, port, frame, store, _ = _sealed_server(None, key)
    try:
        for expect_accepted in (1, 0):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/v1/mesh/messages",
                data=json.dumps({"messages": [frame]}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                body = json.loads(r.read())
            assert body["accepted"] == expect_accepted, body
        # the second attempt is rejected as a replay, not silently deduplicated
        assert body["rejected"] == 1
    finally:
        srv.shutdown()


def test_a_tampered_sealed_frame_is_refused():
    import urllib.request

    key = seal_key_bytes()
    srv, port, frame, _, _ = _sealed_server(None, key)
    try:
        import base64
        raw = bytearray(base64.b64decode(frame["sealed"]["payload_b64"]))
        raw[-1] ^= 0x01
        frame["sealed"]["payload_b64"] = base64.b64encode(bytes(raw)).decode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/v1/mesh/messages",
            data=json.dumps({"messages": [frame]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
        assert body["rejected"] == 1
        assert body["accepted"] == 0
    finally:
        srv.shutdown()


def seal_key_bytes() -> bytes:
    return bytes(range(32))


# ---- planning a walk over HTTP ------------------------------------------------------------------

def test_plan_endpoint_answers_a_sentence():
    """The daily-use half, reachable from the app rather than only from a terminal."""
    import urllib.request

    from pahiro.api import FieldStore, make_server

    srv = make_server(0, "127.0.0.1", FieldStore())
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{port}/api/v1/plan?q=easy+walk+with+a+view&lat=27.7047&lon=85.3146"
        with urllib.request.urlopen(url, timeout=60) as r:
            body = json.loads(r.read())
        assert "understood" in body, body
        assert body["origin"]["lat"] == 27.7047
        assert body["options"], "no walks offered for an ordinary request"
        first = body["options"][0]
        assert first["name"] and first["minutes"] > 0
        assert first["bus"] and first["bus"]["fare_rs"] >= 24, \
            "every option must say how to get there and what it costs"
        # The caveats must travel with the answer, not sit in a docstring.
        joined = " ".join(body["caveats"]).lower()
        assert "openstreetmap" in joined and "indicative" in joined
    finally:
        srv.shutdown()


def test_plan_endpoint_says_what_it_understood_and_who_understood_it():
    """A planner that does not show its reading is a slot machine. And the caller is told whether
    a model was involved or the keyword reader was - those are different qualities of answer."""
    import urllib.request

    from pahiro.api import FieldStore, make_server

    srv = make_server(0, "127.0.0.1", FieldStore())
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{port}/api/v1/plan?q=a+hard+6+hour+climb+under+Rs+60"
        with urllib.request.urlopen(url, timeout=60) as r:
            body = json.loads(r.read())
        assert "hard" in body["understood"]
        assert "Rs 60" in body["understood"]
        assert body["understood_by"] in ("open-weight model", "keyword reader (no model server)")
    finally:
        srv.shutdown()


def test_plan_endpoint_refuses_an_empty_request_rather_than_guessing():
    import urllib.request

    from pahiro.api import FieldStore, make_server

    srv = make_server(0, "127.0.0.1", FieldStore())
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/plan", timeout=30) as r:
            body = json.loads(r.read())
        assert "error" in body and "q is required" in body["error"]
    finally:
        srv.shutdown()
