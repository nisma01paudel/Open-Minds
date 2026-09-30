"""Mutate a load-bearing constant, run the suite, and see whether anything notices.

A test suite that passes is not evidence of anything until you know it can fail. This is the
cheapest possible check on that: break one thing at a time, on purpose, and count how many
mutations survive.

Every mutation is reverted with `git checkout` before the next one, so the tree is left exactly
as it was found.
"""
import subprocess, sys, pathlib

ROOT = pathlib.Path("/home/logic/win/open-minds")
PY = str(ROOT / ".venv/bin/python")

MUTATIONS = [
    # NOTE: the first version of this list pointed at dtn.py for DEFAULT_TTL. It lives in
    # protocol.py, so that mutation silently skipped and the output read as though it had been
    # tested. A mutation that does not apply is worse than no mutation: it looks like coverage.
    ("src/pahiro/mesh/protocol.py", "DEFAULT_TTL = 7", "DEFAULT_TTL = 1",
     "how many hops a message may take"),
    ("src/pahiro/mesh/beacon.py", "ENCODED_BYTES = 20", "ENCODED_BYTES = 19",
     "the beacon's advertised size"),
    ("src/pahiro/triage.py", "W_PEOPLE = 35", "W_PEOPLE = 5",
     "how much a headcount is worth in triage"),
    ("src/pahiro/endurance.py", "CONSERVE_AT_PCT = 25", "CONSERVE_AT_PCT = 90",
     "when the phone stops scanning continuously"),
    ("src/pahiro/shelter.py", "DEFAULT_RISE_M = 5.0", "DEFAULT_RISE_M = 0.5",
     "how high above the flood the escape target must be"),
    ("src/pahiro/mesh/seal.py", "NONCE_BYTES = 12", "NONCE_BYTES = 8",
     "the AEAD nonce length"),
]

survived, killed, not_applied = [], [], []
for path, old, new, what in MUTATIONS:
    f = ROOT / path
    src = f.read_text(encoding="utf-8")
    if old not in src:
        # Loud, and counted as a problem: a mutation that never applied is not a killed mutant.
        print(f"  DID NOT APPLY  {path}: {old!r} not found - this constant did not get tested")
        not_applied.append(f"{what} ({path})")
        continue
    f.write_text(src.replace(old, new, 1), encoding="utf-8")
    try:
        r = subprocess.run([PY, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
                           cwd=ROOT, capture_output=True, text=True, timeout=900)
        failures = [l for l in (r.stdout or "").splitlines() if l.startswith("FAILED")]
        n_failed = len(failures)
        if r.returncode != 0:
            killed.append((what, n_failed or 1, failures[0][:80] if failures else "(error)"))
            print(f"  KILLED  {what}")
        else:
            survived.append(what)
            print(f"  SURVIVED  {what}   <-- nothing detected this")
    finally:
        subprocess.run(["git", "checkout", "--", path], cwd=ROOT, check=True)

if not_applied:
    print("\nDID NOT APPLY (these were NOT tested, whatever the summary says):")
    for s in not_applied:
        print(f"  - {s}")
print(f"\n{len(killed)} killed, {len(survived)} survived, {len(not_applied)} not applied, "
      f"of {len(MUTATIONS)} mutations")
if survived:
    print("SURVIVED (the suite does not cover these):")
    for s in survived:
        print(f"  - {s}")
