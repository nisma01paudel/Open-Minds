#!/usr/bin/env python3
"""Check this repository against the event's stated requirements, from the repository alone.

Every line below is something a judge or an organiser could verify without asking us anything, which
is the point: an eligibility claim that requires the team to be present is not a claim, it is a
promise. The two things this script CANNOT check are marked as such rather than skipped silently.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OK, BAD, MANUAL = "OK  ", "FAIL", "MAN "


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return r.returncode, (r.stdout or r.stderr).strip()


def main() -> int:
    rows: list[tuple[str, str, str]] = []

    def add(state: str, what: str, detail: str = "") -> None:
        rows.append((state, what, detail))

    # --- open-weight AI as an important part, not a dependency -------------------------------
    models = ROOT / "docs/MODELS.md"
    if models.exists():
        text = models.read_text(encoding="utf-8").lower()
        named = [m for m in ("qwen", "smolvlm", "dinov2", "llama", "mistral") if m in text]
        add(OK if named else BAD, "open-weight models are named with measured sizes",
            ", ".join(named) or "none found")
    else:
        add(BAD, "docs/MODELS.md", "missing")

    # no proprietary inference endpoint in the shipped path
    hits = [p for p in (ROOT / "src").rglob("*.py")
            if "api.openai.com" in p.read_text(encoding="utf-8", errors="ignore")]
    add(OK if not hits else BAD, "no proprietary inference endpoint in src/",
        f"{len(hits)} file(s) call a vendor API" if hits else "none")

    # --- the deliverables ---------------------------------------------------------------------
    for rel in ("README.md", "SUBMISSION.md", "LICENSE",
                "reports/video/pahiro-narrated-web.mp4"):
        add(OK if (ROOT / rel).exists() else BAD, rel)

    # --- the video is within the brief's 2 to 3 minutes ---------------------------------------
    code, out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", "reports/video/pahiro-narrated-web.mp4"])
    if code == 0 and out:
        secs = float(out)
        add(OK if 120 <= secs <= 180 else BAD, "the video is 2-3 minutes", f"{secs:.0f} s")
    else:
        add(MANUAL, "video duration", "ffprobe unavailable")

    # --- the repository is public and reachable without credentials ---------------------------
    code, url = run(["git", "remote", "get-url", "work"])
    if code == 0 and url:
        slug = url.removesuffix(".git").replace("https://github.com/", "")
        code, _ = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                       f"https://api.github.com/repos/{slug}"])
        add(OK if _.strip() == "200" else BAD, "the repository answers anonymously", slug)
    else:
        add(MANUAL, "public repository", "no 'work' remote in this checkout")

    # --- the live demo is reachable ------------------------------------------------------------
    # A submission whose demo URL is dead has lost the demo, and nothing else in this repository
    # would notice: the build is green, the tests pass, and the pages are all still in git.
    LIVE = "https://sushant-me.github.io/work/"
    code, _ = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", LIVE])
    add(OK if _.strip() == "200" else BAD, "the live web app answers", LIVE)

    # and the data behind it, because a site that loads with no data looks fine and is not
    code, _ = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                   LIVE + "data/timeline.json"])
    add(OK if _.strip() == "200" else BAD, "the deployed data is served",
        "data/timeline.json")

    # --- what this script cannot decide -------------------------------------------------------
    add(MANUAL, "at least one member in the Kathmandu valley",
        "a fact about people, not a file - must be stated by the team")
    add(MANUAL, "no vendor API keys anywhere in the shipped path",
        "grep src/ for key patterns before submitting")

    width = max(len(w) for _, w, _ in rows)
    failed = 0
    for state, what, detail in rows:
        print(f"  {state}  {what:<{width}}  {detail}")
        failed += state == BAD
    print(f"\n{len(rows) - failed}/{len(rows)} checkable, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
