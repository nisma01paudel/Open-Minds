"""The SOS that lives inside a Bluetooth advertisement.

WHY THIS EXISTS
---------------
The mesh protocol in `protocol.py` relays messages phone-to-phone, but every relay in that
design has to be *doing something*: a node opens a transport, receives a frame, decides, and
re-emits. That is fine between two phones whose owners are helping. It is useless in the
situation this project exists for, because the people standing in the debris are not running
our app, and the phone in the trapped person's pocket cannot open a connection to anybody.

This module removes both requirements. The distress payload is small enough to fit inside the
BLE **advertisement** itself, the 31-byte packet a phone broadcasts whether or not anyone is
listening. That changes the shape of the problem:

- **No pairing, no connection, no handshake.** An advertisement is fire-and-forget. There is
  nothing to negotiate and nothing to fail.
- **The relaying phone does not need our app in the foreground.** The operating system scans
  for BLE advertisements for its own reasons. Any handset running a scanner - ours, a rescue
  organisation's, or a stock phone with a scanning app - collects the frame with no
  interaction from its owner.
- **The advertisement's own RSSI is a locating measurement.** A searcher walking the debris
  reads signal strength straight off each advertisement, which feeds `locate.py` with no
  extra apparatus: the thing that carries the message is also the thing that finds the person.

The frame is a *carrier*, not a replacement for the protocol. A receiver decodes it into an
ordinary `MeshMessage` and hands it to the ordinary mesh store, so nothing downstream changed.

THE BUDGET IS THE WHOLE DESIGN
------------------------------
BLE legacy advertising gives 31 bytes for the entire packet, and the payload we control is 24 of
them, because four are spent framing our own AD structure and three more on the Flags structure
a discoverable advertiser must still carry:

    31 - 3 (Flags AD) - 1 (length) - 1 (type 0xFF) - 2 (company id) = 24

Extended advertising raises this a great deal, but support is uneven and a rescue cannot be
conditional on the handset, so this format is built to fit legacy advertising - and to use those
bytes on the things a searcher actually needs. Twenty of the twenty-four:

    offset  size  field
    0       1     version:3 | kind:3 | flags:2
    1       2     device id, truncated to 16 bits    - who is calling
    3       2     message id, truncated to 16 bits   - which call
    5       1     ttl:3 | hops:3 | severity:2
    6       1     people:4 | reserved:4              - 0 unknown, 1-14 count, 15 = "15 or more"
    7       4     latitude,  int32, degrees x 1e5, big-endian
    11      4     longitude, int32, degrees x 1e5, big-endian
    15      4     creation time, uint32, 5-minute buckets since the Unix epoch
    19      1     CRC-8/ATM over the preceding 19 bytes

Twenty of the twenty-four bytes, leaving four unallocated for future fields.

WHY THOSE FIELDS AND NOT OTHERS
-------------------------------
A device id and a message id are both present, and they answer different questions. The
message id suppresses the duplicate: a flood delivers the same call by several paths, and a
rescuer must not count it twice. The **device** id is what separates *three people calling for
help* from *one person calling three times* - which is the first question any rescue
coordinator asks, and which no single id can answer. Sixteen bits each is a truncation, and is
documented as one rather than presented as a unique key.

`people` is four bits because the difference between "one person under this slab" and "a bus"
changes what gets dispatched. Zero means *unknown*, which is the honest default: a phone that
has just started broadcasting has no idea how many people are with it.

WHAT WAS TRADED AWAY, AND WHY
-----------------------------
`protocol.py` argues at length for JSON over packed bytes, on the grounds that a human must be
able to read a message off a serial log during a rescue. **This module makes the opposite trade
deliberately, and the two do not conflict**: the advertisement is not the message, it is a
carrier for one. A receiver decodes the bytes into the same `MeshMessage` the JSON path
produces, so the human-readable form still exists one step later. Packed bytes are used here
only because 31 is not negotiable.

The position is quantised to 1e-5 degrees. At Nepal's latitudes that is under 1.2 m of
latitude and about 1 m of longitude per step, so the worst-case error is half a step, around
0.6 m - two orders of magnitude finer than the 15 m search radius `locate.py` reports.
Quantisation is therefore not what limits the search, and saying so is part of the claim.

DEGRADABILITY
-------------
Rule 4 of the mesh protocol is that a dying phone with a bad fix must still emit something
useful. A position is therefore *optional*: `flags` bit 0 records whether one is present. A
phone with no GPS lock emits an SOS with no coordinates, and the searchers fall back to RSSI
trilateration alone - exactly the mode `locate.py` supports, and why it refuses to answer with
fewer than three receivers rather than inventing a point.

THE TIMESTAMP IS FOUR BYTES BECAUSE TWO OF THEM LIED
----------------------------------------------------
The first draft stored the clock in a uint16 count of five-minute buckets, and the module
docstring cheerfully explained that it wrapped after 227 days. A smoke test caught what that
sentence actually meant: a frame emitted on 2026-09-30 decoded as 1970-01-19, so every live
beacon would read as fifty-six years stale and be discarded by the first `is_stale` check it
met. A format whose failure mode is "silently drops every distress call" is not a format with
a caveat, it is a broken format. The extra two bytes are simply spent - the frame is 20 of its
24 available bytes - and the wrap concern disappears entirely.

NOT IMPLEMENTED
---------------
**Web Bluetooth cannot advertise.** The specification has no advertiser role: a browser can
scan, and can connect as a central, but it cannot put bytes on the air. So this codec is the
half a browser *can* complete - it decodes frames it hears - and the transmitting half needs a
native build (Android `AdvertiseData`, iOS `CBPeripheralManager`). That is stated rather than
glossed, and the wire format above is the whole specification such an implementation would
need. `web/public/field/beacon.js` is the JavaScript mirror, checked against this file by
`scripts/check_beacon_parity.py`.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime, timezone

WIRE_VERSION = 1

# The payload we control inside a legacy advertising packet:
#   31  total legacy advertising payload
#   -3  the Flags AD structure a discoverable advertiser must include
#   -1  our AD structure's length byte
#   -1  our AD structure's type byte (0xFF, manufacturer specific)
#   -2  the manufacturer company identifier
#   =24
MAX_AD_BYTES = 24
ENCODED_BYTES = 20

# Kinds, ordered so a lower number is more urgent on the wire. The names match the PRIORITY
# keys in protocol.py, so a decoded beacon maps onto a kind the mesh already understands.
KIND_SOS = 0
KIND_BEACON = 1
KIND_STATUS = 2
KIND_NAMES = {KIND_SOS: "sos", KIND_BEACON: "beacon", KIND_STATUS: "status"}
KIND_VALUES = {v: k for k, v in KIND_NAMES.items()}

SEVERITIES = ("info", "concern", "urgent", "critical")

MAX_TTL = 7               # 3 bits, matching DEFAULT_TTL in protocol.py
MAX_HOPS = 7              # 3 bits
MAX_PEOPLE = 15           # 4 bits; 15 means "15 or more"
AGE_BUCKET_SECONDS = 300  # 5 minutes; a trapped person's position is static, so finer is noise

FLAG_HAS_POSITION = 0b01
FLAG_LOW_BATTERY = 0b10

POS_SCALE = 100_000       # 1e-5 degrees


class BeaconError(ValueError):
    """A frame that must not be emitted, because it would decode as something else."""


@dataclass(frozen=True)
class Beacon:
    """A decoded advertisement, before it is expanded into a mesh message."""

    dev16: int
    msg_id16: int
    kind: str
    ttl: int
    hops: int
    severity: str
    people: int          # 0 = unknown, 1..14 = count, 15 = "15 or more"
    lat: float | None
    lon: float | None
    created: datetime
    low_battery: bool = False

    @property
    def has_position(self) -> bool:
        return self.lat is not None and self.lon is not None

    @property
    def people_text(self) -> str:
        if self.people == 0:
            return "unknown number of people"
        if self.people >= MAX_PEOPLE:
            return f"{MAX_PEOPLE}+ people"
        return f"{self.people} " + ("person" if self.people == 1 else "people")

    @property
    def origin(self) -> str:
        return f"dev-{self.dev16:04x}"

    @property
    def message_id(self) -> str:
        return f"beacon-{self.msg_id16:04x}"

    def age_seconds(self, now: datetime | None = None) -> float:
        return ((now or datetime.now(timezone.utc)) - self.created).total_seconds()

    def is_stale(self, max_age_seconds: float = 6 * 3600,
                 now: datetime | None = None) -> bool:
        """A frame from the future is stale, not fresh - a wrong clock is not a rescue."""
        age = self.age_seconds(now)
        return age < 0 or age > max_age_seconds


def truncate16(value: str) -> int:
    """Truncate an identifier to the 16 bits that fit on the wire.

    FNV-1a, 32-bit, folded to 16 by XOR of the halves - not blake2s, which was the first
    choice and had to go. The browser has no blake2s: `crypto.subtle` does not offer it, and
    Node's `crypto.createHash("blake2s256")` is no help inside a page. Two implementations
    that hash the same name to different bits would defeat dedupe at exactly the boundary the
    parity check exists to protect - a Python gateway and a JavaScript phone would each think
    the other's message was new. FNV-1a is twenty lines in either language and identical in
    both, which matters more here than collision resistance: this is a *truncation for
    dedupe*, not a security property, and nothing depends on it being hard to invert.

    Sixteen bits collide after a few hundred identifiers in one valley. `dev16` and the
    five-minute creation bucket break the tie, because two different devices are not emitting
    from the same place in the same bucket by accident.
    """
    h = 0x811C9DC5
    for byte in str(value).encode("utf-8"):
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFF


def crc8(data: bytes) -> int:
    """CRC-8/ATM (polynomial 0x07, init 0x00). Cheap enough for a dying phone."""
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def _bucket(when: datetime) -> int:
    """Five-minute bucket, 32 bits. A uint16 here silently rewrote 2026 into 1970."""
    return (int(when.timestamp()) // AGE_BUCKET_SECONDS) & 0xFFFFFFFF


def _unbucket(bucket: int) -> datetime:
    return datetime.fromtimestamp(bucket * AGE_BUCKET_SECONDS, tz=timezone.utc)


def pack(dev16: int, msg16: int, *, kind: str = "sos", lat: float | None = None,
         lon: float | None = None, ttl: int = MAX_TTL, hops: int = 0,
         severity: str = "urgent", people: int = 0, low_battery: bool = False,
         when: datetime | None = None) -> bytes:
    """Build a frame from raw 16-bit identifiers, already truncated.

    Split out from `encode` because a relay holds only the truncated bits: it must be able to
    rebuild the frame it received without knowing the strings those bits came from. Hashing
    and packing are therefore separate steps, and `relay` uses this one.
    """
    if kind not in KIND_VALUES:
        raise BeaconError(f"unknown kind {kind!r}; expected one of {sorted(KIND_VALUES)}")
    if severity not in SEVERITIES:
        raise BeaconError(f"unknown severity {severity!r}; expected one of {SEVERITIES}")
    if not 0 <= ttl <= MAX_TTL:
        raise BeaconError(f"ttl {ttl} outside 0..{MAX_TTL}")
    if not 0 <= hops <= MAX_HOPS:
        raise BeaconError(f"hops {hops} outside 0..{MAX_HOPS}")
    if not 0 <= people <= MAX_PEOPLE:
        raise BeaconError(f"people {people} outside 0..{MAX_PEOPLE}")
    if (lat is None) != (lon is None):
        raise BeaconError("latitude and longitude must be given together or not at all")

    flags = (FLAG_HAS_POSITION if lat is not None else 0) | (
        FLAG_LOW_BATTERY if low_battery else 0)

    frame = bytearray()
    frame.append((WIRE_VERSION << 5) | (KIND_VALUES[kind] << 2) | flags)
    frame += struct.pack(">H", dev16 & 0xFFFF)
    frame += struct.pack(">H", msg16 & 0xFFFF)
    frame.append(((ttl & 0x07) << 5) | ((hops & 0x07) << 2) | SEVERITIES.index(severity))
    frame.append((people & 0x0F) << 4)          # low nibble reserved, written as zero
    if lat is None:
        frame += b"\x00" * 8
    else:
        if not -90.0 <= lat <= 90.0:
            raise BeaconError(f"latitude {lat} out of range")
        if not -180.0 <= lon <= 180.0:
            raise BeaconError(f"longitude {lon} out of range")
        frame += struct.pack(">ii", round(lat * POS_SCALE), round(lon * POS_SCALE))
    frame += struct.pack(">I", _bucket(when or datetime.now(timezone.utc)))

    assert len(frame) == ENCODED_BYTES - 1, "layout table and encoder have drifted apart"
    return bytes(frame) + bytes([crc8(bytes(frame))])


def encode(device_id: str, msg_id: str, **kw) -> bytes:
    """Pack a distress frame into `ENCODED_BYTES` bytes, ready for an advertisement.

    Identifiers are hashed down to the 16 bits that fit. Raises `BeaconError` rather than
    emitting a frame that would decode as something else: a silently corrupted distress call
    is worse than no distress call, because it is a rescue sent to the wrong place.
    """
    return pack(truncate16(device_id), truncate16(msg_id), **kw)


def decode(payload: bytes) -> Beacon | None:
    """Read a frame back. Returns None for anything that is not a valid beacon.

    None rather than an exception, because this runs on every advertisement a scanner hears:
    a phone in a market hears hundreds a minute from headphones, tags and watches, and every
    one of them lands here. A decoder that raised would make the scanner unusable, and a
    decoder that guessed would turn a pair of earbuds into a landslide victim.
    """
    if payload is None:
        return None
    data = bytes(payload)
    if len(data) != ENCODED_BYTES:
        return None
    if crc8(data[:ENCODED_BYTES - 1]) != data[ENCODED_BYTES - 1]:
        return None

    header = data[0]
    if header >> 5 != WIRE_VERSION:
        return None
    kind = KIND_NAMES.get((header >> 2) & 0x07)
    if kind is None:
        return None
    flags = header & 0x03

    dev16 = struct.unpack(">H", data[1:3])[0]
    msg_id16 = struct.unpack(">H", data[3:5])[0]

    timing = data[5]
    ttl = (timing >> 5) & 0x07
    hops = (timing >> 2) & 0x07
    severity = SEVERITIES[timing & 0x03]

    people = (data[6] >> 4) & 0x0F

    if flags & FLAG_HAS_POSITION:
        lat_raw, lon_raw = struct.unpack(">ii", data[7:15])
        lat, lon = lat_raw / POS_SCALE, lon_raw / POS_SCALE
    else:
        lat = lon = None

    created = _unbucket(struct.unpack(">I", data[15:19])[0])
    return Beacon(dev16=dev16, msg_id16=msg_id16, kind=kind, ttl=ttl, hops=hops,
                  severity=severity, people=people, lat=lat, lon=lon, created=created,
                  low_battery=bool(flags & FLAG_LOW_BATTERY))


def relay(payload: bytes) -> bytes | None:
    """Decode, spend one hop, re-encode - the whole relay decision in one call.

    Returns None when the frame is invalid or has no hops left, which is the signal to stop
    rebroadcasting. Every field except `ttl` and `hops` is preserved byte for byte: a relay
    that "improved" the coordinates would be inventing a rescue location it never measured,
    and a relay that changed the ids would defeat dedupe across paths of different length.
    """
    b = decode(payload)
    if b is None or b.ttl <= 0:
        return None
    return pack(b.dev16, b.msg_id16, kind=b.kind, lat=b.lat, lon=b.lon,
                ttl=b.ttl - 1, hops=min(b.hops + 1, MAX_HOPS), severity=b.severity,
                people=b.people, low_battery=b.low_battery, when=b.created)


def to_message(b: Beacon):
    """Expand a decoded advertisement into the `MeshMessage` the rest of the system speaks.

    This is the join between the two halves of the design: the advertisement is a carrier, and
    what a receiver ends up holding is an ordinary message that the existing store, dedupe,
    priority and API already understand. The beacon path needed no changes downstream.
    """
    from .protocol import MeshMessage  # local import keeps this module importable alone

    body = f"{b.severity.upper()} {b.kind}: {b.people_text}"
    if b.has_position:
        body += f" at {b.lat:.5f},{b.lon:.5f}"
    else:
        body += " (no position fix)"
    body += f" - emitted {b.created.strftime('%Y-%m-%dT%H:%MZ')}, {b.hops} hop(s) away"
    if b.low_battery:
        body += ", low battery"

    return MeshMessage(
        kind="sos" if b.kind == "sos" else "beacon",
        body=body,
        origin=b.origin,
        origin_name=b.origin,
        id=b.message_id,
        created_at=b.created,
        ttl=b.ttl,
        hops=b.hops,
        lat=b.lat,
        lon=b.lon,
        people=b.people or None,
        battery=None,
    )
