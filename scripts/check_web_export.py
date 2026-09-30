#!/usr/bin/env python3
"""Check the BUILT web app for every feature, using strings the build actually contains.

Written after a round in which grepping the export for guessed strings produced four false "missing
feature" reports - the panorama directory is `panoramas` not `panorama`, and three of the strings I
searched for are the PHONE's wording, not the web's. A false report of a missing feature is the most
damaging kind of false finding, because it sends somebody to fix something that works.

So this checks two things and keeps them separate:

  1. the data the app needs is present in out/data/, by exact path
  2. the strings a USER SEES are present, taken from the SOURCE rather than from memory

Run after `npm run build` in web/.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = WEB / "out"

# Exact paths, because a directory name guessed from the singular is how the first false report began.
# Derived from the source directory, not typed from memory. The first version of this file listed
# "beni.png" because a panorama of that name seemed plausible - it does not exist, and the check
# reported a missing data file that had never been promised.
DATA = sorted(
    str(p.relative_to(ROOT / "web" / "public"))
    for p in (ROOT / "web" / "public" / "data").rglob("*")
    if p.is_file()
)



def user_strings() -> dict[str, str]:
    """Feature labels lifted from the source, so this file cannot guess them."""
    found: dict[str, str] = {}
    page = (WEB / "app/page.tsx").read_text(encoding="utf-8")
    # Layer titles. The first version searched the bundle for the bare word "Places" after finding
    # `>Places<` in the JSX - but minification splits JSX text into separate strings, so a label
    # present on screen reads as missing in the chunk. An attribute survives, so titles are the
    # checkable form and a rendered label is checked by looking at the page, not by grepping.
    for m in re.finditer(r'title="([^"]{6,60})"', page):
        found[f'title="{m.group(1)[:24]}"'] = m.group(1)

    # whatever the presenter says, which is the beat list a judge hears
    pres = (WEB / "components/Presenter.tsx").read_text(encoding="utf-8")
    cues = re.findall(r'cue:\s*"([^"]{25,})"', pres)
    if cues:
        found["presenter cue"] = cues[0][:40]
    # the API routes the source actually calls
    for src in list((WEB / "app").rglob("*.tsx")) + list((WEB / "components").rglob("*.tsx")):
        for route in re.findall(r'"(/api/v1/[a-z/]+)', src.read_text(encoding="utf-8")):
            found[f"route {route}"] = route
    return found


def main() -> int:
    if not OUT.exists():
        print("web/out does not exist - run `npm run build` in web/ first")
        return 1

    bad = 0
    print("data the app loads:")
    for rel in DATA:
        ok = (OUT / rel).exists()
        bad += not ok
        print(f"  {'OK  ' if ok else 'MISS'}  {rel}")

    print("\nstrings taken from the source:")
    blob = ""
    for f in OUT.rglob("*.js"):
        try:
            blob += f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
    for name, text in user_strings().items():
        ok = text in blob
        bad += not ok
        print(f"  {'OK  ' if ok else 'MISS'}  {name}: {text[:50]!r}")

    print(f"\n{'all present' if not bad else f'{bad} missing'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
