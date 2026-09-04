#!/usr/bin/env python3
"""
rhyme_engine.py — Lyrisee's TRUE rhyme detector (core app logic, no LLM needed).

Uses the CMU Pronouncing Dictionary (via `pronouncing`) to find REAL rhymes — including
INTERNAL rhymes anywhere in a line, not just line-ends — by phonemes, then groups words
into rhyme families and assigns each family a color (the emNoFavors-style color-coding).

Approach (rap-multi friendly):
  • Each word -> CMU phones; key = the stressed-vowel assonance signature of its rhyming part
    (last stressed vowel, optionally + trailing vowel for tighter multis). Out-of-vocabulary
    slang falls back to a spelling->vowel heuristic so nothing is dropped.
  • Words sharing a key rhyme. Families with >=2 members get a palette color.
  • Emits per-word group ids so the engine colors EVERY occurrence (captures internal rhyme),
    plus human-readable families for verification.

Output merged into lyric_data.json as:  words[i]["rhyme"] = <familyId or -1>, plus
  "rhyme_palette": [...hex...], "rhyme_families": [["word","word",...], ...]
"""
from __future__ import annotations
import re, json, sys

# emNoFavors-style vivid, high-contrast palette (distinct hues; data-viz, not UI chrome)
PALETTE = ["#19E0E0","#A6E22E","#FF3D7F","#FF1E1E","#9D6B4A","#9AA0A6","#FF9F1C",
           "#2D9CFF","#FF66C4","#B388FF","#7CFF6B","#E6C229","#FF5C2A","#5CE1E6"]

# spelling -> coarse vowel (fallback for OOV slang words; mirrors engine's phon())
def _heur_vowel(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w: return None
    w = (w.replace("igh","AY").replace("ay","EY").replace("ai","EY").replace("ee","EE")
          .replace("ea","EE").replace("oo","UW").replace("ow","OW").replace("ou","OW"))
    for ch in reversed(w):
        up = ch.upper()
        if up in ("A","E","I","O","U","Y") or up in ("AY","EY","EE","UW","OW"):
            return {"A":"AE","E":"EH","I":"IH","O":"AA","U":"AH","Y":"AY"}.get(up, up)
    return None

# coda -> manner class, mirroring the engine's codaClass(): bucks/sucks group, bucks/fuck don't.
_CODA = {"P":"P","B":"P","T":"T","D":"T","K":"K","G":"K","F":"F","V":"F","S":"S","Z":"S",
         "SH":"X","ZH":"X","CH":"X","JH":"X","TH":"H","DH":"H","M":"N","N":"N","NG":"N",
         "L":"L","R":"R","ER":"R","W":"","Y":"","HH":""}

def _rime_for(word):
    """(exact_key, vowel) — exact = last vowel + coda class (true rhyme); vowel alone = near."""
    try:
        import pronouncing
        w = re.sub(r"[^a-z']", "", word.lower())
        ph = pronouncing.phones_for_word(w)
        if ph:
            part = pronouncing.rhyming_part(ph[0]).split()   # from last stressed vowel
            vowels = [p[:-1] for p in part if p[-1:].isdigit()]
            if vowels:
                # coda = consonants after the LAST vowel in the rhyming part
                last_v = max(i for i, p in enumerate(part) if p[-1:].isdigit())
                coda = "".join(_CODA.get(p, "") for p in part[last_v + 1:])
                multi = "·".join(vowels[:2])                 # nucleus (+ next vowel for multis)
                return f"{multi}:{coda}", vowels[-1]
    except Exception:
        pass
    v = _heur_vowel(word)
    return (f"{v}:", v) if v else (None, None)

def _key_for(word):
    return _rime_for(word)[0]

def have_cmudict():
    try:
        import pronouncing  # noqa: F401
        return True
    except Exception:
        return False

def analyze(words, min_family=2):
    """Return (per_word_group_ids, palette, families) for a list of word dicts."""
    if not have_cmudict():
        # Without CMUdict the spelling heuristic collapses the whole song into a handful of
        # vowel blobs — worse than nothing, because it overrides the browser's rime engine.
        print("[rhyme] pronouncing (CMUdict) not installed — deferring to the in-engine rime "
              "detector. `pip install pronouncing` for phoneme-exact families.")
        return [-1] * len(words), [], []
    FN = {"the","a","an","of","to","in","on","at","for","and","or","but","is","it","i",
          "you","he","she","we","they","my","your","his","her","its","our","their","be"}
    keys, vowels = [], []
    for w in words:
        t = re.sub(r"[^a-z']", "", w["text"].lower())
        k, v = (None, None) if (not t or t in FN) else _rime_for(w["text"])
        keys.append(k); vowels.append(v)
    # group on the exact rime (true rhyme)
    by_key = {}
    for i, k in enumerate(keys):
        if k: by_key.setdefault(k, []).append(i)
    fam_keys = [k for k, idxs in by_key.items() if len(idxs) >= min_family]
    # order families by first appearance for stable coloring
    fam_keys.sort(key=lambda k: min(by_key[k]))
    group_of = [-1] * len(words)
    families = []
    vowel_fam = {}
    for fi, k in enumerate(fam_keys):
        for i in by_key[k]:
            group_of[i] = fi
        families.append([words[i]["text"] for i in by_key[k]])
        vowel_fam.setdefault(k.split(":")[0].split("·")[-1], fi)
    # near-rhyme: same vowel, different coda -> same family, flagged so the engine shades it softer
    for i, v in enumerate(vowels):
        if group_of[i] >= 0 or not v:
            continue
        fi = vowel_fam.get(v)
        if fi is not None:
            group_of[i] = fi
            words[i]["rhyme_near"] = True
    palette = [PALETTE[i % len(PALETTE)] for i in range(len(fam_keys))]
    return group_of, palette, families

def enrich_file(words):
    g, pal, fams = analyze(words)
    for i, w in enumerate(words):
        w["rhyme"] = g[i]
    return {"words": words, "rhyme_palette": pal, "rhyme_families": fams}

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "lyric_data_80k.json"
    out = sys.argv[2] if len(sys.argv) > 2 else None
    d = json.load(open(src))
    W = d["words"]
    g, pal, fams = analyze(W)
    n_colored = sum(1 for x in g if x >= 0)
    print(f"{len(W)} words -> {len(fams)} rhyme families, {n_colored} words colored")
    print("\nTop families (proof these are real rhymes):")
    for fi, fam in sorted(enumerate(fams), key=lambda kv: -len(kv[1]))[:12]:
        uniq = []
        for w in fam:
            wl = re.sub(r"[^a-z']","",w.lower())
            if wl not in [re.sub(r"[^a-z']","",x.lower()) for x in uniq]: uniq.append(w)
        print(f"  [{pal[fi]}] " + ", ".join(uniq[:10]))
    if out:
        for i, w in enumerate(W): w["rhyme"] = g[i]
        d["rhyme_palette"] = pal; d["rhyme_families"] = fams
        json.dump(d, open(out, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
        print("wrote", out)
