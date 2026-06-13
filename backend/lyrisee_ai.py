#!/usr/bin/env python3
"""
lyrisee_ai.py — Lyrisee's built-in language intelligence (a CORE app stage, not a human in the loop).

Given a raw word-level transcript (from faster-whisper), Lyrisee itself calls an LLM to:
  1. REPAIR mis-heard words from context  — read the lyric as a story; fix transcription errors
     using subject matter, rhyme scheme, and surrounding lines; preserve the artist's voice/slang.
  2. MAP rhyme pockets                     — which words rhyme, and where the rhyme sits in the bar.
  3. ART-DIRECT the visuals                — per-line "word-art" metaphor cue + which word to emphasize,
     chosen from the engine's vocabulary, so the visual embodies what the words are saying.

Crucially, corrected text is re-aligned to the ORIGINAL word timings (difflib), so true sync is kept.

Provider-agnostic: uses whichever API key is configured —
    ANTHROPIC_API_KEY | OPENAI_API_KEY | GEMINI_API_KEY   (model via LYRISEE_LLM_MODEL)
Falls back to a deterministic heuristic (intent_director) when no key is present, so the pipeline
never hard-fails — but the high-quality repair/art-direction is the LLM path.

This module is imported by audio_processor.py (the `--ai` stage) and is also runnable standalone:
    python3 lyrisee_ai.py fw_words.json -o lyric_data.json
"""
from __future__ import annotations
import os, re, json, time, difflib, shutil, subprocess, urllib.request, urllib.error

_LAST = [0.0]
def _throttle(gap=2.0):
    """Space out API calls to respect free-tier rate limits."""
    wait = gap - (time.time() - _LAST[0])
    if wait > 0:
        time.sleep(wait)
    _LAST[0] = time.time()

METAPHORS = ["cage","ascend","fall","spiral","path","split","stack","row"]

# ---------------------------------------------------------------- LLM dispatch
def _http_json(url, headers, payload, timeout=120):
    # Prefer curl: it uses the system CA store (which trusts the sandbox proxy); Python's
    # requests/urllib use certifi and fail SSL behind a MITM proxy. On a normal machine curl also works.
    if shutil.which("curl"):
        args = ["curl", "-sS", "--max-time", str(timeout), "-X", "POST", url, "-H", "Content-Type: application/json"]
        for k, v in headers.items():
            if k.lower() != "content-type":
                args += ["-H", f"{k}: {v}"]
        args += ["--data-binary", json.dumps(payload)]
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout + 30)
        if r.returncode != 0:
            raise RuntimeError("curl error: " + (r.stderr or "")[:200])
        return json.loads(r.stdout)
    import requests  # type: ignore
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()

def gemini_cli_path():
    """Locate the user's local gemini CLI (their cached OAuth makes it keyless)."""
    return os.environ.get("GEMINI_CLI_PATH") or shutil.which("gemini")

def _llm_gemini_cli(system: str, user: str) -> str:
    """Run a headless prompt through the local gemini CLI — uses ITS auth cache, no API key needed."""
    path = gemini_cli_path()
    if not path:
        raise RuntimeError("gemini CLI not found (install it, or set GEMINI_CLI_PATH)")
    cmd = [path, "-y", "--skip-trust", "-p", system + "\n\n" + user]
    model = os.environ.get("LYRISEE_LLM_MODEL")
    if model:
        cmd += ["-m", model]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                       cwd=os.environ.get("LYRISEE_CLI_CWD") or os.getcwd())
    out = (r.stdout or "").strip()
    if not out:
        raise RuntimeError("gemini CLI returned nothing (auth? run `gemini` once to log in): "
                           + (r.stderr or "")[:300])
    return out

def _prefer_gemini_cli() -> bool:
    forced = os.environ.get("LYRISEE_LLM", "").lower()
    if forced == "gemini-cli":
        return True
    if forced in ("anthropic", "openai", "gemini"):
        return False
    return bool(gemini_cli_path())          # default: use the local CLI whenever it's installed

