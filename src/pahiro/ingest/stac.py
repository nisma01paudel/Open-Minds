"""Anonymous STAC access to free satellite and terrain data.

No account, no API key, no cost. Verified against the live service.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date

# Public STAC endpoints occasionally return 5xx or drop a connection. A demo that
# dies on a transient 502 is a failed demo, so every request retries with backoff.
RETRY_STATUS = {429, 500, 502, 503, 504}
RETRIES = 4
BACKOFF_SECONDS = 2.0

STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"

# Collections verified reachable without credentials.
OPTICAL = "sentinel-2-l2a"
RADAR = "sentinel-1-grd"
DEM = "cop-dem-glo-30"
LANDSAT = "landsat-c2-l2"

# Asset keys as published by the Earth Search collection (verified).
BANDS = {
    "blue": "blue", "green": "green", "red": "red", "nir": "nir",
    "nir08": "nir08", "swir16": "swir16", "swir22": "swir22",
    "scl": "scl", "visual": "visual",
}


@dataclass
class Scene:
    """One satellite observation, with the assets we need to read it."""
    id: str
    collection: str
    acquired: date
    cloud_cover: float | None
    assets: dict[str, str] = field(default_factory=dict)
    platform: str | None = None
    epsg: int | None = None

    @property
    def is_optical(self) -> bool:
        return self.collection == OPTICAL

    @property
    def usable_for_change(self) -> bool:
        """Optical scenes need a low cloud fraction; radar is always usable."""
        if not self.is_optical:
            return True
        return self.cloud_cover is not None and self.cloud_cover < 20.0


def _scene_from_feature(feat: dict, collection: str) -> "Scene | None":
    """Build a Scene from one STAC feature, or None if it has no usable timestamp."""
    props = feat.get("properties", {})
    ts = props.get("datetime") or props.get("start_datetime")
    if not ts:
        return None
    assets = {}
    for key, a in feat.get("assets", {}).items():
        href = _readable_href(a.get("href"))
        if href:
            assets[key] = href
    proj = props.get("proj:epsg")
    return Scene(
        id=feat["id"],
        collection=collection,
        acquired=date.fromisoformat(ts[:10]),
        cloud_cover=props.get("eo:cloud_cover"),
        assets=assets,
        platform=props.get("platform"),
        epsg=int(proj) if proj else None,
    )


def search(
    collection: str,
    bbox: tuple[float, float, float, float],
    start: str,
    end: str,
    cloud_lt: float | None = 20.0,
    limit: int = 250,
    max_items: int | None = None,
    paginate: bool = True,
    timeout: int = 60,
) -> list[Scene]:
    """Search a STAC collection anonymously, following pagination.

    bbox is (min_lon, min_lat, max_lon, max_lat) in EPSG:4326.

    Page size matters: on a large bbox the upstream service returns 502 rather than
    a page when limit is too big, so pages stay modest and we follow the `next` link
    (Earth Search puts the continuation token in links[rel=next].body, merge=False).
    """
    body: dict = {
        "collections": [collection],
        "bbox": list(bbox),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": limit,
    }
    if cloud_lt is not None and collection == OPTICAL:
        body["query"] = {"eo:cloud_cover": {"lt": cloud_lt}}

    scenes: list[Scene] = []
    seen: set[str] = set()
    while True:
        payload = _post_json(STAC_SEARCH, body, timeout)
        features = payload.get("features", [])
        for feat in features:
            scene = _scene_from_feature(feat, collection)
            if scene is not None and scene.id not in seen:
                seen.add(scene.id)
                scenes.append(scene)
        if not paginate or not features:
            break
        if max_items is not None and len(scenes) >= max_items:
            break
        nxt = next((l for l in payload.get("links", []) if l.get("rel") == "next"), None)
        if not nxt or not isinstance(nxt.get("body"), dict):
            break
        body = dict(nxt["body"])
        body.setdefault("collections", [collection])
    scenes.sort(key=lambda s: s.acquired)
    return scenes[:max_items] if max_items else scenes


def _post_json(url: str, body: dict, timeout: int = 60) -> dict:
    """POST JSON with retries on transient failures. Raises on the last attempt."""
    last: Exception | None = None
    for attempt in range(RETRIES):
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in RETRY_STATUS:
                raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
        if attempt < RETRIES - 1:
            time.sleep(BACKOFF_SECONDS * (2 ** attempt))
    raise RuntimeError(f"STAC request failed after {RETRIES} attempts: {last}")


def _readable_href(href: str | None) -> str | None:
    """Normalise an asset href into something GDAL can read.

    Some collections - Copernicus DEM in particular - publish `s3://bucket/key`
    rather than an HTTPS URL. Dropping those silently loses the whole terrain layer,
    which is what happened before this existed: the DEM query returned a tile with an
    empty asset map. Convert to the bucket's HTTPS endpoint, which /vsicurl reads
    directly.
    """
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("s3://"):
        rest = href[len("s3://"):]
        bucket, _, key = rest.partition("/")
        if bucket and key:
            return f"https://{bucket}.s3.amazonaws.com/{key}"
    return None
