#!/usr/bin/env python3
"""
lyrisee_ai.py — Lyrisee Director (CONCEPT + DIRECTION)

Two-stage LLM art-direction that invents a song-specific visual world and then
directs every line inside it. Explicitly hunts dual meanings / double-entendres
and privileges the unsaid (the gap) when it is stronger than the spoken text.

Providers (first available wins):
  GEMINI_API_KEY | OPENAI_API_KEY | ANTHROPIC_API_KEY | OLLAMA_API_KEY

Public API used by audio_processor.py:
  have_llm() -> bool
  enrich(words) -> dict with repaired words + concept + metaphors + direction cues
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

def have_llm() -> bool:
    return bool(
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OLLAMA_API_KEY")
        or os.environ.get("LYRISEE_LLM")
    )


def _provider() -> str:
    pref = (os.environ.get("LYRISEE_LLM") or "").lower().strip()
    if pref in ("gemini", "openai", "anthropic", "ollama", "claude"):
        if pref == "claude":
            return "anthropic"
        return pref
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OLLAMA_API_KEY"):
        return "ollama"
    return "none"


# ---------------------------------------------------------------------------
# Prompts — dual-meaning + unsaid first
# ---------------------------------------------------------------------------

CONCEPT_SYS = """You are the Auditory-to-Visual Translation Director for Lyrisee.
Your only job is to invent the song's own visual world from first principles.
Never reuse a previous song's palette, motifs, or motion grammar.

Process (do not skip any step):

1. Surface reading: what the song appears to be saying on its face.
2. Undercurrent / dual readings: every significant double-entendre, power dynamic,
   sexual undertone, ironic self-awareness, or emotional contradiction. List the strongest 2–4.
3. The Unsaid: the central question, confession, fear, or invitation that the lyrics
   circle but never resolve. This is usually the strongest visual lever.
4. Derive the world exclusively from the above:
   - palette {bg, ink, accents[]} — mood + genre derived, never defaulted
   - fonts {display, accent, script?} — voice-matched
   - motif_lexicon: only images that actually appear in (or are strongly implied by)
     THIS song's language (word → short form name, e.g. "tire", "cards", "heart")
   - motion: snap | drift | float | crawl | simmer | stick | pulse | etc.
   - restraint: 0.0–1.0
   - construct_bias: list from [embodiment, isolation, kinetic_art, rhyme_scheme, chameleon]
   - visual_priority: almost always "emphasize_unsaid"
   - gap_strategy: negative_space | recursive_loop | withheld_reveal | isolation | slow_decay

Output ONLY valid JSON matching this exact schema (no commentary, no markdown):
{
  "palette": {"bg": "#000000", "ink": "#EDEAE4", "accents": ["#C41E3A"]},
  "fonts": {"display": "Anton", "accent": "Archivo Black", "script": null},
  "motifs": {"example_word": "form_name"},
  "motion": "deliberate_crawl_with_sudden_snaps",
  "restraint": 0.72,
  "mood": "short mood phrase",
  "construct_bias": ["embodiment", "isolation"],
  "dual_readings": {
    "surface": "...",
    "undercurrent": "...",
    "unsaid": "..."
  },
  "visual_priority": "emphasize_unsaid",
  "gap_strategy": "negative_space + recursive_question_isolation"
}"""

DIRECTION_SYS = """You are the line-level Art Director working inside an already-approved concept.
For each line you receive you must:

1. State primary (literal) reading.
2. State secondary / dual reading (if any).
3. State the gap — what is left unsaid or hanging in this specific line.
4. Decide emphasis_target: "spoken" | "gap" | "both". Prefer gap or both when the unsaid is stronger.
5. Choose visual_action: "build_form" | "semantic_motion" | "isolate" | "withhold" | "embody" | "clean".
6. If build_form, pick a form from the concept's motif_lexicon (or null).
7. If semantic_motion, pick a motion_verb that embodies the lyric (crawl, simmer, spill, stick, flow…).
8. Apply hierarchy, register, and restraint strictly inside the given concept.

