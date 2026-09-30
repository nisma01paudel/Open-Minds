"""Gap-state calibration: on how many days can this system actually speak?

This is contribution C, measured. For every day in a period we ask the
staleness gate whether an advisory could be issued, then report:

- the share of days we can speak, per month;
- the longest stretch of consecutive blind days;
- an ablation: optical-only versus optical + radar.

The ablation is the argument for radar in one number. Optical goes dark in the
monsoon (measured: in July, 0.0% of Sentinel-2 scenes over eleven years had
>80% clear pixels at the AOI); radar keeps looking every month of every year.

    python -m pahiro.eval.gap --obs evidence/dhading-2024-obs.jsonl \
        --radar evidence/s1-radar-dates.jsonl --year 2024
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from pahiro.routing.abstain import Observation, staleness_gate


def load_observations(path: str | Path, sensor: str | None = None,
                      quality: float | None = None) -> list[Observation]:
    """Read an observation series.

    Accepts the `pahiro.ingest.series` format (`usable_fraction`) and the
    `pahiro.ingest.screen` format (`aoi_clear_fraction`, no sensor field).

    `quality` overrides the measured quality - used ONLY for radar, where we
    know the acquisition times but have not yet measured per-pixel usability.
    Such a run is an upper bound and must be labelled as one.
    """
    obs = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        q = quality if quality is not None else float(
            r.get("usable_fraction") or r.get("aoi_clear_fraction") or 0.0)
        obs.append(Observation(
            sensor=r.get("sensor") or sensor or "sentinel-2",
            observed_at=date.fromisoformat(r["acquired"]),
            quality=q, scene_id=r.get("scene_id"),
        ))
    return obs


def daily_status(observations: list[Observation], start: date, end: date) -> dict[date, bool]:
    """For each day, could an advisory have been issued with the evidence then available?"""
    out: dict[date, bool] = {}
    obs_sorted = sorted(observations, key=lambda o: o.observed_at)
    d = start
    while d <= end:
        available = [o for o in obs_sorted if o.observed_at <= d]
        out[d] = staleness_gate(available, d).may_issue
        d += timedelta(days=1)
    return out


def longest_blind_streak(timeline: dict[date, bool]) -> int:
    best = cur = 0
    for d in sorted(timeline):
        cur = 0 if timeline[d] else cur + 1
        best = max(best, cur)
    return best


def monthly_share(timeline: dict[date, bool]) -> dict[str, float]:
    buckets: dict[str, list[bool]] = defaultdict(list)
    for d, ok in timeline.items():
        buckets[f"{d.year}-{d.month:02d}"].append(ok)
    return {k: 100.0 * sum(v) / len(v) for k, v in sorted(buckets.items())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure how often the system can speak.")
    ap.add_argument("--obs", required=True, help="optical observation series JSONL")
    ap.add_argument("--radar", help="radar acquisition JSONL (adds the ablation)")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out", help="write the per-month table as CSV")
    a = ap.parse_args(argv)

    start, end = date(a.year, 1, 1), date(a.year, 12, 31)
    optical = load_observations(a.obs)
    # Radar acquisitions are known; per-pixel usability is not yet measured.
    # Treating an acquisition as fully usable is an UPPER BOUND, and is labelled
    # as such wherever it is reported.
    radar = load_observations(a.radar, sensor="sentinel-1", quality=1.0) if a.radar else []

    tl_optical = daily_status([o for o in optical], start, end)
    print(f"OPTICAL ONLY  ({len(optical)} observations)")
    print(f"  days an advisory could be issued: {sum(tl_optical.values())}/{len(tl_optical)} "
          f"({100*sum(tl_optical.values())/len(tl_optical):.1f}%)")
    print(f"  longest blind streak: {longest_blind_streak(tl_optical)} days")

    rows = []
    if radar:
        tl_both = daily_status(optical + radar, start, end)
        both_pct = 100 * sum(tl_both.values()) / len(tl_both)
        opt_pct = 100 * sum(tl_optical.values()) / len(tl_optical)
        print(f"\nOPTICAL + RADAR  [radar = acquisition coverage, an UPPER BOUND: "
              f"per-pixel usability not yet measured] ({len(optical)}+{len(radar)} observations)")
        print(f"  days an advisory could be issued: {sum(tl_both.values())}/{len(tl_both)} "
              f"({both_pct:.1f}%)")
        print(f"  longest blind streak: {longest_blind_streak(tl_both)} days")
        print(f"  => radar adds {both_pct - opt_pct:+.1f} percentage points of coverage")

        mo, mr = monthly_share(tl_optical), monthly_share(tl_both)
        print(f"\n{'month':<9}{'optical':>9}{'+radar':>9}{'delta':>8}")
        for k in sorted(mo):
            print(f"{k:<9}{mo[k]:>8.0f}%{mr[k]:>8.0f}%{mr[k]-mo[k]:>+8.0f}")
            rows.append((k, mo[k], mr[k]))
    else:
        for k, v in monthly_share(tl_optical).items():
            print(f"  {k}: {v:.0f}% of days")
            rows.append((k, v, None))

    if a.out:
        with open(a.out, "w") as fh:
            fh.write("month,optical_pct_days_issuable,with_radar_pct_days_issuable\n")
            for k, o, r in rows:
                fh.write(f"{k},{o:.1f},{'' if r is None else f'{r:.1f}'}\n")
        print(f"\nwrote {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
