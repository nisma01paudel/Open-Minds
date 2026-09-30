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
