#!/usr/bin/env bash
# Capture each presentation beat as a 1920x1080 still, for assembly into a draft video.
set -uo pipefail
BASE="${BASE:-http://127.0.0.1:8100}"
OUT="reports/video/stills"
mkdir -p "$OUT"

shot () {  # name  url  budget_seconds
  local name="$1" url="$2" budget="${3:-28}"
  rm -rf "/tmp/cr-$name"
  timeout 400 chromium --headless=new --disable-gpu --use-gl=angle --use-angle=swiftshader \
    --enable-unsafe-swiftshader --no-sandbox --hide-scrollbars \
    --user-data-dir="/tmp/cr-$name" --window-size=1920,1080 \
    --virtual-time-budget=$((budget * 1000)) \
    --screenshot="$OUT/$name.png" "$url" >/dev/null 2>&1
  printf '  %-16s %s bytes\n' "$name" "$(stat -c%s "$OUT/$name.png" 2>/dev/null || echo FAIL)"
}

echo "capturing beats ..."
shot 01-map        "$BASE/?mode=replay&on=2024-06-02" 30
shot 02-peak       "$BASE/?mode=replay&on=2024-09-28" 30
shot 03-advisory   "$BASE/?mode=replay&on=2024-09-28&adv=72526" 30
shot 04-3d         "$BASE/fly/?step=8" 55
shot 05-phone      "$BASE/ar/" 14
shot 06-share      "$BASE/share/" 16
echo "done"
