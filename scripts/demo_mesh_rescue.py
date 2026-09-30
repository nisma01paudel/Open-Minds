#!/usr/bin/env python3
"""One landslide, end to end: SOS -> carried by hand -> located -> on the board.

This is the scenario the system exists for, and it runs entirely offline until the moment
someone walks into signal. Nothing here is mocked:

  * the messages are real `MeshMessage` frames, relayed with real TTL and hop counts
  * the carriers are real `MeshNode`s on a real (in-memory) radio
  * the location is computed by the same trilateration the API serves
  * the board is the same code the HTTP endpoint returns

What is simulated is the PHYSICS: people walking between villages, and the RSSI a rescuer
would read standing on the debris. Those are generated from a stated model, and the script
prints the model's assumptions rather than hiding them.

    python scripts/demo_mesh_rescue.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.api import FieldStore
from pahiro.locate import DEFAULT_TX_POWER, Reading
from pahiro.mesh import LoopbackRadio, MeshNode, MeshRunner

# ---------------------------------------------------------------------------------------
# The valley. Coordinates near the Dhading slopes the earlier work uses.
# ---------------------------------------------------------------------------------------
VILLAGE = (27.7620, 85.0535)          # where the phone is buried
# Within Bluetooth range, because that is the only way they can hear the handset at all.
# Rough metres: 1 deg lat ~ 111.3 km, 1 deg lon ~ 98.5 km at this latitude.
#   north ~30 m, south ~45 m, east ~55 m
RESCUERS = [
    ("rescuer-north", 27.76227, 85.05350),
    ("rescuer-south", 27.76160, 85.05350),
    ("rescuer-east", 27.76200, 85.05406),
]

BAR = "─" * 78


def hr(title: str) -> None:
    print(f"\n{BAR}\n{title}\n{BAR}")


def rssi_for(true_lat: float, true_lon: float, r_lat: float, r_lon: float,
             n: float = 2.0, noise: float = 0.0) -> float:
    """What a rescuer's handset would read. Log-distance path loss, the model the
    locator inverts. `noise` is added to make the demo honest about a real radio."""
    d = math.dist(_plane(true_lat, true_lon, r_lat, r_lon), (0.0, 0.0))
    rssi = DEFAULT_TX_POWER - 10.0 * n * math.log10(max(d, 1.0))
    return rssi + noise


def _plane(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    from pahiro.locate import _to_plane
    return _to_plane(lat, lon, lat0, lon0)


def main() -> int:
    hr("PAHIRO — the last metre, when there is no network")

    # --- the mesh ---------------------------------------------------------------------
    radio = LoopbackRadio()
    phones = {
        "phone-sita": MeshNode("phone-sita", name="Sita (village)"),
        "phone-ram": MeshNode("phone-ram", name="Ram (walking to the bazaar)"),
        "phone-maya": MeshNode("phone-maya", name="Maya (bazaar, has a bar of signal)"),
    }
    runners = {k: MeshRunner(v, radio) for k, v in phones.items()}
    # Only Sita and Ram are near each other. Maya is 4 km away, in the bazaar.
    radio.detach("phone-maya")

    hr("1. The slope fails. No tower, no internet, no road.")
    sos = phones["phone-sita"].sos(
        "पहिरोले घर पुरियो — दुई जना भित्र छन्। (House buried by the slide, two of us inside)",
        lat=VILLAGE[0], lon=VILLAGE[1], accuracy_m=18.0, people=2, battery=11)
    runners["phone-sita"].send(sos)
    runners["phone-ram"].pump()
    print(f"  Sita's phone sends an SOS and shouts it over Bluetooth.")
    print(f"  Ram, walking past, hears it — hops={phones['phone-ram'].store[sos.id].hops}.")
    print(f"  Ram has no network either. He keeps the message and keeps walking.")

    # --- the gateway ------------------------------------------------------------------
    hr("2. Four kilometres later, Ram reaches the bazaar.")
    radio.attach("phone-maya")
    handed, taken = runners["phone-ram"].meet(runners["phone-maya"])
    carried = phones["phone-maya"].store[sos.id]
    print(f"  Ram and Maya exchange what they hold ({handed} handed over).")
    print(f"  Maya now has Sita's SOS — hops={carried.hops}, carried by {carried.path}.")
    print(f"  Message id {carried.id}: the sender never changed. Origin is {carried.origin}.")

    # --- the internet -----------------------------------------------------------------
    hr("3. Maya's bar of signal. The board fills in.")
    store = FieldStore()
    store.ingest_message(carried)
    print(f"  Ingested. The district board now shows {len(store.sos)} person(s).")

    # --- locating ---------------------------------------------------------------------
    hr("4. A rescue team reaches the debris. GPS is useless under rock.")
    lat, lon = VILLAGE
    # A real reading wanders. Adding none of it would be a demo of arithmetic, not radios.
    noise = {"rescuer-north": 2.0, "rescuer-south": -3.0, "rescuer-east": 1.5}
    for label, rlat, rlon in RESCUERS:
        rssi = rssi_for(lat, lon, rlat, rlon, noise=noise[label])
        store.record_sighting("phone-sita", Reading(lat=rlat, lon=rlon, rssi_dbm=rssi,
                                                    label=label))
        d = math.dist(_plane(lat, lon, rlat, rlon), (0.0, 0.0))
        print(f"  {label:<14} at {d:5.0f} m reads {rssi:6.1f} dBm")

    est = store.locate("phone-sita")
    err = math.dist(_plane(est.lat, est.lon, lat, lon), (0.0, 0.0))
    print(f"\n  Estimated position: {est.lat:.5f}, {est.lon:.5f}")
    print(f"  True position     : {lat:.5f}, {lon:.5f}   (error {err:.0f} m)")
    print(f"  Search radius     : {est.radius_m:.0f} m  ({est.search_area_m2/10_000:.1f} ha)")
    print(f"  Confidence        : {est.confidence}   residual {est.residual_m:.0f} m")
    for n in est.notes:
        print(f"    · {n}")

    # --- the board --------------------------------------------------------------------
    hr("5. The board")
    for row in store.trapped():
        who = row["name"] or row["device_id"]
        pos = f"{row['lat']:.4f},{row['lon']:.4f}" if row.get("lat") is not None else "no fix"
        loc = row.get("located")
        area = f"search {loc['radius_m']:.0f} m" if loc else "not yet located"
        print(f"  {who:<22} {row['people']} people  battery {row['battery']}%  "
              f"{pos}  {area}")
        print(f"    “{row['message']}”")
        print(f"    carried {row['hops']} hop(s) by hand, {row['reports']} report(s)")

    hr("What this is honest about")
    print("  · Distances come from a path-loss model. Under debris the real distance is")
    print("    SHORTER than modelled, so the search circle still contains the person.")
    print("  · The answer is an area, not a point. A coordinate would send a team to dig")
    print("    one spot; a circle sends them to search.")
    print("  · Bluetooth does not go through rock. The mesh carries messages, not voices,")
    print("    and it works because people MOVE — which is what makes the hops.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