Return a JSON array of direction objects, one per input line, in the same order.
Each object:
{
  "line_index": 0,
  "primary": "...",
  "secondary": "...",
  "gap": "...",
  "emphasis_target": "gap",
  "visual_action": "build_form",
  "form": "tire" or null,
  "motion_verb": "stick" or null,
  "gap_treatment": "short instruction",
  "register": "display|accent|script",
  "hierarchy": "brief note on which words are charged"
}

Output ONLY the JSON array. No commentary."""

REPAIR_SYS = """You are a precise lyric repair assistant for music transcription.
Given a list of words with timing (from Whisper), correct obvious transcription errors,
restore proper capitalization and punctuation where clear, and keep every original
timing intact. Do not invent new words or change meaning. Return a JSON object:
{"words": [{"text": "...", "start": 0.0, "end": 0.1}, ...]}
Keep the exact same number of words and the same start/end values unless a clear merge
or split is required for correctness. Prefer minimal change."""


# ---------------------------------------------------------------------------
# LLM call abstraction
# ---------------------------------------------------------------------------

def _call_llm(system: str, user: str, temperature: float = 0.4) -> str:
    provider = _provider()
    if provider == "none":
        raise RuntimeError("No LLM API key configured")

    if provider == "gemini":
        return _call_gemini(system, user, temperature)
    if provider == "openai":
        return _call_openai(system, user, temperature)
    if provider == "anthropic":
        return _call_anthropic(system, user, temperature)
    if provider == "ollama":
        return _call_ollama(system, user, temperature)
    raise RuntimeError(f"Unknown provider: {provider}")


def _call_gemini(system: str, user: str, temperature: float) -> str:
    import urllib.request
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_openai(system: str, user: str, temperature: float) -> str:
    import urllib.request
    key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    url = "https://api.openai.com/v1/chat/completions"
    body = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def _call_anthropic(system: str, user: str, temperature: float) -> str:
    import urllib.request
    key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    url = "https://api.anthropic.com/v1/messages"
    body = {
        "model": model,
        "max_tokens": 8192,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return data["content"][0]["text"]


def _call_ollama(system: str, user: str, temperature: float) -> str:
    import urllib.request
    key = os.environ.get("OLLAMA_API_KEY", "")
    model = os.environ.get("OLLAMA_MODEL", "deepseek-v3")
    base = os.environ.get("OLLAMA_HOST", "https://api.ollama.com")
    url = f"{base}/v1/chat/completions"
    body = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def _parse_json(text: str) -> Any:
    text = text.strip()
    # strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # try to find the first { or [
        m = re.search(r"[\{\[]", text)
        if m:
            try:
                return json.loads(text[m.start():])
            except json.JSONDecodeError:
                pass
        raise


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def _words_to_lyrics(words: list[dict]) -> str:
    return " ".join(w.get("text", "") for w in words)


def _build_lines_simple(words: list[dict], gap: float = 0.55, max_words: int = 10) -> list[dict]:
    """Lightweight line grouping for the Director (mirrors intent_director logic)."""
    lines, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gp = (nxt["start"] - w["end"]) if nxt else 999
        ends = bool(re.search(r"[.!?…]$", w.get("text", "")))
        if not nxt or gp > gap or len(cur) >= max_words or (ends and len(cur) >= 3):
            lines.append({
                "idx": cur[:],
                "start": words[cur[0]]["start"],
                "end": words[cur[-1]]["end"],
                "text": " ".join(words[k]["text"] for k in cur),
            })
            cur = []
    return lines


def concept(lyrics: str, extra: str = "") -> dict:
    """Stage 1 — invent the song's visual world."""
    user = f"Full lyrics:\n\n{lyrics}\n\n"
    if extra:
        user += f"Additional context:\n{extra}\n\n"
    user += "Produce the concept JSON now."
    raw = _call_llm(CONCEPT_SYS, user, temperature=0.5)
    return _parse_json(raw)


