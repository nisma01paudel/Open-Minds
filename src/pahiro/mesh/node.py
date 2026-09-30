"""A node in the phone-to-phone mesh.

Two phones that come within Bluetooth range exchange what they have. Neither needs a
network, an account, or a server. A message handed to one phone is carried by the next
person who walks past, and the one after that, until it reaches someone with signal.

The three behaviours that make that work, and that this module is really about:

DEDUPE. A flood means the same message arrives over several paths, often several times. A
node stores the message id on first sight and ignores every later copy. Without this the
mesh amplifies itself instead of carrying anything.

STORE AND FORWARD. A message is not deleted once relayed. It is held, so it can be handed
to the next phone that appears - including one that arrives hours later. This is the whole
difference between a mesh and a walkie-talkie: the message does not need the listener to be
there when it was sent.

PRIORITY EVICTION. Storage is bounded, because a phone is not a server. When a node is
full, something must go. Chat goes first; a distress message is the last thing to be
dropped, and a node would rather hold 200 SOS messages than 200 pleasantries.

WHAT THIS IS NOT. It is not a radio. `MeshNode` is the logic above the radio - what to
keep, what to forget, what to hand over. The radio is a `Transport`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .protocol import DEFAULT_TTL, MeshMessage, PRIORITY


@dataclass
class NodeStats:
    sent: int = 0
    received: int = 0
    duplicates: int = 0
    expired: int = 0
    evicted: int = 0
    relayed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"sent": self.sent, "received": self.received, "duplicates": self.duplicates,
                "expired": self.expired, "evicted": self.evicted, "relayed": self.relayed}


class MeshNode:
    """One phone.

    `device_id` is stable for the life of the install: it is how a reply is addressed, and
    how a rescue team reconstructs which messages came from the same handset.
    """

    def __init__(self, device_id: str, name: str = "", ttl: int = DEFAULT_TTL,
                 capacity: int = 200, clock: Callable[[], float] = time.time) -> None:
        self.device_id = device_id
        self.name = name or device_id
        self.ttl = ttl
        self.capacity = capacity
        self.clock = clock

        self.seen: set[str] = set()
        self.store: dict[str, MeshMessage] = {}
        self.inbox: list[MeshMessage] = []          # what the human should read
        self.stats = NodeStats()

    # ---- composing ---------------------------------------------------------------------

    def compose(self, kind: str, body: str, **fields) -> MeshMessage:
        """Create a message attributed to this node and keep a copy for relaying."""
        msg = MeshMessage(kind=kind, body=body, origin=self.device_id,
                          origin_name=self.name, ttl=self.ttl, **fields)
        self._remember(msg)
        self.inbox.append(msg)
        return msg

    def sos(self, body: str, **fields) -> MeshMessage:
        return self.compose("sos", body, **fields)

    def chat(self, body: str, reply_to: str | None = None) -> MeshMessage:
        return self.compose("chat", body, reply_to=reply_to)

    # ---- receiving ---------------------------------------------------------------------

    def receive(self, msg: MeshMessage) -> bool:
        """Accept a message from the radio. Returns True if it was new.

        The message is stored and queued for relay regardless of who it is from: a relay
        does not get to have an opinion about the content, or the mesh stops working.
        """
        if msg.id in self.seen:
            self.stats.duplicates += 1
            return False
        self.stats.received += 1
        if not msg.alive():
            self.stats.expired += 1
            return False

        # A message we originated may come back to us around a loop; remember it but do
        # not show it to the user twice.
        if msg.origin != self.device_id:
            self.inbox.append(msg)
        self._remember(msg)
        return True

    def relayable(self, exclude: Iterable[str] = ()) -> list[MeshMessage]:
        """Everything this node could hand to a peer, most urgent first.

        Ordered by priority so that when a link is short-lived - two people walking past
        each other - the SOS goes first and the chat may never go at all. That ordering is
        the entire reason the priority field exists.
        """
        # Own messages ARE included. An SOS that is never offered to a peer is an SOS that
        # stays on one phone - this filter used to exclude them, which meant the origin
        # could never spread its own distress message.
        skip = set(exclude)
        out = [m for m in self.store.values() if m.alive() and m.id not in skip]
        out.sort(key=lambda m: (m.priority, -m.created_at.timestamp()))
        return out

    def _remember(self, msg: MeshMessage) -> None:
        self.seen.add(msg.id)
        self.store[msg.id] = msg
        if len(self.store) > self.capacity:
            self._evict()

    def _evict(self) -> None:
        """Drop the least important message. Chat before SOS, oldest first.

        Deliberately never evicts simply the oldest: on a long rescue a day-old SOS is
        still a person, and a fresh joke is not.
        """
        worst = max(self.store.values(),
                    key=lambda m: (m.priority, -m.created_at.timestamp()))
        del self.store[worst.id]
        self.stats.evicted += 1

    # ---- meeting another node ----------------------------------------------------------

    def sync_with(self, peer: "MeshNode", max_messages: int = 50) -> tuple[int, int]:
        """Exchange messages with a peer as if the two had just come into range.

        Returns (handed_over, taken_on). Both directions are limited, because a real radio
        link is brief and a node that spends it all on one peer is useless to the next.
        """
        # 1. What do we each already have? In a real BLE link this is a compact id list.
        ours, theirs = set(self.store), set(peer.store)

        # 2. Send what they lack, most urgent first.
        to_send = [m for m in self.relayable(exclude=theirs)][:max_messages]
        for m in to_send:
            # Relay it: the hop count and path are updated as it crosses this link.
            try:
                peer.receive(m.relay(via=self.device_id))
            except ValueError:
                self.stats.expired += 1
                continue
            self.stats.relayed += 1
            self.stats.sent += 1

        # 3. And take what we lack.
        to_take = [m for m in peer.relayable(exclude=ours)][:max_messages]
        taken = 0
        for m in to_take:
            try:
                if self.receive(m.relay(via=peer.device_id)):
                    taken += 1
                    peer.stats.relayed += 1
                    peer.stats.sent += 1
            except ValueError:
                peer.stats.expired += 1
        return len(to_send), taken

    # ---- views -------------------------------------------------------------------------

    def distress(self) -> list[MeshMessage]:
        """Every SOS this node knows about, worst first, one per origin device.

        One per device, because a panicking person sends several and a rescue board that
        shows the same person five times is a board that hides someone else.
        """
        by_origin: dict[str, MeshMessage] = {}
        for m in self.store.values():
            if not m.is_sos:
                continue
            prev = by_origin.get(m.origin)
            if prev is None or m.created_at > prev.created_at:
                by_origin[m.origin] = m
        return sorted(by_origin.values(),
                      key=lambda m: (not m.has_position(), -m.created_at.timestamp()))

    def transcript(self, kind: str | None = None) -> list[MeshMessage]:
        msgs = [m for m in self.inbox if kind is None or m.kind == kind]
        return sorted(msgs, key=lambda m: m.created_at)

    def known_ids(self) -> set[str]:
        return set(self.store)
