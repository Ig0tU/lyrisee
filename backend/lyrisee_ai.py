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

CONCEPT_SYS = """You are Lyrisee's visual Director. Invent this song's visual world from scratch.
Process: (1) surface reading (2) dual readings / entendres (3) the Unsaid — the unresolved question/confession.
Then derive palette, fonts, motif_lexicon (only from THIS song's imagery), motion, restraint, construct_bias,
visual_priority (usually emphasize_unsaid), gap_strategy.
Output ONLY JSON:
{\"palette\":{\"bg\":\"#000\",\"ink\":\"#EDEAE4\",\"accents\":[\"#C41E3A\"]},\"fonts\":{\"display\":\"Anton\",\"accent\":\"Archivo Black\"},
\"motifs\":{},\"motion\":\"...\",\"restraint\":0.7,\"mood\":\"...\",\"construct_bias\":[\"embodiment\"],
\"dual_readings\":{\"surface\":\"...\",\"undercurrent\":\"...\",\"unsaid\":\"...\"},
\"visual_priority\":\"emphasize_unsaid\",\"gap_strategy\":\"negative_space\"}"""

DIRECTION_SYS = """Line-level Art Director. For each line: primary, secondary, gap (unsaid),
emphasis_target (spoken|gap|both), visual_action (build_form|semantic_motion|isolate|withhold|embody|clean),
form, motion_verb, gap_treatment, register, hierarchy.
Prefer gap when the unsaid is stronger. Output ONLY a JSON array of direction objects."""

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
    """OpenAI or LM Studio (OPENAI_BASE_URL)."""
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

def _call_ollama(system, user, temperature):
    """Ollama Cloud ONLY — https://ollama.com/api/chat + OLLAMA_API_KEY."""
    import urllib.error, urllib.request
    key = (os.environ.get("OLLAMA_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Ollama Cloud requires OLLAMA_API_KEY from https://ollama.com/settings/keys")
    model = os.environ.get("OLLAMA_MODEL", "deepseek-v3")
    base = (os.environ.get("OLLAMA_HOST") or "https://ollama.com").rstrip("/")
    if any(x in base for x in ("localhost", "127.0.0.1", ":11434")):
        base = "https://ollama.com"
    url = f"{base}/api/chat"
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False, "options": {"temperature": temperature}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama Cloud HTTP {e.code}: {e.read().decode(errors='replace')[:400]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama Cloud unreachable: {e.reason}") from e
    if "message" in data:
        return data["message"].get("content", "")
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    raise RuntimeError(f"Unexpected Ollama response: {list(data)[:6]}")

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

def concept(lyrics, extra=""):
    user = f"Full lyrics:\n\n{lyrics}\n\n"
    if extra:
        user += f"Context:\n{extra}\n\n"
    user += "Produce the concept JSON now."
    return _parse_json(_call_llm(CONCEPT_SYS, user, 0.5))

def direct(lines, concept_obj):
    payload = [{"index": i, "text": ln["text"]} for i, ln in enumerate(lines)]
    user = "CONCEPT:\n" + json.dumps(concept_obj, ensure_ascii=False) + "\n\nLINES:\n" + json.dumps(payload, ensure_ascii=False) + "\n\nReturn direction array."
    result = _parse_json(_call_llm(DIRECTION_SYS, user, 0.35))
    if isinstance(result, dict) and "directions" in result:
        result = result["directions"]
    if not isinstance(result, list):
        raise ValueError("Direction response was not a list")
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
    directions, metaphors = [], []
    if concept_obj and lines:
        try:
            for start in range(0, len(lines), 18):
                chunk = lines[start:start + 18]
                for d in direct(chunk, concept_obj):
                    if "line_index" in d:
                        d["line_index"] = start + int(d["line_index"])
                    directions.append(d)
                    metaphors.append({"line": chunk[d.get("line_index", 0) - start]["text"] if chunk else "",
                                      "action": d.get("visual_action"), "form": d.get("form"),
                                      "emphasis": d.get("emphasis_target"), "gap": d.get("gap")})
            print(f"[ai] directed {len(directions)} lines")
        except Exception as e:
            print(f"[ai] direction failed ({e})")
    return {"words": words, "concept": concept_obj, "metaphors": metaphors,
            "directions": directions, "rhyme_families": None}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python lyrisee_ai.py lyric_data.json"); sys.exit(1)
    data = json.load(open(sys.argv[1]))
    result = enrich(data["words"])
    out = {**data, **{k: v for k, v in result.items() if v is not None}}
    dest = sys.argv[2] if len(sys.argv) > 2 else "lyric_data_directed.json"
    json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("wrote", dest)
