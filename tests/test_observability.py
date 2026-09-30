"""Observability must count evidence, never claim skill."""
from datetime import date, timedelta

from pahiro.eval.observability import SiteObservability, load_sites, summarise


def mk(**kw):
    base = dict(site_id="1", event_date="2024-09-28", lat=27.7, lon=85.3, title="t",
                window_days=30)
    base.update(kw)
    return SiteObservability(**base)


def test_had_usable_optical_requires_a_count():
    assert not mk(optical_scenes=5, optical_usable=0).had_usable_optical
    assert mk(optical_scenes=5, optical_usable=1).had_usable_optical


def test_summary_computes_shares():
    rows = [mk(optical_usable=2, optical_scenes=4, radar_passes=3, days_since_last_usable_optical=5),
            mk(optical_usable=0, optical_scenes=3, radar_passes=2),
            mk(optical_usable=0, optical_scenes=0, radar_passes=0)]
    rep = summarise(rows, 30)
    assert rep["sites"] == 3
    assert rep["sites_with_usable_optical"] == 1
    assert rep["pct_with_usable_optical"] == 33.3
    assert rep["sites_with_radar"] == 2
    assert rep["sites_with_no_optical_at_all"] == 1
    assert rep["median_days_since_last_usable"] == 5


def test_summary_handles_zero_sites():
    rep = summarise([], 30)
    assert rep["sites"] == 0 and rep["pct_with_usable_optical"] == 0.0


def test_load_sites_filters_by_day_cluster(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("incident_id,date,lat,lon,title,day_cluster\n"
                 "1,2024-09-28,27.7,85.3,a,9\n"
                 "2,2024-09-28,27.8,85.4,b,2\n"
                 "3,2024-07-06,27.9,85.5,c,12\n")
    rows = load_sites(p, min_day_cluster=5)
    assert {r["incident_id"] for r in rows} == {"1", "3"}
    assert rows[0]["date"] >= rows[-1]["date"], "newest first"


def test_per_month_stratification_spreads_the_sample(tmp_path):
    """Without stratification the sample would be almost entirely late September."""
    p = tmp_path / "e.csv"
    lines = ["incident_id,date,lat,lon,title,day_cluster"]
    for month in (6, 7, 8, 9, 10):
        for i in range(6):
            lines.append(f"{month}{i},2024-{month:02d}-1{i},27.7,85.3,t,9")
    p.write_text("\n".join(lines) + "\n")
    rows = load_sites(p, per_month=2)
    months = [r["date"][:7] for r in rows]
    assert len(months) == 10
    assert len(set(months)) == 5, "every month must be represented"
    assert all(months.count(m) == 2 for m in set(months))


def test_months_filter_restricts_to_monsoon(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("incident_id,date,lat,lon,title,day_cluster\n"
                 "1,2024-07-15,27.7,85.3,a,9\n"
                 "2,2024-09-28,27.7,85.3,b,9\n")
    rows = load_sites(p, months=(7, 8))
    assert [r["incident_id"] for r in rows] == ["1"]
