"""Sealing: a carrier must be able to move a bundle without being able to read it.

The tests that matter are the negative ones - a relay cannot recover the body, tampering is
caught, and a replay is refused - because those are the failures that stay invisible until
somebody is listening.
"""
from __future__ import annotations

import pytest

from pahiro.mesh import seal as S

KEY = b"k" * 32
OTHER_KEY = b"x" * 32
SENDER = b"district-key-alpha"


@pytest.fixture
def cipher() -> S.InsecureTestCipher:
    # The stand-in, used only because no vetted AEAD exists in this environment. Its refusal to
    # run without the flag is itself asserted below.
    return S.InsecureTestCipher(allow_insecure=True)


# ---- the invariant that protects the placeholder from shipping ---------------------------------

def test_the_placeholder_cipher_refuses_to_run_without_an_explicit_flag():
    """An operational deployment must fail loudly rather than quietly carry plaintext."""
    with pytest.raises(S.SealError) as exc:
        S.InsecureTestCipher()
    assert "not encryption" in str(exc.value)
    assert "vetted AEAD" in str(exc.value)


def test_the_placeholder_names_itself_honestly():
    assert S.InsecureTestCipher(allow_insecure=True).name == "insecure-test-cipher"


# ---- what a relay may and may not see -----------------------------------------------------------

def test_a_relay_can_route_without_being_able_to_read(cipher):
    """The split is the design: metadata to route, body sealed."""
    sealed = S.seal("b1", "sos", "six trapped under the bus at KM 42", KEY, cipher,
                    sender_key=SENDER)
    view = sealed.relay_view()
    assert view["kind"] == "sos"
    assert view["size"] > 0
    assert view["id"] == "b1"
    # the body must not be recoverable from anything a relay holds
    assert "trapped" not in str(view)
    assert "trapped" not in sealed.payload.decode("latin-1")


def test_the_sealed_object_has_no_accessor_that_yields_the_body(cipher):
    """A relay that cannot call it cannot leak it."""
    sealed = S.seal("b1", "sos", "secret", KEY, cipher, sender_key=SENDER)
    public_names = [n for n in dir(sealed) if not n.startswith("_")]
    assert "body" not in public_names
    assert "plaintext" not in public_names
    assert "content" not in public_names


def test_the_right_key_recovers_the_exact_payload(cipher):
    text = "six trapped under the bus at KM 42 — २८.२१, ८३.९८"
    sealed = S.seal("b1", "sos", text, KEY, cipher, sender_key=SENDER)
    assert S.unseal_text(sealed, KEY, cipher) == text


def test_the_wrong_key_fails_rather_than_returning_rubbish(cipher):
    sealed = S.seal("b1", "sos", "six trapped", KEY, cipher, sender_key=SENDER)
    with pytest.raises(S.SealError) as exc:
        S.unseal(sealed, OTHER_KEY, cipher)
    assert "authentication failed" in str(exc.value)


# ---- voice and images are the same problem ------------------------------------------------------

def test_a_voice_note_seals_and_opens_as_bytes(cipher):
    audio = bytes(range(256)) * 40          # ~10 KB, the shape of a short recording
    sealed = S.seal("v1", "sos", audio, KEY, cipher, sender_key=SENDER,
                    content_type=S.CONTENT_VOICE)
    assert sealed.relay_view()["content_type"] == "voice"
    assert S.unseal(sealed, KEY, cipher) == audio


def test_a_photograph_seals_and_opens_as_bytes(cipher):
    photo = b"\xff\xd8\xff\xe0" + bytes(range(256)) * 200   # JPEG-shaped, ~50 KB
    sealed = S.seal("i1", "sos", photo, KEY, cipher, sender_key=SENDER,
                    content_type=S.CONTENT_IMAGE)
    assert S.unseal(sealed, KEY, cipher) == photo


def test_an_unknown_content_type_is_refused(cipher):
    with pytest.raises(S.SealError):
        S.seal("x", "sos", b"data", KEY, cipher, sender_key=SENDER, content_type="video")


