#!/usr/bin/env python3
"""lyrisee_ai.py — Director. Custom stroke clipart + type-as-form."""
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

CONCEPT_SYS = """You are Lyrisee's visual Director. Build ONE song-specific world.

Reasoning order:
1) SURFACE 2) UNDERCURRENT 3) THE UNSAID (concrete sentence) 4) then palette/motion/motifs

HOUSE STYLE: type can BE the object; OR the stage may show simple stroke CLIPART of the intention.
No emoji. Custom per-line drawings are first-class (paths), stock motifs are shortcuts only.
Allowed stock motif values: """ + ", ".join(MOTIFS) + """

Output ONLY JSON:
{"palette":{"bg":"#000000","ink":"#EDEAE4","accents":["#C41E3A"]},
 "fonts":{"display":"Anton","accent":"Archivo Black"},
 "motifs":{"<image word>":"<engine motif>"},
 "motion":"...","restraint":0.72,"mood":"...",
 "construct_bias":["embodiment"],
 "dual_readings":{"surface":"...","undercurrent":"...","unsaid":"..."},
 "visual_priority":"emphasize_unsaid","gap_strategy":"negative_space"}"""

DIRECTION_SYS = """You are Lyrisee's line Art Director. Insanely high adhesion to intention:
visualize nuance and undercurrent, not dictionary nouns.

Three tools per line (combine when it serves meaning):
1) layout — words as form: """ + ", ".join(LAYOUTS) + """
2) motif — optional stock clipart shortcut: """ + ", ".join(MOTIFS) + """
3) paths — CUSTOM stroke clipart: array of SVG path `d` strings, viewBox 0 0 200 200.
   Simple line-art, 1–6 paths, no fill. Invent when stock motifs cannot carry the INTENTION.
   Draw the unsaid/undercurrent. Example: unspoken goodbye → door gap + incomplete circle.

Per line:
{"line_index":0,"layout":"split","motif":null,
 "paths":["M40 100 H160","M160 100 L140 80","M160 100 L140 120"],
 "on":"<word>","hit":"<ONE charged word>",
 "emphasis":[],"script":[],"glow":[],"rotate":{},
 "surface":"≤12 words","undercurrent":"≤12 words","gap":"<unsaid>"}

RULES:
- Prefer custom paths over stock motif when the idea is specific.
- Omit drawing when silence is stronger.
- Vary layouts; no heart/moon/ring spam; no three identical layouts in a row.
- Every named word must appear verbatim in the line.
Output ONLY a JSON array (or {"directions":[...]})."""

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
    body = {"model": model, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if "openai.com" in base:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
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

OLLAMA_FALLBACKS = ["deepseek-v3", "llama3.3", "qwen2.5", "deepseek-r1", "mistral", "gemma2"]
_OLLAMA_MODEL_OK = None

def _ollama_base():
    return (os.environ.get("OLLAMA_HOST") or "https://ollama.com").rstrip("/")

def _ollama_once(model, key, system, user, temperature, timeout=180):
    import urllib.request
    body = {"model": model, "messages": [{"role": "system", "content": system},
            {"role": "user", "content": user}], "stream": False, "options": {"temperature": temperature}}
    req = urllib.request.Request(f"{_ollama_base()}/api/chat", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"]

def _call_ollama(system, user, temperature):
    global _OLLAMA_MODEL_OK
    key = (os.environ.get("OLLAMA_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Ollama Cloud requires OLLAMA_API_KEY")
    configured = os.environ.get("OLLAMA_MODEL", "deepseek-v3")
    order = [_OLLAMA_MODEL_OK] if _OLLAMA_MODEL_OK else [configured] + [m for m in OLLAMA_FALLBACKS if m != configured]
    last = None
    for model in order:
        try:
            out = _ollama_once(model, key, system, user, temperature)
            _OLLAMA_MODEL_OK = model
            return out
        except Exception as e:
            last = e
            if not re.match(r"HTTP (402|403|404)", str(e)):
                print(f"[ai] ollama '{model}' failed ({str(e)[:80]})")
            continue
    raise RuntimeError(f"Ollama Cloud: no model. Last — {last}")

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
    paths = d.get("paths") or d.get("svg_paths") or []
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list):
        paths = []
    safe = []
    for pr in paths:
        if not isinstance(pr, str):
            continue
        pr = pr.strip()
        if pr and re.match(r"^[MmLlHhVvCcSsQqTtAaZz0-9.,\s\-eE]+$", pr):
            safe.append(pr)
        if len(safe) >= 8:
            break
    paths = safe
    if layout:
        metaphors.append({"start": start, "metaphor": layout, "line": line["text"],
                          "gap": d.get("gap"), "undercurrent": d.get("undercurrent")})
    rotate = {k: v for k, v in (d.get("rotate") or {}).items()
              if isinstance(v, (int, float))} if isinstance(d.get("rotate"), dict) else {}
    if motif or rotate or paths:
        scenes.append({"start": start, "metaphor": layout or "row", "motif": motif,
                       "paths": paths or None,
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
        if n in emph: dirn["emphasis"] = 3
        if n in script: dirn["register"] = "script"
        if n in glow: dirn["glow"] = True
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
    weak_unsaid = (not unsaid) or unsaid in {"tension", "ambiguity", "uncertainty", "the unsaid", "n/a", "none", "..."}
    motifs = c.get("motifs") or {}
    mood = (c.get("mood") or "").strip().lower()
    weak_mood = (not mood) or mood in {"emotional", "dramatic", "intense", "sad", "happy"}
    return weak_unsaid or (not motifs and weak_mood)

def concept(lyrics, extra=""):
    user = f"Full lyrics:\n\n{lyrics}\n\n"
    if extra:
        user += f"Context:\n{extra}\n\n"
    user += "Produce concept JSON. dual_readings.unsaid MUST be a concrete sentence."
    obj = _parse_json(_call_llm(CONCEPT_SYS, user, 0.55))
    if _concept_is_weak(obj):
        print("[ai] concept weak — retry")
        try:
            obj2 = _parse_json(_call_llm(CONCEPT_SYS, user + "\n\nPrevious was generic. Name the specific unsaid. 2+ motif mappings.", 0.6))
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
    has_custom = sum(1 for d in dirs if d.get("paths"))
    row_ratio = sum(1 for x in layouts if x == "row") / max(len(layouts), 1)
    streak, bad_streak = 1, False
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
    return (row_ratio > 0.55 and has_custom < len(dirs) * 0.25) or bad_streak or motif_dom or gap_ratio < 0.3

def direct(lines, concept_obj):
    payload = [{"index": i, "text": ln["text"]} for i, ln in enumerate(lines)]
    slim = {k: concept_obj.get(k) for k in
            ("mood", "restraint", "visual_priority", "gap_strategy", "dual_readings", "motifs", "motion")}
    user = ("CONCEPT:\n" + json.dumps(slim, ensure_ascii=False) +
            "\n\nLINES:\n" + json.dumps(payload, ensure_ascii=False) +
            "\n\nPrefer custom paths for specific intention. Vary layouts.")
    result = _parse_json(_call_llm(DIRECTION_SYS, user, 0.45))
    if isinstance(result, dict) and "directions" in result:
        result = result["directions"]
    if not isinstance(result, list):
        raise ValueError("Direction response was not a list")
    if _directions_are_weak(result):
        print("[ai] directions weak — retry")
        try:
            result2 = _parse_json(_call_llm(DIRECTION_SYS, user +
                "\n\nCRITIQUE: too generic. Add custom paths for intention; vary layouts; fill gap.", 0.55))
            if isinstance(result2, dict) and "directions" in result2:
                result2 = result2["directions"]
            if isinstance(result2, list) and not _directions_are_weak(result2):
                result = result2
            elif isinstance(result2, list):
                result = result2
        except Exception as e:
            print(f"[ai] direction retry failed ({e})")
    return result

def repair_words(words):
    try:
        payload = [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in words]
        data = _parse_json(_call_llm(REPAIR_SYS, "Transcribed words:\n" + json.dumps(payload), 0.1))
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
    print(f"[ai] provider={_provider()} — CONCEPT + DIRECTION")
    words = repair_words(words)
    lyrics = _words_to_lyrics(words)
    lines = _build_lines_simple(words)
    try:
        concept_obj = concept(lyrics)
        print(f"[ai] concept mood={concept_obj.get('mood')} priority={concept_obj.get('visual_priority')}")
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
            print(f"[ai] directed {len(directions)} lines -> {len(metaphors)} layouts, {len(scenes)} scenes")
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
