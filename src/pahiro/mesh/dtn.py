"""The transport ladder, and the custody rules that make four radios behave like one network.

WHY THIS EXISTS
---------------
`protocol.py` relays a message phone-to-phone. `beacon.py` fits a distress call into a Bluetooth
advertisement. Both assume there is *something* to carry the frame and someone to carry it to.
Neither answers the question a district actually faces:

    the road is gone, the towers are flaky, and the nearest working signal is nine kilometres
    away down a valley nobody has walked today. Which of the four things I have should this
    message go over, and when am I allowed to stop holding it?

That is a routing and custody problem, not a radio problem, and it is the same problem the
Delay-Tolerant Networking work (Bundle Protocol, RFC 9171) was invented for: links that
partition, latencies measured in hours, and no end-to-end path at any moment. This module
implements the part of that which matters here, in software, over radios the phone already has.

THE LADDER, AND WHY IT IS A LADDER
----------------------------------
No single transport is right for a valley, so the design is not "pick the best one" - it is
"exhaust them in order, and hold the bundle between rungs":

    SMS        anything with a cell signal, anywhere, ~160 bytes, and it costs the sender money
    Wi-Fi Aware  ~300 m phone-to-phone over the handset's own Wi-Fi chip, no infrastructure
    BLE advert   ~30 m, 20 bytes, carried by strangers who never open the app
    courier      a person walking out; unlimited range, hours of latency, zero power

The ranges are the honest ones a phone achieves without extra hardware, and the ladder is
ordered by *range per unit of cost*. The crucial property is at the bottom: when nothing is
available, the bundle is **held, not dropped**. Every link that assumes it can send is useless
in the situation this exists for.

CUSTODY, NOT FIRE-AND-FORGET
----------------------------
A relay that forwards and forgets loses the message exactly when the next hop fails - which is
the normal case here. So a bundle is held until someone *acknowledges custody*, and the holder
is named. `hand_off` records that responsibility moved; `release` is the only thing that lets the
original drop its copy. A bundle with no acknowledgement stays where it is and is offered again
on the next transport that appears.

WHAT THIS IS NOT
----------------
Not an implementation of the Bundle Protocol. RFC 9171's wire format, extension blocks and
security are a specification of their own, and claiming conformance without it would be a lie.
This is the *behaviour* a rescue needs - hold, offer, acknowledge, deduplicate, expire - over
transports the phone already has, and `docs/` states that distinction plainly.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from .protocol import DEFAULT_TTL, MAX_BODY, PRIORITY

# ---- the ladder --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Transport:
    """One way a bundle can leave this device."""

    name: str
    range_m: float          # per hop, without extra hardware; math.inf for a person walking
    max_payload: int        # bytes of body this transport will carry in one go
    latency_s: float        # expected delay before the next hop sees it
    cost: float             # relative cost per hop, arbitrary units; SMS costs money
    needs: str              # "cell" | "radio" | "none"
    note: str

    @property
    def bytes_per_meter(self) -> float:
        """How much payload one metre of this transport buys. A courier wins by carrying a lot."""
        return self.max_payload / self.range_m if math.isfinite(self.range_m) else 0.0


SMS = Transport("sms", math.inf, 160, 30.0, 5.0, "cell",
                "works when data is dead but the cell network is not")
# 300 m, not a vendor figure: this is the measured range of consumer smartphone Wi-Fi in
# https://www.duo.uio.no/bitstream/handle/10852/53773/Smartphones-in-wireless-communication-without-mobile-networks.pdf
# Wi-Fi Aware shares the same radio and power budget. See docs/OFFLINE-RANGE.md.
WIFI_AWARE = Transport("wifi_aware", 300.0, 4096, 1.0, 1.0, "radio",
                       "~300 m phone-to-phone on the handset's own Wi-Fi chip (measured)")
BLE = Transport("ble", 30.0, 20, 2.0, 0.5, "radio",
                "20 bytes inside an advertisement, carried by strangers")
COURIER = Transport("courier", math.inf, MAX_BODY, 21600.0, 0.0, "none",
                    "a person walking out; unlimited range, hours of delay, no power")

# Ordered by range, nearest first. The order is the point: try the cheap short hop repeatedly
# before spending the expensive long one.
LADDER: tuple[Transport, ...] = (BLE, WIFI_AWARE, SMS, COURIER)

BY_NAME = {t.name: t for t in LADDER}


class NoTransport(RuntimeError):
    """Nothing can carry this bundle right now. The caller must hold it, never discard it."""


# ---- the bundle --------------------------------------------------------------------------------


@dataclass
class Bundle:
    """One message, plus the state needed to keep it alive across partitions."""

    id: str
    kind: str
    body: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl: int = DEFAULT_TTL
    hops: int = 0
    path: list[str] = field(default_factory=list)
    custody: str | None = None          # which device is currently responsible for it
    attempts: int = 0                   # how many times it has been offered

    def __post_init__(self) -> None:
        if self.kind not in PRIORITY:
            raise ValueError(f"unknown kind {self.kind!r}; expected one of {sorted(PRIORITY)}")
        if len(self.body) > MAX_BODY:
            self.body = self.body[: MAX_BODY - 14].rstrip() + " [truncated]"

    @property
    def priority(self) -> int:
        return PRIORITY[self.kind]

    @property
    def is_control(self) -> bool:
        """Acknowledgements are not cargo: they ride any transport, however small."""
        return self.kind == "ack"

    def size_bytes(self) -> int:
        """The body, which is what a transport's payload limit applies to."""
        return len(self.body.encode("utf-8"))

    def fits(self, transport: Transport) -> bool:
        return self.size_bytes() <= transport.max_payload

    def age_seconds(self, now: datetime | None = None) -> float:
        return ((now or datetime.now(timezone.utc)) - self.created_at).total_seconds()


