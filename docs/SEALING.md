# Sealing: what the phone carrying your message is allowed to know

The design hands your message to strangers — a Bluetooth advertisement is collected by whoever
walks past, a Wi-Fi hop is relayed by whoever is in the chain, a courier is a person. That is the
point of the mesh, and it is exactly why the payload must be sealed.

## The split

Relaying needs very little. The sealed form gives a carrier this and nothing else:

| A carrier MAY see | A carrier MAY NOT see |
|---|---|
| id, kind, size, ttl | the body — not text, not a voice note, not a photograph |
| sender fingerprint, content type, creation time | anything that reveals what it says |

`Sealed.relay_view()` returns only the first column, and the sealed object has **no accessor that
yields the body without the key**. A relay that cannot call it cannot leak it, and cannot log a
message it was never able to read.

## Voice and images are the same problem

A voice note and a photograph are byte strings, so the envelope is byte-oriented and carries a
content type rather than assuming text. Same sealing, same authenticity, same replay guard. Tests
cover a ~10 KB recording and a ~50 KB JPEG.

## What is verified

- A relay cannot recover the body from anything it holds.
- The wrong key **fails** rather than returning rubbish.
- **Tampering is detected**, including the three attacks that would otherwise work:
  altering the ciphertext, **promoting a `chat` to an `sos`**, and **extending the ttl** — the
  kind, content type and ttl are bound into the tag, so a valid body cannot be re-labelled.
- **Truncating a voice note** is detected, so a carrier cannot shorten a recording and have it
  accepted.
- **A forged sender is refused** when the recipient requires a specific one.
- **A replayed bundle is refused** by a replay guard. This matters more than it sounds: sealing
  stops a carrier *reading* a message, not *re-sending* it. A recorded SOS replayed an hour later
  sends a team somewhere nothing is happening, and every relay would authenticate it correctly.

## The crypto IS wired

`cryptography` 50.0.1 is installed and declared as the `crypto` extra:

```
pip install '.[crypto]'
```

`seal.chacha20poly1305()` returns a real `AeadCipher`. ChaCha20-Poly1305 is the recommendation
here rather than AES-GCM because it is constant time in software without hardware acceleration,
and the handsets this runs on are old. The tag covers the associated data, so the kind, content
type and ttl cannot be altered in flight — which is what makes the anti-promotion property real
rather than aspirational.

The nonce is generated per message with `os.urandom` inside the cipher. Reusing a nonce under one
key is fatal for both ciphers, so it is never a caller's job.

### Keys between people

A group key is fine for a ward's own handsets. `generate_keypair()` and `shared_key()` add X25519
with HKDF for the case that actually matters here: **sealing a bundle to a district server so the
phones relaying it — which include strangers — cannot read it even if one of them is compromised
and the group key leaks.**

`shared_key` runs the raw exchange through HKDF with a domain-separating `info`, because raw
X25519 output is not uniformly random and must not be used as a key directly.

A test asserts the whole property: the district can open a bundle sealed by a phone, and a third
party holding **both public keys** cannot.

### What is verified against the real AEAD

- text, a ~10 KB voice note and a ~50 KB JPEG all round-trip exactly
- the plaintext words do not appear in the ciphertext
- tampering is refused, including **promoting a `chat` to an `sos`**
- the wrong key is refused
- a fresh nonce every time, so sealing the same words twice gives different bytes
- a truncated payload is refused before decryption
- the replay guard works on real ciphertext

## It is now on the mesh path

`pipeline.py` is the join that was missing: `dtn.Bundle` carried a plaintext `body` and
`seal.Sealed` carried an opaque payload, and **nothing converted between them**. A `SealedBundle`
satisfies exactly the interface `dtn.py` needs to route it — `kind`, `size_bytes`, `fits`,
`priority`, `ttl`, `hops`, `custody`, `attempts` — and has **no body attribute at all**.

So a carrier can choose a transport, take custody, spend a hop and hand off, without ever being
able to read what it moved. That is not a policy; there is no method that returns the plaintext,
and a test asserts the absence.

Verified on the joined path: relaying three strangers deep leaves the payload byte-identical and
the message still opens correctly at the end.

## The bug that only wiring could find

`ttl` was in the authenticated data. A ttl **decrements at every hop**, so the tag failed the
moment a relay did its job — **a sealed bundle could not be relayed even once.** Every unit test
on either side passed; the layers were individually correct and jointly useless.

Mutable routing metadata cannot be authenticated directly. The ttl is now sealed *inside* the
payload as a leading byte, and the recipient refuses a bundle whose outer ttl exceeds the sealed
one. A relay can spend hops; nobody can add them. The test that used to assert "rewriting the ttl
is detected" at the seal layer was **wrong by design** and now documents why the protection moved
up a layer.

Two further interface mismatches surfaced the same way: `Custody` records responsibility with
`dataclasses.replace(..., custody=...)` and counts offers in `attempts`, and neither field existed
on the sealed form.

## The browser can seal too, and it is proven

`web/public/field/seal.js` implements the same envelope with WebCrypto, and
`scripts/check_seal_parity.py` proves each language opens what the other sealed — both
directions, tampering refused, carrier view identical.

**AES-GCM on the client, not ChaCha20-Poly1305**, and that is a real constraint rather than a
preference: WebCrypto does not standardly offer ChaCha20-Poly1305. Node exposes it behind an
experimental flag and warns; Safari and Firefox do not expose it at all. A rescue cannot be
conditional on which browser a phone happens to run, so the client uses AES-GCM, which every
WebCrypto implementation has. Both are AEADs with a 12-byte nonce and a 16-byte tag, so the
*envelope* is identical and only the primitive differs — which cipher is in use is a deployment
agreement, not something encoded in the frame.

The shared parts, which a parity check exists to keep shared:

    layout   nonce(12) || ciphertext || tag(16)
    aad      id \x1f kind \x1f contentType \x1f sender      (UTF-8)
    no ttl   the ttl is sealed INSIDE the payload, because a ttl decrements at every hop

## What is still NOT done

- **The gateway accepts sealed frames; the client still sends plaintext.**
  `POST /api/v1/mesh/messages` now takes `{"sealed": {...}}` frames when the server is started with
  `--seal-key <hex>`; without a key it **refuses** them with a reason rather than dropping them,
  because silence looks identical to an empty mesh. What remains is switching `syncMeshToApi()`
  over to sealing at compose time and deciding where keys live — a product decision, not a code
  one.
- **The client uses AES-GCM and the Python default is ChaCha20-Poly1305.** The gateway uses
  AES-GCM for sealed frames because that is what WebCrypto provides. A deployment must pick one and
  state it; nothing in the frame says which.
- **The client uses AES-GCM and the Python default is ChaCha20-Poly1305.** They interoperate
  through AES-GCM; a deployment must pick one and state it. Nothing in the frame says which.
- Nothing has been reviewed by a cryptographer.
- **So do not tell a judge the message path is end-to-end encrypted today.** The sealing layer is
  built and tested on both sides of the language boundary, and the Python mesh path carries sealed
  bundles. The browser's compose path is still plaintext.
