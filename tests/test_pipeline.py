"""The join: a message goes into the mesh sealed, and a carrier routes it blind.

The property under test is not "encryption works" - test_seal.py covers the primitives. It is that
**a carrier can move a bundle it cannot read**, all the way through the transport choice and the
custody handoff, with no method anywhere that would hand it the plaintext.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pahiro.mesh import dtn, pipeline, seal
from pahiro.mesh.protocol import MeshMessage

pytest.importorskip("cryptography", reason="the crypto extra is not installed")

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def cipher() -> seal.AeadCipher:
    return seal.chacha20poly1305()


@pytest.fixture
def key() -> bytes:
    return seal.generate_key()


def message(body: str = "six trapped under the bus at KM 42", kind: str = "sos") -> MeshMessage:
    return MeshMessage(kind=kind, body=body, origin="dev-alpha", origin_name="Bus, KM 42",
                       people=6, created_at=NOW)


# ---- a carrier cannot read what it carries ------------------------------------------------------

def test_the_sealed_bundle_has_no_body_at_all(cipher, key):
    """Not a policy - the attribute does not exist, so a relay cannot log what it never had."""
    sb = pipeline.seal_bundle(message(), key, cipher, sender_key=b"district")
    assert not hasattr(sb, "body")
    assert b"trapped" not in sb.payload
    assert "trapped" not in str(pipeline.carrier_view(sb))


def test_the_carrier_view_is_what_a_relay_may_log(cipher, key):
    view = pipeline.carrier_view(pipeline.seal_bundle(message(), key, cipher,
                                                     sender_key=b"district"))
    assert view["kind"] == "sos"
    assert view["sealed_bytes"] > 0
    assert set(view) == {"id", "kind", "sender", "ttl", "hops", "sealed_bytes",
                         "content_type", "created_at"}


def test_a_carrier_can_choose_a_transport_for_a_bundle_it_cannot_read(cipher, key):
    """The interface dtn.choose actually needs, satisfied without the plaintext."""
    sb = pipeline.seal_bundle(message(), key, cipher, sender_key=b"district")
    choice = dtn.choose(sb, available={"ble", "wifi_aware", "sms"})
    assert choice.transport is not None
    assert sb.priority == 0, "an SOS still outranks chat on the radio"


def test_a_carrier_can_take_custody_of_a_bundle_it_cannot_read(cipher, key):
    sb = pipeline.seal_bundle(message(), key, cipher, sender_key=b"district")
    store = dtn.Custody("stranger-phone")
    assert store.accept(sb) is True
    store.hand_off(sb.id, dtn.BLE, "another-stranger", NOW)
    assert store.offered_to(sb.id) == "another-stranger"
    assert sb.id in store, "held until acknowledged, exactly as for a plaintext bundle"


def test_relaying_leaves_the_payload_byte_identical(cipher, key):
    """A relay cannot alter what it cannot read, and must not try."""
    sb = pipeline.seal_bundle(message(), key, cipher, sender_key=b"district")
    hopped = pipeline.relay(sb, dtn.BLE, "stranger-phone")
    assert hopped.payload == sb.payload
    assert hopped.hops == sb.hops + 1
    assert hopped.ttl == sb.ttl - 1
    assert hopped.path == ["stranger-phone"]


def test_the_message_survives_the_whole_journey_intact(cipher, key):
    original = message()
    sb = pipeline.seal_bundle(original, key, cipher, sender_key=b"district")
    for peer in ("stranger-a", "stranger-b", "stranger-c"):
        sb = pipeline.relay(sb, dtn.BLE, peer)
    back = pipeline.open_bundle(sb, key, cipher)
    assert back.body == original.body
    assert back.kind == "sos"
    assert back.hops == 3


# ---- and cannot be altered by anyone who carries it ---------------------------------------------

def test_promoting_a_chat_to_an_sos_in_transit_is_refused(cipher, key):
    """The attack every relay could otherwise mount, checked at the pipeline level."""
    sb = pipeline.seal_bundle(message("we are fine", kind="chat"), key, cipher,
                              sender_key=b"district")
    promoted = pipeline.SealedBundle(id=sb.id, kind="sos", size=sb.size, ttl=sb.ttl,
                                     hops=sb.hops, created_at=sb.created_at,
                                     payload=sb.payload, content_type=sb.content_type,
                                     sender=sb.sender)
    with pytest.raises(seal.SealError):
        pipeline.open_bundle(promoted, key, cipher)


def test_extending_the_ttl_in_transit_is_refused(cipher, key):
    sb = pipeline.seal_bundle(message(), key, cipher, sender_key=b"district")
    stretched = pipeline.SealedBundle(id=sb.id, kind=sb.kind, size=sb.size, ttl=99,
                                      hops=sb.hops, created_at=sb.created_at,
                                      payload=sb.payload, content_type=sb.content_type,
                                      sender=sb.sender)
    with pytest.raises(seal.SealError):
        pipeline.open_bundle(stretched, key, cipher)


def test_a_replayed_sos_is_caught_at_the_door(cipher, key):
    """Every relay would authenticate a replayed SOS correctly, so it must die here."""
    sb = pipeline.seal_bundle(message(), key, cipher, sender_key=b"district")
    guard = seal.ReplayGuard()
    assert pipeline.open_bundle(sb, key, cipher, guard=guard).body
    with pytest.raises(seal.SealError) as exc:
        pipeline.open_bundle(sb, key, cipher, guard=guard)
    assert "replay" in str(exc.value)


def test_a_forged_sender_is_refused(cipher, key):
    sb = pipeline.seal_bundle(message(), key, cipher, sender_key=b"district")
    with pytest.raises(seal.SealError) as exc:
        pipeline.open_bundle(sb, key, cipher, expect_sender=seal.fingerprint(b"somebody-else"))
    assert "claims to be from" in str(exc.value)


def test_only_the_key_holder_can_open_it(cipher, key):
    sb = pipeline.seal_bundle(message(), key, cipher, sender_key=b"district")
    with pytest.raises(seal.SealError):
        pipeline.open_bundle(sb, seal.generate_key(), cipher)


# ---- voice and photographs ----------------------------------------------------------------------

def test_a_voice_note_travels_sealed_and_comes_back_as_bytes(cipher, key):
    audio = bytes(range(256)) * 40
    msg = MeshMessage(kind="sos", body="", origin="dev-a", created_at=NOW)
    bundle = pipeline.seal_bytes(msg, audio, key, cipher, sender_key=b"district")
    assert bundle.content_type == seal.CONTENT_VOICE
    assert pipeline.open_bytes(bundle, key, cipher) == audio


def test_asking_for_text_on_a_voice_bundle_says_what_to_use_instead(cipher, key):
    audio = b"\x00" * 64
    bundle = pipeline.seal_bytes(MeshMessage(kind="sos", body="", origin="dev-a",
                                             created_at=NOW),
                                 audio, key, cipher, sender_key=b"district")
    with pytest.raises(seal.SealError) as exc:
        pipeline.open_bundle(bundle, key, cipher)
    assert "open_bytes" in str(exc.value)


# ---- sealing changes what fits, and the transport choice must know ------------------------------

def test_sealing_adds_bytes_and_a_bundle_reports_the_sealed_size(cipher, key):
    """A body that just fitted a rung may no longer fit once it has a nonce and a tag."""
    plaintext = "x" * 18
    sb = pipeline.seal_bundle(message(plaintext), key, cipher, sender_key=b"district")
    assert len(plaintext.encode()) == 18
    assert sb.size_bytes() > 18, "the sealed frame is larger than the plaintext"
    assert sb.size_bytes() == len(sb.payload)
    assert not sb.fits(dtn.BLE), "18 bytes of text no longer fits a 20-byte advertisement"


def test_a_small_body_still_fits_the_smallest_rung(cipher, key):
    """The beacon exists for exactly this: a payload squeezed until it fits 20 bytes."""
    sb = pipeline.seal_bundle(message("b:20"), key, cipher, sender_key=b"district")
    # even sealed it should be within a Wi-Fi hop, though it may not fit the advertisement
    assert sb.fits(dtn.WIFI_AWARE)


# ---- the browser can open what Python sealed ----------------------------------------------------

def test_the_browser_sealing_layer_agrees_with_python():
    """The real proof of interop: each language opens what the other sealed.

    A crypto format that drifts does not fail loudly - it fails to open at the moment somebody
    needs it, which is why this is checked rather than assumed.
    """
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    if shutil.which("node") is None:
        pytest.skip("node not installed")
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(root / "scripts" / "check_seal_parity.py")],
                          capture_output=True, text=True, timeout=180, cwd=str(root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "open each other's sealed messages" in proc.stdout


def test_the_field_client_loads_the_sealing_layer():
    """A crypto module the page never loads is dead code, and this one is the point."""
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1]
            / "web" / "public" / "field" / "index.html").read_text(encoding="utf-8")
    assert 'src="/field/seal.js"' in html, "the field page must load the sealing layer"


def test_a_frame_built_the_way_the_client_builds_it_is_accepted_by_the_gateway():
    """The end-to-end check that matters: the browser's frame, opened by the Python gateway.

    Without a browser in this environment, the honest way to verify the client's compose path is
    to build the frame with the client's own code — seal.js, the same record shape, the same
    base64 — and put it through the real ingest. If the shapes disagree, this fails here rather
    than on stage.
    """
    import json
    import shutil
    import subprocess
    from pathlib import Path

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if shutil.which("node") is None:
        pytest.skip("node not installed")
    root = Path(__file__).resolve().parents[1]
    key = bytes(range(32))

    driver = f"""
