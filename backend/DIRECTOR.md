# Lyrisee Director — prompting-logic map (dynamic, NOT a format to impose)

**The mistake to never make:** treating any previous song (Die Alone, Do I Wanna Know, etc.) as a template and stamping its palette / motifs / motion onto the next track. Each song receives its own world derived from *its* language, dual readings, and unsaid.

The Director is a two-stage process:

1. **CONCEPT** (once per song) — invent the visual world
2. **DIRECTION** (per line) — art-direct inside that world, privileging the gap when it is stronger than the spoken text

Quality tier = the kinetic-typography reference videos that make the unsaid louder than the lyrics. Format = whatever the song demands.

---

## House style — the stage vocabulary (hard constraint)

**Type IS the object.** Objects are drawn as stroke line-art, never pictographs. No emoji, no Unicode
symbols, no icon glyphs anywhere on stage — that is the one rule the Director cannot bend. The reference
language is a tire drawn as a ring with the lyric arcing around it, an ace falling as a stroked card,
a figure drawn inside the letterforms.

The engine only renders these two closed vocabularies; anything else is dropped at ingest
(`lyrisee_ai.LAYOUTS` / `MOTIFS`, `MOTIF_PATH` in `index.html`):

| `layout` (how the words arrange — meaning as form) | |
|---|---|
| `row` | neutral |
| `split` | two opposed halves |
| `ascend` / `fall` | climbing / dropping |
| `stack` | building |
| `spiral` | circling, obsessive |
| `path` | a journey across |
| `cage` / `cagebars` | words box themselves in / stand as bars |

`motif` (drawn stroke object behind the type, optional):
`ring · heart · staff · card · moon · boot · car · figure · bars · ladder · coin · ring_split`

Per-word direction: `hit` (one charged word per line, painted in the song's accent), `emphasis`,
`script` (intimate register), `glow`, `rotate`.

If no Director runs, the engine derives layout and motif from the line itself — the visual world
degrades, it never goes blank.

---

## Core reasoning chain (forced by the prompts)

For every song the model must:

1. Surface reading  
2. Undercurrent / dual readings (double-entendres, power dynamics, sexual undertones, irony, self-sabotage)  
3. **The Unsaid** — the central question, confession, or invitation the lyrics circle but never resolve  
4. Derive palette, fonts, motif lexicon, motion grammar, restraint, and gap_strategy *exclusively* from the above

This is what makes the system reusable on any future track (including the owner's own music).

---

## STAGE 1 — CONCEPT schema

```jsonc
{
  "palette": {"bg": "#000000", "ink": "#EDEAE4", "accents": ["#C41E3A"]},
  "fonts":   {"display": "Anton", "accent": "Archivo Black", "script": null},
  "motifs":  {"teeth_stick": "tire", "aces": "playing_cards", "heart": "outlined_heart"},
  "motion":  "deliberate_crawl_with_sudden_snaps",
  "restraint": 0.72,
  "mood": "nocturnal_desire_under_restraint",
  "construct_bias": ["embodiment", "isolation", "kinetic_art"],
  "dual_readings": {
    "surface": "...",
    "undercurrent": "...",
    "unsaid": "..."
  },
  "visual_priority": "emphasize_unsaid",
  "gap_strategy": "negative_space + recursive_question_isolation + withheld_reveal"
}
```

- `motifs` are drawn only from the song's own imagery.  
- `visual_priority` defaults to `emphasize_unsaid`.  
- `gap_strategy` tells the renderer how to treat silence and unanswered questions.

---

## STAGE 2 — DIRECTION schema (per line)

```jsonc
{
  "line_index": 0,
  "primary": "literal reading",
  "secondary": "double-entendre / layered reading",
  "gap": "what is deliberately left unsaid or hanging",
  "emphasis_target": "spoken | gap | both",
  "visual_action": "build_form | semantic_motion | isolate | withhold | embody | clean",
  "form": "tire | cards | heart | null",
  "motion_verb": "crawl | simmer | stick | spill | null",
  "gap_treatment": "hold_negative | loop_question | fade_before_answer | …",
  "register": "display | accent | script",
  "hierarchy": "which words are charged"
}
```

The renderer can now act on `emphasis_target`, `visual_action`, `form`, and `gap_treatment` without any song-specific hard-coding.

---

## Guardrails (anti-format-forcing)

- Palette / fonts / motifs come from `data.concept` only.  
- Never hard-code crimson, pink script, coffins, tires, or any previous answer.  
- Hits stay sparse (1–3 charged moments per line). Negative space is a feature.  
- Quality, not look, is the constant: legible, intentional, synced, restrained.

---

## Implementation

- `lyrisee_ai.concept(lyrics)` → Stage 1  
- `lyrisee_ai.direct(lines, concept)` → Stage 2  
- `lyrisee_ai.enrich(words)` → full pass used by `audio_processor.py`  
  (returns repaired words + concept + directions + metaphors for backward compatibility)

Providers (first key found wins): `GEMINI_API_KEY` | `OPENAI_API_KEY` | `ANTHROPIC_API_KEY` | `OLLAMA_API_KEY`.  
Override with `LYRISEE_LLM=gemini|openai|anthropic|ollama`.

---

## Reference quality bar

The Arctic Monkeys “Do I Wanna Know?” kinetic-typography treatment is the craft target: literal embodiment of the lyric’s own images, isolation of the unanswered question, and motion that makes the hesitation and the one-sided desire louder than any spoken resolution. The prompts above are engineered so the same reasoning produces an equally intentional (but completely different) world for the next song.