def test_text_is_not_readable_as_text_after_sealing(cipher):
    """If the ciphertext contained the words, this whole module would be theatre."""
    sealed = S.seal("b1", "chat", "meet at the bridge at dawn", KEY, cipher, sender_key=SENDER)
    assert b"bridge" not in sealed.payload
    assert b"dawn" not in sealed.payload


# ---- tampering and forgery ----------------------------------------------------------------------

def test_altering_the_ciphertext_is_detected(cipher):
    sealed = S.seal("b1", "sos", "six trapped", KEY, cipher, sender_key=SENDER)
    broken = bytearray(sealed.payload)
    broken[-1] ^= 0x01
    damaged = S.Sealed(id=sealed.id, kind=sealed.kind, content_type=sealed.content_type,
                       sender=sealed.sender, ttl=sealed.ttl, size=sealed.size,
                       payload=bytes(broken), created_at=sealed.created_at)
    with pytest.raises(S.SealError):
        S.unseal(damaged, KEY, cipher)


def test_promoting_a_chat_message_to_an_sos_is_detected(cipher):
    """Without associated data an attacker keeps a valid body and upgrades its urgency."""
    sealed = S.seal("b1", "chat", "we are fine", KEY, cipher, sender_key=SENDER)
    promoted = S.Sealed(id=sealed.id, kind="sos", content_type=sealed.content_type,
                        sender=sealed.sender, ttl=sealed.ttl, size=sealed.size,
                        payload=sealed.payload, created_at=sealed.created_at)
    with pytest.raises(S.SealError):
        S.unseal(promoted, KEY, cipher)


def test_the_ttl_is_deliberately_not_authenticated_here(cipher):
    """The ttl is mutable routing metadata and cannot be in the tag.

    It was, and that made the layer unusable: a ttl decrements at every hop, so the tag failed as
    soon as a relay did its job. The ttl is sealed inside the payload instead, and the refusal of
    a raised ttl is asserted at the pipeline layer where it belongs - see
    tests/test_pipeline.py::test_extending_the_ttl_in_transit_is_refused.
    """
    sealed = S.seal("b1", "sos", "help", KEY, cipher, sender_key=SENDER, ttl=1)
    changed = S.Sealed(id=sealed.id, kind=sealed.kind, content_type=sealed.content_type,
                       sender=sealed.sender, ttl=99, size=sealed.size,
                       payload=sealed.payload, created_at=sealed.created_at)
    assert S.unseal(changed, KEY, cipher) == b"help"


def test_truncating_a_voice_note_is_detected(cipher):
    sealed = S.seal("v1", "sos", b"\x00" * 500, KEY, cipher, sender_key=SENDER,
                    content_type=S.CONTENT_VOICE)
    short = S.Sealed(id=sealed.id, kind=sealed.kind, content_type=sealed.content_type,
                     sender=sealed.sender, ttl=sealed.ttl, size=100,
                     payload=sealed.payload, created_at=sealed.created_at)
    with pytest.raises(S.SealError):
        S.unseal(short, KEY, cipher)


def test_a_sender_can_be_required_and_a_forgery_is_refused(cipher):
    sealed = S.seal("b1", "sos", "help", KEY, cipher, sender_key=SENDER)
    assert S.unseal(sealed, KEY, cipher, expect_sender=S.fingerprint(SENDER))
    with pytest.raises(S.SealError) as exc:
        S.unseal(sealed, KEY, cipher, expect_sender=S.fingerprint(b"somebody-else"))
    assert "claims to be from" in str(exc.value)


def test_the_sender_fingerprint_is_stable_and_does_not_leak_the_key(cipher):
    a = S.fingerprint(SENDER)
    assert a == S.fingerprint(SENDER)
    assert a != S.fingerprint(b"district-key-beta")
    assert len(a) == 16
    assert SENDER.hex() not in a


def test_a_short_key_is_refused(cipher):
    with pytest.raises(S.SealError):
        S.seal("b1", "sos", "x", b"tooshort", cipher, sender_key=SENDER)


# ---- replay -------------------------------------------------------------------------------------

