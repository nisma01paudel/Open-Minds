"""Trip planning over real hiking trails, with no network at all.

WHY THIS IS HERE
----------------
Everything else in this repository assumes something is going wrong. That is the wrong thing for
an app to be good at and nothing else - nobody opens a landslide tool on a sunny Saturday, and a
tool nobody opens is a tool nobody has installed when the mountain moves.

So this half is for the ordinary day: pick a trail, see how far and how much climbing, get a time.
It runs off two files that ship with the app - the OSM trail network and the bundled terrain - and
it never calls anything.

WHAT IT IS HONEST ABOUT
-----------------------
Three things, and they are in the returned object rather than only in this docstring:

1. **The trail data is OpenStreetMap, and Nepali footpath coverage is incomplete.** In the
   Kathmandu valley the valley floor is mapped well and the high ridges are not. A trail missing
   from here is not a trail that does not exist; it is one nobody has drawn yet.
2. **The bundled terrain is a 1.2 km grid.** Ascent and descent are computed from it and are
   therefore INDICATIVE - they will miss a 40 m knoll entirely, and a walk that crosses one will
   read flatter than it is. Distance is trustworthy; climbing is a guide.
3. **The route follows mapped paths.** It does not know about a washed-out bridge, a locked gate,
   a landslide that closed the trail last week, or a dog. It plans a line; a walker decides
   whether to walk it.

Attribution: trail data © OpenStreetMap contributors, ODbL 1.0. It stays in the output.
"""
from __future__ import annotations

import heapq
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

EARTH_R_M = 6371008.8

# Naismith's rule, the standard for estimating walking time: 5 km/h on the flat, plus a minute for
# every 10 m of ascent. It is a rule of thumb from 1892 and it is still what mountain rescue uses,
# which is exactly why it is the right thing to quote rather than something invented here.
FLAT_KMH = 5.0
MINUTES_PER_10M_UP = 1.0

# A trail step is only merged into the graph if it connects points closer than this. Beyond it,
# something is wrong with the data rather than with the walker.
MAX_EDGE_M = 2000.0

# JUNCTION SNAP, and why it is needed.
#
# Two OSM footpaths that meet on the ground often do not share a node: they are drawn as separate
# ways that visually touch. Straight out of Overpass the valley network came apart into 2,246
# components of which the LARGEST WAS 4.3% OF NODES - so "route from Budhanilkantha to the
# Shivapuri ridge" answered "these are on separate parts of the mapped network", which is true of
# the data and false of the mountain.
#
# So endpoints within this distance of each other are treated as the same junction. This is what
# every real router does; the alternative is to refuse to plan a walk that a person can plainly
# walk. 25 m is a compromise: large enough to close a mapping gap at a junction, small enough that
# it will not silently bridge a stream or join two switchbacks of the same trail.
JUNCTION_SNAP_M = 25.0

DEFAULT_TRAILS = "web/public/data/trails.geojson"


@dataclass
class TrailPlan:
    """A planned walk. Every field is something a person would actually ask."""

    ok: bool
    distance_m: float | None = None
    ascent_m: float | None = None
    descent_m: float | None = None
    minutes: int | None = None
    points: list[tuple[float, float]] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    start_snap_m: float | None = None
    end_snap_m: float | None = None
    reason: str = ""
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.ok:
            return f"no route: {self.reason}"
        km = (self.distance_m or 0) / 1000.0
        h, m = divmod(self.minutes or 0, 60)
        out = f"{km:.1f} km, +{self.ascent_m:.0f} m / -{self.descent_m:.0f} m, about {h}h{m:02d}"
        if self.names:
            out += f" — via {', '.join(self.names[:3])}"
        return out


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * math.asin(min(1.0, math.sqrt(h)))


def _key(lon: float, lat: float) -> tuple[float, float]:
    """Node identity. 5 decimals is the precision the bundle was written at, so two ways that
    share an endpoint produce the same key and the network joins up."""
    return (round(lon, 5), round(lat, 5))


