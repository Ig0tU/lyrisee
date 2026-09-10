#!/usr/bin/env python3
"""lyrisee_ai.py — Director. Ollama = Cloud only (https://ollama.com). Local = LM Studio."""
from __future__ import annotations
import json, os, re, sys
from typing import Any

def have_llm() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OLLAMA_API_KEY")
                or os.environ.get("LYRISEE_LLM"))

def _provider() -> str:
    pref = (os.environ.get("LYRISEE_LLM") or "").lower().strip()
    if pref in ("gemini", "openai", "anthropic", "ollama", "claude"):
        return "anthropic" if pref == "claude" else pref
    for k, v in (("GEMINI_API_KEY", "gemini"), ("OPENAI_API_KEY", "openai"),
                 ("ANTHROPIC_API_KEY", "anthropic"), ("OLLAMA_API_KEY", "ollama")):
        if os.environ.get(k):
            return v
    return "none"

LAYOUTS = ["row", "split", "ascend", "fall", "stack", "spiral", "path", "cage", "cagebars"]
MOTIFS = ["ring", "heart", "staff", "card", "moon", "boot", "car", "figure",
          "bars", "ladder", "coin", "ring_split"]

CONCEPT_SYS = """You are Lyrisee's visual Director. Build ONE song-specific world. Do not recycle a previous song's palette or motifs.

Reasoning order (required — skip any step and the direction stage collapses):
1) SURFACE — what the lyrics literally say
2) UNDERCURRENT — double meanings, power, irony, desire, self-sabotage
3) THE UNSAID — the question / confession / invitation the song circles but never answers
4) Only then: palette, fonts, motion, restraint, motif map

HOUSE STYLE: type IS the object. Stroke line-art only. No emoji, no Unicode icons.
motifs maps THIS song's imagery → engine shapes, e.g. {"wheel":"ring","vow":"heart","climb":"ladder"}.
Allowed motif values ONLY: """ + ", ".join(MOTIFS) + """

HARD RULES:
- dual_readings.unsaid must be a concrete sentence (not "ambiguity" or "tension").
- accents: 1–2 hex colors that fit THIS song, not default red.
- restraint 0.55–0.9 (higher = fewer motifs, more negative space).
- Intimate/confessional → gap_strategy "negative_space" or "withhold_motif".
- Confrontational → "clash_layout" or "hard_hits".

Output ONLY JSON:
{"palette":{"bg":"#000000","ink":"#EDEAE4","accents":["#C41E3A"]},
 "fonts":{"display":"Anton","accent":"Archivo Black"},
 "motifs":{"<image word>":"<engine motif>"},
 "motion":"<one sentence motion grammar>",
 "restraint":0.72,
 "mood":"<3-6 word mood>",
 "construct_bias":["embodiment"],
 "dual_readings":{"surface":"...","undercurrent":"...","unsaid":"..."},
 "visual_priority":"emphasize_unsaid",
 "gap_strategy":"negative_space"}"""

DIRECTION_SYS = """You are the line-level Art Director. You stage TYPE as meaning. You do not illustrate nouns.

Closed vocabularies only:
layout ∈ """ + ", ".join(LAYOUTS) + """
  row=neutral (use sparingly) · split=opposition · ascend=rising · fall=collapse
  stack=accumulation · spiral=obsession · path=journey · cage=trapped · cagebars=prison bars as words
motif ∈ """ + ", ".join(MOTIFS) + """  (omit if the line earns no object)

For EACH line return one object:
{"line_index":0,"layout":"cage","motif":"bars","on":"<verbatim word that earns the motif>",
 "hit":"<ONE charged word>",
 "emphasis":["..."],"script":["..."],"glow":["..."],
 "rotate":{},
 "surface":"<≤12 words>","undercurrent":"<≤12 words>","gap":"<the unsaid for THIS line>"}

QUALITY RULES (breaking these = bad direction):
1. Direct the UNDERCURRENT / UNSAID from the concept, not the surface nouns.
2. At most one "hit" per line; every named word must appear VERBATIM in that line.
3. motif only when the line has a real earned image — prefer omit over decoration.
4. Do NOT default to layout "row". Across a batch, vary layouts; never three identical layouts in a row.
5. Do NOT spam the same motif (heart/moon/ring) across consecutive lines.
6. Quiet / intimate lines → more script + omit motif. Confrontational → hit + harder layout.
7. If concept.visual_priority is emphasize_unsaid, put the real charge in "gap", not in motif.

BAD (never do this): every line {"layout":"row","motif":"heart","hit":"love"}
GOOD: a verse that moves row → split → cage → fall as the emotional stakes change.

Output ONLY a JSON array (or {"directions":[...]}). No prose."""

