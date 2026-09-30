/* Sealing, in the browser. The same envelope as src/pahiro/mesh/seal.py.
 *
 * WHY AES-GCM HERE AND CHACHA20-POLY1305 IN PYTHON
 * ------------------------------------------------
 * WebCrypto does not standardly offer ChaCha20-Poly1305. Node has it behind an experimental flag
 * and it warns; Safari and Firefox do not expose it at all. A rescue cannot be conditional on
 * which browser a phone happens to run, so the client uses AES-GCM, which every WebCrypto
 * implementation has.
 *
 * Both are AEADs with a 12-byte nonce and a 16-byte tag, so the ENVELOPE is identical and only
 * the primitive differs. Which one is in use is a deployment agreement, not something encoded in
 * the bytes - state it in the config, not in the frame.
 *
 * WHAT IS SHARED, AND MUST STAY SHARED
 * ------------------------------------
 *   layout       nonce(12) || ciphertext || tag(16)
 *   aad          id \x1f kind \x1f contentType \x1f sender      (UTF-8)
 *   no ttl       ttl is mutable routing metadata and is sealed INSIDE the payload, because a
 *                ttl decrements at every hop and an authenticated ttl could not be relayed
 *                even once. See pipeline.py.
 *
 * scripts/check_seal_parity.py opens a message sealed by the other language, both ways. Two
 * implementations of one format in two languages will drift, and a crypto format that drifts does
 * not fail loudly - it fails to open at the moment somebody needs it.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory(); }
  else { root.PahiroSeal = factory(); }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var NONCE_BYTES = 12;
  var TAG_BYTES = 16;
  var KEY_BYTES = 32;
  var SEP = "\x1f";

  function subtle() {
    if (typeof crypto !== "undefined" && crypto.subtle) return crypto.subtle;
    if (typeof require === "function") return require("crypto").webcrypto.subtle;
    throw new Error("no WebCrypto in this environment");
  }

  function aad(id, kind, contentType, sender) {
    return new TextEncoder().encode([id, kind, contentType, sender].join(SEP));
  }

  async function importKey(key) {
    if (key.length !== KEY_BYTES) {
      throw new Error("keys must be " + KEY_BYTES + " bytes, got " + key.length);
    }
    return subtle().importKey("raw", key, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
  }

  /* Returns nonce || ciphertext || tag, byte for byte what AeadCipher produces in Python. */
  async function sealBytes(id, kind, contentType, sender, plaintext, key) {
    var k = await importKey(key);
    var nonce = crypto.getRandomValues(new Uint8Array(NONCE_BYTES));
    var ct = new Uint8Array(await subtle().encrypt(
      { name: "AES-GCM", iv: nonce, additionalData: aad(id, kind, contentType, sender), tagLength: 128 },
      k, plaintext));
    var out = new Uint8Array(nonce.length + ct.length);
    out.set(nonce, 0);
    out.set(ct, nonce.length);
    return out;
  }

  async function openBytes(id, kind, contentType, sender, payload, key) {
    if (!payload || payload.length < NONCE_BYTES + TAG_BYTES) {
      throw new Error("sealed payload is too short to be valid");
    }
    var k = await importKey(key);
    var nonce = payload.slice(0, NONCE_BYTES);
    var body = payload.slice(NONCE_BYTES);
    try {
      var pt = await subtle().decrypt(
        { name: "AES-GCM", iv: nonce, additionalData: aad(id, kind, contentType, sender), tagLength: 128 },
        k, body);
      return new Uint8Array(pt);
    } catch (e) {
      /* One message for a wrong key and for altered ciphertext, deliberately: telling an
       * attacker which one it was is free information. */
      throw new Error("authentication failed: wrong key, or the payload was altered");
    }
  }

  /* The envelope: the sender's ttl, then the payload. Mirrors pipeline._wrap / _unwrap, so a
   * relay can decrement the outer ttl while nobody can raise it past what was sealed. */
  function wrap(ttl, raw) {
    var out = new Uint8Array(raw.length + 1);
    out[0] = ttl & 0xFF;
    out.set(raw, 1);
    return out;
  }

  function unwrap(outerTtl, sealedBytes) {
    if (!sealedBytes || !sealedBytes.length) throw new Error("sealed payload is empty");
    var inner = sealedBytes[0];
    if (outerTtl > inner) {
      throw new Error("ttl was raised in transit: " + outerTtl + " exceeds the sealed maximum " +
        "of " + inner + ". A relay may spend hops, never add them");
    }
    return sealedBytes.slice(1);
  }

  async function sealText(meta, text, key) {
    var raw = new TextEncoder().encode(text);
    var sealed = await sealBytes(meta.id, meta.kind, meta.contentType || "text", meta.sender,
                                 wrap(meta.ttl, raw), key);
    return sealed;
  }

  async function openText(meta, payload, key) {
    var raw = await openBytes(meta.id, meta.kind, meta.contentType || "text", meta.sender,
                              payload, key);
    return new TextDecoder().decode(unwrap(meta.ttl, raw));
  }

  /* What a carrier is allowed to know, in the browser too. */
  function carrierView(meta, payload) {
    return {
      id: meta.id, kind: meta.kind, sender: meta.sender, ttl: meta.ttl,
      content_type: meta.contentType || "text", sealed_bytes: payload.length
    };
  }

  function randomKey() {
    return crypto.getRandomValues(new Uint8Array(KEY_BYTES));
  }

  return {
    NONCE_BYTES: NONCE_BYTES, TAG_BYTES: TAG_BYTES, KEY_BYTES: KEY_BYTES,
    sealText: sealText, openText: openText,
    sealBytes: sealBytes, openBytes: openBytes,
    carrierView: carrierView, randomKey: randomKey, wrap: wrap, unwrap: unwrap
  };
}));
