# Lyrisee Director — the prompting-logic map (dynamic, NOT a format to impose)

**The mistake to never make:** treating "Die Alone" as a template (crimson canvas, pink script, coffins)
and stamping it on every song. Die Alone is **one excellent answer** a designer arrived at *for that song*.
Lyrisee must run the **reasoning that produced it**, and for a different song arrive at a *different* world.

So the Director is a two-stage prompt-logic: **CONCEPT** (invent the song's visual world) → **DIRECTION**
(art-direct lines *within that world*). Quality tier = Die Alone. Format = whatever the song demands.

---

## Reverse-engineering the brief: "if I were prompted to make Die Alone"

A designer handed *Die Alone* didn't start from "use crimson + coffins." They reasoned:

> Subject = death, sin, judgment, faith, Eminem's voice. Tone = grave, confessional, ominous.
> → **Palette:** blood/oxblood crimson (mortality, sin) on near-black. Restrained.
> → **Type:** clean condensed sans for the narration; a glowing **script** reserved for *sacred/tender/
>   named* words (Jesus, Dreams) so they feel set-apart.
> → **Motifs (from the lyric's OWN imagery):** coffins, crosses, hands — because the words say them.
> → **Motion/pacing:** hard snap on stresses, breath on the heavy lines; everything on the syllable.
> → **Restraint:** mostly clean type; 1–2 charged hits per line.

Every one of those is a *derivation from the song*. Change the song, every choice changes.

## STAGE 1 — CONCEPT (run once per song)

Input: full repaired lyrics, genre/era cues, tempo/energy, emotional arc, central metaphors, artist persona.
Reason like an art director and output a **creative brief** — the song's own world:

- **palette**: `{bg, ink, accents[]}` keyed to mood/genre. *Derive, never default.*
  (drill → cold steel/concrete + ice blue; love song → warm dusk pastels; gospel-rap → gold/ivory;
  Dark Nights → nocturnal ink-blue/charcoal with a cold accent — **not** Die Alone's crimson.)
- **type**: `{display, accent, script?}` faces + weights that fit the voice.
- **motif lexicon**: word/concept → icon mappings drawn from **THIS song's** imagery (don't reuse another
  song's coffins). e.g. money-rap → cash/chains/crowns; nature → leaves/rain; this track → its nouns.
- **motion**: snap / drift / float / glitch — matched to the beat and attitude.
- **format bias**: which constructs and in what mix — single-word focus, line blocks, scene vignettes,
  the rhyme-map — and how often to switch. Some songs want stillness; some want chaos.
- **restraint**: how charged vs clean (a minimal ballad ≠ a maximalist posse cut).

Output schema (`data.concept`):
```jsonc
{ "palette": {"bg":"#0b0f1a","ink":"#EDEAE4","accents":["#5CE1E6","#FF7A6B","#FFD166"]},
  "fonts":   {"display":"Anton","accent":"Archivo Black","script":"Dancing Script"},
  "motifs":  {"cage":"🧱","lights":"🕯️","water":"💧","mic":"🎤"},   // derived from THIS song
  "motion":  "snap|drift|float", "restraint": 0.0-1.0, "mood": "…", "construct_bias": ["embodiment","rhyme_scheme"] }
```

## STAGE 2 — DIRECTION (per line/word, *inside* the concept)

Now apply the world with craft + restraint: per-word emphasis (hierarchy), register (use the concept's
script for tender/named words, heavy for aggression), iconography (**only** from the concept's motif
lexicon), composition/metaphor, glow/lighting from the concept's palette, all synced to word timing.
Choose 1–3 hits per line; leave the rest clean.

## Guardrails (anti-format-forcing)
- The palette/fonts/motifs come from `data.concept` (the song's world) — the engine must **not** hardcode
  crimson, pink script, or coffins. Those only appear if a song's concept calls for them.
- Don't impose one construct everywhere; the concept's `construct_bias` + per-section mood decide the mix.
- Quality, not look, is the constant: legible, intentional, synced, restrained — Die-Alone-tier *craft*.

Implementation: `lyrisee_ai.concept()` (Stage 1) → `lyrisee_ai.direct()` (Stage 2, given the concept) →
engine reads `data.concept` (palette/fonts/motifs/bias) so **each song renders in its own world**.
```
