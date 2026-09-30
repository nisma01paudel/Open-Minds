#!/usr/bin/env python3
"""Render the 2024 monsoon as a time-lapse: Nepal's slopes lighting up, day by day.

This is the awareness asset. A map you have to go and look at changes nothing; a ten
second film of the country loading up during the season is the thing that gets forwarded.

Real satellite imagery underneath, real CHIRPS rainfall on top, using the same
multi-window trigger as the system (a slope counts if ANY of the 24/48/72-hour windows
crosses its own threshold).

    python scripts/build_timelapse.py --out reports/timelapse
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]
BBOX = (79.8, 26.0, 88.6, 30.6)
W, H = 1400, 760
WINDOWS = [(24, 118.8), (48, 141.9), (72, 157.5)]

COLOUR = {"exceeded": "#ff2d20", "approaching": "#ff9f0a", "below": "#93a3b8"}


def project(lat: float, lon: float) -> tuple[float, float]:
    x = (lon - BBOX[0]) / (BBOX[2] - BBOX[0]) * W
    y = (BBOX[3] - lat) / (BBOX[3] - BBOX[1]) * H
    return x, y


def state_for(r: list, i: int) -> tuple[str, float] | None:
    v = r[i]
    if v is None:
        return None
    back = [r[i - k] for k in (0, 1, 2) if i - k >= 0 and r[i - k] is not None]
    if not back:
        return None
    sums = [back[0],
            sum(back[:2]) if len(back) >= 2 else None,
            sum(back[:3]) if len(back) >= 2 else None]
    best = 0.0
    for w, (_, thr) in enumerate(WINDOWS):
        if sums[w] is not None:
            best = max(best, sums[w] / thr)
    return ("exceeded" if best >= 1 else "approaching" if best >= 0.8 else "below"), v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default="web/public/data/timeline.json")
    ap.add_argument("--base", default="reports/timelapse/base.png")
    ap.add_argument("--out", default="reports/timelapse")
    a = ap.parse_args()

    out = ROOT / a.out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    tl = json.loads((ROOT / a.timeline).read_text())
    base = ROOT / a.base

    if not base.exists():
        base.parent.mkdir(parents=True, exist_ok=True)
        url = ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
               "MapServer/export?bbox=" + ",".join(str(v) for v in BBOX) +
               f"&bboxSR=4326&imageSR=4326&size={W},{H}&format=png&f=image")
        print("fetching the satellite base ...")
        subprocess.run(["curl", "-s", "-o", str(base), url], check=True)
    # darken and slightly desaturate so the dots read
    subprocess.run(["magick", str(base), "-modulate", "82,72", "-brightness-contrast", "-14x12",
                    str(out / "base-tuned.png")], check=True)

    days = tl["days"]
    peak = 0
    print(f"rendering {len(days)} frames ...")
    for i, day in enumerate(days):
        circles, counts = [], {"exceeded": 0, "approaching": 0, "below": 0}
        hot = []
        for s in tl["sites"]:
            got = state_for(s["r"], i)
            if not got:
                continue
            st, v = got
            counts[st] += 1
            x, y = project(s["lat"], s["lon"])
            r = 7.5 if st == "exceeded" else 5.5 if st == "approaching" else 2.6
            op = 1.0 if st != "below" else 0.42
            if st != "below":
                circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r*1.9:.1f}" '
                               f'fill="{COLOUR[st]}" opacity="0.20"/>')
                hot.append((v, s["lat"], s["lon"]))
            circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{COLOUR[st]}" '
                           f'opacity="{op}" stroke="{"#fff" if st!="below" else "#0f172a"}" '
                           f'stroke-width="{1.2 if st!="below" else 0.7}"/>')
        peak = max(peak, counts["exceeded"])
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">'
               + "".join(circles) + "</svg>")
        svg_path = frames_dir / "layer.svg"
        svg_path.write_text(svg)
        frame = frames_dir / f"{i:03d}.png"
        # Rasterise the SVG with rsvg-convert, which preserves transparency. ImageMagick's
        # own SVG renderer fills the canvas white, and `-background none` applied AFTER the
        # read does not change that - it silently produced 153 frames with no satellite
        # imagery underneath, which looks like a deliberate minimal style and is not.
        layer_png = frames_dir / "layer.png"
        subprocess.run(["rsvg-convert", "-o", str(layer_png), str(svg_path)], check=True)
        subprocess.run(["magick", str(out / "base-tuned.png"), str(layer_png),
                        "-composite", str(frame)], check=True)
        # burn in the date + the count
        label = (f"{day}    {counts['exceeded']} slopes above the rainfall threshold"
                 f"    worst {max([h[0] for h in hot], default=0):.0f} mm/24h")
        subprocess.run(["magick", str(frame), "-gravity", "south",
                        "-fill", "#ffffff", "-undercolor", "#000000cc",
                        "-pointsize", "30", "-annotate", "+0+18", label, str(frame)], check=True)
        if (i + 1) % 25 == 0 or i == 0:
            print(f"  {i+1}/{len(days)}  {counts['exceeded']:4} above", flush=True)

    print(f"\npeak day had {peak} slopes above threshold")
    print("assembling ...")
    mp4 = out / "pahiro-monsoon-2024.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", "10", "-i", str(frames_dir / "%03d.png"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)],
                   check=True, capture_output=True)
    gif = out / "pahiro-monsoon-2024.gif"
    subprocess.run(["ffmpeg", "-y", "-framerate", "10", "-i", str(frames_dir / "%03d.png"),
                    "-vf", "fps=10,scale=760:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse",
                    str(gif)], check=True, capture_output=True)
    for f in (mp4, gif):
        print(f"  {f}  ({f.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
