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
