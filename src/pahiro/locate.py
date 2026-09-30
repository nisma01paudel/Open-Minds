"""Finding a trapped phone from radio signal alone.

A person under a landslide is under rock, wet soil and metal. Their phone has no GPS fix -
the sky is not visible - and no network. What it does have is a battery and a radio. If it
keeps advertising, a rescuer walking the debris can hear it, and the strength of that
signal gets stronger as they get closer.

This module turns signal strength into a place to dig. It is deliberately conservative
about what that place means.

THE MODEL. `rssi_to_distance` uses the log-distance path loss model,

    RSSI = TX_POWER - 10 * n * log10(d)

with `n` the path-loss exponent, about 2.0 in free air. Under debris n is higher - signal
falls off faster - so an assumed n under-estimates the distance. That error direction
matters and is stated rather than buried: an under-estimate means the search area still
contains the person.

WHY THE OUTPUT IS A RADIUS, NOT A POINT. Three receivers with noisy RSSI give a position
with a residual, and the residual is large because the medium is not uniform - a boulder
between the phone and one rescuer can cost 20 dB. Reporting a confident-looking coordinate
would send a team to dig in one spot; reporting a circle sends them to search an area. The
`PositionEstimate` therefore always carries `radius_m` and a confidence grade, and the API
returns the circle.

WHAT IT REFUSES TO DO. With fewer than three receivers it does not triangulate - two
circles intersect in two places and geometry cannot choose between them. It returns the
strongest receiver and the bearing, and says so. That is less useful and more true.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

EARTH_R = 6371000.0

# Free-space reference: the RSSI expected at 1 m, for a typical BLE beacon.
DEFAULT_TX_POWER = -59.0
# Path-loss exponent. 2.0 = free air, 3.0-4.0 = through soil, rock and rubble.
FREE_AIR_N = 2.0
DEBRIS_N = 3.2


def rssi_to_distance(rssi_dbm: float, tx_power: float = DEFAULT_TX_POWER,
                     path_loss: float = FREE_AIR_N) -> float:
    """Metres from a single RSSI reading.

    Clamped at 1 m: RSSI stronger than the 1 m reference means the reader is essentially on
    top of the device, and a negative distance is meaningless.
    """
    if path_loss <= 0:
        raise ValueError("path_loss exponent must be positive")
    exponent = (tx_power - rssi_dbm) / (10.0 * path_loss)
    return max(1.0, 10.0 ** exponent)


def _to_plane(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Local equirectangular metres. Accurate to well under a metre over a debris field."""
    x = math.radians(lon - lon0) * EARTH_R * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * EARTH_R
    return x, y


def _to_geo(x: float, y: float, lat0: float, lon0: float) -> tuple[float, float]:
    lat = lat0 + math.degrees(y / EARTH_R)
    lon = lon0 + math.degrees(x / (EARTH_R * math.cos(math.radians(lat0))))
    return lat, lon


@dataclass
class Reading:
    """One rescuer's sighting of the target device."""

    lat: float
    lon: float
    rssi_dbm: float
    label: str = ""
    # a rescuers' GPS is good to a few metres; that error propagates into the fix
    gps_accuracy_m: float = 5.0


@dataclass
class PositionEstimate:
    lat: float | None
    lon: float | None
    radius_m: float
    confidence: str                 # "high" | "medium" | "low" | "bearing-only"
    method: str
    receivers: int
    residual_m: float | None = None
    bearing_deg: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def search_area_m2(self) -> float:
        """The area a team has to search. This is the number that decides how many people
        and how many hours, so it is a first-class output rather than a derived detail."""
        return math.pi * self.radius_m ** 2

    def as_dict(self) -> dict:
        return {"lat": self.lat, "lon": self.lon, "radius_m": round(self.radius_m, 1),
                "confidence": self.confidence, "method": self.method,
                "receivers": self.receivers,
                "residual_m": None if self.residual_m is None else round(self.residual_m, 1),
                "bearing_deg": self.bearing_deg,
                "notes": self.notes,
                "search_area_m2": round(self.search_area_m2, 0)}


def _solve_2x2(a11: float, a12: float, a22: float, b1: float, b2: float
               ) -> tuple[float, float] | None:
    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-9:
        return None
    return ((b1 * a22 - b2 * a12) / det, (a11 * b2 - a12 * b1) / det)


