"""The radio under the mesh.

`MeshNode` decides what to keep and what to hand over. This module is how a message
actually crosses from one phone to another. Keeping the two apart is what lets the mesh
logic be tested at all: a real BLE link cannot be exercised in CI, and a protocol that can
only be tested on two phones in a field is a protocol that is wrong in ways nobody finds
until the field.

Three implementations:

`LoopbackRadio` - an in-memory medium. Every attached node hears every broadcast, with
   delivery on poll. This is what the tests and the demo run on.

`LossyRadio` - the same, but with a configurable drop rate and range. It exists to answer
   the question that matters: does a message still get through when half the frames are
   lost? A mesh that needs a perfect link is not a mesh.

`BleTransport` - the interface a real device implements (Web Bluetooth on Android, or a
   native shim). It is declared, not faked: the methods are the ones a real radio needs,
   and there is no pretend implementation pretending to be a phone.

A NOTE ON RANGE. Bluetooth does not reach as far as people assume, and it reaches much
less far through rock and wet soil - which is precisely the material a landslide is made
of. Nothing here hides that: `LossyRadio(in_range=...)` makes the consequence explicit,
and the rescue-facing output reports a search radius rather than a position, because a
distance inferred from a signal that went through six metres of debris is not a distance.
"""
from __future__ import annotations

import random
from typing import Callable, Iterable, Protocol, runtime_checkable

from .protocol import MeshMessage


@runtime_checkable
class Transport(Protocol):
    """What a radio must do for `MeshNode`. Intentionally tiny."""

    def broadcast(self, msg: MeshMessage) -> None: ...
    def poll(self) -> list[MeshMessage]: ...


class LoopbackRadio:
    """An in-memory shared medium.

    Every node attached to one radio hears every broadcast. That is a simplification of a
    real radio, and a deliberate one: it isolates the mesh LOGIC (dedupe, relay, expiry)
    from the radio PHYSICS (range, loss, collisions), so a failure tells you which of the
    two is broken.
    """

    def __init__(self, name: str = "loopback") -> None:
        self.name = name
        self._attached: dict[str, list[MeshMessage]] = {}
        self.log: list[tuple[str, str, MeshMessage]] = []   # (sender, receiver, message)

    def attach(self, device_id: str) -> "LoopbackRadio":
        self._attached.setdefault(device_id, [])
        return self

    def detach(self, device_id: str) -> None:
        self._attached.pop(device_id, None)

    def broadcast(self, msg: MeshMessage) -> None:
        """Deliver to every attached node except the sender."""
        for device_id, queue in self._attached.items():
            if device_id == msg.origin:
                continue
            queue.append(msg)
            self.log.append((msg.origin, device_id, msg))

    def poll(self, device_id: str) -> list[MeshMessage]:
        queue = self._attached.setdefault(device_id, [])
        out, queue[:] = list(queue), []
        return out

    def receivers(self, msg: MeshMessage) -> int:
        """How many nodes heard a given message - the reach of one broadcast."""
        return sum(1 for s, _r, m in self.log if m.id == msg.id)


class LossyRadio(LoopbackRadio):
    """A radio that behaves like a real one: limited range, and frames that just vanish.

    `in_range` is measured in hops, not metres, because the question being tested is
    topological - "does the message survive when only some neighbours can hear it" - and
    a fake metre is more misleading than an honest hop.

    `loss` is the per-frame probability of a frame not arriving.
    """

    def __init__(self, loss: float = 0.3, in_range: Callable[[str, str], bool] | None = None,
                 seed: int | None = None, name: str = "lossy") -> None:
        super().__init__(name)
        self.loss = loss
        self.in_range = in_range or (lambda _a, _b: True)
        self.rng = random.Random(seed)
        self.dropped = 0

    def broadcast(self, msg: MeshMessage) -> None:
        for device_id, queue in self._attached.items():
            if device_id == msg.origin:
                continue
            if not self.in_range(msg.origin, device_id):
                self.dropped += 1
                continue
            if self.rng.random() < self.loss:
                self.dropped += 1
                continue
            queue.append(msg)
            self.log.append((msg.origin, device_id, msg))


class BleTransport:
    """The interface a real phone radio must implement.

    Declared so the contract is explicit and testable against, NOT implemented here - there
    is no code in this repository that pretends to be a Bluetooth stack. On Android these
    methods map onto Web Bluetooth (a central scanning and connecting to peripherals that
    advertise the mesh service UUID) or onto a native shim where background operation is
    required, which a browser cannot provide.

    A device that implements this can be dropped into `MeshRunner` unchanged.
    """

    MESH_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    MESH_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self._inbox: list[MeshMessage] = []

    def broadcast(self, msg: MeshMessage) -> None:              # pragma: no cover
        raise NotImplementedError(
            "implement with Web Bluetooth (navigator.bluetooth.requestDevice + GATT write) "
            "or a native BLE peripheral/advertiser; see docs/MESH.md")

    def poll(self) -> list[MeshMessage]:                        # pragma: no cover
        raise NotImplementedError("drain notifications from the GATT characteristic")

    def advertise(self, payload: bytes) -> None:                # pragma: no cover
        """Emit a non-connectable advertisement. This is how a phone with no network and
        no one to talk to still makes itself findable: an SOS beacon that a rescuer's
        scanner can hear without pairing."""
        raise NotImplementedError("requires a native advertiser")

    def scan(self, seconds: float) -> list[tuple[str, int]]:     # pragma: no cover
        """Return (device_address, rssi) for nearby advertisers. RSSI is what the rescue
        search turns into a distance, so it must be a raw dBm reading, unfiltered."""
        raise NotImplementedError("requires a native scanner")


class MeshRunner:
    """Glue: a node, a radio, and the polling loop.

    Kept separate from `MeshNode` so the node stays a pure data structure and can be tested
    without any radio at all.
    """

    def __init__(self, node, radio: LoopbackRadio) -> None:
        self.node = node
        self.radio = radio
        radio.attach(node.device_id)

    def send(self, msg: MeshMessage) -> None:
        self.radio.broadcast(msg)

    def pump(self) -> int:
        """Take everything the radio has for us and hand it to the node."""
        got = 0
        for msg in self.radio.poll(self.node.device_id):
            if self.node.receive(msg):
                got += 1
        return got

    def meet(self, peer: "MeshRunner", rounds: int = 3) -> tuple[int, int]:
        """Two nodes come into range: pump the radio, then sync directly.

        `rounds` because a real encounter is a short conversation, not a single packet -
        the exchange may take several frames and the link may drop mid-way.
        """
        handed = taken = 0
        for _ in range(rounds):
            self.pump()
            peer.pump()
            h, t = self.node.sync_with(peer.node)
            handed += h
            taken += t
            if h == 0 and t == 0:
                break
        return handed, taken
