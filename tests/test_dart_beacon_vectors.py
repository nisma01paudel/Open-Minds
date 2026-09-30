"""Pin the Dart beacon vectors to the Python implementation.

The Dart suite asserts 8 encoded frames, 8 relays and 6 truncations against hardcoded vectors.
Hardcoded vectors rot: someone changes the Python layout, updates the Python tests, and the Dart
file keeps asserting yesterday's bytes while `flutter test` still passes. Neither suite would
notice, and the three implementations would quietly disagree about a radio format.

So the vectors themselves are re-derived here from the Python source of truth. Change the format
and one of the two suites fails, whichever side you changed.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pahiro.mesh import beacon as B  # noqa: E402

DART_TEST = ROOT / "mobile" / "test" / "beacon_test.dart"

# The cases the Dart file's encodeFor() builds, expressed the same way for Python. Kept in step
# with the switch in the Dart file, which the fixture-name check below enforces.
CASES = {
    "typical sos": ("handset-7f3a", "msg-abc123",
                    dict(kind="sos", lat=27.71542, lon=85.31234, people=3,
                         severity="critical", low_battery=True)),
    "no position": ("d1", "m1", dict(lat=None, lon=None, people=3)),
    "minimal": ("x", "y", dict(ttl=0, hops=0, severity="info", people=0)),
    "maxed bits": ("x", "y", dict(ttl=7, hops=7, severity="critical", people=15)),
    "negative longitude": ("gps-1", "m-2",
                           dict(lat=26.12345, lon=-80.54321, severity="concern")),
    "southern hemisphere": ("gps-2", "m-3",
                            dict(lat=-33.98765, lon=151.01234, people=1)),
    "status kind": ("relay-9", "m-9", dict(kind="status", lat=27.7, lon=85.3)),
    "utf8 id": ("हाते-फोन", "सन्देश-१", dict(lat=28.2096, lon=83.9856, people=2)),
}

TRUNCATIONS = ("handset-7f3a", "d1", "x", "gps-1", "हाते-फोन", "shesh-9f2c")


def _dart() -> str:
    if not DART_TEST.exists():
        pytest.skip("the Flutter app is not present in this checkout")
    return DART_TEST.read_text(encoding="utf-8")


def _when() -> datetime:
    m = re.search(r"fromMillisecondsSinceEpoch\((\d+) \* 1000", _dart())
    assert m, "could not find the fixed timestamp in the Dart test"
    return datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc)


def _rows(block_name: str, source: str) -> dict[str, str | None]:
    """Pull rows out of one const list in the Dart file.

    The element type differs per list - `<String>`, `<String?>` for the relay vector where a
    frame out of hops correctly relays to nothing, and `<Object>` for the truncations, which are
    integers - so the declaration is matched loosely on purpose.
    """
    m = re.search(rf"const List<List<[^>]+>> {block_name} = \[(.*?)\n\];", source, re.S)
    assert m, f"could not find {block_name} in the Dart test"
    rows: dict[str, str | None] = {}
    for line in m.group(1).strip().splitlines():
        mm = re.match(r"\s*\[(.+?),\s*(.+?)\],?\s*$", line)
        if not mm:
            continue
        name = mm.group(1).strip().strip("'")
        value = mm.group(2).strip()
        rows[name] = None if value == "null" else value.strip("'")
    return rows


def test_the_dart_fixture_names_match_this_file():
    """If someone adds a case to one side only, the pinning below would silently miss it."""
    dart_names = set(re.findall(r"case '([^']+)':", _dart()))
    assert dart_names == set(CASES), (
        f"the Dart fixtures and this file disagree: "
        f"only in Dart {dart_names - set(CASES)}, only here {set(CASES) - dart_names}")


def test_the_dart_encoded_vectors_are_what_python_produces_today():
    when = _when()
    rows = _rows("encoded", _dart())
    assert rows, "no encoded vectors found"
    for name, dev, msg, opts in [(n, *CASES[n]) for n in CASES]:
        expected = B.encode(dev, msg, when=when, **opts).hex()
        assert rows.get(name) == expected, (
            f"{name}: the Dart test asserts {rows.get(name)} but Python now produces "
            f"{expected} - the two codecs have drifted")


def test_the_dart_relay_vectors_are_what_python_produces_today():
    when = _when()
    rows = _rows("relayed", _dart())
    for name, dev, msg, opts in [(n, *CASES[n]) for n in CASES]:
        frame = B.encode(dev, msg, when=when, **opts)
        r = B.relay(frame)
        expected = r.hex() if r else None
        assert rows.get(name) == expected, (
            f"{name}: Dart asserts relay {rows.get(name)}, Python produces {expected}")


def test_the_dart_truncation_vectors_are_what_python_produces_today():
    rows = _rows("truncations", _dart())
    for ident in TRUNCATIONS:
        expected = str(B.truncate16(ident))
        assert rows.get(ident) == expected, (
            f"{ident}: Dart asserts FNV-1a {rows.get(ident)}, Python produces {expected} - "
            f"the two would disagree about which messages are duplicates")


def test_the_dart_file_pins_the_same_wire_constants():
    """The sizes are the contract; a third implementation must agree on them too.

    Read from the implementation, not the test file - the test file asserting 20 proves nothing
    about what the codec actually uses.
    """
    impl = (ROOT / "mobile" / "lib" / "beacon.dart")
    if not impl.exists():
        pytest.skip("the Flutter app is not present in this checkout")
    src = impl.read_text(encoding="utf-8")
    assert re.search(r"const int encodedBytes = 20;", src)
    assert re.search(r"const int maxAdBytes = 24;", src)
    assert "canAdvertise = true" in src, (
        "a Flutter app can put bytes on the air and a browser cannot - the difference is the "
        "whole argument for the native build")
