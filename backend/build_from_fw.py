#!/usr/bin/env python3
"""Build tight-sync lyric_data.json from faster-whisper word-level output.
   Adds POS (heuristic), real beats (numpy onset+tempo, no librosa), and intent arrangement."""
import json, re, subprocess, sys
import numpy as np
import imageio_ffmpeg
from intent_director import build_arrangement

AUDIO = sys.argv[1] if len(sys.argv) > 1 else "80K_tokens_mix.mp3"
FW    = sys.argv[2] if len(sys.argv) > 2 else "fw_words.json"
OUT   = sys.argv[3] if len(sys.argv) > 3 else "lyric_data_80k.json"

FN = set("a an the of to in on at for and or but nor so yet as if then than that this these those i you he she it we they me him her us them my your his its our their is am are was were be been being do does did have has had will would can could should may might must not no up down out off over into onto from with by about".split())
PRON = {"i","you","he","she","it","we","they","me","him","her","us","them"}
def pos(tok, first):
    w = re.sub(r"[^a-zA-Z']", "", tok); lw = w.lower().strip("'")
    if not w: return "X"
    if lw in FN: return "PRON" if lw in PRON else "ADP"
    if w[:1].isupper() and not first and lw != "i": return "PROPN"
    if re.search(r"(ing|ed)$", lw): return "VERB"
    if re.search(r"ly$", lw): return "ADV"
    if re.search(r"(ous|ful|ive|able|ible|est|less|ish)$", lw): return "ADJ"
    return "NOUN"

# conservative, high-confidence cleanups only (preserve timing slot)
CORR = {"tastein":"tasting","tastein'":"tasting","listenin":"listening","goin":"goin'"}
def fix(t):
    k = re.sub(r"[^a-z']","",t.lower())
    return CORR.get(k, t)

fw = json.load(open(FW))["words"]
words = []
for i, w in enumerate(fw):
    txt = fix(w["text"].strip())
    words.append({"text": txt, "start": round(float(w["start"]),3), "end": round(float(w["end"]),3), "pos": pos(txt, i==0)})

# ---- beats: decode -> spectral-flux onset envelope -> tempo (autocorr) -> beat grid ----
def detect_beats(path):
    try:
        ff = imageio_ffmpeg.get_ffmpeg_exe(); sr = 22050
        raw = subprocess.run([ff,"-v","quiet","-i",path,"-f","f32le","-ac","1","-ar",str(sr),"pipe:1"],
                             stdout=subprocess.PIPE, check=True).stdout
        y = np.frombuffer(raw, dtype=np.float32)
        if y.size < sr: return [], 0
        hop, win = 512, 1024
        n = 1 + (len(y)-win)//hop
        fps = sr/hop
        w = np.hanning(win); prev=None; flux=np.zeros(n)
        for i in range(n):
            seg = y[i*hop:i*hop+win]*w
            mag = np.abs(np.fft.rfft(seg))
            if prev is not None:
                flux[i] = np.sum(np.maximum(0, mag-prev))
            prev = mag
        flux -= flux.mean(); flux[flux<0]=0
        # tempo via autocorrelation in 70..170 BPM
        lo, hi = int(fps*60/170), int(fps*60/70)
        ac = np.correlate(flux, flux, "full")[len(flux)-1:]
        lag = lo + int(np.argmax(ac[lo:hi])); period = lag/fps
        # beat grid anchored at first strong onset
        start = (np.argmax(flux[:int(fps*8)]) / fps) if flux[:int(fps*8)].size else 0.0
        dur = len(y)/sr; beats = list(np.arange(start, dur, period))
        return [round(float(b),3) for b in beats], round(60/period,1)
    except Exception as e:
        print("[beats] skipped:", e); return [], 0

beats, bpm = detect_beats(AUDIO)
arr, secs = build_arrangement(words)
# embed-friendly: 3D-only constructs -> embodiment (DOM) so it shows without WebGL
MAP = {"kinetic_art":"embodiment","chameleon":"embodiment","classic":"embodiment"}
arr = [{"start":a["start"],"construct":MAP.get(a["construct"],a["construct"]),"label":a["label"]} for a in arr]
out=[]
for a in arr:
    if out and out[-1]["construct"]==a["construct"]: continue
    out.append(a)
if out and out[0]["start"]>0: out[0]["start"]=0

data = {"words":words, "beats":beats, "arrangement":out}
json.dump(data, open(OUT,"w",encoding="utf-8"), separators=(",",":"), ensure_ascii=False)
print(f"words={len(words)} beats={len(beats)} (~{bpm} BPM) sections->{len(out)} cues")
print("arrangement:", json.dumps(out))
