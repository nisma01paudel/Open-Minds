"""The field API: a real HTTP surface a mobile app can be built against.

WHY AN API AND NOT ANOTHER SCREEN
---------------------------------
A warning is information. Information helps someone decide. What is missing in the hours
after a slope fails is not another view of the same data - it is a common place for the
things that are happening to land, so that a phone in a village, a phone carried by a
rescuer, and a desk in the district office are all looking at the same picture.

That is what this is. Three things can be posted to it and one thing can be read back:

  POST /api/v1/mesh/messages   messages that reached the internet over someone's phone
  POST /api/v1/sos             a distress report, with or without a position
  POST /api/v1/track/{id}      one rescuer's RSSI sighting of a buried handset
  GET  /api/v1/trapped         everyone who has called for help, worst first

and the slope data the earlier work already produces is exposed alongside it, so a client
does not need two backends.

DESIGNED FOR A BAD NETWORK. Every write is idempotent - a phone that has no idea whether
its last frame got through will send it again, and must not create a second person. Reads
take `?since=` so a device that has been offline for six hours syncs the delta instead of
the world. There is no session, because a session is a thing that expires while you are
under a rock.

Run it:

    python -m pahiro.api --port 8080 --data evidence/field.json
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import navigate, shelter, triage

from .locate import Reading, estimate_position
from .mesh.protocol import MeshMessage

API_VERSION = "v1"
MAX_BODY_BYTES = 256 * 1024


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class FieldStore:
    """The shared operational picture.

    In memory, with an optional JSON file so a restart does not erase the board. This is
    deliberately not a database: the deployment it is designed for is a laptop or a phone
    in a district office, and a store that needs a server to exist would not run there.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.lock = threading.Lock()
        self.messages: dict[str, MeshMessage] = {}
        self.sightings: dict[str, list[Reading]] = {}
        self.sos: dict[str, dict[str, Any]] = {}         # origin -> latest report
        self.rejected: list[dict[str, Any]] = []
        if self.path and self.path.exists():
            self.load()

    # ---- writes -----------------------------------------------------------------------

    def ingest_message(self, msg: MeshMessage) -> bool:
        """True if this is a message we had not seen. Duplicates are expected, not errors."""
        with self.lock:
            if msg.id in self.messages:
                return False
            self.messages[msg.id] = msg
            if msg.is_sos:
                self._note_sos(msg)
            self.persist()
            return True

    def _note_sos(self, msg: MeshMessage) -> None:
        """Keep the newest report per device.

        One row per handset, because a frightened person sends several and a board that
        lists them all buries everyone else.
        """
        prev = self.sos.get(msg.origin)
        if prev and prev.get("created_at", "") > _iso(msg.created_at):
            return
        self.sos[msg.origin] = {
            "device_id": msg.origin,
            "name": msg.origin_name,
            "message": msg.body,
            "created_at": _iso(msg.created_at),
            "lat": msg.lat,
            "lon": msg.lon,
            "accuracy_m": msg.accuracy_m,
            "people": msg.people,
            "battery": msg.battery,
            "reports": (prev or {}).get("reports", 0) + 1,
            "hops": msg.hops,
            "path": msg.path,
        }

    def record_sighting(self, target: str, reading: Reading) -> int:
        with self.lock:
            self.sightings.setdefault(target, []).append(reading)
            self.persist()
            return len(self.sightings[target])

    def locate(self, target: str):
        with self.lock:
            readings = list(self.sightings.get(target, []))
        return estimate_position(readings)

    def reject(self, reason: str, payload: Any) -> None:
        with self.lock:
            self.rejected.append({"at": _now_iso(), "reason": reason,
                                  "payload": str(payload)[:400]})
            del self.rejected[:-200]

    # ---- reads ------------------------------------------------------------------------

    def since(self, since: str | None) -> list[MeshMessage]:
        with self.lock:
            msgs = list(self.messages.values())
        if since:
            msgs = [m for m in msgs if _iso(m.created_at) > since]
        # urgent first, then oldest first: a phone syncing after hours offline should meet
        # the distress messages before the conversation.
        msgs.sort(key=lambda m: (m.priority, _iso(m.created_at)))
        return msgs

    def trapped(self) -> list[dict[str, Any]]:
        """The board.

        Ordered by: has a position, then most recent, then most people. Position first
        because a team can be sent to a coordinate, and a report without one needs a
        different response - a search, not a dispatch.
        """
        with self.lock:
            rows = list(self.sos.values())
        for r in rows:
            est = self.locate(r["device_id"]) if r["device_id"] in self.sightings else None
            r["located"] = est.as_dict() if est else None
        # Applied as STABLE sorts, least significant first.
        #
        # This used to be one sort followed by reversed(), which flips EVERY key at once: the
        # board put reports WITHOUT a position at the top, which is the exact opposite of the
        # intent documented above, and ranked the smallest group of people first. Both keys
        # that matter for triage were inverted, on the endpoint a coordinator actually reads.
        rows.sort(key=lambda r: -(r.get("people") or 0))                 # most people first
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)   # then newest
        rows.sort(key=lambda r: r.get("lat") is None)                    # then has a position
        return rows

    def stats(self) -> dict[str, Any]:
        with self.lock:
            return {"messages": len(self.messages),
                    "sos_devices": len(self.sos),
                    "tracked": len(self.sightings),
                    "rejected": len(self.rejected),
                    "sightings": sum(len(v) for v in self.sightings.values())}

    # ---- persistence ------------------------------------------------------------------

    def persist(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            blob = {
                "messages": [m.to_dict() for m in self.messages.values()],
                "sos": self.sos,
                "sightings": {k: [asdict(r) for r in v] for k, v in self.sightings.items()},
            }
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)          # atomic: a crash mid-write must not lose the board
        except OSError:
            pass

    def load(self) -> None:
        try:
            blob = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for d in blob.get("messages", []):
            try:
                m = MeshMessage.from_dict(d)
                self.messages[m.id] = m
            except (ValueError, KeyError):
                continue
        self.sos = blob.get("sos", {})
        for k, rows in blob.get("sightings", {}).items():
            self.sightings[k] = [Reading(**r) for r in rows if isinstance(r, dict)]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------------------

