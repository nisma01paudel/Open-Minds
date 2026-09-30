#!/usr/bin/env python3
"""Submission-readiness check.

The eligibility gate asks for a repo a stranger can run and understand. The most
common way to fail that without noticing is a document that points at a file which
does not exist - usually because the file was renamed mid-build. This walks every
markdown file, extracts path-like references, and reports the ones that are missing.

    python scripts/verify_repo.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md", "LICENSE", "pyproject.toml",
    "docs/AI-USAGE.md", "docs/MODELS.md", "docs/DATA.md", "docs/AGENT.md",
    "docs/PRIOR-ART.md", "docs/DIFERENTIATION.md", "docs/AUTHORITY-MAP.md",
    "docs/COMPETITION.md", "docs/DEMO-SCRIPT.md", "docs/LIMITATIONS.md",
    "docs/SPEECH.md", "docs/SEALING.md", "docs/OFFLINE-RANGE.md", "docs/MESH.md",
    "ontology/nepal-slope-routing.json",
    "benchmark/events.csv", "benchmark/controls.csv", "benchmark/routing-scenarios.jsonl",
    "reports/eval-v1.md", "reports/routing-ablation.md",
    "scripts/agent_demo.py", "scripts/verify_data_access.py",
    "scripts/check_beacon_parity.py", "scripts/check_seal_parity.py",
    "scripts/build_event_benchmark.py", "scripts/build_controls.py",
]

# Generated or vendored trees that are not our documentation. Flutter writes its own READMEs
# under ios/ and android/ describing paths relative to a different root, so scanning them
# produces broken references that are not ours. A verifier that cries wolf gets ignored.
VENDORED = ("mobile/ios", "mobile/android", "mobile/web", "mobile/macos", "mobile/linux",
            "mobile/windows", "mobile/build", "mobile/.dart_tool", ".venv", ".git",
            "node_modules", "web/.next", "web/out", "web/node_modules")

# A path-like reference: something with a slash and a file extension.
PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)`")
LINK_RE = re.compile(r"\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")


# References to things outside this repo, which the checker must not flag.
EXTERNAL = re.compile(r"^(data\.|elevation-tiles|sentinel-cogs|copernicus-dem|bipadportal|earth-search"
                      r"|gis\.earthdata|overpass|10\.\d|annotation/|ne/ne_NP|onnx/)")


def _looks_like_coordinates(ref: str) -> bool:
    return bool(re.fullmatch(r"[\d.,-]+", ref))


def repo_paths(text: str) -> set[str]:
    found = set(PATH_RE.findall(text))
    for target in LINK_RE.findall(text):
        if not target.startswith(SKIP_PREFIXES):
            found.add(target.split("#")[0])
    return {f for f in found if not EXTERNAL.match(f) and not _looks_like_coordinates(f)}


def main() -> int:
    problems: list[str] = []

    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            problems.append(f"MISSING required file: {rel}")

    # Line references like file.py::function or file.py:12 are fine; strip them.
    refs: dict[str, set[str]] = {}
    for md in sorted(ROOT.glob("**/*.md")):
        rel_md = md.relative_to(ROOT).as_posix()
        if any(rel_md.startswith(v) for v in VENDORED):
            continue
        if any(part in {".venv", "cache", "node_modules"} for part in md.parts):
            continue
        # docs/research/ holds verbatim third-party audit transcripts. Their internal
        # paths belong to other projects and are not ours to satisfy.
        if "research" in md.parts:
            continue
        for ref in repo_paths(md.read_text(encoding="utf-8", errors="replace")):
            clean = ref.split("::")[0]
            clean = re.sub(r":\d+(-\d+)?$", "", clean)
            if not clean or clean.startswith(SKIP_PREFIXES):
                continue
            if (ROOT / clean).exists():
                continue
            # It may be a directory, or the reference may be relative to docs/.
            if (ROOT / clean).is_dir() or (md.parent / clean).exists():
                continue
            refs.setdefault(clean, set()).add(str(md.relative_to(ROOT)))

    for ref, where in sorted(refs.items()):
        problems.append(f"BROKEN reference: {ref}  (referenced from {', '.join(sorted(where))})")

    try:
        tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                               capture_output=True, text=True)
    except Exception as exc:                                   # noqa: BLE001
        tests = None
        print(f"tests: could not run ({type(exc).__name__})")
    if tests is not None:
        output = (tests.stdout or "") + (tests.stderr or "")
        if "No module named pytest" in output:
            problems.append("pytest is not installed - run: pip install -e '.[dev]'")
            print("tests: pytest is not installed")
        else:
            tail = (tests.stdout or "").strip().splitlines()[-1:] or ["(no output)"]
            print(f"tests: {tail[0]}")
            if tests.returncode != 0:
                problems.append("the test suite does not pass")

            # A SKIP IS NOT A PASS, and this is the exact false-clean this project keeps
            # finding elsewhere: the cross-language parity tests skip when node is absent, so a
            # verifier that only reads "passed" would report OK on a machine where the two
            # implementations were never compared at all.
            if " skipped" in output:
                line = [x for x in output.splitlines() if " skipped" in x][-1]
                problems.append(
                    f"tests SKIPPED, and a skip is not a pass: {line.strip()}. "
                    f"The cross-language parity checks need node.")

    # The two checks that prove the Python and JavaScript implementations agree. Run directly as
    # well, so the result is a sentence a reader can see rather than a line in a test summary.
    for name, needs in (("check_beacon_parity.py", "node"),
                        ("check_seal_parity.py", "node")):
        script = ROOT / "scripts" / name
        if not script.exists():
            problems.append(f"MISSING cross-language check: scripts/{name}")
            continue
        if shutil.which(needs) is None:
            problems.append(
                f"cannot run scripts/{name}: {needs} is not installed, so the Python and "
                f"JavaScript implementations have NOT been compared")
            print(f"{name}: NOT RUN ({needs} missing)")
            continue
        try:
            got = subprocess.run([sys.executable, str(script)], cwd=ROOT,
                                 capture_output=True, text=True, timeout=300)
        except Exception as exc:                               # noqa: BLE001
            problems.append(f"scripts/{name} could not run ({type(exc).__name__})")
            continue
        last = ((got.stdout or "").strip().splitlines() or ["(no output)"])[-1]
        print(f"{name}: {last}")
        if got.returncode != 0:
            problems.append(f"scripts/{name} FAILED: {last}")

    # Counted from git rather than from the filesystem: build output and virtualenvs are noise,
    # and "tracked" should mean tracked. Falls back to a filesystem walk with the vendored trees
    # excluded when this is not a git checkout.
    try:
        listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                                timeout=60)
        n_files = len([x for x in (listed.stdout or "").splitlines() if x.strip()])
        print(f"tracked files (git): {n_files}")
    except Exception:                                          # noqa: BLE001
        n_files = sum(1 for f in ROOT.rglob("*") if f.is_file()
                      and not any(f.relative_to(ROOT).as_posix().startswith(v)
                                  for v in VENDORED))
        print(f"tracked files (filesystem, vendored excluded): {n_files}")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nOK: every required file present, no broken document references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