def test_a_recorded_bundle_replayed_later_is_refused(cipher):
    """Every relay would authenticate it correctly. Only the replay guard catches this."""
    sealed = S.seal("b1", "sos", "six trapped", KEY, cipher, sender_key=SENDER)
    guard = S.ReplayGuard()
    assert guard.accept(sealed, now=1000.0) is True
    assert guard.accept(sealed, now=1010.0) is False
    with pytest.raises(S.SealError) as exc:
        guard.check(sealed, now=1020.0)
    assert "replay" in str(exc.value)


def test_the_same_text_sealed_twice_is_two_legitimate_bundles(cipher):
    """A fresh nonce per seal, so a person sending the same sentence twice is not a replay."""
    first = S.seal("b1", "sos", "still here", KEY, cipher, sender_key=SENDER)
    second = S.seal("b2", "sos", "still here", KEY, cipher, sender_key=SENDER)
    guard = S.ReplayGuard()
    assert guard.accept(first, now=1000.0) is True
    assert guard.accept(second, now=1000.0) is True


def test_replays_from_different_senders_are_not_confused(cipher):
    one = S.seal("b1", "sos", "same words", KEY, cipher, sender_key=SENDER)
    two = S.seal("b1", "sos", "same words", KEY, cipher, sender_key=b"another-node")
    guard = S.ReplayGuard()
    assert guard.accept(one, now=1000.0) is True
    assert guard.accept(two, now=1000.0) is True
    assert len(guard) == 2


def test_the_replay_window_expires_so_the_guard_does_not_grow_forever():
    guard = S.ReplayGuard(max_age_s=60)
    sealed = S.seal("b1", "sos", "x", KEY, S.InsecureTestCipher(allow_insecure=True),
                    sender_key=SENDER)
    guard.accept(sealed, now=1000.0)
    assert len(guard) == 1
    assert guard.expire(now=2000.0) == 1
    assert len(guard) == 0


def test_generate_key_is_the_right_length_and_not_repeated():
    a, b = S.generate_key(), S.generate_key()
    assert len(a) == 32 and a != b


# ---- the real cipher ----------------------------------------------------------------------------

crypto = pytest.importorskip("cryptography", reason="the crypto extra is not installed")


@pytest.fixture
def real() -> S.AeadCipher:
    return S.chacha20poly1305()


def test_the_real_cipher_round_trips_text_voice_and_image(real):
    key = S.generate_key()
    for content, ctype in ((("six trapped at KM 42"), S.CONTENT_TEXT),
                           (bytes(range(256)) * 40, S.CONTENT_VOICE),
                           (b"\xff\xd8\xff\xe0" + bytes(range(256)) * 200, S.CONTENT_IMAGE)):
        sealed = S.seal(f"b-{ctype}", "sos", content, key, real, sender_key=b"alpha",
                        content_type=ctype)
        got = S.unseal(sealed, key, real)
        expected = content.encode("utf-8") if isinstance(content, str) else content
        assert got == expected, f"{ctype} did not survive the round trip"


def test_the_real_cipher_hides_the_words(real):
    sealed = S.seal("b1", "chat", "meet at the bridge at dawn", S.generate_key(), real,
                    sender_key=b"alpha")
    assert b"bridge" not in sealed.payload
    assert b"dawn" not in sealed.payload


def test_the_real_cipher_detects_tampering(real):
    key = S.generate_key()
    sealed = S.seal("b1", "sos", "six trapped", key, real, sender_key=b"alpha")
    broken = bytearray(sealed.payload)
    broken[-1] ^= 0x01
    damaged = S.Sealed(id=sealed.id, kind=sealed.kind, content_type=sealed.content_type,
                       sender=sealed.sender, ttl=sealed.ttl, size=sealed.size,
                       payload=bytes(broken), created_at=sealed.created_at)
    with pytest.raises(S.SealError) as exc:
        S.unseal(damaged, key, real)
    assert "authentication failed" in str(exc.value)


def test_the_real_cipher_refuses_the_wrong_key(real):
    sealed = S.seal("b1", "sos", "six trapped", S.generate_key(), real, sender_key=b"alpha")
    with pytest.raises(S.SealError):
        S.unseal(sealed, S.generate_key(), real)