OPENAPI = {
    "openapi": "3.0.3",
    "info": {
        "title": "Pahiro Field API",
        "version": API_VERSION,
        "description": (
            "Offline-first field API for landslide response. Devices post here when they "
            "have a connection; they use the mesh when they do not. Every write is "
            "idempotent so an uncertain phone can retry safely."
        ),
    },
    "paths": {
        "/api/v1/health": {"get": {"summary": "Liveness and counters"}},
        "/api/v1/mesh/messages": {
            "post": {"summary": "Ingest mesh messages that reached the internet"},
            "get": {"summary": "Sync messages, optionally since a timestamp"},
        },
        "/api/v1/sos": {"post": {"summary": "Report a distress call"}},
        "/api/v1/trapped": {"get": {"summary": "Everyone who has called for help"}},
        "/api/v1/track/{device_id}": {
            "post": {"summary": "Record one RSSI sighting of a buried handset"},
            "get": {"summary": "Estimated position and search radius"},
        },
        "/api/v1/slopes": {"get": {"summary": "Documented slopes and their current state"}},
        "/api/v1/triage": {
            "get": {"summary": "The board, ranked for search order, with a reason per point"},
        },
        "/api/v1/escape": {
            "get": {"summary": "Which way to run and how high, from the bundled DEM",
                    "parameters": [
                        {"name": "lat", "in": "query", "required": True,
                         "schema": {"type": "number"}},
                        {"name": "lon", "in": "query", "required": True,
                         "schema": {"type": "number"}},
                        {"name": "rise_m", "in": "query", "required": False,
                         "schema": {"type": "number", "default": shelter.DEFAULT_RISE_M}},
                    ]},
        },
    },
}


_DEM = None
_DEM_TRIED = False


def _national_dem():
    """Load the bundled DEM once, on first use.

    Lazy and cached: the API must start and serve the mesh on a machine where the terrain
    artefacts were never built, because an SOS relayed off a hillside matters more than a
    flood-escape answer.
    """
    global _DEM, _DEM_TRIED
    if not _DEM_TRIED:
        _DEM_TRIED = True
        root = Path(__file__).resolve().parents[2]
        _DEM = shelter.load_dem(root / "web/public/data/terrain.bin",
                                root / "web/public/data/terrain.json")
    return _DEM


