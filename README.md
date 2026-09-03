# Lyrisee — AI Kinetic Typography Engine

Turn any song into a synced, intelligent lyric video whose visual world is derived from the song’s own dual meanings and the things it leaves unsaid.

**Live:** https://lyrisee-eight.vercel.app

## What it does

1. **Transcribe** — word-level timestamps via stable-ts / Whisper  
2. **Understand** — rhyme families (CMUdict), coarse section/intent, then the **Director**:
   - Stage 1 **CONCEPT** invents a song-specific world (palette, fonts, motif lexicon, motion, gap strategy)
   - Stage 2 **DIRECTION** art-directs every line inside that world, explicitly hunting double-entendres and privileging the unsaid when it is stronger than the spoken text
3. **Render** — kinetic typography engine consumes the resulting `lyric_data.json` (words + beats + arrangement + concept + directions)

The Director never stamps a previous song’s look onto a new track. Every piece receives its own visual logic.

## Quick start

```bash
# Backend (Hugging Face Space or local)
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # optional but recommended

# Set at least one LLM key
export GEMINI_API_KEY=...          # or OPENAI_API_KEY / ANTHROPIC_API_KEY / OLLAMA_API_KEY

# Process a song
python audio_processor.py path/to/song.mp3 -o lyric_data.json

# Frontend
# Open https://lyrisee-eight.vercel.app or serve index.html and drop the JSON + audio
```

## Key files

| Path | Role |
|------|------|
| `backend/lyrisee_ai.py` | Full Director (CONCEPT + DIRECTION + repair) |
| `backend/DIRECTOR.md` | Prompting logic, schemas, guardrails |
| `backend/audio_processor.py` | ASR → POS → rhyme → Director → lyric_data.json |
| `backend/intent_director.py` | Deterministic section / construct arrangement |
| `backend/rhyme_engine.py` | True rhyme families (CMUdict) |
| `index.html` | Kinetic typography engine + UI |

## Schema highlights (subtext-aware)

```jsonc
{
  "concept": {
    "dual_readings": { "surface": "...", "undercurrent": "...", "unsaid": "..." },
    "visual_priority": "emphasize_unsaid",
    "gap_strategy": "negative_space + …",
    "motifs": { "…": "form_name" }
  },
  "directions": [
    {
      "emphasis_target": "gap | spoken | both",
      "visual_action": "build_form | semantic_motion | isolate | withhold | …",
      "form": "tire | null",
      "motion_verb": "crawl | null",
      "gap_treatment": "…"
    }
  ]
}
```

The frontend can act on these fields directly.

## Design principle

> The strongest kinetic moves often land on the implication or the gap rather than the spoken word.

That is the quality bar. The prompts and schema exist so any future song (including the owner’s own music) receives the same depth of treatment without ever becoming a template.

## Status

Director finalized. Pipeline functional. Creative expansion complete for dual-meaning / unsaid emphasis.
