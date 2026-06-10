# Lyrisee — Kinetic Typography Engine

Turn any song into a synced, intelligent lyric video. Drop audio + a `lyric_data.json`, and the engine
renders kinetic typography that reads the lyrics' meaning — rhyme color-coding, semantic word-forms, and a
per-song "Director" that art-directs the look.

**Live (Vercel):** the production app is the static engine in this repo's root.

## Routes
| Path | What |
|------|------|
| `/` | The engine — ingest any audio + `lyric_data.json` (or load the demo) |
| `/dark-nights` | "Dark Nights" opening — word-art vignette (back rotates, peace ☮, cage→bars, free lifts) |
| `/80k` | "80K tokens mix" — full render with embedded audio (press ▶) |
| `/rhyme` | The rhyme-map (true CMUdict rhyme color-coding, emNoFavors style) |

## How it deploys
Pure static site — no build step. `vercel.json` sets clean URLs; `.vercelignore` excludes `backend/`
(the Python pipeline isn't part of the web deploy). Vercel serves the HTML directly.

## The engine (`index.html`)
Self-contained. Drop an audio file, add the `lyric_data.json` your pipeline emits (or auto-transcribe in
browser), press Play. Constructs: **Embodiment** (words-as-imagery), **Rhyme Scheme** (color-coded),
**Kinetic Art / Vivid / Classic** (WebGL). Use **✎ Edit lyrics** to fix transcription; auto-arrange switches
constructs by section.

`lyric_data.json` schema:
```jsonc
{ "words":[{"text","start","end","pos","rhyme","dir":{...}}], "beats":[...],
  "arrangement":[{"start","construct"}], "metaphors":[...], "scenes":[...],
  "concept":{"palette":{...},"motifs":{...}}, "rhyme_palette":[...], "rhyme_families":[...] }
```

## The pipeline (`backend/`, not deployed)
Local toolchain that produces `lyric_data.json` from audio (needs the deps in `backend/requirements.txt`):
- `fw_transcribe.py` — faster-whisper **word-level** timing
- `rhyme_engine.py` — CMUdict true rhyme detection (internal + end)
- `lyrisee_ai.py` — the **Director**: concept (per-song world) + lyric repair + per-word art-direction.
  Uses your local **`gemini` CLI** by default (keyless), or `GEMINI_API_KEY`/`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`.
- `audio_processor.py` — orchestrates the above into `lyric_data.json`. See `backend/run.sh`.

Run: `cd backend && python3 audio_processor.py yoursong.mp3 -o ../lyric_data.json` then open the engine.