class _Handler(BaseHTTPRequestHandler):
    server_version = "PahiroField/1.0"
    store: FieldStore = None          # set by make_server

    # ---- plumbing ---------------------------------------------------------------------

    def log_message(self, fmt, *args):        # keep the console readable during a demo
        if self.server.verbose:               # type: ignore[attr-defined]
            super().log_message(fmt, *args)

    def _send(self, code: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # A mobile client is a different origin. Without these the API is unreachable from
        # a browser-based app, which is how most field clients would be built.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Device-Id")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any] | None:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if n <= 0 or n > MAX_BODY_BYTES:
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    def do_OPTIONS(self):                                  # noqa: N802
        self._send(204, {})

    def do_GET(self):                                      # noqa: N802
        url = urlparse(self.path)
        q = parse_qs(url.query)
        path = url.path.rstrip("/")

        if path in ("", "/api", "/api/v1"):
            return self._send(200, {"service": "pahiro-field", "version": API_VERSION,
                                    "endpoints": list(OPENAPI["paths"])})
        if path == "/api/v1/health":
            return self._send(200, {"status": "ok", "time": _now_iso(),
                                    **self.store.stats()})
        if path == "/api/v1/openapi.json":
            return self._send(200, OPENAPI)
        if path == "/api/v1/mesh/messages":
            since = (q.get("since") or [None])[0]
            msgs = self.store.since(since)
            return self._send(200, {"count": len(msgs),
                                    "messages": [m.to_dict() for m in msgs]})
        if path == "/api/v1/trapped":
            rows = self.store.trapped()
            return self._send(200, {"count": len(rows), "trapped": rows})
        if path.startswith("/api/v1/track/"):
            target = path.rsplit("/", 1)[-1]
            est = self.store.locate(target)
            return self._send(200, est.as_dict())
        if path == "/api/v1/slopes":
            return self._send(200, self._slopes(q))
        if path == "/api/v1/escape":
            return self._send(200, self._escape(q))
        if path == "/api/v1/triage":
            return self._send(200, self._triage())
        return self._send(404, {"error": "not found", "path": path})

    def do_POST(self):                                     # noqa: N802
        url = urlparse(self.path)
        path = url.path.rstrip("/")
        data = self._body()
        if data is None:
            return self._send(400, {"error": "a JSON object body is required"})

        if path == "/api/v1/mesh/messages":
            return self._ingest_mesh(data)
        if path == "/api/v1/sos":
            return self._ingest_sos(data)
        if path.startswith("/api/v1/track/"):
            return self._ingest_sighting(path.rsplit("/", 1)[-1], data)
        return self._send(404, {"error": "not found", "path": path})

    # ---- handlers ---------------------------------------------------------------------

    def _ingest_mesh(self, data: dict[str, Any]) -> None:
        items = data.get("messages")
        if not isinstance(items, list):
            return self._send(400, {"error": "'messages' must be a list"})
        accepted = duplicates = rejected = 0
        ids: list[str] = []
        # PER-ID OUTCOMES, not just counts.
        #
        # The gateway phone needs to know WHICH frames landed, because it must not re-send
        # the whole backlog forever - but it also must not mark a frame as delivered when
        # the server refused it. With counts alone the client has to guess, and the obvious
        # guess ("anything not accepted, when there was at least one duplicate, was a
        # duplicate") silently discards refused messages and never tells anyone.
        duplicate_ids: list[str] = []
        rejected_ids: list[str] = []
        for raw in items:
            try:
                if isinstance(raw, dict):
                    msg = MeshMessage.from_dict(raw)
                elif isinstance(raw, str):
                    msg = MeshMessage.from_bytes(raw.encode("utf-8"))
                else:
                    msg = None
                if msg is None:
                    raise ValueError("each item must be an object or a JSON frame string")
            except (ValueError, KeyError) as exc:
                rejected += 1
                if isinstance(raw, dict) and raw.get("id"):
                    rejected_ids.append(str(raw["id"]))
                self.store.reject(f"mesh: {exc}", raw)
                continue
            if self.store.ingest_message(msg):
                accepted += 1
                ids.append(msg.id)
            else:
                duplicates += 1
                duplicate_ids.append(msg.id)
        return self._send(202, {"accepted": accepted, "duplicates": duplicates,
                                "rejected": rejected, "ids": ids,
                                "duplicate_ids": duplicate_ids,
                                "rejected_ids": rejected_ids})

    def _ingest_sos(self, data: dict[str, Any]) -> None:
        device = (data.get("device_id") or self.headers.get("X-Device-Id") or "").strip()
        if not device:
            return self._send(400, {"error": "device_id is required (body or X-Device-Id)"})
        body = (data.get("message") or data.get("body") or "").strip()
        if not body:
            return self._send(400, {"error": "message is required"})

        # The client's own id, reused on every retry. Without it a resend is a new random
        # id and the board grows a phantom victim - which is what happened before this.
        supplied = str(data.get("id") or "").strip()
        msg = MeshMessage(
            kind="sos", body=body, origin=device,
            origin_name=data.get("name", ""),
            **({"id": supplied} if supplied else {}),
            lat=_as_float(data.get("lat")), lon=_as_float(data.get("lon")),
            accuracy_m=_as_float(data.get("accuracy_m")),
            people=_as_int(data.get("people")), battery=_as_int(data.get("battery")),
        )
        fresh = self.store.ingest_message(msg)
        return self._send(201 if fresh else 200,
                          {"id": msg.id, "device_id": device, "duplicate": not fresh,
                           "accepted_at": _now_iso()})

    def _ingest_sighting(self, target: str, data: dict[str, Any]) -> None:
        lat, lon, rssi = (_as_float(data.get("lat")), _as_float(data.get("lon")),
                          _as_float(data.get("rssi_dbm")))
        if lat is None or lon is None or rssi is None:
            return self._send(400, {"error": "lat, lon and rssi_dbm are required"})
        n = self.store.record_sighting(target, Reading(
            lat=lat, lon=lon, rssi_dbm=rssi, label=str(data.get("label", "")),
            gps_accuracy_m=_as_float(data.get("gps_accuracy_m")) or 5.0))
        est = self.store.locate(target)
        return self._send(201, {"target": target, "readings": n, **est.as_dict()})

    def _escape(self, q: dict[str, list[str]]) -> dict[str, Any]:
        """Which way to run and how high, for one point, from the bundled DEM.

        This is the answer a warning normally leaves out. "Flash flood expected" tells someone
        a thing is happening and leaves the only decision that matters - which way, and how
        far up - for them to guess at, in the dark, in a minute.

        Terrain only, and the response says so: a DEM cannot see bridges, culverts or the water
        itself, and the bundled grid is about a kilometre a cell.
        """
        try:
            lat = float((q.get("lat") or [""])[0])
            lon = float((q.get("lon") or [""])[0])
        except (TypeError, ValueError):
            return {"error": "lat and lon are required as decimal degrees",
                    "example": "/api/v1/escape?lat=28.35&lon=83.57&rise_m=5"}

        try:
            rise = float((q.get("rise_m") or [shelter.DEFAULT_RISE_M])[0])
        except (TypeError, ValueError):
            rise = shelter.DEFAULT_RISE_M

        dem = _national_dem()
        if dem is None:
            return {"error": "the national DEM is not built in this checkout",
                    "hint": "see scripts/build_terrain.py"}

        e = shelter.plan_escape(dem, lat, lon, rise_m=rise)

        # Live guidance. The phone sends where it was when it started and where it was a moment
        # ago; the *rule* stays here, in the tested module, rather than being reimplemented in
        # JavaScript where it would drift. A phone that has climbed 20 m of a 200 m climb must
        # not be told it is failing, and that judgement belongs in one place.
        def _opt(name: str) -> float | None:
            raw = (q.get(name) or [None])[0]
            try:
                return None if raw in (None, "") else float(raw)
            except (TypeError, ValueError):
                return None

        live = navigate.update(e, dem, lat, lon,
                               started_elevation_m=_opt("started_m"),
                               last_elevation_m=_opt("last_m"))

        return {
            "query": {"lat": lat, "lon": lon, "rise_m": rise},
            "reachable": e.reachable,
            "from_elevation_m": round(e.from_elevation_m, 1),
            "target": None if not e.reachable else {
                "lat": round(e.target_lat, 6), "lon": round(e.target_lon, 6),
                "elevation_m": round(e.target_elevation_m, 1),
            },
            "climb_m": None if e.climb_m is None else round(e.climb_m, 1),
            "distance_m": None if e.distance_m is None else round(e.distance_m, 1),
            "bearing_deg": None if e.bearing_deg is None else round(e.bearing_deg, 1),
            "compass": e.compass,
            "walk_minutes": None if e.walk_minutes is None else round(e.walk_minutes, 1),
            "why": e.reason,
            "advice_en": shelter.advice_text(e),
            "advice_ne": shelter.advice_text(e, nepali=True),
            "navigation": navigate.plan_summary(e),
            "live": {"kind": live.kind, "ne": live.ne, "en": live.en,
                     "remaining_m": (None if live.remaining_m is None
                                     else round(live.remaining_m, 1)),
                     "elevation_now_m": (None if live.elevation_now_m is None
                                         else round(live.elevation_now_m, 1))},
            "resolution_m": round(e.resolution_m, 0),
            "caveat": ("Terrain only, from a coarse national grid. It cannot see bridges, "
                       "culverts, roads or the water. Move away from the stream first."),
        }

    def _triage(self) -> dict[str, Any]:
        """The board with a ranked search order attached.

        Deliberately deterministic and explainable: a coordinator has to be able to ask why one
        call is above another and get an answer they can argue with. Every point traces to a
        named factor, and the ranking is explicitly not a judgement about who matters.
        """
        rows = self.store.trapped()
        ranked = triage.triage(rows)
        # The board itself travels with the ranking, so the panel needs one call and cannot
        # render a rank against a row it does not have.
        by_id = {str(r.get("device_id")): r for r in rows}
        for entry in ranked["ranked"]:
            entry["report"] = by_id.get(entry["device_id"])
        ranked["stats"] = self.store.stats()
        return ranked

    def _slopes(self, q: dict[str, list[str]]) -> dict[str, Any]:
        """Expose the slope picture the earlier work already produces.

        Both existing workstreams face the same client, so a mobile app does not need to
        know that the warning data and the rescue data come from different places.
        """
        day = (q.get("day") or [None])[0]
        data = Path(__file__).resolve().parents[2] / "web" / "public" / "data" / "timeline.json"
        if not data.exists():
            return {"error": "slope data not built", "expected": str(data),
                    "hint": "run scripts/build_timeline.py"}
        try:
            blob = json.loads(data.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"error": f"slope data unreadable: {exc}"}

        days = blob.get("days", [])
        idx = days.index(day) if day in days else (len(days) - 1 if days else -1)
        if idx < 0:
            return {"error": "no days in the slope data"}
        rows = []
        for s in blob.get("sites", []):
            r = s.get("r") or []
            value = r[idx] if idx < len(r) else None
            rows.append({"id": s.get("id"), "title": s.get("title"),
                         "lat": s.get("lat"), "lon": s.get("lon"),
                         "rain_24h_mm": value,
                         "threshold_mm_24h": blob.get("threshold_mm_24h")})
        return {"day": days[idx] if days else None,
                "threshold_mm_24h": blob.get("threshold_mm_24h"),
                "count": len(rows), "slopes": rows}


def _as_float(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _as_int(v: Any) -> int | None:
    try:
        return None if v is None else int(v)
    except (TypeError, ValueError):
        return None


def make_server(port: int = 8080, host: str = "127.0.0.1", store: FieldStore | None = None,
                verbose: bool = False) -> ThreadingHTTPServer:
    handler = type("Handler", (_Handler,), {"store": store or FieldStore()})
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.verbose = verbose          # type: ignore[attr-defined]
    return httpd


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Pahiro field API")
    ap.add_argument("--host", default="0.0.0.0",
                    help="0.0.0.0 by default: field devices are not on localhost")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--data", default="evidence/field.json")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)

    store = FieldStore(a.data)
    httpd = make_server(a.port, a.host, store, verbose=a.verbose)
    print(f"Pahiro field API on http://{a.host}:{a.port}/api/v1")
    print(f"  state: {a.data}   openapi: /api/v1/openapi.json")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
