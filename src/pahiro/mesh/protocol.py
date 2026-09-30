"""Mesh message protocol — the wire format for the offline chat and the SOS.

WHY THIS EXISTS
---------------
A landslide takes the road, the cell tower and the power with it. The hours that follow are
the ones that matter, and they happen with no network. Every rescue tool that assumes a
connection is useless exactly when it is needed.

So the messages are designed to travel phone-to-phone over Bluetooth, and to be carried by
whoever happens to walk within range. That imposes four rules on the format:

1. SMALL. The radio is low-bandwidth and the phone is on battery. A message must be
   compact enough to relay many times.
2. SELF-CONTAINED. A relay cannot look anything up. It may have never had a network.
3. IDEMPOTENT. The mesh floods, so the same message arrives by several paths. A node must
   be able to tell that it has already seen it, from the message alone.
4. DEGRADABLE. A dying phone with 3% battery and a bad fix can still emit something useful.

The format is JSON rather than packed bytes. That is a deliberate trade: JSON costs roughly
2-3x the bytes of a binary encoding, and buys the ability to read a message off a serial
log, or type one by hand into a terminal, during an actual rescue. Correctness under
pressure beats bytes. `to_bytes`/`from_bytes` are the only place that would change if that
trade is ever revisited.

TTL AND THE FLOOD
-----------------
Every message carries a time-to-live that decrements at each hop, and a hop count that
increments. TTL is what stops a flood from becoming a broadcast storm on a radio shared
with the people you are trying to save. Seven hops is chosen to cover a valley, not a
country.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

# Messages that must outlive chit-chat in a relay queue, and must never be dropped for a
# chat message when the buffer is full.
PRIORITY = {"sos": 0, "beacon": 1, "status": 2, "ack": 3, "chat": 4}

DEFAULT_TTL = 7
MAX_BODY = 480          # chars; a long message is a luxury when the radio is shared
WIRE_VERSION = 1


def _now() -> datetime:
    """Second resolution, deliberately.

    The wire format carries seconds, so a model that kept microseconds would produce a
    message that is not equal to itself after a round trip - and a relay comparing
    timestamps across the mesh would see spurious differences. It also saves bytes on a
    radio shared with the people you are trying to reach.
    """
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@dataclass
class MeshMessage:
    """One message, as it looks on the wire.

    `origin` identifies the device that created it and never changes as it is relayed -
    that is what a reply is addressed to. `path` is the trail of device ids that carried
    it, which is how a rescue team can tell that a message came over the ridge rather than
    down the valley, and therefore roughly where the sender is.
    """

    kind: str
    body: str
    origin: str
    origin_name: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    created_at: datetime = field(default_factory=_now)
    ttl: int = DEFAULT_TTL
    hops: int = 0
    path: list[str] = field(default_factory=list)
    reply_to: str | None = None

    # optional payload, present on sos / beacon / status
    lat: float | None = None
    lon: float | None = None
    accuracy_m: float | None = None
    people: int | None = None
    battery: int | None = None

    # ---- construction -----------------------------------------------------------------

    def __post_init__(self) -> None:
        if self.kind not in PRIORITY:
            raise ValueError(f"unknown message kind {self.kind!r}; "
                             f"expected one of {sorted(PRIORITY)}")
        if len(self.body) > MAX_BODY:
            # Truncation is better than a dropped SOS. Say so in the body so the reader
            # knows they are not looking at the whole message.
            self.body = self.body[: MAX_BODY - 14].rstrip() + " [truncated]"

    @property
    def priority(self) -> int:
        return PRIORITY[self.kind]

    @property
    def is_sos(self) -> bool:
        return self.kind == "sos"

    def has_position(self) -> bool:
        return self.lat is not None and self.lon is not None

    def relay(self, via: str) -> "MeshMessage":
        """Return the message as it should leave this node.

        Raises when the message has no life left, so a caller cannot accidentally relay a
        dead message back into the mesh and start a slow storm.
        """
        if self.ttl <= 0:
            raise ValueError("cannot relay a message with ttl <= 0")
        return replace(self, ttl=self.ttl - 1, hops=self.hops + 1, path=[*self.path, via])

    def alive(self) -> bool:
        return self.ttl > 0

    # ---- wire -------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "v": WIRE_VERSION,
            "id": self.id,
            "k": self.kind,
            "b": self.body,
            "o": self.origin,
            "n": self.origin_name,
            "t": _iso(self.created_at),
            "ttl": self.ttl,
            "h": self.hops,
        }
        if self.path:
            d["p"] = self.path
        if self.reply_to:
            d["r"] = self.reply_to
        if self.lat is not None:
            d["y"] = round(self.lat, 6)
        if self.lon is not None:
            d["x"] = round(self.lon, 6)
        if self.accuracy_m is not None:
            d["a"] = round(self.accuracy_m, 1)
        if self.people is not None:
            d["pp"] = self.people
        if self.battery is not None:
            d["bat"] = self.battery
        return d

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MeshMessage":
        v = d.get("v", WIRE_VERSION)
        if v != WIRE_VERSION:
            raise ValueError(f"unsupported wire version {v}")
        return cls(
            id=d["id"], kind=d["k"], body=d.get("b", ""),
            origin=d["o"], origin_name=d.get("n", ""),
            created_at=_parse_iso(d["t"]) if "t" in d else _now(),
            ttl=int(d.get("ttl", DEFAULT_TTL)), hops=int(d.get("h", 0)),
            path=list(d.get("p", [])), reply_to=d.get("r"),
            lat=d.get("y"), lon=d.get("x"), accuracy_m=d.get("a"),
            people=d.get("pp"), battery=d.get("bat"),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "MeshMessage":
        """Parse a frame off the radio.

        A malformed frame must raise, not be silently guessed at: a relay that invents a
        message is worse than one that drops it.
        """
        try:
            d = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"not a mesh frame: {exc}") from exc
        if not isinstance(d, dict):
            raise ValueError("mesh frame must be a JSON object")
        for k in ("id", "k", "o"):
            if k not in d:
                raise ValueError(f"mesh frame missing required field {k!r}")
        return cls.from_dict(d)

    # ---- display ----------------------------------------------------------------------

    def summary(self) -> str:
        where = f" @{self.lat:.4f},{self.lon:.4f}" if self.has_position() else ""
        return (f"[{self.kind}] {self.origin_name or self.origin}{where} "
                f"hops={self.hops} ttl={self.ttl} :: {self.body[:60]}")


def make_sos(origin: str, body: str, *, origin_name: str = "", lat: float | None = None,
             lon: float | None = None, accuracy_m: float | None = None,
             people: int | None = None, battery: int | None = None,
             ttl: int = DEFAULT_TTL) -> MeshMessage:
    """Build a distress message. Kept as a helper because every field matters and a caller
    should not have to remember which ones an SOS is expected to carry."""
    return MeshMessage(kind="sos", body=body, origin=origin, origin_name=origin_name,
                       lat=lat, lon=lon, accuracy_m=accuracy_m, people=people,
                       battery=battery, ttl=ttl)
