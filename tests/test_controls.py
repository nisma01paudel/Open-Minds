"""Controls must be far from known failures and reproducible."""
import pytest

from pahiro.eval.controls import generate_controls, haversine_km, write_csv

EVENTS = [
    {"incident_id": "1", "date": "2024-09-28", "lat": "27.7600", "lon": "85.3000"},
    {"incident_id": "2", "date": "2024-09-28", "lat": "27.8000", "lon": "85.4000"},
]


def test_haversine_is_sane():
    assert haversine_km(27.7, 85.3, 27.7, 85.3) == pytest.approx(0.0)
    # one degree of latitude is about 111 km
    assert haversine_km(27.0, 85.0, 28.0, 85.0) == pytest.approx(111.2, abs=0.5)


def test_controls_are_generated_per_event():
    controls = generate_controls(EVENTS, per_event=3, min_km=2.0, max_km=5.0)
    assert len(controls) == 6
    assert {c.matched_event_id for c in controls} == {"1", "2"}


def test_controls_respect_the_exclusion_radius():
    controls = generate_controls(EVENTS, per_event=5, min_km=1.0, max_km=8.0,
                                 exclusion_km=2.0)
    assert controls, "the generator must not give up"
    assert all(c.nearest_known_event_km >= 2.0 for c in controls)
    assert all(c.distance_from_event_km >= 1.0 for c in controls)


def test_generation_is_deterministic_for_a_seed():
    a = generate_controls(EVENTS, per_event=3, seed=7)
    b = generate_controls(EVENTS, per_event=3, seed=7)
    c = generate_controls(EVENTS, per_event=3, seed=8)
    assert [(x.lat, x.lon) for x in a] == [(x.lat, x.lon) for x in b]
    assert [(x.lat, x.lon) for x in a] != [(x.lat, x.lon) for x in c]


def test_exclusion_uses_the_whole_inventory_not_just_the_matched_event():
    """A control near ANY recorded failure is not a control."""
    far_third = EVENTS + [{"incident_id": "3", "date": "2019-07-12",
                           "lat": "27.7650", "lon": "85.3050"}]
    controls = generate_controls(EVENTS, per_event=6, min_km=1.0, max_km=10.0,
                                 exclusion_km=3.0, all_events=far_third)
    assert all(c.nearest_known_event_km >= 3.0 for c in controls)


def test_every_control_carries_the_limitation(tmp_path):
    controls = generate_controls(EVENTS, per_event=2)
    assert all("absence of a record" in c.note for c in controls)
    path = write_csv(controls, tmp_path / "controls.csv")
    text = path.read_text()
    assert "absence of a record is not evidence of stability" in text
    assert "matched_event_id" in text
