"""The beacon codec: it must fit the radio, survive being read by strangers, and never lie.

Every test here is about a failure that would cost a rescue rather than fail a build: a frame
too large to transmit is never sent, a frame whose corruption is accepted sends a team to the
wrong coordinates, and a frame whose timestamp is wrong gets discarded as stale by the first
receiver that checks.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.mesh import beacon as B  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WHEN = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


def a_frame(**kw):
    opts = dict(kind="sos", lat=27.71542, lon=85.31234, people=3,
                severity="critical", when=WHEN)
    opts.update(kw)
    return B.encode("handset-7f3a", "msg-abc123", **opts)


# ---- the budget ---------------------------------------------------------------------------

def test_the_frame_fits_inside_a_legacy_ble_advertisement():
    """31 bytes total, and the framing that is not ours is counted rather than waved at."""
    frame = a_frame()
    assert len(frame) == B.ENCODED_BYTES
    assert len(frame) <= B.MAX_AD_BYTES
    # 31 = 3 Flags AD + 1 length + 1 type(0xFF) + 2 company id + the payload we control
    assert 3 + 1 + 1 + 2 + B.MAX_AD_BYTES == 31, "the budget must describe a legacy advertisement"
    assert len(frame) < 31


def test_a_frame_carries_room_to_grow():
    """A format with no headroom forces a version bump for every added field."""
    assert B.MAX_AD_BYTES - len(a_frame()) >= 4


# ---- reading it back ----------------------------------------------------------------------

def test_a_frame_round_trips_every_field():
    b = B.decode(a_frame(low_battery=True))
    assert b is not None
    assert b.kind == "sos"
    assert b.severity == "critical"
    assert b.people == 3
    assert b.ttl == B.MAX_TTL and b.hops == 0
    assert b.low_battery is True
    assert b.has_position
    assert b.lat == pytest.approx(27.71542, abs=1e-5)
    assert b.lon == pytest.approx(85.31234, abs=1e-5)


def test_position_quantisation_is_far_finer_than_the_search_radius():
    """1e-5 degrees must not be what limits the search. locate.py reports a 15 m radius."""
    lat, lon = 27.71542, 85.31234
    b = B.decode(a_frame(lat=lat, lon=lon))
    metres_per_deg_lat = 111_320.0
    metres_per_deg_lon = 111_320.0 * 0.883  # cos(28 deg)
    err_lat = abs(b.lat - lat) * metres_per_deg_lat
    err_lon = abs(b.lon - lon) * metres_per_deg_lon
    assert err_lat < 0.6, f"latitude quantisation of {err_lat:.2f} m is too coarse"
    assert err_lon < 0.6, f"longitude quantisation of {err_lon:.2f} m is too coarse"
    assert max(err_lat, err_lon) < 15.0 / 10, "quantisation must be an order finer than 15 m"


def test_a_phone_with_no_fix_can_still_call_for_help():
    """Rule 4 of the protocol: a dying phone with a bad fix must still emit something useful."""
    f = a_frame(lat=None, lon=None)
    b = B.decode(f)
    assert b is not None, "a positionless SOS must not be rejected"
    assert not b.has_position
    assert b.people == 3, "the rest of the frame survives losing the fix"
    assert len(f) == B.ENCODED_BYTES, "dropping the position must not change the frame size"


def test_people_count_covers_unknown_one_many_and_overflow():
    assert B.decode(a_frame(people=0)).people_text == "unknown number of people"
    assert B.decode(a_frame(people=1)).people_text == "1 person"
    assert B.decode(a_frame(people=4)).people_text == "4 people"
    assert B.decode(a_frame(people=15)).people_text == "15+ people"


def test_both_kinds_of_position_extreme_round_trip():
    for lat, lon in ((90.0, 180.0), (-90.0, -180.0), (0.0, 0.0), (-33.98765, 151.01234)):
        b = B.decode(a_frame(lat=lat, lon=lon))
        assert b is not None, (lat, lon)
        assert b.lat == pytest.approx(lat, abs=1e-4), (lat, lon)
        assert b.lon == pytest.approx(lon, abs=1e-4), (lat, lon)


# ---- refusing what is not a beacon ---------------------------------------------------------

def test_a_single_flipped_bit_is_refused():
    """Every bit of the frame is load-bearing. A corrupted position is a team sent elsewhere."""
    good = a_frame()
    for i in range(len(good)):
        for bit in (0x01, 0x10, 0x80):
            bad = bytearray(good)
            bad[i] ^= bit
            assert B.decode(bytes(bad)) is None, f"byte {i} bit {bit:#x} was accepted"


def test_rubbish_from_the_world_is_refused_not_raised():
    """A market full of earbuds, tags and watches lands in this decoder."""
    for payload in (b"", b"\x00", b"\x00" * 19, b"\x00" * 20, b"\xff" * 20,
                    bytes(range(20)), bytes(range(19, -1, -1)), b"\x00" * 40):
        assert B.decode(payload) is None, payload
    assert B.decode(None) is None


def test_an_unknown_version_is_refused_rather_than_guessed_at():
    """A v2 frame read by a v1 decoder must not be interpreted as a v1 position."""
    f = bytearray(a_frame())
    f[0] = (2 << 5) | (f[0] & 0x1F)
    f[-1] = B.crc8(bytes(f[:-1]))  # make it a *valid* crc under the wrong version
    assert B.decode(bytes(f)) is None


def test_encoding_refuses_what_would_decode_as_something_else():
    with pytest.raises(B.BeaconError):
        a_frame(ttl=8)
    with pytest.raises(B.BeaconError):
        a_frame(hops=9)
    with pytest.raises(B.BeaconError):
        a_frame(people=16)
    with pytest.raises(B.BeaconError):
        a_frame(severity="very-bad")
    with pytest.raises(B.BeaconError):
        a_frame(kind="picnic")
    with pytest.raises(B.BeaconError):
        a_frame(lat=27.7, lon=None)          # half a position is not a position
    with pytest.raises(B.BeaconError):
        a_frame(lat=91.0, lon=85.0)


# ---- relaying ------------------------------------------------------------------------------

def test_a_relay_changes_only_ttl_and_hops():
    """Dedupe is by message id. A relay that re-hashed the ids would defeat it across paths."""
    first = a_frame()
    relayed = B.relay(first)
    assert relayed is not None
    differing = [i for i in range(len(first)) if first[i] != relayed[i]]
    # byte 5 carries ttl|hops|severity; byte 19 is the CRC over it. Nothing else may move.
    assert differing == [5, 19], f"a relay touched bytes {differing}"
    out = B.decode(relayed)
    src = B.decode(first)
    assert (out.dev16, out.msg_id16, out.lat, out.lon, out.people, out.created) == \
           (src.dev16, src.msg_id16, src.lat, src.lon, src.people, src.created)


def test_hops_are_spent_and_the_flood_stops():
    p = a_frame(ttl=2, hops=0)
    hops = 0
    while True:
        nxt = B.relay(p)
        if nxt is None:
            break
        p = nxt
        hops += 1
        assert hops <= 10, "the flood never stopped"
    assert hops == 2, "ttl is the number of hops the frame has left"
    assert B.decode(p).ttl == 0
    assert B.relay(p) is None, "a frame with no ttl left must not be rebroadcast"


def test_a_full_ttl_frame_crosses_a_valley_not_a_country():
    assert B.MAX_TTL == 7, "TTL must match DEFAULT_TTL in protocol.py"


# ---- time ----------------------------------------------------------------------------------

def test_the_timestamp_survives_the_wire():
    """The first draft stored this in 16 bits and turned 2026 into 1970."""
    for offset in (0, 300, 3600, 86400 * 30, 86400 * 365 * 3):
        when = WHEN + timedelta(seconds=offset)
        b = B.decode(a_frame(when=when))
        assert b.created.timestamp() == pytest.approx(when.timestamp(), abs=300)
        assert b.created.year == when.year, f"{when} decoded as {b.created}"


def test_a_live_beacon_is_not_mistaken_for_a_stale_one():
    b = B.decode(a_frame())
    assert not b.is_stale(now=WHEN)
    assert b.age_seconds(WHEN) == pytest.approx(0, abs=1)
    assert not b.is_stale(now=WHEN + timedelta(hours=5))
    assert b.is_stale(now=WHEN + timedelta(hours=7))


def test_a_frame_from_the_future_is_stale_not_fresh():
    """A wrong clock on one handset must not make its frame look like the newest one."""
    b = B.decode(a_frame())
    assert b.is_stale(now=WHEN - timedelta(hours=1))


# ---- the join to the rest of the system ----------------------------------------------------

def test_a_decoded_beacon_becomes_an_ordinary_mesh_message():
    m = B.to_message(B.decode(a_frame(low_battery=True)))
    assert m.kind == "sos"
    assert m.priority == 0, "an SOS must outrank chat in the relay queue"
    assert m.lat == pytest.approx(27.71542, abs=1e-5)
    assert m.people == 3
    assert m.origin.startswith("dev-")
    assert m.id.startswith("beacon-")
    assert "3 people" in m.body and "low battery" in m.body


def test_the_same_frame_expands_to_the_same_message_id_twice():
    """That is what lets the existing dedupe in node.py suppress a flood's duplicates."""
    f = a_frame()
    assert B.to_message(B.decode(f)).id == B.to_message(B.decode(f)).id


