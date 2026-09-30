#!/usr/bin/env python3
"""Render the trail network as a video still, from the real bundle.

The demo video showed only the disaster half. This draws the daily-use half from the same
GeoJSON the app ships - not an illustration of it - so the film and the product are the same
data.

    python scripts/render_trails_still.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BG = "#05070d"
REGION_COLOUR = {"kathmandu": "#34d399", "khumbu": "#fbbf24",
                 "annapurna": "#f97316", "langtang": "#60a5fa"}
LABELS = [("Kathmandu", 85.324, 27.717), ("Pokhara", 83.985, 28.209),
          ("Namche Bazaar", 86.714, 27.807), ("Dhunche", 85.30, 28.11)]


def main() -> int:
    data = json.loads((ROOT / "web/public/data/trails.geojson").read_text(encoding="utf-8"))
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=BG)

    counts: dict[str, int] = {}
    for f in data["features"]:
        region = (f.get("properties") or {}).get("r", "other")
        counts[region] = counts.get(region, 0) + 1
        xs = [c[0] for c in f["geometry"]["coordinates"]]
        ys = [c[1] for c in f["geometry"]["coordinates"]]
        ax.plot(xs, ys, color=REGION_COLOUR.get(region, "#94a3b8"),
                linewidth=0.55, alpha=0.85, solid_capstyle="round")

    offsets = {"Pokhara": (-150, -34), "Kathmandu": (14, -30), "Dhunche": (14, 8),
               "Namche Bazaar": (-210, 10)}
    for name, lon, lat in LABELS:
        ax.plot([lon], [lat], marker="o", markersize=7, color="#ffffff")
        ax.annotate(name, (lon, lat), textcoords="offset points",
                    xytext=offsets.get(name, (11, 7)),
                    color="#ffffff", fontsize=17, fontweight="bold")

    ax.set_xlim(83.4, 87.3)
    ax.set_ylim(27.4, 28.6)
    ax.axis("off")

    total = len(data["features"])
    fig.text(0.045, 0.925, f"{total:,} mapped footpaths, offline", color="#ffffff",
             fontsize=46, fontweight="bold")
    fig.text(0.045, 0.872,
             "four regions of Nepal — 4.5 MB, no network, on the web and on the phone",
             color="#c7d2fe", fontsize=23)
    fig.text(0.045, 0.055,
             "© OpenStreetMap contributors, ODbL 1.0 — every line here is in the bundle the app ships",
             color="#8b98b8", fontsize=16)

    y = 0.93
    for region, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        fig.text(0.795, y, "\u2014", color=REGION_COLOUR.get(region, "#94a3b8"), fontsize=26,
                 fontweight="bold")
        fig.text(0.818, y + 0.004, f"{region.title()}  {n:,}", color="#e2e8f0", fontsize=18)
        y -= 0.040

    dest = ROOT / "reports/video/stills/09-trails.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, facecolor=BG)
    plt.close(fig)
    print(f"wrote {dest.relative_to(ROOT)} ({dest.stat().st_size/1024:.0f} KB), "
          f"{total} trails across {len(counts)} regions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
