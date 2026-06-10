#!/usr/bin/env bash
#
# Lyrisee / Lyric Weaver — setup & run
# ------------------------------------
# Reconstructed from README__v2.md (the original run.sh was not present in the
# uploaded project archive). Adjust paths if your layout differs.
#
# Usage:
#   ./run.sh [path/to/audio.mp3]
# Defaults to DarkNights-80K.mp3 if no argument is given.
#
set -euo pipefail

AUDIO="${1:-DarkNights-80K.mp3}"
PUBLIC_DIR="public"

echo "==> Lyrisee setup"
if [ ! -f "$AUDIO" ]; then
  echo "!! Audio file not found: $AUDIO"
  echo "   Pass one explicitly:  ./run.sh path/to/song.mp3"
  exit 1
fi

# 1) Python dependencies (Flask, demucs, stable-ts, librosa, spacy, torch, moviepy, ...)
echo "==> Installing Python dependencies (this can take a while the first time)"
python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install -r requirements.txt

# 2) spaCy English model (for part-of-speech tagging used by the visual rules)
echo "==> Ensuring spaCy English model is available"
python3 -m spacy download en_core_web_sm >/dev/null 2>&1 || \
  echo "   (spaCy model download skipped/failed — install manually if POS tagging errors)"

# 3) Audio intelligence pipeline -> lyric_data.json
#    demucs (vocal separation) + stable-ts/whisper (word-level transcription)
#    + librosa (beat detection) + spaCy (POS).  Produces words[], beats[].
#    NOTE: audio_processor.py is part of your backend (it was not in the archive
#    shared with the agent). This calls it as documented in README__v2.md.
echo "==> Processing audio: $AUDIO"
if [ -f "audio_processor.py" ]; then
  python3 audio_processor.py "$AUDIO"
else
  echo "!! audio_processor.py not found in this folder."
  echo "   It lives in your backend per README__v2.md. Restore it, or generate"
  echo "   lyric_data.json another way, then re-run from step 4."
  echo "   The viewer also accepts a lyric_data.json dropped in via its ingest screen."
fi

# 4) Stage assets for the front-end
echo "==> Staging public/ assets"
mkdir -p "$PUBLIC_DIR"
[ -f lyric_data.json ] && cp -f lyric_data.json "$PUBLIC_DIR/lyric_data.json"
cp -f "$AUDIO" "$PUBLIC_DIR/$(basename "$AUDIO")"
# Use the enhanced engine as the public index if present
[ -f index.html ] && cp -f index.html "$PUBLIC_DIR/index.html"

# 5) Serve
echo "==> Done. Start the local server in a new terminal:"
echo
echo "      python3 -m http.server -d $PUBLIC_DIR 8000"
echo "      open http://localhost:8000"
echo
echo "   In the viewer: drop your audio + lyric_data.json (or 'Load the demo'),"
echo "   press Play, switch constructs, and use 'Edit lyrics' to fix transcription."