def test_a_plain_beacon_outranks_chat_but_sits_below_an_sos():
    m = B.to_message(B.decode(a_frame(kind="beacon")))
    assert m.kind == "beacon"
    assert m.priority == 1
    assert m.priority < 4, "a beacon must be evicted after chat, never before an SOS"


def test_identifiers_truncate_deterministically_and_apart():
    assert B.truncate16("handset-a") == B.truncate16("handset-a")
    assert B.truncate16("handset-a") != B.truncate16("handset-b")
    assert 0 <= B.truncate16("anything") <= 0xFFFF
    # a name whose utf-8 encoding is multi-byte must not crash or collide trivially
    assert B.truncate16("हाते-फोन") != B.truncate16("")


# ---- parity --------------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_python_and_javascript_beacons_are_byte_identical():
    """A radio format that disagrees across the boundary is a rescue sent to the wrong place."""
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_beacon_parity.py")],
                          capture_output=True, text=True, timeout=180, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "agree exactly" in proc.stdout
    assert "MISMATCH" not in proc.stdout


def test_the_field_page_loads_the_beacon_module():
    """A codec the page never loads is dead code, and this one is the whole point."""
    html = (ROOT / "web" / "public" / "field" / "index.html").read_text(encoding="utf-8")
    assert 'src="/field/beacon.js"' in html, "the field page must load the beacon module"
    assert "PahiroBeacon" in html, "the page must actually use it"
