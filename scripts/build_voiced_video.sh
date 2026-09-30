#!/usr/bin/env bash
# Build the demo video WITH narration.
#
# Each beat's narration decides its own on-screen duration, so the visuals follow the
# voice instead of the other way round - the usual reason a narrated demo feels rushed.
#
# Expects the stills from scripts/capture_beats.sh and one wav per beat in VOICE_DIR,
# keyed to the narration file: a=titles, b=map, c=season, d=peak, e=blind, f=advisory,
# g=fly, h=phone, i=share, j=close.
set -euo pipefail

STILLS="reports/video/stills"
CLIPS="reports/video/clips-voiced"
VOICE="${VOICE_DIR:-reports/video/voice-omni}"
TIMELAPSE="reports/timelapse/pahiro-monsoon-2024.mp4"
FONT="$(fc-match -f '%{file}' 'DejaVu Sans' 2>/dev/null || echo /usr/share/fonts/TTF/DejaVuSans.ttf)"
FPS=30
OUT="reports/video/pahiro-narrated.mp4"
PAD=1.4          # seconds of silence after each line

mkdir -p "$CLIPS"; rm -f "$CLIPS"/*.mp4

need () { [ -f "$1" ] || { echo "MISSING: $1" >&2; exit 1; }; }
dur () { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }

# clip name, still (or "SEASON"), narration key, caption file
build () {
  local out="$1" still="$2" key="$3" cap="$4"
  local wav="$VOICE/$key.wav"
  need "$wav"
  local d; d=$(dur "$wav")
  local total; total=$(python3 -c "print(round(max($d + $PAD, 4.0), 2))")
  local frames; frames=$(python3 -c "print(int(round($total * $FPS)))")
  printf '  %-10s voice %5.1fs -> clip %5.1fs\n' "$out" "$d" "$total"

  if [ "$still" = "SEASON" ]; then
    # the time-lapse is already moving; pad or trim it to the narration
    ffmpeg -hide_banner -loglevel error -y -stream_loop -1 -i "$TIMELAPSE" -t "$total" \
      -i "$wav" \
      -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x05070d,\
drawtext=fontfile='$FONT':textfile='$CLIPS/$cap.txt':expansion=none:fontcolor=white:fontsize=33:line_spacing=10:x=70:y=h-210:box=1:boxcolor=0x05070dee:boxborderw=18,fps=$FPS" \
      -map 0:v -map 1:a -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
      -c:a aac -b:a 160k -shortest "$CLIPS/$out.mp4" || { echo "FAILED $out" >&2; return 1; }
    return
  fi

  if [ "$still" = "CARD" ]; then
    ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=c=0x05070d:s=1920x1080:d=$total:r=$FPS" -i "$wav" \
      -vf "drawtext=fontfile='$FONT':textfile='$CLIPS/$cap.txt':expansion=none:fontcolor=white:fontsize=50:line_spacing=22:x=(w-text_w)/2:y=(h-text_h)/2" \
      -map 0:v -map 1:a -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
      -c:a aac -b:a 160k -shortest "$CLIPS/$out.mp4" || { echo "FAILED $out" >&2; return 1; }
    return
  fi

  ffmpeg -hide_banner -loglevel error -y -loop 1 -i "$STILLS/$still.png" -t "$total" -i "$wav" \
    -vf "scale=2688:1512,zoompan=z='min(1.0+0.00030*on,1.14)':d=$frames:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=$FPS,\
drawtext=fontfile='$FONT':textfile='$CLIPS/$cap.txt':expansion=none:fontcolor=white:fontsize=33:line_spacing=10:x=70:y=h-210:box=1:boxcolor=0x05070dee:boxborderw=18" \
    -map 0:v -map 1:a -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
    -c:a aac -b:a 160k -shortest "$CLIPS/$out.mp4" || { echo "FAILED $out" >&2; return 1; }
}

cap () { printf '%b' "$2" > "$CLIPS/$1.txt"; }

echo "building narrated clips (voice: $VOICE) ..."
cap ca "Nepal can already detect.\nNepal cannot dispatch."
build t0 CARD a ca
cap cb "613 documented landslide-prone slopes.\nEach paired with the office responsible for it."
build map 01-map b cb
cap cc "The 2024 monsoon."
build season SEASON c cc
cap cd "28 September 2024.\n305 of 613 slopes above the rainfall threshold.\nThat day Nepal recorded 167 landslides."
build peak 02-peak d cd
cap ce "And only 27.8% of that month's satellite imagery had clear ground."
build blind 03-advisory e ce
cap cf "A Nepali notice: the office, the section of law,\nand where to build instead."
build advisory 03-advisory f cf
cap cg "Real elevation. Real satellite imagery. Real rainfall."
build fly 04-3d g cg
cap ch "Point a phone at a hillside."
build phone 05-phone h ch
cap ci "And a ten-second film, so the finding leaves the room."
build share 06-share i ci
cap cj "Nepal can already detect.\nNepal cannot dispatch.\nWe built the last metre."
build t1 CARD j cj

echo "concatenating ..."
: > "$CLIPS/list.txt"
for f in t0 map season peak blind advisory fly phone share t1; do
  [ -f "$CLIPS/$f.mp4" ] && echo "file '$PWD/$CLIPS/$f.mp4'" >> "$CLIPS/list.txt"
done
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$CLIPS/list.txt" \
  -c:v libx264 -preset slow -crf 22 -c:a aac -b:a 160k -pix_fmt yuv420p -movflags +faststart "$OUT"
printf '\nwrote %s  (%s s, %s MB)\n' "$OUT" \
  "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT" | cut -d. -f1)" \
  "$(python3 -c "import os;print(f'{os.path.getsize(\"$OUT\")/1048576:.1f}')")"