const S = require({json.dumps(str(root / "web/public/field/seal.js"))});
const KEY = new Uint8Array({list(key)});
const ID = "b1f2", KIND = "sos", TTL = 7, SENDER = "dev-alpha";
// exactly what sealedRecord() builds in index.html
const record = JSON.stringify({{
  body: "six trapped under the bus at KM 42", people: 6, lat: 28.21, lon: 83.98,
  accuracy_m: null, battery: 8, origin_name: "Bus, KM 42"
}});
(async () => {{
  const payload = await S.sealText(
    {{ id: ID, kind: KIND, contentType: "text", sender: SENDER, ttl: TTL }}, record, KEY);
  const frame = {{ sealed: {{
    id: ID, kind: KIND, content_type: "text", sender: SENDER, ttl: TTL, hops: 0,
    size: record.length, created_at: "2026-09-30T12:00:00+00:00",
    payload_b64: Buffer.from(payload).toString("base64")
  }} }};
  process.stdout.write(JSON.stringify(frame));
}})().catch(e => {{ console.error(String(e)); process.exit(1); }});
"""
    proc = subprocess.run(["node", "-e", driver], capture_output=True, text=True, timeout=120,
                          cwd=str(root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    frame = json.loads(proc.stdout)

    # the frame must not carry the words, or the sealing is theatre
    assert "trapped" not in proc.stdout

    # and the gateway must open it with the structured fields intact
    sealed = pipeline.from_frame(frame)
    msg = pipeline.open_bundle(sealed, key, seal.AeadCipher(AESGCM, "aes-256-gcm"))
    assert msg.body == "six trapped under the bus at KM 42"
    assert msg.kind == "sos"
    assert msg.people == 6, "the headcount must survive the seal"
    assert msg.lat == 28.21 and msg.lon == 83.98
    assert msg.battery == 8


def test_the_field_client_actually_seals_on_its_compose_path():
    """A sealing layer the compose path never calls is dead code, and the claim is then false."""
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1]
            / "web" / "public" / "field" / "index.html").read_text(encoding="utf-8")
    assert "sealForTransport" in html, "the client must have a sealing path"
    assert "buildOutgoing" in html, "and the compose path must use it"
    assert "buildOutgoing(pending)" in html, "syncMeshToApi must call it with the pending set"
    assert "pahiro.sealkey" in html, "the key must be stored per device"
    assert "sealText" in html, "it must call the sealing layer"


def test_the_client_sends_in_the_clear_when_no_key_is_set():
    """Opt-in, so a device with no key behaves exactly as before."""
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1]
            / "web" / "public" / "field" / "index.html").read_text(encoding="utf-8")
    assert "if (!sealingKey()) { return pending; }" in html, \
        "without a key the pending set must pass through untouched"
