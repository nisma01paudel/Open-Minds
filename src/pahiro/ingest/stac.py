"""Anonymous STAC access to free satellite and terrain data.

No account, no API key, no cost. Verified against the live service.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from datetime import date

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


def search(
    collection: str,
    bbox: tuple[float, float, float, float],
    start: str,
    end: str,
    cloud_lt: float | None = 20.0,
    limit: int = 200,
    timeout: int = 60,
) -> list[Scene]:
    """Search a STAC collection anonymously.

    bbox is (min_lon, min_lat, max_lon, max_lat) in EPSG:4326.
    """
    body: dict = {
        "collections": [collection],
        "bbox": list(bbox),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": limit,
    }
    if cloud_lt is not None and collection == OPTICAL:
        body["query"] = {"eo:cloud_cover": {"lt": cloud_lt}}

    req = urllib.request.Request(
        STAC_SEARCH,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)

    scenes: list[Scene] = []
    for feat in payload.get("features", []):
        props = feat.get("properties", {})
        ts = props.get("datetime") or props.get("start_datetime")
        if not ts:
            continue
        assets = {
            key: a["href"]
            for key, a in feat.get("assets", {}).items()
            if "href" in a and a["href"].startswith("http")
        }
        proj = props.get("proj:epsg")
        scenes.append(
            Scene(
                id=feat["id"],
                collection=collection,
                acquired=date.fromisoformat(ts[:10]),
                cloud_cover=props.get("eo:cloud_cover"),
                assets=assets,
                platform=props.get("platform"),
                epsg=int(proj) if proj else None,
            )
        )
    scenes.sort(key=lambda s: s.acquired)
    return scenes