def llm(system: str, user: str, max_tokens: int = 4000) -> str:
    """Single chat turn against the configured provider. Returns assistant text.
    Prefers the local gemini CLI (keyless via its own auth cache); falls back to API keys."""
    model = os.environ.get("LYRISEE_LLM_MODEL")
    forced = os.environ.get("LYRISEE_LLM", "").lower()
    if _prefer_gemini_cli():
        return _llm_gemini_cli(system, user)
    if (forced == "ollama") or (forced == "" and os.environ.get("OLLAMA_API_KEY")):
        # Default to deepseek-v4-flash, or a similar cloud model since models are deprecating
        # The user provided replacements: deepseek-v4-flash for cogito-2.1:671b, kimi-k2.6 for kimi-k2-thinking, minimax-m3, glm-5.1, qwen3.5
        m = model or "deepseek-v4-flash"
        # We can just use the _http_json helper which simulates curl, instead of installing the pip package to avoid dependency hell
        # Ollama API is compatible with OpenAI chat completions format usually, but let's be careful.
        # The prompt says: "https://ollama.com/api/tags" and provides a python example: client.chat(...)
        # Actually, Ollama's native API is slightly different (`/api/chat`), but if we can't install the `ollama` package easily inside `run.sh` without modifying requirements.txt, using `_http_json` against `https://ollama.com/api/chat` is safest.

        body = {
            "model": m,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "stream": False
        }
        out = _http_json(
            "https://ollama.com/api/chat",
            {"Authorization": "Bearer " + os.environ["OLLAMA_API_KEY"], "content-type": "application/json"},
            body
        )
        return out.get("message", {}).get("content", "")

    if (forced == "anthropic") or (forced == "" and os.environ.get("ANTHROPIC_API_KEY")):
        out = _http_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
             "content-type": "application/json"},
            {"model": model or "claude-3-5-sonnet-latest", "max_tokens": max_tokens,
             "system": system, "messages": [{"role": "user", "content": user}]})
        return "".join(b.get("text", "") for b in out.get("content", []))
    if (forced == "openai") or (forced == "" and os.environ.get("OPENAI_API_KEY")):
        out = _http_json(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "content-type": "application/json"},
            {"model": model or "gpt-4o", "max_tokens": max_tokens,
             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        return out["choices"][0]["message"]["content"]
    if (forced == "gemini") or (forced == "" and os.environ.get("GEMINI_API_KEY")):
        m = model or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key=" + os.environ["GEMINI_API_KEY"]
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in
                    ("HARM_CATEGORY_HARASSMENT","HARM_CATEGORY_HATE_SPEECH",
                     "HARM_CATEGORY_SEXUALLY_EXPLICIT","HARM_CATEGORY_DANGEROUS_CONTENT")],
                "generationConfig": {"maxOutputTokens": max(max_tokens, 8192), "temperature": 0.85,
                                      "thinkingConfig": {"thinkingBudget": 0}}}
        _throttle()
        for attempt in range(5):                       # retry on empty / 429 (free-tier rate limits)
            try:
                out = _http_json(url, {"content-type": "application/json"}, body, timeout=150)
                cand = (out.get("candidates") or [{}])[0]
                txt = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
                if txt.strip():
                    return txt
            except Exception:
                if attempt == 4:
                    raise
            time.sleep(3 * (attempt + 1))
        return ""
    raise RuntimeError("no LLM key configured (set ANTHROPIC_API_KEY | OPENAI_API_KEY | GEMINI_API_KEY)")

def have_llm() -> bool:
    return bool(gemini_cli_path()) or any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "OLLAMA_API_KEY"))

# ---------------------------------------------------------------- helpers
def _norm(t): return re.sub(r"[^a-z']", "", (t or "").lower())

def _lines_from(words, gap=0.6, maxw=10):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(i); nxt = words[i+1] if i+1 < len(words) else None
        g = (nxt["start"]-w["end"]) if nxt else 9
        if not nxt or g > gap or len(cur) >= maxw or re.search(r"[.!?]$", w["text"]):
            out.append(cur); cur = []
    return out

def _extract_json(text):
    """Pull the first JSON object/array out of an LLM reply (handles code fences/prose)."""
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
    for opn, cls in (("{", "}"), ("[", "]")):
        s = text.find(opn)
        if s >= 0:
            d = 0
            for i in range(s, len(text)):
                if text[i] == opn: d += 1
                elif text[i] == cls:
                    d -= 1
                    if d == 0:
                        try: return json.loads(text[s:i+1])
                        except Exception: break
    return json.loads(text)

