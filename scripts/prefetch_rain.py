#!/usr/bin/env python3
"""Fetch CHIRPS daily windows in parallel.

The serial version is bound by network, not CPU: a window read is ~17 s because
/vsigzip/ cannot seek in a gzip stream, so GDAL pulls the whole file. Fetching several
days concurrently turns a 43-minute wait into a few minutes.

    python scripts/prefetch_rain.py --from 2024-06-01 --to 2024-10-31 --workers 6
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.ingest.rainfall import fetch_window_cached


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    days, d = [], date.fromisoformat(a.start)
    end = date.fromisoformat(a.end)
    while d <= end:
        days.append(d)
        d += timedelta(days=1)

    done = miss = 0
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(fetch_window_cached, day): day for day in days}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                if f.result() is None:
                    miss += 1
                else:
                    done += 1
            except Exception:
                miss += 1
            if i % 10 == 0 or i == len(days):
                print(f"  [{i}/{len(days)}] fetched {done}, unavailable {miss}", flush=True)
    print(f"\ndone: {done} fetched, {miss} unavailable, of {len(days)} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
