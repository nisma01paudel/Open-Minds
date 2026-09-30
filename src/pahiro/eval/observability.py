"""Could we actually have seen the slopes that failed?

The single-AOI monsoon finding (zero usable optical scenes in July and August) is
suggestive but it is one convenient slope. This asks the honest version of the
question at *real* documented landslide sites:

    for each documented failure, did at least one usable satellite observation
    exist in the 30 (and 60) days before it?

This is deliberately NOT a skill claim. We are not saying the system would have
predicted the failure. We are measuring **observability** - whether the evidence
needed to say anything at all existed - which is the precondition for every
downstream claim, and the honest bound on what any optical system could do.

    python -m pahiro.eval.observability --events benchmark/events.csv --limit-sites 12
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from pahiro.ingest import stac
from pahiro.ingest.screen import screen_scene

# A site bbox of about 1.1 km: big enough to catch a hillside, small enough that a
# single SCL window read is cheap.
SITE_PAD = 0.01
USABLE_CLEAR = 0.30


@dataclass
class SiteObservability:
    site_id: str
    event_date: str
    lat: float
    lon: float
    title: str
    window_days: int
    optical_scenes: int = 0
    optical_usable: int = 0
    best_clear: float = 0.0
    radar_passes: int = 0
    days_since_last_usable_optical: int | None = None

    @property
    def had_usable_optical(self) -> bool:
        return self.optical_usable > 0


def analyse_site(site: dict, window_days: int = 30, usable_clear: float = USABLE_CLEAR,
                 include_radar: bool = True) -> SiteObservability:
    lat, lon = float(site["lat"]), float(site["lon"])
    event_day = date.fromisoformat(site["date"])
    bbox = (lon - SITE_PAD, lat - SITE_PAD, lon + SITE_PAD, lat + SITE_PAD)
    start, end = (event_day - timedelta(days=window_days)).isoformat(), event_day.isoformat()

    out = SiteObservability(
        site_id=str(site.get("incident_id") or f"{lat},{lon}"),
        event_date=site["date"], lat=lat, lon=lon,
        title=site.get("title", ""), window_days=window_days,
    )

    # No tile-cloud filter: it describes a 110 km tile, not this hillside.
    scenes = stac.search(stac.OPTICAL, bbox, start, end, cloud_lt=None)
    out.optical_scenes = len(scenes)
    newest_usable: date | None = None
    for scene in scenes:
        try:
            rec = screen_scene(scene, bbox)
        except Exception:
            continue
        if rec["aoi_clear_fraction"] > out.best_clear:
            out.best_clear = rec["aoi_clear_fraction"]
        if rec["aoi_clear_fraction"] >= usable_clear:
            out.optical_usable += 1
            if newest_usable is None or scene.acquired > newest_usable:
                newest_usable = scene.acquired
    if newest_usable is not None:
        out.days_since_last_usable_optical = (event_day - newest_usable).days

    if include_radar:
        try:
            out.radar_passes = len(stac.search(stac.RADAR, bbox, start, end, cloud_lt=None))
        except Exception:
            out.radar_passes = 0
    return out


def summarise(rows: list[SiteObservability], window_days: int) -> dict:
    n = len(rows)
    with_optical = sum(1 for r in rows if r.had_usable_optical)
    with_radar = sum(1 for r in rows if r.radar_passes > 0)
    gaps = [r.days_since_last_usable_optical for r in rows
            if r.days_since_last_usable_optical is not None]
    return {
        "window_days": window_days,
        "sites": n,
        "sites_with_usable_optical": with_optical,
        "pct_with_usable_optical": round(100.0 * with_optical / n, 1) if n else 0.0,
        "sites_with_radar": with_radar,
        "pct_with_radar": round(100.0 * with_radar / n, 1) if n else 0.0,
        "sites_with_no_optical_at_all": sum(1 for r in rows if r.optical_scenes == 0),
        "median_usable_optical": sorted(r.optical_usable for r in rows)[n // 2] if n else 0,
        "median_days_since_last_usable": sorted(gaps)[len(gaps) // 2] if gaps else None,
        "rows": [asdict(r) for r in rows],
    }


def markdown(rep: dict, window_days: int) -> str:
    L = [
        f"# Observability at documented landslide sites — {window_days}-day pre-event window",
        "",
        f"Sites analysed: **{rep['sites']}** · usable = at least {int(USABLE_CLEAR*100)}% of the "
        "1.1 km site clear of cloud in the SCL band.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Sites with **any** usable optical observation | **{rep['sites_with_usable_optical']} / "
        f"{rep['sites']} ({rep['pct_with_usable_optical']}%)** |",
        f"| Sites with a radar pass | {rep['sites_with_radar']} ({rep['pct_with_radar']}%) |",
        f"| Sites with **no optical scene at all** | {rep['sites_with_no_optical_at_all']} |",
        f"| Median usable optical observations per site | {rep['median_usable_optical']} |",
        f"| Median days since the last usable look | {rep['median_days_since_last_usable']} |",
        "",
        "## Per site",
        "",
        "| site | event date | optical scenes | usable | best clear | radar | days since usable |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rep["rows"]:
        L.append(f"| {r['title'][:42] or r['site_id']} | {r['event_date']} | {r['optical_scenes']} "
                 f"| {r['optical_usable']} | {r['best_clear']:.2f} | {r['radar_passes']} "
                 f"| {r['days_since_last_usable_optical'] if r['days_since_last_usable_optical'] is not None else '—'} |")
    L += ["", "**This is not a skill claim.** It measures whether the evidence required to say "
          "anything existed at all — the precondition for any downstream warning, and the honest "
          "ceiling on what an optical system could have done."]
    return "\n".join(L) + "\n"


def load_sites(path: str | Path, limit: int | None = None,
               min_day_cluster: int = 5, per_month: int | None = None,
               months: tuple[int, ...] | None = None) -> list[dict]:
    """Load benchmark sites.

    `per_month` stratifies the sample across calendar months. This matters more
    than it looks: the multi-site days cluster in late September and October,
    because that is when the rains end AND when optical imagery returns. Sampling
    only the biggest clusters would quietly measure the one season when satellites
    can see, and would overstate observability. Stratifying by month is the honest
    choice, and the July sites are the ones that matter.
    """
    rows = list(csv.DictReader(open(path)))
    rows = [r for r in rows if int(r.get("day_cluster") or 0) >= min_day_cluster]
    if months:
        rows = [r for r in rows if int(r["date"][5:7]) in months]
    if per_month:
        buckets: dict[str, list[dict]] = {}
        for r in rows:
            buckets.setdefault(r["date"][:7], []).append(r)
        picked: list[dict] = []
        for key in sorted(buckets):
            group = sorted(buckets[key], key=lambda r: r["date"])
            step = max(1, len(group) // per_month)
            picked.extend(group[::step][:per_month])
        rows = picked
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows[:limit] if limit else rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Measure pre-event observability at real sites.")
    ap.add_argument("--events", default="benchmark/events.csv")
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--limit-sites", type=int, default=12)
    ap.add_argument("--per-month", type=int,
                    help="stratify the sample: N sites per calendar month (honest)")
    ap.add_argument("--months", type=int, nargs="*",
                    help="restrict to these calendar months, e.g. --months 6 7 8 9")
    ap.add_argument("--out", default="reports/observability.json")
    ap.add_argument("--no-radar", action="store_true")
    a = ap.parse_args(argv)

    sites = load_sites(a.events, a.limit_sites, per_month=a.per_month,
                       months=tuple(a.months) if a.months else None)
    print(f"analysing {len(sites)} documented sites, {a.window}-day window", file=sys.stderr)
    rows = []
    for i, site in enumerate(sites, 1):
        try:
            r = analyse_site(site, a.window, include_radar=not a.no_radar)
        except Exception as exc:
            print(f"  [{i}/{len(sites)}] skip {site.get('title','?')[:30]}: "
                  f"{type(exc).__name__}", file=sys.stderr)
            continue
        rows.append(r)
        print(f"  [{i}/{len(sites)}] {r.event_date} optical {r.optical_usable}/{r.optical_scenes} "
              f"usable, best {r.best_clear:.2f}, radar {r.radar_passes}", file=sys.stderr)

    rep = summarise(rows, a.window)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n")
    md = out.with_suffix(".md")
    md.write_text(markdown(rep, a.window))
    print(f"\n{rep['sites_with_usable_optical']}/{rep['sites']} sites had a usable optical look "
          f"in the {a.window} days before failure ({rep['pct_with_usable_optical']}%)")
    print(f"wrote {out} and {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
