#!/usr/bin/env python3
"""
audio_processor.py — Lyrisee audio-intelligence pipeline.

Turns an audio file into the engine's `lyric_data.json`, with the part that makes
sync tight: **word-level** timestamps from stable-ts (not interpolated).

Pipeline:
  1. (optional) demucs       -> isolate vocals for cleaner ASR        [--separate]
  2. stable-ts / Whisper     -> WORD-LEVEL transcription (text, start, end)
  3. librosa                 -> beat tracking (beats[]) for beat-synced motion
  4. spaCy                   -> part-of-speech per word
  5. intent_director         -> sections + intent -> arrangement[]
  -> writes lyric_data.json  { words:[{text,start,end,pos}], beats:[...], arrangement:[...] }

Requirements (already in requirements.txt): stable-ts (stable_whisper), librosa,
spacy (+ `python -m spacy download en_core_web_sm`), torch, demucs (optional), numpy.

Usage:
    python3 audio_processor.py path/to/song.mp3 [-o public/lyric_data.json]
                               [--model base] [--separate] [--no-arrange]
"""
from __future__ import annotations
import argparse, json, os, re, sys, subprocess, tempfile

# Heavy deps are imported lazily inside functions so this file can be read/inspected
# (and --help shown) without the full ML stack installed.

FUNCTION_FALLBACK = set(
    "a an the of to in on at for and or but nor so yet as if then than that this these those "
    "i you he she it we they me him her us them my your his its our their is am are was were be "
    "been being do does did have has had will would can could should may might must not no".split()
)


def separate_vocals(audio_path: str) -> str:
    """Run demucs and return the path to the isolated vocals stem (or original on failure)."""
    try:
        out = tempfile.mkdtemp(prefix="lyrisee_demucs_")
        subprocess.run(
            [sys.executable, "-m", "demucs", "--two-stems", "vocals", "-o", out, audio_path],
            check=True,
        )
        stem = os.path.splitext(os.path.basename(audio_path))[0]
        for root, _dirs, files in os.walk(out):
            for f in files:
                if f.lower().startswith("vocals"):
                    print(f"[demucs] vocals -> {os.path.join(root, f)}")
                    return os.path.join(root, f)
    except Exception as e:  # noqa: BLE001
        print(f"[demucs] skipped ({e}); transcribing original audio")
    return audio_path


def transcribe_words(audio_path: str, model_size: str = "base"):
    """Return word dicts [{text,start,end}] with WORD-LEVEL timing via stable-ts."""
    import stable_whisper  # type: ignore

    print(f"[asr] loading stable-ts model '{model_size}' …")
    model = stable_whisper.load_model(model_size)
    print("[asr] transcribing (word timestamps) …")
    result = model.transcribe(audio_path, vad=True, regroup=True)
    words = []
    for seg in result.segments:
        for w in getattr(seg, "words", []) or []:
            txt = (w.word or "").strip()
            if not txt:
                continue
            s = float(w.start); e = float(w.end)
            if e <= s:
                e = s + 0.12
            words.append({"text": txt, "start": round(s, 3), "end": round(e, 3)})
    words.sort(key=lambda x: x["start"])
    print(f"[asr] {len(words)} words")
    return words


def detect_beats(audio_path: str):
    """Return beat timestamps (seconds) via librosa, plus tempo (bpm)."""
    import librosa  # type: ignore

    print("[beats] loading audio + tracking beats …")
    y, sr = librosa.load(audio_path, mono=True)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
    beats = [round(float(t), 3) for t in librosa.frames_to_time(frames, sr=sr)]
    print(f"[beats] {len(beats)} beats @ ~{float(tempo):.0f} BPM")
    return beats, float(tempo)


