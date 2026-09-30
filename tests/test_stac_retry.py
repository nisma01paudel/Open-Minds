"""Transient upstream failures must not kill a run."""
import urllib.error

import pytest

from pahiro.ingest import stac


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): import json; return json.dumps(self.payload).encode()


def test_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}
    def flaky(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(req.full_url, 502, "Bad Gateway", {}, None)
        return FakeResponse({"ok": True})
    monkeypatch.setattr(stac.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(stac.time, "sleep", lambda s: None)
    assert stac._post_json("http://x", {}) == {"ok": True}
    assert calls["n"] == 3


def test_client_error_is_not_retried(monkeypatch):
    calls = {"n": 0}
    def bad_request(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)
    monkeypatch.setattr(stac.urllib.request, "urlopen", bad_request)
    monkeypatch.setattr(stac.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        stac._post_json("http://x", {})
    assert calls["n"] == 1, "a 400 is our fault, not a transient blip"


def test_gives_up_after_the_configured_retries(monkeypatch):
    calls = {"n": 0}
    def always_down(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.URLError("connection reset")
    monkeypatch.setattr(stac.urllib.request, "urlopen", always_down)
    monkeypatch.setattr(stac.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        stac._post_json("http://x", {})
    assert calls["n"] == stac.RETRIES


def test_search_follows_pagination(monkeypatch):
    """A big bbox needs many pages; the continuation token lives in the next link."""
    pages = [
        {"features": [{"id": f"a{i}", "properties": {"datetime": "2024-01-0%dT00:00:00Z" % (i + 1)},
                       "assets": {}} for i in range(3)],
         "links": [{"rel": "next", "body": {"next": "tok1"}}]},
        {"features": [{"id": f"b{i}", "properties": {"datetime": "2024-02-0%dT00:00:00Z" % (i + 1)},
                       "assets": {}} for i in range(2)],
         "links": []},
    ]
    calls = {"n": 0}

    def fake_post(url, body, timeout=60):
        page = pages[calls["n"]]
        calls["n"] += 1
        return page

    monkeypatch.setattr(stac, "_post_json", fake_post)
    scenes = stac.search(stac.OPTICAL, (85.0, 27.5, 85.6, 28.0), "2024-01-01", "2024-12-31")
    assert len(scenes) == 5, "every page must be collected"
    assert calls["n"] == 2, "the loop must stop when no next link is returned"
    assert scenes[0].acquired.isoformat() == "2024-01-01", "results stay date-sorted"


def test_search_pagination_can_be_disabled(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, body, timeout=60):
        calls["n"] += 1
        return {"features": [{"id": "x", "properties": {"datetime": "2024-03-01T00:00:00Z"},
                              "assets": {}}],
                "links": [{"rel": "next", "body": {"next": "tok"}}]}

    monkeypatch.setattr(stac, "_post_json", fake_post)
    scenes = stac.search(stac.OPTICAL, (85.0, 27.5, 85.6, 28.0), "2024-01-01", "2024-12-31",
                         paginate=False)
    assert len(scenes) == 1 and calls["n"] == 1


def test_s3_asset_hrefs_are_normalised_to_https():
    """Copernicus DEM publishes s3:// URLs; dropping them loses the terrain layer."""
    assert (stac._readable_href("s3://copernicus-dem-30m/N27/E085.tif")
            == "https://copernicus-dem-30m.s3.amazonaws.com/N27/E085.tif")
    assert stac._readable_href("https://x/y.tif") == "https://x/y.tif"
    assert stac._readable_href("gs://bucket/key") is None
    assert stac._readable_href(None) is None


def test_scene_assets_include_s3_sources(monkeypatch):
    feature = {"id": "d1", "properties": {"datetime": "2021-04-22T00:00:00Z"},
               "assets": {"data": {"href": "s3://copernicus-dem-30m/a/b.tif"},
                          "preview": {"href": "https://example.org/p.png"},
                          "weird": {"href": "ftp://nope"}}}
    scene = stac._scene_from_feature(feature, stac.DEM)
    assert scene.assets["data"].startswith("https://copernicus-dem-30m.s3.amazonaws.com/")
    assert "weird" not in scene.assets
