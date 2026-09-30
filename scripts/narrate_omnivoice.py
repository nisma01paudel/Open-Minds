#!/usr/bin/env python3
"""Generate the demo narration with OmniVoice (k2-fsa), Nepali.

OmniVoice is a 600+ language zero-shot TTS with 171.5 h of Nepali training data - a real
step up from Piper's single Nepali voice. It needs a GPU, and this machine's is stuck
after suspend, so the work is sent to the authors' public Space (A10G) through its Gradio
API instead.

    python scripts/narrate_omnivoice.py --in reports/video/voice/narration.txt \
        --out reports/video/voice-omni

Lines are one per file, "key|text". The same voice is requested for every line so the
result sounds like one speaker.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACE = "k2-fsa/OmniVoice"

# one consistent speaker across all lines
DESIGN = dict(
    ns=32, gs=2.0, dn=True, sp=1.0, du=0,
    pp=True, po=True,
    param_9="Male / 男",
    param_10="Young Adult / 青年",
    param_11="Moderate Pitch / 中音调",
    param_12="Auto", param_13="Auto", param_14="Auto",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="reports/video/voice/narration.txt")
    ap.add_argument("--out", default="reports/video/voice-omni")
    ap.add_argument("--lang", default="Nepali")
    ap.add_argument("--pause", type=float, default=3.0, help="seconds between requests")
    a = ap.parse_args()

    try:
        from gradio_client import Client
    except ImportError:
        print("pip install gradio_client", file=sys.stderr)
        return 1

    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for raw in (ROOT / a.src).read_text(encoding="utf-8").splitlines():
        if "|" in raw:
            k, t = raw.split("|", 1)
            lines.append((k.strip(), t.strip()))

    client = Client(SPACE, verbose=False)
    print(f"connected to {SPACE}; {len(lines)} lines, lang={a.lang}")

    ok = 0
    for i, (key, text) in enumerate(lines):
        dst = out / f"{key}.wav"
        if dst.exists() and dst.stat().st_size > 10000:
            print(f"  {key}: already have it")
            ok += 1
            continue
        if i:
            time.sleep(a.pause)
        try:
            path, status = client.predict(text=text, lang=a.lang, **DESIGN,
                                          api_name="/_design_fn")
            if not path or not Path(path).exists():
                print(f"  {key}: no audio ({status})", file=sys.stderr)
                continue
            shutil.copy(path, dst)
            dur = dst.stat().st_size / (24000 * 2)
            print(f"  {key}: {dur:.1f}s  ({len(text)} chars)")
            ok += 1
        except Exception as exc:
            print(f"  {key}: FAILED {type(exc).__name__}: {str(exc)[:120]}", file=sys.stderr)

    print(f"\n{ok}/{len(lines)} lines generated into {out}")
    return 0 if ok == len(lines) else 1


if __name__ == "__main__":
    raise SystemExit(main())