class TrailNetwork:
    """The walkable network as a graph. Built once, then queried offline."""

    def __init__(self) -> None:
        self.nodes: dict[tuple[float, float], int] = {}
        self.coords: list[tuple[float, float]] = []
        self.adj: list[list[tuple[int, float, int]]] = []
        self.trail_meta: list[dict] = []
        self.trails = 0
        self.snapped = 0
        # grid buckets for the junction search; cell size is the snap tolerance in degrees
        self._cell = JUNCTION_SNAP_M / 111_320.0
        self._grid: dict[tuple[int, int], list[int]] = {}

    def _bucket(self, lon: float, lat: float) -> tuple[int, int]:
        return (int(lat // self._cell), int(lon // self._cell))

    def _node(self, lon: float, lat: float) -> int:
        """Existing node within JUNCTION_SNAP_M, or a new one.

        SNAPPING HAPPENS HERE, at insertion, rather than as graph surgery afterwards. Merging two
        nodes that already have edges means rewriting every neighbour's adjacency list, and the
        first version of this did exactly that and made connectivity WORSE - 2,246 components
        became 23,485, because the rewrite was one level deep and left dangling references behind.

        Doing it on the way in is both simpler and correct: a way that arrives at a junction that
        is already known simply attaches to it, and the graph is never in an inconsistent state.
        """
        k = _key(lon, lat)
        i = self.nodes.get(k)
        if i is not None:
            return i

        # look for a nearby node before creating one
        if self._cell:
            r, c = self._bucket(lon, lat)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    for j in self._grid.get((r + dr, c + dc), ()):
                        if _haversine((lon, lat), self.coords[j]) <= JUNCTION_SNAP_M:
                            self.nodes[k] = j
                            self.snapped += 1
                            return j

        i = len(self.coords)
        self.nodes[k] = i
        self.coords.append(k)
        self.adj.append([])
        if self._cell:
            self._grid.setdefault(self._bucket(lon, lat), []).append(i)
        return i

    @classmethod
    def from_geojson(cls, path: str | Path) -> "TrailNetwork":
        net = cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for f in data.get("features", []):
            coords = f.get("geometry", {}).get("coordinates") or []
            if len(coords) < 2:
                continue
            props = f.get("properties") or {}
            tid = len(net.trail_meta)
            net.trail_meta.append({"name": props.get("n", ""), "difficulty": props.get("d", ""),
                                   "highway": props.get("h", "")})
            net.trails += 1
            for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
                a, b = net._node(lon1, lat1), net._node(lon2, lat2)
                if a == b:
                    continue
                d = _haversine(net.coords[a], net.coords[b])
                if d > MAX_EDGE_M:
                    continue
                net.adj[a].append((b, d, tid))
                net.adj[b].append((a, d, tid))
        return net

    def nearest(self, lon: float, lat: float) -> tuple[int, float]:
        """The closest point on the network, and how far away it is.

        A phone at a trailhead is rarely standing on a mapped vertex, so snapping is required -
        and the snap distance is returned, because "2.4 km to the nearest mapped path" is
        information the walker needs and a silent snap would hide.
        """
        best, best_d = -1, float("inf")
        for i, c in enumerate(self.coords):
            d = _haversine((lon, lat), c)
            if d < best_d:
                best, best_d = i, d
        return best, best_d

    def route(self, start: tuple[float, float], end: tuple[float, float],
              dem=None) -> TrailPlan:
        """Shortest walk between two points, by distance.

        Shortest by distance rather than by time or by effort, deliberately: ASCENT IS COMPUTED
        FROM A 1.2 KM GRID and is too coarse to optimise against. Optimising on a number you do
        not trust is how a planner sends someone over a ridge to save four minutes.
        """
        if not self.coords:
            return TrailPlan(False, reason="the trail network is empty")

        src, d_start = self.nearest(*start)
        dst, d_end = self.nearest(*end)
        if src < 0 or dst < 0:
            return TrailPlan(False, reason="no trails near either end of that trip")

        dist = {src: 0.0}
        prev: dict[int, int] = {}
        pq = [(0.0, src)]
        seen = set()
        while pq:
            d, u = heapq.heappop(pq)
            if u in seen:
                continue
            seen.add(u)
            if u == dst:
                break
            for v, w, _ in self.adj[u]:
                nd = d + w
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))

        if dst not in dist:
            return TrailPlan(False, start_snap_m=d_start, end_snap_m=d_end,
                             reason=("the two points are on separate parts of the mapped network - "
                                     "there is no walkable link between them in this data"))

        path: list[int] = []
        cur = dst
        while cur != src:
            path.append(cur)
            cur = prev[cur]
        path.append(src)
        path.reverse()

        points = [self.coords[i] for i in path]
        ascent = descent = 0.0
        if dem is not None and len(points) > 1:
            elev = [dem.elevation_at(lat, lon) for lon, lat in points]
            for a, b in zip(elev, elev[1:]):
                if b > a:
                    ascent += b - a
                else:
                    descent += a - b

        # Names of the distinct trails walked, in order of first use.
        names: list[str] = []
        for u, v in zip(path, path[1:]):
            for nxt, _, tid in self.adj[u]:
                if nxt == v:
                    nm = self.trail_meta[tid]["name"] if tid < len(self.trail_meta) else ""
                    if nm and nm not in names:
                        names.append(nm)
                    break

        total = dist[dst]
        minutes = (total / 1000.0) / FLAT_KMH * 60.0 + (ascent / 10.0) * MINUTES_PER_10M_UP

        warnings = []
        if d_start > 300 or d_end > 300:
            warnings.append(
                f"the nearest mapped trail is {max(d_start, d_end):.0f} m away, so part of this "
                f"walk is off-network and not planned")
        if dem is None:
            warnings.append("no terrain loaded, so ascent and time are distance-only")
        else:
            warnings.append("ascent comes from a 1.2 km terrain grid, so treat the climbing as "
                            "indicative rather than exact")
        warnings.append("follows mapped paths only: it does not know about washed-out bridges, "
                        "closed gates or a trail that moved last monsoon")

        return TrailPlan(True, distance_m=total, ascent_m=ascent, descent_m=descent,
                         minutes=int(round(minutes)), points=points, names=names,
                         start_snap_m=d_start, end_snap_m=d_end, warnings=warnings)

    def stats(self) -> dict:
        live = sum(1 for a in self.adj if a)
        return {"trails": self.trails, "nodes": len(self.coords), "junctions": live,
                "snapped": self.snapped,
                "edges": sum(len(a) for a in self.adj) // 2}


@dataclass
class NearbyTrail:
    """A trail you could walk from where you are standing."""

    name: str
    difficulty: str
    distance_to_start_m: float
    length_m: float
    climb_m: float
    points: list[tuple[float, float]]

    @property
    def walk_minutes(self) -> int:
        return int(round((self.length_m / 1000.0) / FLAT_KMH * 60.0
                         + (self.climb_m / 10.0) * MINUTES_PER_10M_UP))


def nearby(net: "TrailNetwork", lon: float, lat: float, *, radius_m: float = 3000.0,
           limit: int = 20, dem=None, min_length_m: float = 150.0) -> list[NearbyTrail]:
    """Trails whose mapped line passes within `radius_m` of a point, longest first.

    THIS IS THE FEATURE THAT SURVIVES THE FRAGMENTATION, and it is the one a walker actually wants.
    Point-to-point routing needs both ends to be on the same connected component of the mapped
    network, which in the Kathmandu valley is often not true - the footpath data is real but
    disconnected. "What can I walk from here" needs no such thing: it asks what is near you, and
    that question is answerable wherever you are standing.

    `climb_m` comes from the same 1.2 km terrain grid as everything else here and is indicative.
    Trails shorter than `min_length_m` are skipped: a 20 m stretch of steps is not a walk.
    """
    out: list[NearbyTrail] = []
    # Grouped by TRAIL ID. Grouping by name was the first attempt and it was wrong: every unnamed
    # path in the valley shares the name "", so they merged into one 558 km "trail" with 248 km of
    # climbing. A name is a label, not an identity.
    by_tid: dict[int, list[tuple[tuple[float, float], tuple[float, float]]]] = {}
    seen_edges = set()
    for u, edges in enumerate(net.adj):
        for v, _w, tid in edges:
            key = (min(u, v), max(u, v), tid)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            by_tid.setdefault(tid, []).append((net.coords[u], net.coords[v]))

    for tid, edges in by_tid.items():
        pts = [p for e in edges for p in e]
        if not pts:
            continue
        near = min(_haversine((lon, lat), p) for p in pts)
        if near > radius_m:
            continue
        length = sum(_haversine(a, b) for a, b in edges)
        if length < min_length_m:
            continue
        climb = 0.0
        if dem is not None and len(pts) > 1:
            # Sampled at a handful of points, not per vertex. The terrain grid is ~1.2 km, so
            # summing a gain at every mapped vertex counts the same hillside several times and
            # reports climbing that is not there.
            step = max(1, len(pts) // 12)
            samp = pts[::step] + [pts[-1]]
            elev = [dem.elevation_at(p[1], p[0]) for p in samp]
            climb = sum(max(0.0, b - a) for a, b in zip(elev, elev[1:]))
        meta = net.trail_meta[tid] if tid < len(net.trail_meta) else {}
        out.append(NearbyTrail(name=meta.get("name") or "(unnamed path)",
                               difficulty=meta.get("difficulty") or "not recorded",
                               distance_to_start_m=near, length_m=length, climb_m=climb,
                               points=pts[:400]))
    out.sort(key=lambda x: -x.length_m)
    return out[:limit]


def load_default(dem=None) -> "TrailNetwork":
    """The network that ships with the app."""
    root = Path(__file__).resolve().parents[2]
    return TrailNetwork.from_geojson(root / DEFAULT_TRAILS)
