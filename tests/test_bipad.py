"""Geometry and mapping tests for the BIPAD client (no network)."""
from pahiro.ingest.bipad import BipadClient, Ward, point_in_geometry, point_in_ring

SQUARE = [[85.0, 27.0], [86.0, 27.0], [86.0, 28.0], [85.0, 28.0], [85.0, 27.0]]


def test_point_in_ring_basic():
    assert point_in_ring(85.5, 27.5, SQUARE)
    assert not point_in_ring(84.5, 27.5, SQUARE)
    assert not point_in_ring(85.5, 29.0, SQUARE)


def test_point_in_polygon_with_hole():
    outer = SQUARE
    hole = [[85.4, 27.4], [85.6, 27.4], [85.6, 27.6], [85.4, 27.6], [85.4, 27.4]]
    poly = {"type": "Polygon", "coordinates": [outer, hole]}
    assert point_in_geometry(85.2, 27.5, poly), "inside outer, outside hole"
    assert not point_in_geometry(85.5, 27.5, poly), "inside the hole"


def test_multipolygon():
    geom = {"type": "MultiPolygon", "coordinates": [[SQUARE],
            [[[87.0, 27.0], [88.0, 27.0], [88.0, 28.0], [87.0, 28.0], [87.0, 27.0]]]]}
    assert point_in_geometry(87.5, 27.5, geom)
    assert not point_in_geometry(89.0, 27.5, geom)


def test_ward_describe():
    w = Ward(ward="11", municipality="Thakre", district="DHADING",
             province="3", centre="Mahadevbesi", properties={})
    assert w.describe() == "Ward 11, Thakre, DHADING"


def _dispatch(**kw):
    class D:
        as_of = __import__("datetime").date(2025, 7, 20)
        priority = "high"
        recommendation = "relocate above the deformation zone"
        inspect_first = ["road segment", "upper slope drainage"]
        advisory_ne = "सूचना"
        authority = {"institution": "Division Road Office"}
    for k, v in kw.items():
        setattr(D, k, v)
    return D()


def test_payload_never_invents_chainage_or_contact():
    payload = BipadClient().to_bipad_highway_payload(_dispatch())
    assert payload["payload"]["closureReason"] == "Landslide"
    assert "chainage" in payload["requires_from_office"]
    assert "contactPerson" in payload["requires_from_office"], \
        "we must never invent a contact person"
    assert payload["authority"] == "Division Road Office"


def test_payload_uses_ward_when_available():
    ward = Ward(ward="11", municipality="Thakre", district="DHADING",
                province="3", centre=None, properties={})
    payload = BipadClient().to_bipad_highway_payload(_dispatch(), ward)
    assert payload["payload"]["district"] == "DHADING"
    assert payload["payload"]["ward"] == "11"
