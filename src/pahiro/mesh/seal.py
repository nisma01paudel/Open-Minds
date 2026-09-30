"""Sealing a bundle so the phones that carry it cannot read it.

WHY THIS EXISTS
---------------
The whole design hands your message to strangers. A Bluetooth advertisement is collected by
whatever phone walks past; a Wi-Fi hop is relayed by whoever is in the chain; a courier is a
person. That is the point of the mesh and it is also the reason the payload must be sealed: **a
carrier must be able to move a bundle without being able to read it**, and must be able to prove
it came from who it says it did.

`dtn.py` moves bundles between stores. This decides what a store is even allowed to see.

WHAT A RELAY MAY SEE, AND WHAT IT MAY NOT
----------------------------------------
Relaying needs very little, and the sealed form gives it exactly that and nothing more:

    MAY SEE      id, kind, size, ttl, sender fingerprint, creation time
    MAY NOT SEE  the body - not text, not a voice note, not a photograph

That split is the design. `Sealed.relay_view()` returns only the first row, and there is no
accessor on the sealed object that yields the body without the key. A relay cannot accidentally
log a message it was never able to read.

TEXT, VOICE AND IMAGES ARE THE SAME PROBLEM
-------------------------------------------
A voice note and a photograph are byte strings, so the envelope is byte-oriented and carries a
content type rather than assuming text. The same sealing, the same authenticity, the same replay
guard.

THE CRYPTO IS REAL, AND IS NOT YET ON THE MESSAGE PATH
-----------------------------------------------------
`AeadCipher` wraps a real AEAD and `chacha20poly1305()` is the one to use:

    cipher = seal.chacha20poly1305()

ChaCha20-Poly1305 rather than AES-GCM because it is constant time in software without hardware
acceleration, and the handsets this runs on are old. `generate_keypair()` and `shared_key()` add
X25519 with HKDF, so a bundle can be sealed to a district server such that the phones relaying it
- which include strangers - cannot read it even if one of them is compromised.

**None of that is wired into `dtn.py` or the field client yet.** A message sent through the
running system today is not sealed. The layer is built and tested; putting it on the path is
separate work, and saying otherwise would be the same kind of lie this module was written to
avoid.

`InsecureTestCipher` remains for tests only and **refuses to run unless the caller passes
`allow_insecure=True`**, so an operational deployment fails loudly instead of quietly carrying
plaintext. A test asserts that refusal, so the placeholder cannot become the shipped one by
accident.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass, field
from typing import Protocol

# Content types. A relay does not need these to route, and they are sealed as associated data so
# they cannot be altered in flight to make a photograph look like an alert.
CONTENT_TEXT = "text"
CONTENT_VOICE = "voice"
CONTENT_IMAGE = "image"
CONTENT_TYPES = (CONTENT_TEXT, CONTENT_VOICE, CONTENT_IMAGE)

NONCE_BYTES = 12
KEY_BYTES = 32


class SealError(Exception):
    """A bundle that cannot be trusted: wrong key, tampered, or replayed."""


class Cipher(Protocol):
    """Authenticated encryption with associated data. Supply a vetted one."""

    name: str

    def seal(self, plaintext: bytes, key: bytes, aad: bytes) -> bytes: ...

    def open(self, ciphertext: bytes, key: bytes, aad: bytes) -> bytes: ...


class InsecureTestCipher:
    """NOT ENCRYPTION. A stand-in so the envelope logic can be tested without a crypto library.

    It XORs with a SHA-256 keystream and appends an HMAC - which is a construction no one should
    ever use, because the keystream repeats across messages and the MAC is over the ciphertext
    rather than a proper AEAD tag. It is deliberately named so it cannot be mistaken, and it
    refuses to construct without an explicit acknowledgement.
    """

    name = "insecure-test-cipher"

    def __init__(self, *, allow_insecure: bool = False) -> None:
        if not allow_insecure:
            raise SealError(
                "InsecureTestCipher is not encryption and will not run without "
                "allow_insecure=True. Wire a vetted AEAD (ChaCha20Poly1305 or AESGCM) instead - "
                "see the module docstring."
            )

    def _stream(self, key: bytes, nonce: bytes, length: int) -> bytes:
        out = b""
        counter = 0
        while len(out) < length:
            out += hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
            counter += 1
        return out[:length]

    def seal(self, plaintext: bytes, key: bytes, aad: bytes) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        stream = self._stream(key, nonce, len(plaintext))
        body = bytes(a ^ b for a, b in zip(plaintext, stream))
        tag = hmac.new(key, nonce + aad + body, hashlib.sha256).digest()[:16]
        return nonce + body + tag

    def open(self, ciphertext: bytes, key: bytes, aad: bytes) -> bytes:
        if len(ciphertext) < NONCE_BYTES + 16:
            raise SealError("sealed payload is too short to be valid")
        nonce = ciphertext[:NONCE_BYTES]
        body = ciphertext[NONCE_BYTES:-16]
        tag = ciphertext[-16:]
        expected = hmac.new(key, nonce + aad + body, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected):
            raise SealError("authentication failed: wrong key, or the payload was altered")
        stream = self._stream(key, nonce, len(body))
        return bytes(a ^ b for a, b in zip(body, stream))


def fingerprint(public_key: bytes) -> str:
    """A short, stable name for a key, so a panel can show who a bundle is from."""
    return hashlib.sha256(public_key).hexdigest()[:16]


@dataclass(frozen=True)
class Sealed:
    """A bundle after sealing: what a carrier holds, and what it is allowed to know.

    There is no method here that returns the body without the key. That is not an oversight; it
    is the interface. A relay that cannot call it cannot leak it.
    """

    id: str
    kind: str
    content_type: str
    sender: str                 # fingerprint of the sender's key
    ttl: int
    size: int                   # plaintext length, so a transport can be chosen without opening
    payload: bytes              # nonce || ciphertext || tag
    created_at: float = field(default_factory=time.time)

    def relay_view(self) -> dict:
        """Everything a carrier legitimately needs, and nothing else.

        This is what a relay logs, displays, and routes on. Note what is absent: the body.
        """
        return {
            "id": self.id,
            "kind": self.kind,
            "sender": self.sender,
            "ttl": self.ttl,
            "size": self.size,
            "content_type": self.content_type,   # a carrier may know it is voice; not what it says
            "created_at": self.created_at,
        }

    def aad(self) -> bytes:
        """The associated data: bound into the tag, so it cannot be edited in flight.

        Without this an attacker could keep a valid body and change the kind from `chat` to `sos`,
        or reset the ttl, and every relay would believe it.
        """
        return "\x1f".join([self.id, self.kind, self.content_type, self.sender,
                            str(self.ttl)]).encode("utf-8")


def seal(bundle_id: str, kind: str, content: bytes | str, key: bytes, cipher: Cipher, *,
         sender_key: bytes, content_type: str = CONTENT_TEXT, ttl: int = 7) -> Sealed:
    """Seal a payload so only a holder of `key` can read it.

    `content` may be text, a voice note, or a photograph - they are all byte strings, and the
    content type travels sealed so it cannot be altered.
    """
    if content_type not in CONTENT_TYPES:
        raise SealError(f"unknown content type {content_type!r}; expected one of {CONTENT_TYPES}")
    if len(key) != KEY_BYTES:
        raise SealError(f"keys must be {KEY_BYTES} bytes, got {len(key)}")
    raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)

    shell = Sealed(id=bundle_id, kind=kind, content_type=content_type,
                   sender=fingerprint(sender_key), ttl=ttl, size=len(raw), payload=b"")
    payload = cipher.seal(raw, key, shell.aad())
    return Sealed(id=shell.id, kind=shell.kind, content_type=shell.content_type,
                  sender=shell.sender, ttl=shell.ttl, size=shell.size, payload=payload,
                  created_at=shell.created_at)


def unseal(sealed: Sealed, key: bytes, cipher: Cipher, *,
           expect_sender: str | None = None) -> bytes:
    """Recover the payload. Raises `SealError` on tampering, a wrong key, or a forged sender."""
    if expect_sender is not None and not hmac.compare_digest(sealed.sender, expect_sender):
        raise SealError(
            f"bundle claims to be from {sealed.sender} but {expect_sender} was expected")
    raw = cipher.open(sealed.payload, key, sealed.aad())
    if len(raw) != sealed.size:
        # The tag should already have caught this; checking the declared size as well means a
        # carrier cannot truncate a voice note and have it accepted.
        raise SealError(f"payload is {len(raw)} bytes but the bundle declared {sealed.size}")
    return raw


def unseal_text(sealed: Sealed, key: bytes, cipher: Cipher, **kw) -> str:
    if sealed.content_type != CONTENT_TEXT:
        raise SealError(f"bundle is {sealed.content_type}, not text")
    return unseal(sealed, key, cipher, **kw).decode("utf-8")


class ReplayGuard:
    """Refuses a sealed bundle that has already been seen.

    Sealing stops a carrier reading the message; it does not stop them *re-sending* it. A valid
    recorded SOS replayed an hour later sends a team to a place where nothing is happening, and
    every relay would authenticate it correctly. So identity is `(sender, payload)` - the payload
    includes the nonce, so the same plaintext sealed twice is two legitimate bundles and the same
    bytes twice is a replay.
    """

    def __init__(self, max_age_s: float = 6 * 3600) -> None:
        self.max_age_s = max_age_s
        self._seen: dict[tuple[str, bytes], float] = {}

    def _key(self, sealed: Sealed) -> tuple[str, bytes]:
        return (sealed.sender, hashlib.sha256(sealed.payload).digest())

    def accept(self, sealed: Sealed, now: float | None = None) -> bool:
        """True if this is new. False means it has been seen inside the window."""
        now = now if now is not None else time.time()
        self.expire(now)
        k = self._key(sealed)
        if k in self._seen:
            return False
        self._seen[k] = now
        return True

    def check(self, sealed: Sealed, now: float | None = None) -> None:
        """Raise rather than return, for callers that treat a replay as hostile input."""
        if not self.accept(sealed, now):
            raise SealError(f"replay: bundle {sealed.id} from {sealed.sender} was already seen")

    def expire(self, now: float | None = None) -> int:
        now = now if now is not None else time.time()
        stale = [k for k, t in self._seen.items() if now - t > self.max_age_s]
        for k in stale:
            del self._seen[k]
        return len(stale)

    def __len__(self) -> int:
        return len(self._seen)


def generate_key() -> bytes:
    """A key for the group. `os.urandom`, so this is the one part that is already right."""
    return os.urandom(KEY_BYTES)


# ---- the real thing -----------------------------------------------------------------------------

class AeadCipher:
    """A real authenticated cipher, wrapping whichever AEAD the caller supplies.

    This is the implementation to use. It exists so that wiring production crypto is one line and
    not a rewrite:

        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        cipher = AeadCipher(ChaCha20Poly1305, "chacha20-poly1305")

    ChaCha20-Poly1305 is the recommendation for this system rather than AES-GCM: it is constant
    time in software without hardware acceleration, and the handsets this runs on are old. The
    tag covers the associated data, so the kind, content type and ttl cannot be altered in
    flight - see `Sealed.aad`.

    The nonce is generated per message by `os.urandom` and prepended. Reusing a nonce under the
    same key is fatal for both of these ciphers, which is why it is generated here rather than
    accepted from a caller who might reuse it.
    """

    def __init__(self, aead_class, name: str) -> None:
        self._aead_class = aead_class
        self.name = name
        self._check()

    def _check(self) -> None:
        try:
            from cryptography.exceptions import InvalidTag  # noqa: F401
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise SealError(
                "the `cryptography` package is required for real sealing; install the crypto "
                "extra (pip install '.[crypto]') or supply your own Cipher implementation"
            ) from exc

    def seal(self, plaintext: bytes, key: bytes, aad: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305  # noqa: F401

        nonce = os.urandom(NONCE_BYTES)
        aead = self._aead_class(key)
        return nonce + aead.encrypt(nonce, plaintext, aad)

    def open(self, ciphertext: bytes, key: bytes, aad: bytes) -> bytes:
        from cryptography.exceptions import InvalidTag

        if len(ciphertext) < NONCE_BYTES + 16:
            raise SealError("sealed payload is too short to be valid")
        nonce = ciphertext[:NONCE_BYTES]
        try:
            aead = self._aead_class(key)
            return aead.decrypt(nonce, ciphertext[NONCE_BYTES:], aad)
        except InvalidTag as exc:
            # The same message for a wrong key and for altered ciphertext, deliberately: telling
            # an attacker which one it was is free information.
            raise SealError(
                "authentication failed: wrong key, or the payload was altered") from exc


def chacha20poly1305() -> AeadCipher:
    """The recommended cipher for this system."""
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

    return AeadCipher(ChaCha20Poly1305, "chacha20-poly1305")


# ---- keys between people ------------------------------------------------------------------------

def generate_keypair() -> tuple[bytes, bytes]:
    """An X25519 keypair, as (private_bytes, public_bytes).

    A group key is fine for a ward's own handsets. A *pair* is what lets a bundle be sealed to a
    district server so that the phones relaying it - which include strangers - cannot read it even
    if one of them is compromised and the group key leaks.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

    private = X25519PrivateKey.generate()
    return (
        private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    )


def shared_key(private_bytes: bytes, peer_public_bytes: bytes,
               info: bytes = b"pahiro-bundle-v1") -> bytes:
    """Derive a 32-byte key from an X25519 exchange, through HKDF.

    Raw X25519 output is not uniformly random and must not be used as a key directly; HKDF with a
    domain-separating `info` is what makes it one, and what stops the same exchange being reused
    as a key for something else later.
    """
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    private = X25519PrivateKey.from_private_bytes(private_bytes)
    peer = X25519PublicKey.from_public_bytes(peer_public_bytes)
    _ = serialization  # imported for parity with generate_keypair's serialisation use
    return HKDF(
        algorithm=hashes.SHA256(), length=KEY_BYTES, salt=None, info=info
    ).derive(private.exchange(peer))