def estimate_position(readings: list[Reading], path_loss: float = FREE_AIR_N,
                      tx_power: float = DEFAULT_TX_POWER) -> PositionEstimate:
    """Locate the transmitter from several receivers' RSSI.

    Weighted linearised least squares. Each reading is weighted by 1/d^2, because a reading
    taken at 5 m says far more about where someone is than one taken at 200 m - and the
    far reading is also the one most distorted by whatever is in between.
    """
    if not readings:
        return PositionEstimate(None, None, 0.0, "bearing-only", "no-signal", 0,
                                notes=["no readings; nothing to locate"])

    # One reading: a distance, no direction. A circle, centred on the rescuer.
    if len(readings) == 1:
        r = readings[0]
        d = rssi_to_distance(r.rssi_dbm, tx_power, path_loss)
        return PositionEstimate(
            r.lat, r.lon, max(d, 15.0), "low", "single-receiver-proximity", 1,
            notes=[f"one receiver only: {d:.0f} m from {r.label or 'the reader'}. "
                   "Move and read again to get a direction."])

    # Two readings: two circles meet at up to two points. Geometry cannot choose, so report
    # the stronger one as a bearing and refuse to invent a fix.
    if len(readings) == 2:
        best = max(readings, key=lambda r: r.rssi_dbm)
        other = min(readings, key=lambda r: r.rssi_dbm)
        d_best = rssi_to_distance(best.rssi_dbm, tx_power, path_loss)
        bearing = math.degrees(math.atan2(other.lat - best.lat, other.lon - best.lon)) % 360
        return PositionEstimate(
            best.lat, best.lon, max(d_best, 15.0), "low", "two-receiver-bearing", 2,
            bearing_deg=round(bearing, 1),
            notes=["two receivers cannot resolve a position - the circles cross in two "
                   "places. Head away from the reader with the weaker signal until the "
                   "reading rises."])

    # Three or more: least squares.
    lat0 = sum(r.lat for r in readings) / len(readings)
    lon0 = sum(r.lon for r in readings) / len(readings)
    pts = [(_to_plane(r.lat, r.lon, lat0, lon0), r) for r in readings]
    dists = [rssi_to_distance(r.rssi_dbm, tx_power, path_loss) for _, r in pts]

    (x0, y0), r0 = pts[0]
    d0 = dists[0]
    a11 = a12 = a22 = b1 = b2 = 0.0
    for i in range(1, len(pts)):
        (xi, yi), ri = pts[i]
        di = dists[i]
        # weight: trust the near reading, distrust the far one
        w = 1.0 / max(min(d0, di) ** 2, 1.0)
        ax, ay = -2.0 * (xi - x0), -2.0 * (yi - y0)
        bb = (di ** 2 - d0 ** 2) - (xi ** 2 - x0 ** 2) - (yi ** 2 - y0 ** 2)
        a11 += w * ax * ax
        a12 += w * ax * ay
        a22 += w * ay * ay
        b1 += w * ax * bb
        b2 += w * ay * bb

    sol = _solve_2x2(a11, a12, a22, b1, b2)
    if sol is None:
        # Receivers are collinear - no perpendicular information. Say so rather than
        # return a fix produced by a singular matrix.
        best = max(readings, key=lambda r: r.rssi_dbm)
        return PositionEstimate(best.lat, best.lon, 200.0, "low", "collinear-receivers",
                                len(readings),
                                notes=["receivers are in a line; a position cannot be "
                                       "resolved perpendicular to it. Spread out."])

    x, y = sol
    lat, lon = _to_geo(x, y, lat0, lon0)

    # Residual: how well the answer explains the readings. Large residual = the model is
    # wrong somewhere, usually because debris is attenuating one path more than others.
    residual = math.sqrt(sum((math.dist((x, y), p) - d) ** 2
                             for (p, _r), d in zip(pts, dists)) / len(pts))

    # Search radius: the residual, the receiver geometry, and a floor. Debris makes RSSI
    # distance under-estimate, so the floor is generous on purpose.
    spread = max(math.dist(pts[0][0], p) for p, _ in pts) if len(pts) > 1 else 0.0
    geometry = 20.0 if spread < 30 else 5.0
    radius = max(residual * 1.5 + geometry, 15.0)

    if residual < 12 and len(readings) >= 4:
        conf = "high"
    elif residual < 30:
        conf = "medium"
    else:
        conf = "low"

    notes = [f"{len(readings)} receivers, residual {residual:.0f} m"]
    if path_loss <= FREE_AIR_N + 1e-9:
        notes.append("distance is modelled for free air; under debris the true distance "
                     "is shorter, so the search area still contains the device.")
    if spread < 30:
        notes.append("receivers were close together; spread out to tighten the fix.")

    return PositionEstimate(lat, lon, radius, conf, "weighted-least-squares",
                            len(readings), residual_m=residual, notes=notes)


def search_radius_for(path_loss: float, distance_m: float, rssi_sigma_db: float = 6.0
                      ) -> float:
    """How much distance uncertainty a given RSSI noise implies.

    Included because it is the honest answer to "how accurate is this": BLE RSSI is noisy
    to several dB, and under debris far more. A 1 dB error at 50 m is roughly 12% of the
    distance; 6 dB is roughly a factor of two.
    """
    if path_loss <= 0:
        raise ValueError("path_loss exponent must be positive")
    factor = 10.0 ** (rssi_sigma_db / (10.0 * path_loss))
    return distance_m * (factor - 1.0 / factor)
