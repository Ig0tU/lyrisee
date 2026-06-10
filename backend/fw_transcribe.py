#!/usr/bin/env python3
"""
fw_transcribe.py — real WORD-LEVEL transcription via faster-whisper (CPU).

This is what makes sync actually tight: per-word start/end times, not interpolation.
Outputs raw words [{text,start,end}] to JSON; POS + correction happen downstream.

Usage:
    python3 fw_transcribe.py "80K_tokens_mix.mp3" -o fw_words.json --model small
"""
import argparse, json, os, sys


def to_wav_16k(audio_path):
    """Decode any audio to 16k mono wav using imageio-ffmpeg's bundled ffmpeg (fallback path)."""
    import imageio_ffmpeg, subprocess, tempfile
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out = os.path.join(tempfile.gettempdir(), "fw_input_16k.wav")
    subprocess.run([ff, "-y", "-i", audio_path, "-ac", "1", "-ar", "16000", out],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("-o", "--out", default="fw_words.json")
    ap.add_argument("--model", default="small")   # tiny|base|small|medium
    ap.add_argument("--compute", default="int8")
    args = ap.parse_args()

    from faster_whisper import WhisperModel
    print(f"[fw] loading model '{args.model}' (cpu/{args.compute}) …", flush=True)
    model = WhisperModel(args.model, device="cpu", compute_type=args.compute)

    src = args.audio
    try:
        segments, info = model.transcribe(src, word_timestamps=True, vad_filter=True,
                                           beam_size=5, condition_on_previous_text=True)
    except Exception as e:  # decode fallback via ffmpeg
        print(f"[fw] direct decode failed ({e}); converting with ffmpeg …", flush=True)
        src = to_wav_16k(args.audio)
        segments, info = model.transcribe(src, word_timestamps=True, vad_filter=True, beam_size=5)

    words, seg_texts = [], []
    for seg in segments:
        seg_texts.append(f"[{seg.start:6.2f}] {seg.text.strip()}")
        for w in (seg.words or []):
            t = (w.word or "").strip()
            if not t:
                continue
            s = float(w.start); e = float(w.end)
            if e <= s:
                e = s + 0.12
            words.append({"text": t, "start": round(s, 3), "end": round(e, 3)})
    words.sort(key=lambda x: x["start"])
    json.dump({"words": words}, open(args.out, "w", encoding="utf-8"),
              separators=(",", ":"), ensure_ascii=False)
    dur = words[-1]["end"] if words else 0
    print(f"[fw] {len(words)} words, span 0–{dur:.1f}s  (lang={getattr(info,'language','?')})")
    print(f"[fw] wrote {args.out}")
    print("\n--- segment preview ---")
    print("\n".join(seg_texts[:12]))


if __name__ == "__main__":
    main()