def test_the_real_cipher_refuses_promoting_a_chat_to_an_sos(real):
    """The attack associated data exists to stop, now checked against a real AEAD."""
    key = S.generate_key()
    sealed = S.seal("b1", "chat", "we are fine", key, real, sender_key=b"alpha")
    promoted = S.Sealed(id=sealed.id, kind="sos", content_type=sealed.content_type,
                        sender=sealed.sender, ttl=sealed.ttl, size=sealed.size,
                        payload=sealed.payload, created_at=sealed.created_at)
    with pytest.raises(S.SealError):
        S.unseal(promoted, key, real)


def test_the_real_cipher_uses_a_fresh_nonce_every_time(real):
    """Reusing a nonce under one key is fatal for ChaCha20-Poly1305, so it is never a caller's job."""
    key = S.generate_key()
    a = S.seal("b1", "chat", "same words", key, real, sender_key=b"alpha")
    b = S.seal("b2", "chat", "same words", key, real, sender_key=b"alpha")
    assert a.payload != b.payload
    assert a.payload[:S.NONCE_BYTES] != b.payload[:S.NONCE_BYTES]


def test_a_truncated_real_payload_is_refused_before_decrypting(real):
    sealed = S.seal("b1", "sos", "x", S.generate_key(), real, sender_key=b"alpha")
    stub = S.Sealed(id=sealed.id, kind=sealed.kind, content_type=sealed.content_type,
                    sender=sealed.sender, ttl=sealed.ttl, size=sealed.size,
                    payload=sealed.payload[:8], created_at=sealed.created_at)
    with pytest.raises(S.SealError):
        S.unseal(stub, S.generate_key(), real)


def test_the_replay_guard_works_on_real_ciphertext(real):
    sealed = S.seal("b1", "sos", "six trapped", S.generate_key(), real, sender_key=b"alpha")
    guard = S.ReplayGuard()
    assert guard.accept(sealed, now=1000.0) is True
    assert guard.accept(sealed, now=1001.0) is False


# ---- keys between people ------------------------------------------------------------------------

def test_two_parties_derive_the_same_key_and_a_third_does_not():
    alice_priv, alice_pub = S.generate_keypair()
    bob_priv, bob_pub = S.generate_keypair()
    eve_priv, eve_pub = S.generate_keypair()

    ab = S.shared_key(alice_priv, bob_pub)
    ba = S.shared_key(bob_priv, alice_pub)
    assert ab == ba, "X25519 must agree in both directions"
    assert len(ab) == S.KEY_BYTES

    assert S.shared_key(eve_priv, alice_pub) != ab
    assert S.shared_key(alice_priv, eve_pub) != ab


def test_the_derived_key_is_domain_separated():
    """The same exchange must not yield the same key for two different purposes."""
    a_priv, a_pub = S.generate_keypair()
    b_priv, b_pub = S.generate_keypair()
    one = S.shared_key(a_priv, b_pub, info=b"pahiro-bundle-v1")
    two = S.shared_key(a_priv, b_pub, info=b"pahiro-something-else")
    assert one != two


def test_a_bundle_sealed_to_a_recipient_can_only_be_opened_by_them(real):
    """The property that matters when a stranger's phone is the one carrying it."""
    district_priv, district_pub = S.generate_keypair()
    phone_priv, phone_pub = S.generate_keypair()
    stranger_priv, stranger_pub = S.generate_keypair()

    key = S.shared_key(phone_priv, district_pub)
    sealed = S.seal("b1", "sos", "six trapped under the bus", key, real, sender_key=phone_pub)

    # the district can open it with its own private key and the phone's public key
    assert S.unseal_text(sealed, S.shared_key(district_priv, phone_pub), real) == \
        "six trapped under the bus"

    # a relay that has both PUBLIC keys still cannot
    with pytest.raises(S.SealError):
        S.unseal(sealed, S.shared_key(stranger_priv, phone_pub), real)


def test_the_placeholder_is_still_refused_alongside_a_real_cipher(real):
    """Shipping the real thing must not quietly enable the fake one."""
    with pytest.raises(S.SealError):
        S.InsecureTestCipher()