def tag_pos(words):
    """Attach spaCy POS to each word by aligning whisper words to spaCy tokens in order."""
    try:
        import spacy  # type: ignore
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("[pos] en_core_web_sm not found; run: python -m spacy download en_core_web_sm")
            raise RuntimeError("missing spaCy model")
        text = " ".join(w["text"] for w in words)
        doc = nlp(text)
        toks = [t for t in doc if not t.is_space]
        ti = 0
        for w in words:
            key = re.sub(r"[^a-z']", "", w["text"].lower())
            pos = "X"
            # advance through spaCy tokens to find the matching word
            scan = ti
            while scan < len(toks) and scan < ti + 6:
                tk = re.sub(r"[^a-z']", "", toks[scan].text.lower())
                if tk and (tk == key or key.startswith(tk) or tk.startswith(key)):
                    pos = toks[scan].pos_
                    ti = scan + 1
                    break
                scan += 1
            else:
                if ti < len(toks):
                    pos = toks[ti].pos_; ti += 1
            w["pos"] = pos
        print("[pos] spaCy tags applied")
    except Exception as e:  # noqa: BLE001
        print(f"[pos] spaCy unavailable ({e}); using lightweight heuristic")
        for w in words:
            lw = re.sub(r"[^a-z']", "", w["text"].lower())
            if not lw:
                w["pos"] = "X"
            elif lw in FUNCTION_FALLBACK:
                w["pos"] = "ADP"
            elif re.search(r"(ing|ed)$", lw):
                w["pos"] = "VERB"
            elif re.search(r"ly$", lw):
                w["pos"] = "ADV"
            elif w["text"][:1].isupper():
                w["pos"] = "PROPN"
            else:
                w["pos"] = "NOUN"
    return words


def main():
    ap = argparse.ArgumentParser(description="Lyrisee audio -> lyric_data.json (word-level sync)")
    ap.add_argument("audio", help="input audio file (mp3/wav/m4a)")
    ap.add_argument("-o", "--out", default="lyric_data.json", help="output JSON path")
    ap.add_argument("--model", default="base", help="Whisper size: tiny|base|small|medium|large")
    ap.add_argument("--separate", action="store_true", help="run demucs to isolate vocals first")
    ap.add_argument("--no-arrange", action="store_true", help="skip the intent-driven arrangement")
    ap.add_argument("--no-ai", action="store_true", help="skip the LLM lyric-repair + art-direction stage")
    args = ap.parse_args()

    if not os.path.isfile(args.audio):
        sys.exit(f"audio not found: {args.audio}")

    asr_input = separate_vocals(args.audio) if args.separate else args.audio
    words = transcribe_words(asr_input, args.model)
    if not words:
        sys.exit("no words transcribed")
    tag_pos(words)

    # --- Lyrisee AI stage: context lyric repair + rhyme + word-art art-direction (CORE app logic) ---
    ai_metaphors = ai_rhymes = None
    if not args.no_ai:
        try:
            import lyrisee_ai
            if lyrisee_ai.have_llm():
                enriched = lyrisee_ai.enrich(words)
                words = enriched.get("words", words)
                tag_pos(words)                       # re-tag POS on the corrected words
                ai_metaphors = enriched.get("metaphors")
                ai_rhymes = enriched.get("rhyme_families")
                print(f"[ai] repaired + art-directed -> {len(words)} words, "
                      f"{len(ai_metaphors or [])} line cues, {len(ai_rhymes or [])} rhyme families")
            else:
                print("[ai] no LLM key set; skipping repair/art-direction "
                      "(set ANTHROPIC_API_KEY | OPENAI_API_KEY | GEMINI_API_KEY)")
        except Exception as e:  # noqa: BLE001
            print(f"[ai] skipped ({e})")

    try:
        beats, _bpm = detect_beats(args.audio)
    except Exception as e:  # noqa: BLE001
        print(f"[beats] skipped ({e})"); beats = []

    # true rhyme detection (CMUdict) -> per-word rhyme group ids + palette (the emNoFavors color map)
    rhyme_pal = None
    try:
        import rhyme_engine
        g, rhyme_pal, fams = rhyme_engine.analyze(words)
        for i, w in enumerate(words):
            w["rhyme"] = g[i]
        if not ai_rhymes:
            ai_rhymes = fams
        print(f"[rhyme] {len(fams)} true rhyme families, {sum(1 for x in g if x>=0)} words colored")
    except Exception as e:  # noqa: BLE001
        print(f"[rhyme] skipped ({e})")

    out = {"words": words, "beats": beats}
    if ai_metaphors: out["metaphors"] = ai_metaphors
    if ai_rhymes: out["rhyme_families"] = ai_rhymes
    if rhyme_pal: out["rhyme_palette"] = rhyme_pal

    if not args.no_arrange:
        try:
            from intent_director import build_arrangement
            arrangement, sections = build_arrangement(words)
            out["arrangement"] = arrangement
            print(f"[arrange] {len(sections)} sections -> {len(arrangement)} construct cues")
        except Exception as e:  # noqa: BLE001
            print(f"[arrange] skipped ({e})")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print(f"[done] wrote {args.out}  ({len(words)} words, {len(beats)} beats)")


if __name__ == "__main__":
    main()