# ---- choosing a transport ----------------------------------------------------------------------


@dataclass
class Choice:
    transport: Transport
    reason: str
    reachable: bool


def _spans(transport: Transport, distance_m: float) -> bool:
    """Whether one hop of this transport covers the whole remaining distance.

    False is a normal answer, not a failure: a 30 m advertisement against a 9 km gap is exactly
    the case the relay mesh exists for, and the reason string says so rather than hiding it.
    """
    return (not math.isfinite(distance_m)) or transport.range_m >= distance_m


def choose(bundle: Bundle, *, available: set[str], distance_m: float = 0.0,
           hops_left: int | None = None) -> Choice:
    """Pick the next transport for a bundle, or raise `NoTransport`.

    The rule, in order of what actually matters in a valley:

    1. **An SOS never waits.** If any transport can carry it at all, it goes now, even the
       expensive one - a distress call that arrives in six hours by courier is a record, not a
       rescue.
    2. **Short hops first.** A bundle should climb the ladder: a 30 m BLE hop that works beats
       spending the one SMS on something a walking stranger could carry.
    3. **A courier is the floor, not a failure.** If no radio reaches and no cell exists, the
       bundle is handed to a person, which always works because people are already walking out.

    `distance_m` is how far the bundle still has to travel. A transport whose range is shorter
    than that is still usable *if* someone will relay it - that is what the mesh is for - so it
    is preferred rather than rejected.
    """
    if hops_left is not None and hops_left <= 0:
        raise NoTransport("no hops left: this bundle has travelled as far as it is allowed to")

    usable = [t for t in LADDER if t.name in available and bundle.fits(t)]
    if not usable:
        fits_somewhere = [t for t in LADDER if t.name in available]
        if fits_somewhere:
            smallest = min(t.max_payload for t in fits_somewhere)
            raise NoTransport(
                f"the bundle is {bundle.size_bytes()} bytes and the available transports carry "
                f"at most {smallest}")
        raise NoTransport("no transport is available and no one is walking out")

    # 1. an SOS takes whatever exists, now
    if bundle.kind == "sos":
        pick = min(usable, key=lambda t: (t.latency_s, t.cost))
        return Choice(pick, f"SOS takes the fastest available transport "
                            f"({pick.name}, {pick.latency_s:.0f}s)",
                      reachable=_spans(pick, distance_m))

    # 2. control traffic rides the lowest rung that fits - it is not cargo
    if bundle.is_control:
        pick = usable[0]
        return Choice(pick, f"acknowledgement takes the lowest ladder rung that fits "
                            f"({pick.name})",
                      reachable=_spans(pick, distance_m))

    # 3. ordinary traffic climbs the ladder: the lowest rung that fits, courier last
    pick = usable[0]
    reachable = _spans(pick, distance_m)
    why = (f"{pick.name} is the lowest ladder rung that fits "
           f"({pick.range_m:.0f} m a hop, {pick.latency_s:.0f}s)")
    if not reachable:
        why += (f"; it does not span the remaining {distance_m:.0f} m, so it relies on relays "
                f"- which is what the mesh is for")
    return Choice(pick, why, reachable)


# ---- the store, with custody -------------------------------------------------------------------


@dataclass
class Held:
    bundle: Bundle
    handed_to: str | None = None        # peer that has been offered custody
    handed_at: datetime | None = None
    acked: bool = False


