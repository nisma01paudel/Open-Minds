#!/usr/bin/env python3
"""Serve the built app over HTTPS on the LAN, so the phone view actually works.

WHY THIS EXISTS. Camera access (getUserMedia), device orientation and service workers
all require a SECURE CONTEXT. Browsers grant that to https:// and to http://localhost -
and to nothing else. So opening http://192.168.1.x:8100 on a phone serves the page fine
and the camera silently refuses to start. On Demo Day that looks like a broken app.

This serves the static export over HTTPS with a self-signed certificate that includes
the machine's LAN address as a Subject Alternative Name, so a phone on the same wifi can
open the camera view. The browser will warn about the certificate once; accept it and the
camera works.

    python3 scripts/serve_https.py --dir web/out --port 8443
"""
from __future__ import annotations

import argparse
import http.server
import socket
import ssl
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT_DIR = ROOT / "cache" / "tls"


def lan_ips() -> list[str]:
    ips = []
    try:
        out = subprocess.run(["ip", "-4", "addr"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                ip = line.split()[1].split("/")[0]
                if not ip.startswith("127."):
                    ips.append(ip)
    except Exception:
        pass
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass
    return ips


def ensure_cert(ips: list[str]) -> tuple[Path, Path]:
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    key, crt = CERT_DIR / "key.pem", CERT_DIR / "cert.pem"
    if crt.exists() and key.exists():
        return crt, key
    san = ",".join(f"IP:{ip}" for ip in ips + ["127.0.0.1"])
    conf = CERT_DIR / "openssl.cnf"
    conf.write_text(
        "[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=v3\n"
        "[dn]\nCN=pahiro.local\n"
        f"[v3]\nsubjectAltName=DNS:localhost,{san}\n"
        "basicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\n"
    )
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(key), "-out", str(crt), "-days", "825",
         "-config", str(conf), "-extensions", "v3"],
        check=True, capture_output=True,
    )
    return crt, key


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # the service worker and camera need these to be treated as same-origin
        self.send_header("Cache-Control", "no-store" if self.path.endswith("sw.js") else "public, max-age=60")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="web/out")
    ap.add_argument("--port", type=int, default=8443)
    a = ap.parse_args()

    directory = (ROOT / a.dir).resolve()
    if not directory.exists():
        print(f"no build at {directory}. Run: cd web && npm run build", file=sys.stderr)
        return 1

    ips = lan_ips()
    crt, key = ensure_cert(ips)

    handler = lambda *args, **kw: Handler(*args, directory=str(directory), **kw)  # noqa: E731
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", a.port), handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(crt), keyfile=str(key))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    print("Pahiro Watch over HTTPS — the phone view needs this to reach the camera.\n")
    print(f"  this machine : https://localhost:{a.port}/")
    for ip in ips:
        print(f"  on your phone: https://{ip}:{a.port}/ar/")
    print("\n  The certificate is self-signed. The browser will warn once — accept it")
    print("  (Advanced / Proceed). After that the camera, compass and offline cache work.")
    print("\n  Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
