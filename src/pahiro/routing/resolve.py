"""Resolve a coordinate to its administrative home, from government data.

This is the factual half of routing: a slope belongs to a ward, inside a
municipality, inside a district, inside a province. That hierarchy is a matter
of record, and BIPAD's public GeoServer serves it. The *legal* half - which
office is mandated to act on which asset - comes from the ontology, and only
with a citation.

Keeping the two apart matters: we can be certain about where a slope is long
before we are certain about who must act on it.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pahiro.ingest.bipad import BipadClient


@dataclass
class RoutingContext:
    lon: float
    lat: float
    ward: str | None = None
    municipality: str | None = None
    district: str | None = None
    province: str | None = None
    centre: str | None = None
    source: str = "none"                      # 'bipad-wfs' | 'cache' | 'none'
    attributes: dict = field(default_factory=dict)

    def describe(self) -> str:
        bits = [b for b in (
            self.ward and f"Ward {self.ward}",
            self.municipality, self.district,
            self.province and f"Province {self.province}") if b]
        return ", ".join(bits) if bits else "unresolved"


def resolve(lon: float, lat: float, client: BipadClient | None = None,
            cache_path: str | Path | None = None, use_cache: bool = True) -> RoutingContext:
    """Resolve a coordinate, falling back to a cached answer when offline."""
    cache: dict = {}
    path = Path(cache_path) if cache_path else None
    if path and path.exists():
        try:
            cache = json.loads(path.read_text())
        except Exception:
            cache = {}

    key = f"{lon:.5f},{lat:.5f}"
    if use_cache and key in cache:
        return RoutingContext(**cache[key], source="cache")

    ctx = RoutingContext(lon=lon, lat=lat)
    try:
        ward = (client or BipadClient()).ward_at(lon, lat)
    except Exception:
        ward = None

    if ward is not None:
        ctx.ward = ward.ward
        ctx.municipality = ward.municipality
        ctx.district = ward.district
        ctx.province = ward.province
        ctx.centre = ward.centre
        ctx.source = "bipad-wfs"
        ctx.attributes = {k: v for k, v in ward.properties.items()
                          if k in ("ward", "municipali", "district", "province")}
        if path:
            cache[key] = {k: v for k, v in asdict(ctx).items() if k != "source"}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    return ctx
