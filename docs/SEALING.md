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

## What is still NOT done

Being precise, because "we have encryption" and "our messages are encrypted" are different
claims:

- **The sealing layer is implemented and tested. It is not yet on the live bundle path.**
  `dtn.py` and the field client do not call it, so a message sent through the running system today
  is **not** sealed. Wiring it means sealing at compose time and unsealing at the destination, and
  choosing where keys live — which is a product decision, not a code one.
- The insecure placeholder still exists for tests and **still refuses to construct** without an
  explicit flag. A test asserts that, so shipping the fake one by accident is not possible.
- Nothing here has been reviewed by a cryptographer. It uses vetted primitives correctly as far
  as the tests show, which is not the same as an audit.

**So: do not tell a judge the system is end-to-end encrypted today.** The right sentence is that
the sealing layer is built and tested against a real AEAD, and the remaining work is wiring it
into the message path and deciding where keys live.
