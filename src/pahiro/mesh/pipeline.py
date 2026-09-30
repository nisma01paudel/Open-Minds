"""The join: a bundle that goes into the mesh sealed, and comes out only for its recipient.

WHY THIS EXISTS
---------------
`dtn.py` moves bundles between stores and `seal.py` decides what a carrier may see, but they did
not know about each other. `dtn.Bundle` carries a plaintext `body`; `seal.Sealed` carries an
opaque payload. Nothing converted between them, which meant a relay in the mesh - a stranger's
phone - was holding the message in the clear.

This module is that conversion, and it is the difference between "we have encryption" and "the
messages are encrypted".

    compose -> seal -> [ carrier holds SealedBundle: no body, routes normally ] -> open

WHAT A CARRIER HOLDS
--------------------
A `SealedBundle` satisfies exactly the interface `dtn.py` needs to route it - `kind`, `size`,
`fits`, `priority`, `ttl`, `hops` - and has **no body attribute at all**. A relay can choose a
transport, spend a hop, and hand off custody without ever being able to read what it moved. That
is not a policy; there is no method that returns the plaintext.

WHO CAN OPEN IT
---------------
Whoever holds the key. A ward's own handsets can share a group key. The stronger arrangement,
which `seal.generate_keypair` and `seal.shared_key` support, is a bundle sealed to the **district**
so that the phones relaying it cannot read it even if one of them is compromised.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import seal
from .dtn import Transport
from .protocol import PRIORITY, MeshMessage
from .seal import Cipher, ReplayGuard, SealError


@dataclass
class SealedBundle:
    """A bundle as a carrier sees it: routing metadata, and an opaque payload.

    Deliberately has no `body`. `dtn.choose` and `dtn.Custody` need `kind`, `size_bytes`,
    `fits`, `priority`, `ttl` and `hops`, and this provides all of them without providing the
    thing that must not travel in the clear.
    """

    id: str
    kind: str
    size: int
    ttl: int
    hops: int
    created_at: datetime
    payload: bytes                      # nonce || ciphertext || tag
    content_type: str = seal.CONTENT_TEXT
    sender: str = ""
    path: list[str] = field(default_factory=list)
    # `dtn.Custody` records responsibility with dataclasses.replace and counts offers on
    # hand-off, so both of these must exist here or a relay cannot take custody of a sealed
    # bundle at all. Found by wiring the two layers together rather than by reading either.
    custody: str | None = None
    attempts: int = 0

    @property
    def priority(self) -> int:
        return PRIORITY[self.kind]

    @property
    def is_control(self) -> bool:
        return self.kind == "ack"

    def size_bytes(self) -> int:
        """What a transport's payload limit applies to: the sealed frame, not the plaintext.

        Sealing adds a nonce and a tag, so a body that just fitted a rung may no longer fit.
        Reporting the sealed size is what keeps a transport choice honest.
        """
        return len(self.payload)

    def fits(self, transport: Transport) -> bool:
        return self.size_bytes() <= transport.max_payload

    def age_seconds(self, now: datetime | None = None) -> float:
        return ((now or datetime.now(timezone.utc)) - self.created_at).total_seconds()


def _wrap(ttl: int, raw: bytes) -> bytes:
    """The sealed envelope: the sender's ttl, then the payload.

    Prefixing a single byte is why the ttl can be authenticated without being immutable. A relay
    decrements the OUTER ttl freely; the inner one is what the sender set, and raising the outer
    past it is refused on open.
    """
    return bytes([ttl & 0xFF]) + raw


def _unwrap(outer_ttl: int, sealed_bytes: bytes) -> bytes:
    if not sealed_bytes:
        raise SealError("sealed payload is empty")
    inner_ttl, body = sealed_bytes[0], sealed_bytes[1:]
    if outer_ttl > inner_ttl:
        raise SealError(
            f"ttl was raised in transit: {outer_ttl} exceeds the sealed maximum of {inner_ttl}. "
            f"A relay may spend hops, never add them")
    return body


def seal_bytes(message: MeshMessage, content: bytes, key: bytes, cipher: Cipher, *,
               sender_key: bytes, content_type: str = seal.CONTENT_VOICE) -> SealedBundle:
    """Seal a voice note or a photograph. Same envelope, same rules, byte payload."""
    sealed = seal.seal(message.id, message.kind, _wrap(message.ttl, content), key, cipher,
                       sender_key=sender_key, content_type=content_type, ttl=message.ttl)
    return SealedBundle(
        id=sealed.id, kind=sealed.kind, size=sealed.size, ttl=message.ttl, hops=message.hops,
        created_at=message.created_at, payload=sealed.payload,
        content_type=sealed.content_type, sender=sealed.sender,
    )


def seal_bundle(bundle: MeshMessage, key: bytes, cipher: Cipher, *,
                sender_key: bytes, content_type: str = seal.CONTENT_TEXT) -> SealedBundle:
    """Seal a message so the phones that carry it cannot read it.

    The associated data binds the id, kind, content type, sender and ttl, so a carrier cannot
    promote a chat to an SOS or extend the ttl without the tag failing - which is the attack that
    would otherwise be available to every relay in the chain.
    """
    # The ttl travels INSIDE the sealed payload as one leading byte, so a relay can decrement
    # the outer ttl freely while nobody can increase it past what the sender set.
    sealed = seal.seal(bundle.id, bundle.kind, _wrap(bundle.ttl, bundle.body.encode("utf-8")),
                       key, cipher,
                       sender_key=sender_key, content_type=content_type, ttl=bundle.ttl)
    return SealedBundle(
        id=sealed.id, kind=sealed.kind, size=sealed.size, ttl=bundle.ttl,
        hops=bundle.hops, created_at=bundle.created_at, payload=sealed.payload,
        content_type=sealed.content_type, sender=sealed.sender,
    )


def open_bundle(sealed: SealedBundle, key: bytes, cipher: Cipher, *,
                guard: ReplayGuard | None = None, expect_sender: str | None = None,
                now: datetime | None = None) -> MeshMessage:
    """Recover the message. Refuses a tampered, forged or replayed bundle.

    The replay guard is applied here rather than left to the caller because a replayed SOS is
    indistinguishable from a real one at every layer above this - every relay authenticates it
    correctly - so if it is not caught here it is not caught.
    """
    if guard is not None:
        guard.check(sealed, now=(now.timestamp() if now else None))

    shell = seal.Sealed(id=sealed.id, kind=sealed.kind, content_type=sealed.content_type,
                        sender=sealed.sender, ttl=sealed.ttl, size=sealed.size,
                        payload=sealed.payload,
                        created_at=sealed.created_at.timestamp())
    raw = _unwrap(sealed.ttl, seal.unseal(shell, key, cipher, expect_sender=expect_sender))

    if sealed.content_type != seal.CONTENT_TEXT:
        raise SealError(
            f"bundle is {sealed.content_type}, not text - use open_bytes and hand it to a "
            f"player or a viewer")
    return MeshMessage(kind=sealed.kind, body=raw.decode("utf-8"), origin=sealed.sender,
                       id=sealed.id, created_at=sealed.created_at, ttl=sealed.ttl,
                       hops=sealed.hops, path=list(sealed.path))


def open_bytes(sealed: SealedBundle, key: bytes, cipher: Cipher, *,
               guard: ReplayGuard | None = None,
               expect_sender: str | None = None) -> bytes:
    """For voice notes and photographs, which are bytes rather than text."""
    if guard is not None:
        guard.check(sealed)
    shell = seal.Sealed(id=sealed.id, kind=sealed.kind, content_type=sealed.content_type,
                        sender=sealed.sender, ttl=sealed.ttl, size=sealed.size,
                        payload=sealed.payload,
                        created_at=sealed.created_at.timestamp())
    return _unwrap(sealed.ttl, seal.unseal(shell, key, cipher, expect_sender=expect_sender))


def relay(sealed: SealedBundle, transport: Transport, peer: str) -> SealedBundle:
    """Move a sealed bundle one hop. The payload is untouched, because a relay cannot touch it.

    This is the whole reason the layer exists: the function that moves a message between strangers
    has no access to its contents, and does not need any.
    """
    return SealedBundle(
        id=sealed.id, kind=sealed.kind, size=sealed.size, ttl=sealed.ttl - 1,
        hops=sealed.hops + 1, created_at=sealed.created_at, payload=sealed.payload,
        content_type=sealed.content_type, sender=sealed.sender,
        path=[*sealed.path, peer],
    )


def carrier_view(sealed: SealedBundle) -> dict:
    """Exactly what a carrier may log. No body, and no method anywhere that would produce one."""
    return {
        "id": sealed.id,
        "kind": sealed.kind,
        "sender": sealed.sender,
        "ttl": sealed.ttl,
        "hops": sealed.hops,
        "sealed_bytes": len(sealed.payload),
        "content_type": sealed.content_type,
        "created_at": sealed.created_at.isoformat(),
    }
