# Lyrisee — Kinetic Typography Engine

Turn any song into a synced, intelligent lyric video. Drop audio or video + a `lyric_data.json`, and the engine
renders kinetic typography that reads the lyrics' meaning — rhyme color-coding, semantic word-forms, and a
per-song "Director" that art-directs the look.

**Live (Vercel):** the production app is the static engine in this repo's root.

## Features Added
- **Audio & Video Support:** Drop `.mp3` or `.mp4`. The engine natively supports video playback mapped transparently beneath WebGL text layers and extracting audio streams dynamically.
- **Custom Backgrounds:** Choose between Plain, Generic, Textured (CSS-driven noise) or use the uploaded Video as a living background.
- **Line-by-Line Approval/Edit Mode:** A tool for transcription quality assurance. It pauses transcription playback just before each line triggers, presenting a modal to review/edit the spoken words. Modifying the text keeps the original as backup in `original_text`, updating the timeline pacing dynamically without disrupting layout constructs.
- **The "Die Alone" AI Director:** The backend AI pipeline (`backend/lyrisee_ai.py`) utilizes a hyper-specialized system prompt to guarantee "quality-tier" understanding of song narrative arcs, vocal hits, and tonal pacing prior to assigning words any visual kinetic properties, eliminating generic fallback templates.
- **SEO & Social Sharing:** Enhanced OpenGraph and Twitter meta tags ensure rich previews on external link shares.

## Routes
| Path | What |
|------|------|
| `/` | The engine — ingest any audio/video + `lyric_data.json` (or load the demo) |
| `/dark-nights` | "Dark Nights" opening — word-art vignette (back rotates, peace ☮, cage→bars, free lifts) |
| `/80k` | "80K tokens mix" — full render with embedded audio (press ▶) |
| `/rhyme` | The rhyme-map (true CMUdict rhyme color-coding, emNoFavors style) |

## How it deploys
Pure static site — no build step. `vercel.json` sets clean URLs; `.vercelignore` excludes `backend/`
(the Python pipeline isn't part of the web deploy). Vercel serves the HTML directly.

## The engine (`index.html`)
Self-contained. Drop an audio/video file, add the `lyric_data.json` your pipeline emits (or auto-transcribe in
browser), press Play. Constructs: **Embodiment** (words-as-imagery), **Rhyme Scheme** (color-coded),
**Kinetic Art / Vivid / Classic** (WebGL). Use **Approval Mode** or **✎ Edit lyrics** to fix transcription; auto-arrange switches
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