# ---------------------------------------------------------------- 1) lyric repair
REPAIR_SYS = (
    "You are Lyrisee's lyric-repair stage. You receive an automatic speech-to-text transcript of a "
    "rap/song, line by line, that may contain MIS-HEARD words. Correct only the transcription errors "
    "using the subject matter, internal/end rhyme scheme, and the surrounding lines — infer what the "
    "artist most likely actually said. PRESERVE the artist's voice: slang, contractions, AAVE, profanity, "
    "proper nouns, and intentional wordplay/homophones. Do NOT rephrase correct words, do NOT add or "
    "remove lines, do NOT censor. Keep the same number of lines and their order. "
    "Return ONLY the corrected lyrics as plain text, one line per input line."
)
def repair_lyrics(words):
    """Return corrected word list with timings preserved (LLM path; identity if no key/err)."""
    lines = _lines_from(words)
    raw_lines = [" ".join(words[i]["text"] for i in ln) for ln in lines]
    if not have_llm():
        return words, raw_lines  # heuristic fallback = unchanged
    user = "Correct this transcript. Output the same number of lines.\n\n" + \
           "\n".join(f"{i+1}. {t}" for i, t in enumerate(raw_lines))
    try:
        reply = llm(REPAIR_SYS, user, max_tokens=2000)
    except Exception as e:
        print("[lyrisee_ai] repair failed:", e); return words, raw_lines
    fixed = [re.sub(r"^\s*\d+[\.\)]\s*", "", l).strip() for l in reply.splitlines() if l.strip()]
    if len(fixed) < len(raw_lines):                 # be safe: only use if line counts line up
        return words, raw_lines
    corrected_tokens = []
    for li, ln in enumerate(lines):
        toks = fixed[li].split() if li < len(fixed) else [words[i]["text"] for i in ln]
        corrected_tokens.append((ln, toks))
    new_words = _realign(words, corrected_tokens)
    return new_words, fixed

def _realign(words, corrected_tokens):
    """Map corrected tokens back onto original per-word timings using difflib within each line."""
    out = []
    for ln_idx, toks in corrected_tokens:
        orig = [words[i] for i in ln_idx]
        a = [_norm(w["text"]) for w in orig]
        b = [_norm(t) for t in toks]
        sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
        result = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(j2-j1):
                    o = orig[i1+k]; result.append({"text": toks[j1+k], "start": o["start"], "end": o["end"], "pos": o.get("pos","X")})
            elif tag == "replace":
                # spread the original block's [start,end] across the replacement tokens
                s, e = orig[i1]["start"], orig[i2-1]["end"]; n = max(1, j2-j1); step = (e-s)/n
                for k in range(j2-j1):
                    result.append({"text": toks[j1+k], "start": round(s+k*step,3), "end": round(s+(k+1)*step,3), "pos": "X"})
            elif tag == "insert":
                # inserted words borrow a sliver near the boundary
                anchor = orig[min(i1, len(orig)-1)]["start"]
                for k in range(j2-j1):
                    result.append({"text": toks[j1+k], "start": round(anchor,3), "end": round(anchor+0.12,3), "pos": "X"})
            # tag == "delete": original word dropped (mis-heard insertion)
        out.extend(result)
    out.sort(key=lambda w: w["start"])
    return out

# ---------------------------------------------------------------- 1.5) CONCEPT (invent the song's world)
CONCEPT_SYS = (
    "You are the Auditory-to-Visual Translation Director for a high-fidelity kinetic typography engine. "
    "Your mission is to deconstruct a vocal performance, reverse-engineering its lyrical content, emotional trajectory, "
    "rhythmic flow, and sonic texture into a dynamic visual score. You don't just display lyrics; you orchestrate them. "
    "THE CORE MANDATE: REPLICATE QUALITY-TIER UNDERSTANDING. "
    "Before generating any directives, you MUST first complete a silent 'pre-flight' internal analysis of the provided audio/lyrics. "
    "Your output should prove that you deeply understand the Narrative Arc & Emotional Tone, Vocal Delivery & Nuance, and Rhythmic Cadence & Pacing. "
    "Output ONLY JSON: "
    "{\"palette\":{\"bg\":\"#dark\",\"ink\":\"#light\",\"accents\":[\"#..\",\"#..\"]}, "
    "\"fonts\":{\"display\":\"Anton|Archivo Black|Inter\",\"accent\":\"Archivo Black|Inter\","
    "\"script\":\"Dancing Script\"}, \"motifs\":{\"<song word/concept>\":\"<one emoji/symbol>\"}, "
    "\"motion\":\"snap|drift|float|glitch\",\"restraint\":0.0-1.0,\"mood\":\"1-3 words\","
    "\"construct_bias\":[\"embodiment\",\"rhyme_scheme\",\"chameleon\",\"kinetic_art\"]}. "
    "Motifs must come from THIS song's own imagery. Key the palette to the song's feeling, not a default."
)
_MOTIF_HINTS = {"cage":"🧱","trapped":"🧱","lights":"🕯️","candle":"🕯️","fire":"🔥","burn":"🔥",
                "water":"💧","streams":"💧","rain":"💧","mic":"🎤","crown":"👑","king":"👑",
                "money":"💸","cash":"💸","gun":"🔫","blood":"🩸","peace":"☮","eyes":"👁",
                "ladder":"🪜","clock":"⏳","heart":"🤍","skull":"💀","coffin":"⚰️"}
