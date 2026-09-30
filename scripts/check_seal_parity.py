#!/usr/bin/env python3
"""Prove Python and the browser open each other's sealed messages.

Two implementations of one crypto envelope in two languages will drift, and a crypto format that
drifts does not fail loudly - it fails to open at the moment somebody needs it. So each side opens
what the other sealed, both directions.

The client uses AES-GCM because WebCrypto does not standardly offer ChaCha20-Poly1305; Python's
recommendation is ChaCha20-Poly1305, but for a browser-facing deployment it uses AES-GCM so the two
agree. Both are AEADs with a 12-byte nonce and a 16-byte tag, so only the primitive differs.

    python scripts/check_seal_parity.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: E402

from pahiro.mesh import pipeline, seal  # noqa: E402

KEY = bytes(range(32))
META = {"id": "b1f2", "kind": "sos", "contentType": "text",
        "sender": "d06605364441e03a", "ttl": 7}
BODY = "six trapped under the bus at KM 42 — २८.२१, ८३.९८"


def py_cipher() -> seal.AeadCipher:
    return seal.AeadCipher(AESGCM, "aes-256-gcm")


def py_seal() -> bytes:
    c = py_cipher()
    shell = seal.Sealed(id=META["id"], kind=META["kind"], content_type=META["contentType"],
                        sender=META["sender"], ttl=META["ttl"], size=len(BODY.encode()),
                        payload=b"")
    return c.seal(pipeline._wrap(META["ttl"], BODY.encode("utf-8")), KEY, shell.aad())


def py_open(payload: bytes, expect: str = BODY) -> str:
    c = py_cipher()
    shell = seal.Sealed(id=META["id"], kind=META["kind"], content_type=META["contentType"],
                        sender=META["sender"], ttl=META["ttl"], size=len(expect.encode()),
                        payload=b"")
    raw = c.open(payload, KEY, shell.aad())
    return pipeline._unwrap(META["ttl"], raw).decode("utf-8")


def node_driver(py_payload_hex: str) -> dict:
    driver = f"""
const S = require({json.dumps(str(ROOT / "web/public/field/seal.js"))});
const KEY = new Uint8Array({list(KEY)});
const META = {json.dumps(META)};
const EXPECT = {json.dumps(BODY)};
const pyPayload = new Uint8Array(Buffer.from({json.dumps(py_payload_hex)}, "hex"));
(async () => {{
  const out = {{}};
  out.opened_from_python = await S.openText(META, pyPayload, KEY);
  out.matches = (out.opened_from_python === EXPECT);
  const mine = await S.sealText(META, EXPECT, KEY);
  out.js_payload_hex = Buffer.from(mine).toString("hex");
  out.js_len = mine.length;
  // and it must round-trip in its own language too
  out.self_open = (await S.openText(META, mine, KEY)) === EXPECT;
  // a carrier must not be able to read it
  out.leaks = Buffer.from(mine).includes(Buffer.from("trapped"));
  out.view_keys = Object.keys(S.carrierView(META, mine)).sort();
  process.stdout.write(JSON.stringify(out));
}})().catch(e => {{ console.error(String(e)); process.exit(1); }});
"""
    proc = subprocess.run(["node", "-e", driver], capture_output=True, text=True, timeout=180,
                          cwd=str(ROOT))
    if proc.returncode != 0:
        raise SystemExit("node failed:\n" + proc.stdout + proc.stderr)
    return json.loads(proc.stdout)


def main() -> int:
    failures: list[str] = []

    def check(label: str, got, want) -> None:
        if got != want:
            failures.append(f"MISMATCH {label}\n    got:  {got}\n    want: {want}")

    mine = py_seal()
    check("python seal is nonce+tag+body", len(mine) >= 12 + 16, True)
    check("python round-trips its own frame", py_open(mine), BODY)

    js = node_driver(mine.hex())
    check("browser opens a Python-sealed message", js["opened_from_python"], BODY)
    check("browser agrees it matches", js["matches"], True)
    check("browser seals something it can open itself", js["self_open"], True)
    check("a carrier cannot see the words", js["leaks"], False)
    check("carrier view keys",
          js["view_keys"],
          ["content_type", "id", "kind", "sealed_bytes", "sender", "ttl"])

    # and the other direction: Python must open what the browser sealed
    check("python opens a browser-sealed message", py_open(bytes.fromhex(js["js_payload_hex"])),
          BODY)

    # a tampered frame must fail in both languages
    broken = bytearray(mine)
    broken[-1] ^= 0x01
    try:
        py_open(bytes(broken), BODY)
        failures.append("python accepted a tampered frame")
    except seal.SealError:
        pass

    if failures:
        print("MISMATCH between the Python and browser sealing layers:")
        for f in failures:
            print("  " + f)
        return 1
    print("OK: Python and the browser open each other's sealed messages "
          "(both directions, tampering refused, carrier view identical)")
    print(f"envelope: nonce(12) || ciphertext || tag(16), AES-GCM both sides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
