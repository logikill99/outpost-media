#!/usr/bin/env bash
# Batch-encode source videos to 720p H.264/AAC with faststart for HTTP streaming.
# Usage: ./scripts/encode_video.sh <input_dir> <output_dir>
# Encode on the M4 MacBook before the event — the Pi is too slow.
set -euo pipefail

IN="${1:-./incoming}"
OUT="${2:-./media/videos}"

mkdir -p "$OUT"

shopt -s nullglob
for f in "$IN"/*.{mkv,mp4,mov,avi,webm,m4v}; do
  base="$(basename "${f%.*}")"
  out="${OUT}/${base}.mp4"
  if [[ -f "$out" ]]; then
    echo "skip (exists): $out"
    continue
  fi
  echo "==> $f -> $out"
  ffmpeg -hide_banner -y -i "$f" \
    -vf "scale='min(1280,iw)':'-2'" \
    -c:v libx264 -preset slow -crf 23 \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    "$out"
done

echo "Done. Files in $OUT:"
ls -lh "$OUT"