def _fallback_concept(words):
    """Deterministic mood/world derivation (used when no LLM key). The LLM concept() is far richer."""
    text = " ".join(w["text"] for w in words).lower()
    def cnt(*terms): return sum(text.count(t) for t in terms)
    scores = {
        "aggressive": cnt("kill","war","fight","blood","gun","savage","murder","beast","clap","choke","hate","blade","rip","destroy","smoke"),
        "nocturnal":  cnt("dark","night","alone","lost","cold","shadow","empty","numb","drown","sober","fog","ghost","grave","sleep"),
        "reflective": cnt("peace","mind","soul","pray","god","pain","heart","cry","faith","hope","truth","quiet","still"),
        "triumphant": cnt("rise","top","win","great","king","crown","elevate","higher","champion","glory","celebrate"),
    }
    mood = max(scores, key=scores.get) if any(scores.values()) else "nocturnal"
    PAL = {
        "aggressive": {"bg":"#0a0a0b","ink":"#F3F1EA","accents":["#FF2E2E","#FF8A3D","#9AA0A6"]},
        "nocturnal":  {"bg":"#0a0e18","ink":"#E7ECF5","accents":["#5CE1E6","#9D7BFF","#3DA0FF"]},
        "reflective": {"bg":"#0c0d10","ink":"#ECEAE4","accents":["#A6E3C8","#C9C2FF","#FFC6A6"]},
        "triumphant": {"bg":"#0c0a06","ink":"#FBF6E9","accents":["#FFD166","#FF9F1C","#7CFF6B"]},
    }
    motifs = {k: v for k, v in _MOTIF_HINTS.items() if (" "+k) in (" "+text) or k in text}
    return {"palette":PAL[mood],
            "fonts":{"display":"Anton","accent":"Archivo Black","script":"Dancing Script"},
            "motifs":dict(list(motifs.items())[:8]),
            "motion":"snap" if mood in ("aggressive","triumphant") else "drift",
            "restraint":0.6 if mood=="aggressive" else 0.75, "mood":mood,
            "construct_bias":["embodiment","rhyme_scheme"]}
def concept(words, lines_text=None):
    if not have_llm():
        return _fallback_concept(words)
    body = "\n".join(lines_text) if lines_text else " ".join(w["text"] for w in words)
    try:
        c = _extract_json(llm(CONCEPT_SYS, "SONG:\n" + body[:6000], max_tokens=1200))
        return c if isinstance(c, dict) and c.get("palette") else _fallback_concept(words)
    except Exception as e:
        print("[lyrisee_ai] concept failed:", e); return _fallback_concept(words)

# ---------------------------------------------------------------- 2+3) rhyme + art direction
ICON_VOCAB = ["coffin","candle","hands","cage","crown","fire","water","ladder","peace","eyes",
              "gun","money","skull","heart","star","clock"]
ART_SYS = (
    "You are the Auditory-to-Visual Translation Director for a high-fidelity kinetic typography engine. "
    "Your mission is to deconstruct a vocal performance, reverse-engineering its lyrical content, emotional trajectory, "
    "rhythmic flow, and sonic texture into a dynamic visual score. You don't just display lyrics; you orchestrate them. "
    "THE METHODOLOGY: "
    "1. Embodiment: The lyric's literal meaning dictates its physical behavior (e.g., 'sinking' drops, 'wall' stacks). "
    "2. Emphasis (The 'Hit'): Identify the 1-3 words per line where the vocalist places heavy stress, an emotional break, or syncopation. "
    "3. Rhythm & Pace: Not every word is a special effect. Let connective tissue remain quiet. "
    "4. Tonal Mapping: The song's dominant and shifting moods dictate a core color palette. "
    "You receive corrected lyrics as numbered lines. For EACH line return a composition 'metaphor' from ["
    + ", ".join(METAPHORS) + "] based on meaning ('row'=neutral, 'stack', 'scatter', 'ascend', 'fall', 'split', 'cage', 'path', 'shatter'). "
    "And return 'hits' = the 1-3 words that carry the line (vocal punch, emotional break, thematic importance). "
    "For each hit: w (the exact word), emphasis 0-3 (3=punchline / rhyme-carrier / proper name), "
    "register one of sans|heavy|script (script for tender/sacred/proper/dreamlike; heavy for aggression), "
    "glow true/false, icon (string representing an emoji/symbol ONLY where visual irony or literalism hits hard, "
    "or null), and count (e.g. \"two\"->2). Also return rhyme_families: arrays of lowercased "
    "words that TRULY rhyme together (internal + end rhyme / multis). "
    "Return ONLY JSON: {\"lines\":[{\"i\":n,\"metaphor\":\"..\",\"hits\":[{\"w\":\"..\",\"emphasis\":2,"
    "\"register\":\"sans\",\"glow\":false,\"icon\":null,\"count\":1}]}],\"rhyme_families\":[[\"..\"]]}"
)