class Custody:
    """A store that holds a bundle until someone takes responsibility for it.

    The failure this prevents: a relay forwards a frame, drops its copy, and the next hop fails.
    In a valley that is not an edge case, it is Tuesday. So the only thing that removes a bundle
    from this store is an acknowledgement, or expiry.
    """

    def __init__(self, device_id: str, capacity: int = 200,
                 max_age: timedelta = timedelta(hours=48)) -> None:
        self.device_id = device_id
        self.capacity = capacity
        self.max_age = max_age
        self._held: dict[str, Held] = {}
        self.delivered: set[str] = set()   # every id ever delivered or forwarded onward

    # ---- taking responsibility
    def accept(self, bundle: Bundle) -> bool:
        """Take custody. Returns False if this bundle has already been seen.

        Idempotent by id across *every* transport, which is the property that stops the same SOS
        arriving over BLE and then again over SMS from being counted as two people.
        """
        if bundle.id in self.delivered or bundle.id in self._held:
            return False
        if len(self._held) >= self.capacity:
            self._evict_for(bundle)
        self._held[bundle.id] = Held(bundle=replace(bundle, custody=self.device_id))
        return True

    def _evict_for(self, incoming: Bundle) -> None:
        """Make room. Chat goes before a distress call, whatever the arrival order.

        A full store that refuses an SOS because it is holding gossip has failed at the only
        thing it was for. `PRIORITY` in protocol.py defines the order; this respects it.
        """
        if not self._held:
            return
        victim_id, victim = max(
            self._held.items(),
            key=lambda kv: (kv[1].bundle.priority, kv[1].bundle.created_at))
        if victim.bundle.priority <= incoming.priority:
            # Nothing lower-priority to drop. The store is full of equally or more urgent work.
            raise MemoryError(
                f"store full of {victim.bundle.kind} and an {incoming.kind} needs the room")
        del self._held[victim_id]

    # ---- handing off
    def hand_off(self, bundle_id: str, transport: Transport, peer: str,
                 now: datetime | None = None) -> Held:
        """Record that responsibility has been offered to a peer. The copy stays here."""
        now = now or datetime.now(timezone.utc)
        held = self._require(bundle_id)
        held.bundle.attempts += 1
        held.bundle.hops += 1
        held.bundle.path.append(self.device_id)
        held.handed_to = peer
        held.handed_at = now
        return held

    def release(self, bundle_id: str, *, acked_by: str | None = None) -> bool:
        """Drop the copy. Only an acknowledgement is good enough, or expiry elsewhere."""
        held = self._held.get(bundle_id)
        if held is None:
            return False
        if not held.acked and acked_by is None:
            raise PermissionError(
                "refusing to drop a bundle nobody has acknowledged: keeping it is the whole point")
        del self._held[bundle_id]
        self.delivered.add(bundle_id)
        return True

    def acknowledge(self, bundle_id: str, by: str) -> bool:
        """A peer confirms it holds this bundle. Now - and only now - our copy may go."""
        held = self._held.get(bundle_id)
        if held is None:
            # We may have already let it go, or never had it. Either way, acknowledge is a no-op
            # rather than an error: acks cross paths and arrive late, and that is normal.
            return False
        held.acked = True
        held.handed_to = by
        return True

    # ---- housekeeping
    def expire(self, now: datetime | None = None) -> list[str]:
        """Drop bundles that are too old to be a lead. Returns the ids removed."""
        now = now or datetime.now(timezone.utc)
        gone = [i for i, h in self._held.items() if now - h.bundle.created_at > self.max_age]
        for i in gone:
            self._held.pop(i, None)
            self.delivered.add(i)
        return gone

    def pending(self, now: datetime | None = None) -> list[Bundle]:
        """What still needs a carrier, most urgent first. This is the offer queue."""
        now = now or datetime.now(timezone.utc)
        self.expire(now)
        out = [h.bundle for h in self._held.values() if not h.acked]
        # Stable sorts, least significant first: priority, then oldest first within a priority.
        out.sort(key=lambda b: b.created_at)
        out.sort(key=lambda b: b.priority)
        return out

    def offered_to(self, bundle_id: str) -> str | None:
        held = self._held.get(bundle_id)
        return held.handed_to if held else None

    def __len__(self) -> int:
        return len(self._held)

    def __contains__(self, bundle_id: str) -> bool:
        return bundle_id in self._held

    def _require(self, bundle_id: str) -> Held:
        held = self._held.get(bundle_id)
        if held is None:
            raise KeyError(f"{bundle_id} is not in this store - it may already be delivered")
        return held


# ---- the relay decision, end to end ------------------------------------------------------------


@dataclass
class RelayPlan:
    bundle_id: str
    transport: str | None
    reason: str
    held: bool


def plan_offers(store: Custody, *, available: set[str], distance_m: float = 0.0) -> list[RelayPlan]:
    """Everything this device should try to hand off, in order.

    Bundle is never dropped for want of a carrier: a plan with `transport=None` and `held=True`
    is a correct outcome, and the message stays in the store for the next transport that appears.
    """
    plans: list[RelayPlan] = []
    for bundle in store.pending():
        try:
            pick = choose(bundle, available=available, distance_m=distance_m)
            plans.append(RelayPlan(bundle.id, pick.transport.name, pick.reason, held=True))
        except NoTransport as exc:
            plans.append(RelayPlan(bundle.id, None, str(exc), held=True))
    return plans


def ladder_summary() -> list[dict]:
    """The ladder as data, for docs and for a settings screen."""
    return [{
        "name": t.name,
        "range_m": None if not math.isfinite(t.range_m) else round(t.range_m, 0),
        "max_payload": t.max_payload,
        "latency_s": round(t.latency_s, 1),
        "cost": t.cost,
        "needs": t.needs,
        "note": t.note,
    } for t in LADDER]
