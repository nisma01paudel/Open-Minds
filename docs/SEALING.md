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

## The crypto is NOT wired, and this page exists to say so

`cryptography`, `nacl` and `pycryptodome` are all absent from this environment and `pip` is not
available to add one. **Hand-rolling authenticated encryption is how projects ship
vulnerabilities**, and doing it in a system intended for a disaster would be indefensible.

So the cipher is a **dependency, injected**. The only implementation shipped is
`InsecureTestCipher`, which is not encryption; it exists so the envelope logic — metadata
separation, authenticity, replay — is fully testable, and it **refuses to construct unless the
caller passes `allow_insecure=True`**. An operational deployment therefore fails loudly instead of
quietly carrying plaintext. A test asserts that refusal, so the placeholder cannot become the
shipped one by accident.

Wiring the real thing is one line:

```python
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
cipher = AeadCipher(ChaCha20Poly1305, "chacha20-poly1305")
```

Until that line exists, **do not describe this system as end-to-end encrypted.** The envelope,
the key handling and the replay guard are real and tested. The cipher is not present.