def art_direct(lines_text, concept=None):
    if not have_llm():
        return None
    note = ""
    if concept:
        note = "Work INSIDE this song's concept — mood: " + str(concept.get("mood","")) + "."
        if concept.get("motifs"):
            note += " Prefer icons from this song's motif lexicon: " + json.dumps(concept["motifs"]) + "."
    # chunk: per-word hits across a whole song overflow one response — batch the lines (global line #s)
    BATCH = 16
    all_lines = []
    for b in range(0, len(lines_text), BATCH):
        chunk = lines_text[b:b+BATCH]
        user = (note + "\nLyrics by line (line numbers are GLOBAL — keep them):\n" +
                "\n".join(f"{b+i+1}. {t}" for i, t in enumerate(chunk)))

        try:
            j = _extract_json(llm(ART_SYS, user, max_tokens=8192))
            if j and isinstance(j.get("lines"), list):
                all_lines += j["lines"]
        except Exception as e:
            print(f"[lyrisee_ai] art_direct batch {b//BATCH} failed:", e)
    return {"lines": all_lines} if all_lines else None

# ---------------------------------------------------------------- top-level enrich
def enrich(words):
    """Full Lyrisee intelligence pass: repair -> (rhyme + art) -> data with line metaphors.
    Always returns a dict {words, metaphors?, rhyme_families?}; degrades gracefully without a key."""
    words2, fixed_lines = repair_lyrics(words)
    data = {"words": words2}
    con = concept(words2, fixed_lines)          # STAGE 1: invent the song's own visual world
    if con: data["concept"] = con
    art = art_direct(fixed_lines, con)          # STAGE 2: direct within that world
    if art and isinstance(art.get("lines"), list):
        lines = _lines_from(words2)
        metas = []
        for cue in art["lines"]:
            i = (cue.get("i", 0) - 1)
            if not (0 <= i < len(lines)):
                continue
            metas.append({"start": round(words2[lines[i][0]]["start"], 3),
                          "metaphor": cue.get("metaphor", "row")})
            # map per-word DIRECTOR hits onto each word's 'dir' (emphasis/register/glow/icon)
            used = set()
            for hit in (cue.get("hits") or []):
                hw = _norm(hit.get("w", ""))
                if not hw:
                    continue
                for wi in lines[i]:
                    if wi in used or _norm(words2[wi]["text"]) != hw:
                        continue
                    words2[wi]["dir"] = {
                        "emphasis": int(hit.get("emphasis", 2)),
                        "register": hit.get("register", "sans"),
                        "glow": bool(hit.get("glow", False)),
                        "icon": (hit.get("icon") or None),
                        "count": int(hit.get("count", 1)),
                    }
                    used.add(wi); break
        if metas: data["metaphors"] = metas
        if art.get("rhyme_families"): data["rhyme_families"] = art["rhyme_families"]
    return data

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Lyrisee AI lyric repair + art direction")
    ap.add_argument("words_json"); ap.add_argument("-o", "--out", default="lyric_data.json")
    a = ap.parse_args()
    W = json.load(open(a.words_json))["words"]
    print(f"[lyrisee_ai] LLM configured: {have_llm()}  ({len(W)} words in)")
    out = enrich(W)
    json.dump(out, open(a.out, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
    print(f"[lyrisee_ai] wrote {a.out}: {len(out['words'])} words, "
          f"{len(out.get('metaphors',[]))} line cues, {len(out.get('rhyme_families',[]))} rhyme families")