def direct(lines: list[dict], concept_obj: dict) -> list[dict]:
    """Stage 2 — per-line direction inside the concept."""
    # Keep payload reasonable
    payload_lines = [{"index": i, "text": ln["text"]} for i, ln in enumerate(lines)]
    user = (
        "CONCEPT (do not deviate):\n"
        + json.dumps(concept_obj, ensure_ascii=False)
        + "\n\nLINES TO DIRECT:\n"
        + json.dumps(payload_lines, ensure_ascii=False)
        + "\n\nReturn the direction array now."
    )
    raw = _call_llm(DIRECTION_SYS, user, temperature=0.35)
    result = _parse_json(raw)
    if isinstance(result, dict) and "directions" in result:
        result = result["directions"]
    if not isinstance(result, list):
        raise ValueError("Direction response was not a list")
    return result


def repair_words(words: list[dict]) -> list[dict]:
    """Light transcription cleanup. Falls back to original on any failure."""
    try:
        payload = [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in words]
        user = "Transcribed words:\n" + json.dumps(payload, ensure_ascii=False)
        raw = _call_llm(REPAIR_SYS, user, temperature=0.1)
        data = _parse_json(raw)
        repaired = data.get("words", data) if isinstance(data, dict) else data
        if not isinstance(repaired, list) or len(repaired) < len(words) * 0.7:
            return words
        # merge back timings if the model dropped them
        out = []
        for i, rw in enumerate(repaired):
            base = words[min(i, len(words) - 1)]
            out.append({
                "text": rw.get("text", base["text"]),
                "start": float(rw.get("start", base["start"])),
                "end": float(rw.get("end", base["end"])),
            })
        return out
    except Exception as e:
        print(f"[ai] repair skipped ({e})")
        return words


def enrich(words: list[dict]) -> dict:
    """
    Full Director pass used by audio_processor.py.

    Returns:
      {
        "words": [...],          # possibly repaired
        "concept": {...},        # Stage-1 world
        "metaphors": [...],      # line-level direction cues (compat)
        "directions": [...],     # full Stage-2 objects
        "rhyme_families": null   # left for rhyme_engine
      }
    """
    if not have_llm():
        return {"words": words}

    print(f"[ai] provider={_provider()} — running CONCEPT + DIRECTION …")

    # 1. optional light repair
    words = repair_words(words)

    lyrics = _words_to_lyrics(words)
    lines = _build_lines_simple(words)

    # 2. CONCEPT
    try:
        concept_obj = concept(lyrics)
        print(f"[ai] concept ready — mood={concept_obj.get('mood')} | priority={concept_obj.get('visual_priority')}")
    except Exception as e:
        print(f"[ai] concept failed ({e}); continuing without")
        concept_obj = None

    # 3. DIRECTION (batched if many lines)
    directions = []
    metaphors = []  # backward-compat list of short cues
    if concept_obj and lines:
        try:
            # batch in chunks of ~18 lines to stay inside context limits
            batch_size = 18
            for start in range(0, len(lines), batch_size):
                chunk = lines[start:start + batch_size]
                chunk_dirs = direct(chunk, concept_obj)
                for d in chunk_dirs:
                    # re-index relative to full list
                    if "line_index" in d:
                        d["line_index"] = start + int(d["line_index"])
                    directions.append(d)
                    # compact metaphor cue for older consumers
                    metaphors.append({
                        "line": chunk[d.get("line_index", 0) - start]["text"] if chunk else "",
                        "action": d.get("visual_action"),
                        "form": d.get("form"),
                        "emphasis": d.get("emphasis_target"),
                        "gap": d.get("gap"),
                    })
            print(f"[ai] directed {len(directions)} lines")
        except Exception as e:
            print(f"[ai] direction failed ({e})")

    return {
        "words": words,
        "concept": concept_obj,
        "metaphors": metaphors,
        "directions": directions,
        "rhyme_families": None,
    }


# ---------------------------------------------------------------------------
# CLI for quick testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python lyrisee_ai.py lyric_data.json")
        sys.exit(1)
    data = json.load(open(sys.argv[1]))
    result = enrich(data["words"])
    out = {**data, **{k: v for k, v in result.items() if v is not None}}
    dest = sys.argv[2] if len(sys.argv) > 2 else "lyric_data_directed.json"
    json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("wrote", dest)