REPAIR_SYS = """Repair Whisper transcription lightly. Keep timings. Return JSON {\"words\":[{\"text\":\"...\",\"start\":0,\"end\":0}]}."""

def _call_llm(system: str, user: str, temperature: float = 0.4) -> str:
    p = _provider()
    if p == "none":
        raise RuntimeError("No LLM key")
    return {"gemini": _call_gemini, "openai": _call_openai, "anthropic": _call_anthropic,
            "ollama": _call_ollama}[p](system, user, temperature)

def _call_gemini(system, user, temperature):
    import urllib.request
    key, model = os.environ["GEMINI_API_KEY"], os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {"system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"]

def _call_openai(system, user, temperature):
    import urllib.request
    key = os.environ.get("OPENAI_API_KEY") or "lm-studio"
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    base = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    body = {"model": model, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if "openai.com" in base:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]

def _call_anthropic(system, user, temperature):
    import urllib.request
    key, model = os.environ["ANTHROPIC_API_KEY"], os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    body = {"model": model, "max_tokens": 8192, "temperature": temperature, "system": system,
            "messages": [{"role": "user", "content": user}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["content"][0]["text"]

OLLAMA_FALLBACKS = ["gpt-oss:20b", "gpt-oss:120b", "qwen3-coder:480b-cloud",
                    "deepseek-v3.1:671b", "kimi-k2:1t-cloud"]
_OLLAMA_MODEL_OK = None

def _ollama_base():
    return (os.environ.get("OLLAMA_HOST") or "https://ollama.com").rstrip("/")

def _ollama_once(model, key, system, user, temperature, timeout=180):
    import urllib.request
    url = f"{_ollama_base()}/api/chat"
    body = {"model": model, "messages": [{"role": "system", "content": system},
            {"role": "user", "content": user}], "stream": False,
            "options": {"temperature": temperature}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
        return data["message"]["content"]

def _call_ollama(system, user, temperature):
    global _OLLAMA_MODEL_OK
    key = (os.environ.get("OLLAMA_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Ollama Cloud requires OLLAMA_API_KEY from https://ollama.com/settings/keys")
    configured = os.environ.get("OLLAMA_MODEL", "gpt-oss:120b")
    order = [_OLLAMA_MODEL_OK] if _OLLAMA_MODEL_OK else [configured] + [
        m for m in OLLAMA_FALLBACKS if m != configured]
    last = None
    for model in order:
        try:
            out = _ollama_once(model, key, system, user, temperature)
            if model != _OLLAMA_MODEL_OK:
                if model != configured:
                    print(f"[ai] '{configured}' unavailable on this key — using '{model}' instead")
                _OLLAMA_MODEL_OK = model
            return out
        except RuntimeError as e:
            last = e
            if not re.match(r"HTTP (402|403|404)", str(e)):
                raise
            print(f"[ai] ollama model '{model}' unavailable ({str(e)[:80]}); trying next")
        except Exception as e:
            last = e
            print(f"[ai] ollama model '{model}' failed ({str(e)[:80]}); trying next")
    raise RuntimeError(f"Ollama Cloud: no available model for this key. Last error — {last}")

def _parse_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"[\{\[]", text)
        if m:
            return json.loads(text[m.start():])
        raise

def _words_to_lyrics(words):
    return " ".join(w.get("text", "") for w in words)

def _build_lines_simple(words, gap=0.55, max_words=10):
    lines, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gp = (nxt["start"] - w["end"]) if nxt else 999
        ends = bool(re.search(r"[.!?…]$", w.get("text", "")))
        if not nxt or gp > gap or len(cur) >= max_words or (ends and len(cur) >= 3):
            lines.append({"idx": cur[:], "start": words[cur[0]]["start"], "end": words[cur[-1]]["end"],
                          "text": " ".join(words[k]["text"] for k in cur)})
            cur = []
    return lines

def _norm(t):
    return re.sub(r"[^\w']+", "", (t or "").lower())

def _clean_concept(c):
    if not isinstance(c, dict):
        return c
    motifs = c.get("motifs") or {}
    if isinstance(motifs, dict):
        c["motifs"] = {k: v for k, v in motifs.items() if v in MOTIFS}
    return c

def _apply_direction(words, line, d, metaphors, scenes):
    idx = line["idx"]
    start = line["start"]
    layout = d.get("layout") or d.get("metaphor")
    if layout not in LAYOUTS:
        layout = None
    motif = d.get("motif") if d.get("motif") in MOTIFS else None
    if layout:
        metaphors.append({"start": start, "metaphor": layout, "line": line["text"],
                          "gap": d.get("gap"), "undercurrent": d.get("undercurrent")})
    rotate = {k: v for k, v in (d.get("rotate") or {}).items()
              if isinstance(v, (int, float))} if isinstance(d.get("rotate"), dict) else {}
    if motif or rotate:
        scenes.append({"start": start, "metaphor": layout or "row", "motif": motif,
                       "on": d.get("on") or "", "rotate": rotate, "breakAt": 0.7,
                       "figure": "figure" if layout in ("cage", "cagebars") else None})
    def names(key):
        v = d.get(key)
        return {_norm(x) for x in v if isinstance(x, str)} if isinstance(v, list) else set()
    emph, script, glow = names("emphasis"), names("script"), names("glow")
    hit = _norm(d.get("hit")) if isinstance(d.get("hit"), str) else None
    for wi in idx:
        w = words[wi]
        n = _norm(w.get("text", ""))
        if not n:
            continue
        dirn = w.get("dir") or {}
        if n in emph:
            dirn["emphasis"] = 3
        if n in script:
            dirn["register"] = "script"
        if n in glow:
            dirn["glow"] = True
        if hit and n == hit:
            dirn["hit"] = True
            dirn.setdefault("emphasis", 3)
        if dirn:
            w["dir"] = dirn

def _concept_is_weak(c):
    if not isinstance(c, dict):
        return True
    dr = c.get("dual_readings") or {}
    unsaid = (dr.get("unsaid") or "").strip().lower()
    weak_unsaid = (not unsaid) or unsaid in {
        "tension", "ambiguity", "uncertainty", "the unsaid", "n/a", "none", "..."
    }
    motifs = c.get("motifs") or {}
    mood = (c.get("mood") or "").strip().lower()
    weak_mood = (not mood) or mood in {"emotional", "dramatic", "intense", "sad", "happy"}
    return weak_unsaid or (not motifs and weak_mood)

def concept(lyrics, extra=""):
    user = f"Full lyrics:\n\n{lyrics}\n\n"
    if extra:
        user += f"Context:\n{extra}\n\n"
    user += (
        "Produce the concept JSON now. "
        "dual_readings.unsaid MUST be a concrete sentence about what the song refuses to say."
    )
    obj = _parse_json(_call_llm(CONCEPT_SYS, user, 0.55))
    if _concept_is_weak(obj):
        print("[ai] concept weak — retrying with sharper unsaid requirement")
        retry = user + (
            "\n\nYour previous answer was too generic. "
            "Name the specific confession or question the singer will not speak. "
            "Fill motifs with at least 2 mappings from THIS lyric's imagery."
        )
        try:
            obj2 = _parse_json(_call_llm(CONCEPT_SYS, retry, 0.6))
            if not _concept_is_weak(obj2):
                obj = obj2
        except Exception as e:
            print(f"[ai] concept retry failed ({e})")
    return obj

def _directions_are_weak(dirs):
    if not dirs or not isinstance(dirs, list):
        return True
    layouts = [d.get("layout") or "row" for d in dirs]
    motifs = [d.get("motif") for d in dirs if d.get("motif")]
    row_ratio = sum(1 for x in layouts if x == "row") / max(len(layouts), 1)
    streak = 1
    bad_streak = False
    for i in range(1, len(layouts)):
        if layouts[i] == layouts[i - 1]:
            streak += 1
            if streak >= 3:
                bad_streak = True
                break
        else:
            streak = 1
    motif_dom = False
    if motifs:
        from collections import Counter
        top = Counter(motifs).most_common(1)[0][1]
        motif_dom = top >= max(3, len(dirs) * 0.5)
    gaps = sum(1 for d in dirs if (d.get("gap") or d.get("undercurrent") or "").strip())
    gap_ratio = gaps / max(len(dirs), 1)
    return row_ratio > 0.55 or bad_streak or motif_dom or gap_ratio < 0.3

def direct(lines, concept_obj):
    payload = [{"index": i, "text": ln["text"]} for i, ln in enumerate(lines)]
    slim = {
        "mood": concept_obj.get("mood"),
        "restraint": concept_obj.get("restraint"),
        "visual_priority": concept_obj.get("visual_priority"),
        "gap_strategy": concept_obj.get("gap_strategy"),
        "dual_readings": concept_obj.get("dual_readings"),
        "motifs": concept_obj.get("motifs"),
        "motion": concept_obj.get("motion"),
    }
    user = (
        "CONCEPT (obey dual_readings.unsaid and gap_strategy):\n"
        + json.dumps(slim, ensure_ascii=False)
        + "\n\nLINES:\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nReturn a direction object per line. Vary layouts. Prefer omit motif over decoration."
    )
    result = _parse_json(_call_llm(DIRECTION_SYS, user, 0.4))
    if isinstance(result, dict) and "directions" in result:
        result = result["directions"]
    if not isinstance(result, list):
        raise ValueError("Direction response was not a list")
    if _directions_are_weak(result):
        print("[ai] directions weak (row spam / motif spam / no gaps) — one retry")
        critique = (
            user
            + "\n\nCRITIQUE of a bad pass: too many layout=row, repeated motifs, missing gap/undercurrent. "
            "Redo the array. Change layout when stakes change. Put the charge in gap + hit, not motif spam."
        )
        try:
            result2 = _parse_json(_call_llm(DIRECTION_SYS, critique, 0.5))
            if isinstance(result2, dict) and "directions" in result2:
                result2 = result2["directions"]
            if isinstance(result2, list) and not _directions_are_weak(result2):
                result = result2
            elif isinstance(result2, list):
                result = result2 if len(set(d.get("layout") for d in result2)) > len(
                    set(d.get("layout") for d in result)
                ) else result
        except Exception as e:
            print(f"[ai] direction retry failed ({e})")
    return result

def repair_words(words):
    try:
        payload = [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in words]
        raw = _call_llm(REPAIR_SYS, "Transcribed words:\n" + json.dumps(payload), 0.1)
        data = _parse_json(raw)
        repaired = data.get("words", data) if isinstance(data, dict) else data
        if not isinstance(repaired, list) or len(repaired) < len(words) * 0.7:
            return words
        out = []
        for i, rw in enumerate(repaired):
            base = words[min(i, len(words) - 1)]
            out.append({"text": rw.get("text", base["text"]), "start": float(rw.get("start", base["start"])),
                        "end": float(rw.get("end", base["end"]))})
        return out
    except Exception as e:
        print(f"[ai] repair skipped ({e})")
        return words

def enrich(words):
    if not have_llm():
        return {"words": words}
    print(f"[ai] provider={_provider()} — CONCEPT + DIRECTION (Ollama=Cloud)")
    words = repair_words(words)
    lyrics = _words_to_lyrics(words)
    lines = _build_lines_simple(words)
    try:
        concept_obj = concept(lyrics)
        print(f"[ai] concept ready — mood={concept_obj.get('mood')} | priority={concept_obj.get('visual_priority')}")
    except Exception as e:
        print(f"[ai] concept failed ({e})")
        concept_obj = None
    directions, metaphors, scenes = [], [], []
    if concept_obj and lines:
        try:
            batch = 8
            for start in range(0, len(lines), batch):
                chunk = lines[start:start + batch]
                for d in direct(chunk, concept_obj):
                    li = start + int(d.get("line_index", 0) or 0)
                    if not 0 <= li < len(lines):
                        continue
                    d["line_index"] = li
                    directions.append(d)
                    _apply_direction(words, lines[li], d, metaphors, scenes)
            print(f"[ai] directed {len(directions)} lines -> "
                  f"{len(metaphors)} layout cues, {len(scenes)} drawn scenes")
        except Exception as e:
            print(f"[ai] direction failed ({e})")
    return {"words": words, "concept": _clean_concept(concept_obj), "metaphors": metaphors,
            "scenes": scenes, "directions": directions, "rhyme_families": None}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python lyrisee_ai.py lyric_data.json"); sys.exit(1)
    data = json.load(open(sys.argv[1]))
    result = enrich(data["words"])
    out = {**data, **{k: v for k, v in result.items() if v is not None}}
    dest = sys.argv[2] if len(sys.argv) > 2 else "lyric_data_directed.json"
    json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("wrote", dest)
