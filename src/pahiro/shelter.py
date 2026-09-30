"""Where to go, and how high, when the water is coming.

WHY THIS EXISTS
---------------
A warning that says "flash flood expected" has already failed the person reading it. It tells
them a thing is happening and leaves the only decision that matters unanswered: *which way do I
run, and how far up?* People have died within sight of safe ground because nobody had told them
which direction it was, and a warning that arrives in a minute is worth nothing if it takes ten
to work out what to do with it.

So this module answers exactly two questions, in advance, for a specific place:

    which way, and how high

It reads elevation from the national DEM the repository already ships for the 3D view - 832x512
over Nepal, uint16 metres, entirely local, so the answer arrives with the network already dead.

WHAT IT CAN AND CANNOT KNOW
---------------------------
A DEM is a surface, not a map. It knows how high the ground is and nothing else: not bridges,
not culverts, not which side of the river you are on, not whether the slope between you and the
target is a cliff or a footpath, and not where the water will actually go. A hydraulic model
would know some of that; this does not have one, and says so on every answer it gives.

The shipped DEM is also coarse - decimated to roughly 1.1 km per cell, which is a *valley-scale*
resolution. It can honestly say "higher ground lies 2.4 km to the north-east, 180 m above you".
It cannot honestly say "run to that house". Every result therefore carries its resolution and a
caveat, and the advice text repeats the caveat rather than burying it in a docstring.

WHY IT REFUSES SOMETIMES
------------------------
In the Terai the ground is flat for tens of kilometres. There is no nearby high ground, and the
honest answer is that you cannot outrun a flash flood on foot - you need a solid multi-storey
building and the highest floor you can reach. An escape planner that always finds *some* point
would send a family running across a plain in the dark towards a spot 18 km away and call that
a plan. `plan_escape` returns `reachable=False` instead, and the advisory changes shape.

The distance limit is a walking estimate, not a hydrological one: a person on foot in the dark,
possibly injured, carrying a child, manages roughly 1 km in 12 minutes on flat ground and far
less uphill. `MAX_WALK_M` is deliberately pessimistic.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Default terrain artefacts, as written by scripts/build_terrain.py for the 3D view.
DEFAULT_DEM_BIN = "web/public/data/terrain.bin"
DEFAULT_DEM_META = "web/public/data/terrain.json"

# A flash flood in a Nepali gully typically rises 3-6 m above the channel bed in minutes. Five
# is the default because it is the middle of that range, not because it is measured for any
# particular stream - the caller should pass the number they have.
DEFAULT_RISE_M = 5.0

# Pessimistic on-foot reach: 2 km is about half an hour flat, and longer uphill in the dark.
MAX_WALK_M = 2000.0

# Climbing one metre costs roughly what walking eight metres on the flat costs, as a walking
# equivalence. This is what stops the planner sending someone up a 300 m cliff face because it
# was marginally closer than a gentle ridge.
CLIMB_PENALTY = 8.0

# A target must clear the expected rise by this much as well, so that "safe" ground is not the
# bank of the same stream one cell over.
SAFETY_MARGIN_M = 2.0

_COMPASS = ("north", "north-east", "east", "south-east",
            "south", "south-west", "west", "north-west")

# The same eight directions in Nepali. A sentence that mixes "पानी आउनुअघि east तर्फ" is worse
# than no Nepali at all: the reader has to translate the one word the instruction turns on,
# in the seconds they do not have.
_COMPASS_NE = ("उत्तर", "उत्तर-पूर्व", "पूर्व", "दक्षिण-पूर्व",
               "दक्षिण", "दक्षिण-पश्चिम", "पश्चिम", "उत्तर-पश्चिम")


def compass_index(bearing_deg: float) -> int:
    return int((bearing_deg + 22.5) % 360 // 45)


@dataclass
class Dem:
    """A local elevation grid, ready to sample. Fully offline."""

    elevation: np.ndarray          # (rows, cols) float64, metres
    west: float
    south: float
    east: float
    north: float

    @property
    def rows(self) -> int:
        return self.elevation.shape[0]

    @property
    def cols(self) -> int:
        return self.elevation.shape[1]

    @property
    def pixel_deg_lat(self) -> float:
        return (self.north - self.south) / self.rows

    @property
    def pixel_deg_lon(self) -> float:
        return (self.east - self.west) / self.cols

    def pixel_size_m(self, lat: float) -> tuple[float, float]:
        """Metres per pixel, north-south and east-west, at a given latitude."""
        dy = self.pixel_deg_lat * 111_320.0
        dx = self.pixel_deg_lon * 111_320.0 * math.cos(math.radians(lat))
        return dy, dx

    def contains(self, lat: float, lon: float) -> bool:
        return (self.south <= lat <= self.north) and (self.west <= lon <= self.east)

    def index_of(self, lat: float, lon: float) -> tuple[int, int]:
        """Row and column for a coordinate. Row 0 is the northern edge."""
        row = int(round((self.north - lat) / self.pixel_deg_lat))
        col = int(round((lon - self.west) / self.pixel_deg_lon))
        return max(0, min(self.rows - 1, row)), max(0, min(self.cols - 1, col))

    def latlon_of(self, row: int, col: int) -> tuple[float, float]:
        lat = self.north - (row + 0.5) * self.pixel_deg_lat
        lon = self.west + (col + 0.5) * self.pixel_deg_lon
        return lat, lon

    def elevation_at(self, lat: float, lon: float) -> float:
        row, col = self.index_of(lat, lon)
        return float(self.elevation[row, col])

    def metres_between(self, a: tuple[int, int], b: tuple[int, int], lat: float) -> float:
        dy, dx = self.pixel_size_m(lat)
        return math.hypot((a[0] - b[0]) * dy, (a[1] - b[1]) * dx)


def load_dem(bin_path: str | Path = DEFAULT_DEM_BIN,
             meta_path: str | Path = DEFAULT_DEM_META) -> Dem | None:
    """Read the bundled national DEM, or None if it has not been built in this checkout."""
    bin_path, meta_path = Path(bin_path), Path(meta_path)
    if not bin_path.exists() or not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    width, height = int(meta["width"]), int(meta["height"])
    raw = np.frombuffer(bin_path.read_bytes(), dtype="<u2")
    if raw.size != width * height:
        return None
    grid = raw.reshape(height, width).astype("float64")
    return Dem(elevation=grid, west=float(meta["west"]), south=float(meta["south"]),
               east=float(meta["east"]), north=float(meta["north"]))


@dataclass
class Escape:
    """An answer to "which way, and how high", with everything needed to judge it."""

    reachable: bool
    target_lat: float | None
    target_lon: float | None
    from_elevation_m: float
    target_elevation_m: float | None
    climb_m: float | None
    distance_m: float | None
    bearing_deg: float | None
    compass: str | None
    rise_m: float
    resolution_m: float
    reason: str

    @property
    def walk_minutes(self) -> float | None:
        """A deliberately slow estimate: 4 km/h flat, and uphill costs more."""
        if self.distance_m is None:
            return None
        metres = self.distance_m + (self.climb_m or 0) * CLIMB_PENALTY
        return metres / (4000.0 / 60.0)


def uphill_bearing(dem: Dem, lat: float, lon: float, window: int = 2) -> float | None:
    """Which way the ground rises, degrees clockwise from north.

    This is the direction that matters in a flood, and it is not the same as "towards the
    nearest cell that happens to be higher". On a coarse grid the nearest higher cell is
    routinely one pixel away in an arbitrary direction, and at Melamchi that agreed with
    "south" - which in a valley is as likely to be downstream as up the hillside. Running
    downstream is how people die.

    So the bearing is taken from the gradient over a small neighbourhood, which is the local
    fall line, and candidates off that line are rejected.
    """
    row, col = dem.index_of(lat, lon)
    r0, r1 = max(0, row - window), min(dem.rows, row + window + 1)
    c0, c1 = max(0, col - window), min(dem.cols, col + window + 1)
    patch = dem.elevation[r0:r1, c0:c1]
    if patch.size < 4 or patch.shape[0] < 2 or patch.shape[1] < 2:
        return None

    dy, dx = dem.pixel_size_m(lat)
    # np.gradient returns (d/drow, d/dcol); row increases southwards, so north is negative.
    d_row, d_col = np.gradient(patch, dy, dx)
    rise_north = -float(np.mean(d_row))
    rise_east = float(np.mean(d_col))
    if not (math.isfinite(rise_north) and math.isfinite(rise_east)):
        return None
    if abs(rise_north) < 1e-9 and abs(rise_east) < 1e-9:
        return None
    return (math.degrees(math.atan2(rise_east, rise_north)) + 360) % 360


def _angle_between(a: float, b: float) -> float:
    """Smallest absolute angle between two bearings, 0..180."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def plan_escape(dem: Dem, lat: float, lon: float, rise_m: float = DEFAULT_RISE_M,
                max_walk_m: float = MAX_WALK_M,
                max_turn_deg: float = 75.0) -> Escape:
    """Find ground that clears the expected rise, in a direction that goes uphill.

    Returns an `Escape`. When nothing within walking distance clears the rise, `reachable` is
    False and `reason` says what to do instead - which in the Terai is the correct answer and
    not a failure of the planner.
    """
    if not dem.contains(lat, lon):
        return Escape(False, None, None, float("nan"), None, None, None, None, None, rise_m,
                      dem.pixel_deg_lat * 111_320.0,
                      "this point is outside the bundled DEM, so no escape can be planned")
    dy, dx = dem.pixel_size_m(lat)
    resolution = max(dy, dx)

    origin = dem.index_of(lat, lon)
    here = float(dem.elevation[origin])
    need = here + rise_m + SAFETY_MARGIN_M
    up = uphill_bearing(dem, lat, lon)

    rows, cols = np.nonzero(dem.elevation >= need)
    if rows.size == 0:
        return Escape(False, None, None, here, None, None, None, None, None, rise_m, resolution,
                      f"nowhere in the DEM is {rise_m:.0f} m above you, which cannot be right - "
                      f"treat this as no answer rather than a safe one")

    lat_arr = dem.north - (rows + 0.5) * dem.pixel_deg_lat
    lon_arr = dem.west + (cols + 0.5) * dem.pixel_deg_lon
    d_north = (rows - origin[0]) * dy
    d_east = (cols - origin[1]) * dx
    distance = np.hypot(d_north, d_east)
    climb = dem.elevation[rows, cols] - here
    bearings = (np.degrees(np.arctan2(d_east, d_north)) + 360.0) % 360.0

    # Keep only ground that is uphill of here, so an answer is never "one pixel that way"
    # across the valley or down the stream.
    allowed = np.ones(rows.shape, dtype=bool)
    if up is not None:
        delta = np.abs((bearings - up + 180.0) % 360.0 - 180.0)
        allowed = delta <= max_turn_deg

    within = distance <= max_walk_m
    cost = distance + climb * CLIMB_PENALTY
    candidates = allowed & within

    if not candidates.any():
        # Distinguish "flat, nowhere to run" from "high ground exists but only behind you".
        nearest = int(np.argmin(distance))
        if within.any():
            reason = (f"the ground that clears {rise_m:.0f} m within walking distance is not "
                      f"uphill of you - it lies {bearings[int(np.argmin(np.where(within, cost, np.inf)))]:.0f}°, "
                      f"across or down from where you are. Do not cross the water for it: climb "
                      f"the slope you are on, away from the stream")
        else:
            reason = (f"the nearest ground that clears {rise_m:.0f} m is "
                      f"{distance[nearest] / 1000:.1f} km away, which is beyond what anyone "
                      f"covers on foot. Do not run for it: get to a solid multi-storey building "
                      f"and go to the highest floor you can reach")
        return Escape(False, None, None, here, None, None,
                      float(distance[nearest]) if not within.any() else None,
                      None, None, rise_m, resolution, reason)

    best = int(np.argmin(np.where(candidates, cost, np.inf)))
    t_lat, t_lon = float(lat_arr[best]), float(lon_arr[best])
    bearing = float(bearings[best])

    return Escape(
        reachable=True,
        target_lat=t_lat, target_lon=t_lon,
        from_elevation_m=here,
        target_elevation_m=float(dem.elevation[rows[best], cols[best]]),
        climb_m=float(climb[best]),
        distance_m=float(distance[best]),
        bearing_deg=bearing,
        compass=_COMPASS[int((bearing + 22.5) % 360 // 45)],
        rise_m=rise_m,
        resolution_m=resolution,
        reason=(f"uphill ground that clears the expected {rise_m:.0f} m rise by "
                f"{SAFETY_MARGIN_M:.0f} m"
                + (f"; the local fall line runs {up:.0f}°" if up is not None
                   else "; no clear fall line in this terrain")),
    )


def advice_text(e: Escape, *, place: str | None = None, nepali: bool = False) -> str:
    """The sentence a person can act on, with the caveat attached rather than omitted."""
    if nepali:
        return _advice_ne(e, place=place)
    where = f" at {place}" if place else ""
    if not e.reachable:
        return (f"NO REACHABLE HIGH GROUND{where}. {e.reason}. "
                f"Nearest terrain grid is about {e.resolution_m:.0f} m, so treat this as "
                f"regional guidance and follow local instruction.")

    lines = [
        f"GO {e.compass.upper()} — about {e.distance_m:.0f} m"
        + (f", climbing {e.climb_m:.0f} m" if e.climb_m and e.climb_m > 1 else "")
        + f" (roughly {e.walk_minutes:.0f} min on foot, uphill).",
        f"You are at {e.from_elevation_m:.0f} m. Reach at least "
        f"{e.target_elevation_m:.0f} m — that clears the expected {e.rise_m:.0f} m rise.",
        f"Target: {e.target_lat:.5f}, {e.target_lon:.5f} (bearing {e.bearing_deg:.0f}°).",
        f"This is terrain-only, from a {e.resolution_m:.0f} m grid, and it cannot see bridges, "
        f"culverts or the water itself. Move away from the stream first, then uphill.",
    ]
    return " ".join(lines)


def _advice_ne(e: Escape, *, place: str | None = None) -> str:
    """The same instruction, wholly in Nepali - including the direction word."""
    where = f" ({place})" if place else ""
    if not e.reachable:
        return (f"नजिकै सुरक्षित उचाइ छैन{where}। पैदल पुग्न सकिने दूरीभित्र "
                f"अनुमानित {e.rise_m:.0f} मिटर माथिको जमिन छैन, वा त्यो दिशा माथि होइन। "
                f"दौडन नखोज्नुहोस् — बलियो बहुतले भवन खोज्नुहोस् र सक्दो माथिल्लो तल्लामा "
                f"जानुहोस्। पहिले खोलाबाट टाढा जानुहोस्। "
                f"यो नक्सा करिब {e.resolution_m:.0f} मिटरको ग्रिडमा आधारित छ, त्यसैले यसलाई "
                f"क्षेत्रीय सुझाव मान्नुहोस् र स्थानीय निर्देशन पालना गर्नुहोस्।")

    direction = _COMPASS_NE[compass_index(e.bearing_deg)]
    climb = f", करिब {e.climb_m:.0f} मिटर माथि चढ्दै" if e.climb_m and e.climb_m > 1 else ""
    return (f"{direction} तर्फ जानुहोस्{where} — करिब {e.distance_m:.0f} मिटर"
            f"{climb} (पैदल करिब {e.walk_minutes:.0f} मिनेट)। "
            f"तपाईं अहिले {e.from_elevation_m:.0f} मिटरमा हुनुहुन्छ। "
            f"कम्तीमा {e.target_elevation_m:.0f} मिटर उचाइमा पुग्नुहोस् — यसले अनुमानित "
            f"{e.rise_m:.0f} मिटर पानीको सतहभन्दा माथि पुर्‍याउँछ। "
            f"लक्ष्य: {e.target_lat:.5f}, {e.target_lon:.5f}। "
            f"यो केवल भू-स्वरूपको जानकारी हो, {e.resolution_m:.0f} मिटरको ग्रिडबाट — पुल, "
            f"नाली वा पानी आफैं यसमा देखिँदैन। पहिले खोलाबाट टाढा जानुहोस्, त्यसपछि माथि।")


def bearing_between(dem: Dem, a: tuple[int, int], b: tuple[int, int]) -> float:
    """Compass bearing from one grid cell to another, degrees clockwise from north."""
    dy, dx = dem.pixel_size_m(dem.latlon_of(*a)[0])
    d_north = (b[0] - a[0]) * dy
    d_east = (b[1] - a[1]) * dx
    return (math.degrees(math.atan2(d_east, d_north)) + 360) % 360
