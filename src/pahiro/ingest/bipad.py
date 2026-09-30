"""BIPAD client: Nepal's national disaster portal, read anonymously.

Why this matters: BIPAD is not a hypothetical integration. It is a live,
public, unauthenticated service with two things we need.

1. ``highway/`` - a road-blockage register maintained by DoR divisions: 398
   records, ~77% of them ``closureReason="Landslide"``, each with road reference,
   chainage, status, repair ETA and a contact person. This is the closest thing
   Nepal has to a work order, and our dispatch object maps onto it field-for-field.

2. ``geoserver`` - 2,610 layers (274 public), including ward-level landslide
   hazard and risk. A coordinate resolves to a ward, a municipality, a district
   and a hazard class with no agreement and no account.

Design notes that matter:
- The API's ``count`` field is broken (returns int64 max), so pagination must
  walk pages until a short page arrives. Never trust ``count``.
- ``citizen-report/`` is world-writable. We deliberately do NOT write to it:
  it holds 7,081 reports of which zero are verified. Writing there without a
  named verifying authority would reproduce an existing failure.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE = "https://bipadportal.gov.np/api/v1"
GEOSERVER = "https://bipadportal.gov.np/geoserver"
USER_AGENT = "pahiro/0.1 (open-source slope change research)"

# Hazard id 17 is Landslide in BIPAD's hazard table.
LANDSLIDE_HAZARD_ID = 17

# Ward polygons carrying both landslide hazard and risk attributes.
WARD_HAZARD_RISK_LAYER = "Bipad:durham_landslide_hazard_risk_ward"


def _request(url: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


# ---------------------------------------------------------------- geometry ---
def point_in_ring(lon: float, lat: float, ring: list) -> bool:
    """Ray casting. Pure Python so the client has no geometry dependency."""
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > lat) != (y2 > lat):
            xin = (x2 - x1) * (lat - y1) / ((y2 - y1) or 1e-12) + x1
            if lon < xin:
                inside = not inside
    return inside


def point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    t = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if t == "Polygon":
        if not coords:
            return False
        if not point_in_ring(lon, lat, coords[0]):
            return False
        return not any(point_in_ring(lon, lat, hole) for hole in coords[1:])
    if t == "MultiPolygon":
        return any(point_in_geometry(lon, lat, {"type": "Polygon", "coordinates": poly})
                   for poly in coords)
    return False


@dataclass
class Ward:
    """The administrative home of a coordinate, plus its hazard classification."""
    ward: str | None
    municipality: str | None
    district: str | None
    province: str | None
    centre: str | None
    properties: dict

    def describe(self) -> str:
        bits = [b for b in (self.ward and f"Ward {self.ward}", self.municipality,
                            self.district) if b]
        return ", ".join(bits) if bits else "unknown ward"


class BipadClient:
    def __init__(self, user_agent: str = USER_AGENT, timeout: int = 60):
        self.user_agent = user_agent
        self.timeout = timeout

    # ------------------------------------------------------------- REST API --
    def _api(self, path: str, **params) -> dict:
        url = f"{BASE}/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return _request(url, self.timeout)

    def road_blockages(self, page_size: int = 50, max_records: int | None = None) -> list[dict]:
        """The DoR road-blockage dispatch register. Paginates past the broken count."""
        out: list[dict] = []
        offset = 0
        while True:
            page = self._api("highway/", limit=page_size, offset=offset,
                             ordering="-dateRoadblockStart")
            results = page.get("results") or []
            out.extend(results)
            if len(results) < page_size:
                break
            offset += page_size
            if max_records and len(out) >= max_records:
                break
        return out[:max_records] if max_records else out

    def landslide_incidents(self, page_size: int = 1000,
                           max_records: int | None = None) -> list[dict]:
        """Every landslide incident BIPAD holds, paginated.

        This is the only Nepal source with per-event day-precision dates AND
        coordinates. Two traps, both handled here:
        - `count` returns int64 max on every endpoint, so pagination walks pages
          until a short page arrives; it never trusts `count`.
        - repeated coordinates are administrative default points, not per-event
          sites. Deduplication is the caller's job - see build_event_benchmark.
        """
        out: list[dict] = []
        offset = 0
        while True:
            page = self._api("incident/", hazard=LANDSLIDE_HAZARD_ID,
                             limit=page_size, offset=offset)
            results = page.get("results") or []
            out.extend(results)
            if len(results) < page_size:
                break
            offset += page_size
            if max_records and len(out) >= max_records:
                break
        return out[:max_records] if max_records else out

    def landslide_blockages(self, **kw) -> list[dict]:
        """Only the road blockages BIPAD attributes to landslides."""
        return [r for r in self.road_blockages(**kw)
                if (r.get("closureReason") or "").lower() == "landslide"]

    # ------------------------------------------------------------ GeoServer --
    def _wfs(self, type_name: str, bbox: tuple[float, float, float, float],
             count: int = 20) -> list[dict]:
        query = urllib.parse.urlencode({
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeName": type_name, "outputFormat": "application/json",
            "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:4326",
            "count": count,
        })
        return _request(f"{GEOSERVER}/wfs?{query}", self.timeout).get("features") or []

    def ward_at(self, lon: float, lat: float, pad: float = 0.02,
                layer: str = WARD_HAZARD_RISK_LAYER) -> Ward | None:
        """Resolve a coordinate to its ward by true point-in-polygon containment."""
        bbox = (lon - pad, lat - pad, lon + pad, lat + pad)
        for feat in self._wfs(layer, bbox, count=40):
            geom = feat.get("geometry") or {}
            if point_in_geometry(lon, lat, geom):
                p = feat.get("properties") or {}
                return Ward(
                    ward=str(p.get("Ward_NEW_W") or p.get("title") or "") or None,
                    municipality=p.get("Ward_GaPa_") or p.get("municipali"),
                    district=p.get("Ward_DISTR") or p.get("district"),
                    province=str(p.get("Ward_STATE") or p.get("province") or "") or None,
                    centre=p.get("Ward_CENTE"),
                    properties=p,
                )
        return None

    # --------------------------------------------------------- dispatch glue --
    def to_bipad_highway_payload(self, dispatch, ward: Ward | None = None) -> dict:
        """Map a dispatch object onto the fields the register actually accepts.

        We fill what we can evidence. We never invent chainage or a contact
        person - those come from the responsible division, so we list them as
        missing rather than guessing.
        """
        payload = {
            "roadRefno": None,                 # needs the road reference dataset
            "division": None,                  # derived from the DoR division of the district
            "chainage": None,                  # we cannot derive chainage from imagery
            "closureReason": "Landslide",
            "status": "CLOSED" if dispatch.priority == "high" else "PARTIAL_OPEN",
            "dateRoadblockStart": dispatch.as_of.isoformat(),
            "effortsBeingMade": (dispatch.recommendation or
                                 dispatch.inspect_first[0] if dispatch.inspect_first else None),
            "contactPerson": None,             # supplied by the responsible office
            "remarks": dispatch.advisory_ne,
        }
        if ward is not None:
            payload["district"] = ward.district
            payload["municipality"] = ward.municipality
            payload["ward"] = ward.ward
        missing = [k for k, v in payload.items() if v is None]
        return {"payload": payload, "requires_from_office": missing,
                "authority": (dispatch.authority or {}).get("institution")}
