#!/usr/bin/env bash
# Render a terminal-style 1920x1080 still from real text.
# Used for beats whose content IS the text - the agent trace, and the E5 result.
set -euo pipefail
TITLE="$1"; BODY="$2"; OUT="$3"
FONT_M="$(fc-match -f '%{file}' 'DejaVu Sans Mono' 2>/dev/null)"
FONT_B="$(fc-match -f '%{file}' 'DejaVu Sans' 2>/dev/null)"
magick -size 1920x1080 xc:'#070b14' \
  -fill '#0f172a' -draw 'roundrectangle 80,60 1840,1020 18,18' \
  -fill '#1e293b' -draw 'roundrectangle 80,60 1840,130 18,18' \
  -fill '#334155' -draw 'roundrectangle 80,112 1840,130 0,0' \
  -fill '#475569' -draw 'circle 118,95 118,84' -draw 'circle 146,95 146,84' -draw 'circle 174,95 174,84' \
  -font "$FONT_B" -fill '#e2e8f0' -pointsize 26 -annotate +210+103 "$TITLE" \
  -font "$FONT_M" -fill '#8ef0c0' -pointsize 25 -interline-spacing 13 \
  -annotate +130+200 @"$BODY" \
  "$OUT"
