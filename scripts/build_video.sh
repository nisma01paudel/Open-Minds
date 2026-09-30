#!/usr/bin/env bash
# Assemble the captured beats into a draft demo video (1920x1080, captioned, no narration).
#
# This is a DRAFT of the mandatory submission item, not a substitute for the team's own
# recording: every frame is the real app, and the captions say what to narrate. Record your
# own voice over it, or re-record from presenter mode.
set -euo pipefail

STILLS="reports/video/stills"
CLIPS="reports/video/clips"
FONT="$(fc-match -f '%{file}' 'DejaVu Sans' 2>/dev/null || echo /usr/share/fonts/TTF/DejaVuSans.ttf)"
FPS=30
mkdir -p "$CLIPS"; rm -f "$CLIPS"/*.mp4 "$CLIPS"/*.txt

caption () { printf '%b' "$2" > "$CLIPS/$1.txt"; }

clip_still () { # outname stillname duration captionname
  local out="$1" still="$2" dur="$3" cap="$4"
  ffmpeg -hide_banner -loglevel error -y -loop 1 -i "$STILLS/$still.png" -t "$dur" \
    -vf "scale=2688:1512,zoompan=z='min(1.0+0.00030*on,1.14)':d=$((dur*FPS)):x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=$FPS,\
drawtext=fontfile='$FONT':textfile='$CLIPS/$cap.txt':expansion=none:fontcolor=white:fontsize=33:line_spacing=10:x=70:y=h-210:box=1:boxcolor=0x05070dee:boxborderw=18,\
fade=t=in:st=0:d=0.5,fade=t=out:st=$((dur-1)).0:d=0.5" \
    -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p "$CLIPS/$out.mp4" || {
      echo "FFMPEG FAILED for $out" >&2; return 1; }
  printf '  %-14s %2s s\n' "$out" "$dur"
}

clip_title () { # outname duration captionname
  local out="$1" dur="$2" cap="$3"
  ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=c=0x05070d:s=1920x1080:d=$dur:r=$FPS" \
    -vf "drawtext=fontfile='$FONT':textfile='$CLIPS/$cap.txt':expansion=none:fontcolor=white:fontsize=50:line_spacing=22:x=(w-text_w)/2:y=(h-text_h)/2,\
fade=t=in:st=0:d=0.8,fade=t=out:st=$((dur-1)).0:d=0.8" \
    -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p "$CLIPS/$out.mp4" || {
      echo "FFMPEG FAILED for $out" >&2; return 1; }
  printf '  %-14s %2s s\n' "$out" "$dur"
}

echo "building clips from $(ls "$STILLS" | wc -l) stills ..."

caption a "Nepal can already detect.\nNepal cannot dispatch."
clip_title t0 7 a

caption b "613 documented landslide-prone slopes.\nEvery one paired with the office legally responsible for it."
clip_still map 01-map 13 b

echo "  season        17 s   (the generated time-lapse)"
ffmpeg -hide_banner -loglevel error -y -i reports/timelapse/pahiro-monsoon-2024.mp4 -t 17 \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x05070d,fps=$FPS" \
  -an -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p "$CLIPS/season.mp4" 2>/dev/null

# SUPERSEDED by build_voiced_video.sh, and left carrying a wrong number for seven rounds.
# Fixed rather than deleted: a dead script with a plausible stale figure is what gets run later.
caption d "28 September 2024.\n31 of 613 slopes above the rainfall threshold.\nThe season peaked the day before, at 149.\nThat day, Nepal recorded 167 landslides."
clip_still peak 02-peak 14 d

caption e "And only 27.8% of satellite imagery that month had clear ground.\nA slope can be loaded and invisible at the same time."
clip_still blind 03-advisory 13 e

caption f "A Nepali notice: the responsible office,\nthe section of law, and where to build instead."
clip_still advisory 03-advisory 12 f

caption g "Real elevation. Real satellite imagery. Real rainfall."
clip_still fly 04-3d 14 g

caption h "Point a phone at a hillside:\nthe slope's state, and who owns it."
clip_still phone 05-phone 10 h

caption i "And a ten-second film, so the finding leaves the room."
clip_still share 06-share 10 i

caption j "Nepal can already detect.\nNepal cannot dispatch.\nWe built the last metre."
clip_title t1 9 j

echo "concatenating ..."
: > "$CLIPS/list.txt"
for f in t0 map season peak blind advisory fly phone share t1; do
  # The concat demuxer resolves relative paths against the LIST FILE's directory, so a
  # CWD-relative path gets prefixed twice and every input 404s. Use absolute paths.
  if [ -f "$CLIPS/$f.mp4" ]; then echo "file '$PWD/$CLIPS/$f.mp4'" >> "$CLIPS/list.txt";
  else echo "MISSING clip: $f" >&2; fi
done
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$CLIPS/list.txt" -c copy reports/video/pahiro-draft.mp4 2>/dev/null
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 reports/video/pahiro-draft.mp4 2>/dev/null)
printf '\nwrote reports/video/pahiro-draft.mp4  (%s s, %s bytes)\n' "${D%%.*}" "$(stat -c%s reports/video/pahiro-draft.mp4)"
