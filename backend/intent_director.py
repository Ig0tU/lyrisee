"""
intent_director.py — Lyrisee "understanding + arrangement" brain.

Pure-Python, dependency-light (only the standard library). Given word-level lyric
timing (text/start/end/pos), it:

  1. Segments the lyrics into LINES (timing gaps + sentence punctuation).
  2. Detects SECTIONS (intro / verse / hook / bridge / outro) using line repetition
     (the hook repeats), density and position.
  3. Reads a coarse INTENT per section (energy + a small sentiment lexicon).
  4. Maps each section to a visual CONSTRUCT, producing the `arrangement` array the
     Lyrisee engine consumes.

This is deterministic and runs at backend time alongside audio_processor.py.
"""
from __future__ import annotations
import re
from collections import Counter, defaultdict

FUNCTION_POS = {"DET", "ADP", "PRON", "AUX", "CCONJ", "SCONJ", "PART", "PUNCT"}

# --- small, transparent sentiment / energy lexicons (extend freely) ---
AGGRESSIVE = {"kill","war","fight","blood","gun","dead","die","fire","burn","attack",
              "smoke","choke","beast","savage","murder","destroy","rage","hate","bust","clap"}
REFLECTIVE = {"peace","calm","mind","soul","alone","lost","pray","god","tears","cry",
              "pain","heart","quiet","still","dream","faith","hope","sober","truth"}
TRIUMPH    = {"rise","elevate","escalate","greatness","win","champion","top","king",
              "celebrate","grind","built","build","higher","above","crown","gold"}


def _clean(t: str) -> str:
    return re.sub(r"[^a-z']", "", (t or "").lower())


def build_lines(words, gap=0.62, max_words=9):
    """Group word dicts into lines using timing gaps + sentence punctuation."""
    lines, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gp = (nxt["start"] - w["end"]) if nxt else 999
        ends = bool(re.search(r"[.!?…]$", w["text"]))
        if not nxt or gp > gap or len(cur) >= max_words or (ends and len(cur) >= 3):
            lines.append({
                "idx": cur[:],
                "start": words[cur[0]]["start"],
                "end": words[cur[-1]]["end"],
                "text": " ".join(words[k]["text"] for k in cur),
            })
            cur = []
    return lines


def _norm_line(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z' ]", "", text.lower())).strip()


def detect_sections(words, lines, max_lines=8):
    """Return sections: list of {start,end,lines,type,intent}.

    Boundaries are placed at: a large timing gap (adaptive), a change in hook status
    (the repeated lines), or after `max_lines` lines. This keeps it robust on real
    word-level timing (which has natural gaps) AND on gap-poor interpolated data.
    """
    if not lines:
        return []
    import statistics
    norm = [_norm_line(l["text"]) for l in lines]
    counts = Counter(n for n in norm if len(n.split()) >= 2)
    hook_lines = {n for n, c in counts.items() if c >= 2}

    def is_hook(i):
        return norm[i] in hook_lines

    gaps = [max(0.0, lines[i]["start"] - lines[i - 1]["end"]) for i in range(1, len(lines))]
    thr = max(1.2, (statistics.median(gaps) if gaps else 0.0) + 0.8)

    blocks, cur = [], [0]
    for i in range(1, len(lines)):
        gap = lines[i]["start"] - lines[i - 1]["end"]
        boundary = (gap > thr) or (is_hook(i) != is_hook(i - 1)) or (len(cur) >= max_lines)
        if boundary:
            blocks.append(cur); cur = [i]
        else:
            cur.append(i)
    blocks.append(cur)

    sections = []
    for bi, block in enumerate(blocks):
        l0, l1 = block[0], block[-1]
        start, end = lines[l0]["start"], lines[l1]["end"]
        text = " ".join(lines[k]["text"] for k in block)
        hooky = any(is_hook(k) for k in block)
        if bi == 0 and start > 8:
            stype = "intro"
        elif hooky:
            stype = "hook"
        elif bi == len(blocks) - 1:
            stype = "outro"
        else:
            stype = "verse"
        sections.append({
            "start": round(start, 2), "end": round(end, 2),
            "lines": block, "type": stype, "intent": _intent(words, lines, block, text),
        })
    return sections


def _density(words, lines, block):
    idx = [i for k in block for i in lines[k]["idx"]]
    if not idx:
        return 0.0
    span = max(0.5, words[idx[-1]]["end"] - words[idx[0]]["start"])
    return len(idx) / span                  # words per second


def _intent(words, lines, block, text):
    toks = [_clean(t) for t in re.split(r"\s+", text) if _clean(t)]
    s = Counter()
    for t in toks:
        if t in AGGRESSIVE: s["aggressive"] += 1
        if t in REFLECTIVE: s["reflective"] += 1
        if t in TRIUMPH:    s["triumph"] += 1
    mood = s.most_common(1)[0][0] if s else "neutral"
    dens = _density(words, lines, block)
    return {"mood": mood, "density": round(dens, 2)}


def _construct_for(section):
    """Map a section's type + intent to a Lyrisee construct id."""
    t, intent = section["type"], section["intent"]
    mood, dens = intent["mood"], intent["density"]
    if t == "intro":
        return "kinetic_art"
    if t == "hook":
        return "chameleon"                 # vivid, punchy for the repeated hook
    if t == "outro":
        return "chameleon" if mood == "triumph" else "kinetic_art"
    # verses: dense / aggressive -> expose the multis with the rhyme map;
    #         reflective -> intimate kinetic; otherwise vivid.
    if mood == "reflective":
        return "kinetic_art"
    if dens >= 3.2 or mood == "aggressive":
        return "rhyme_scheme"
    return "chameleon"


def build_arrangement(words):
    """Top-level: words -> arrangement[{start, construct, label}] (+ sections debug)."""
    lines = build_lines(words)
    sections = detect_sections(words, lines)
    arrangement = []
    for sec in sections:
        arrangement.append({
            "start": sec["start"],
            "construct": _construct_for(sec),
            "label": f'{sec["type"]} · {sec["intent"]["mood"]}',
        })
    # collapse consecutive identical constructs
    collapsed = []
    for a in arrangement:
        if collapsed and collapsed[-1]["construct"] == a["construct"]:
            continue
        collapsed.append(a)
    if collapsed and collapsed[0]["start"] > 0:
        collapsed[0]["start"] = 0
    return collapsed, sections


if __name__ == "__main__":
    import json, sys
    data = json.load(open(sys.argv[1]))
    arr, secs = build_arrangement(data["words"])
    print(json.dumps({"arrangement": arr, "sections": secs}, indent=2))
