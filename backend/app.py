from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
import asyncio
import os
import tempfile
import json
import shutil

app = FastAPI(title="Lyrisee Processing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def serve_index_or_health():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(script_dir, "../index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "ok", "message": "Lyrisee Backend API is running."}

@app.get("/health")
def health(probe: int = 0):
    """Reports whether the two stages that silently no-op are actually wired:
    the Director (needs a provider key) and CMUdict rhymes (needs `pronouncing`)."""
    try:
        import lyrisee_ai
        director, provider = lyrisee_ai.have_llm(), lyrisee_ai._provider()
    except Exception as e:
        director, provider = False, f"error: {e}"
    try:
        import rhyme_engine
        cmudict = rhyme_engine.have_cmudict()
    except Exception:
        cmudict = False
    model = os.environ.get({"ollama": "OLLAMA_MODEL", "gemini": "GEMINI_MODEL",
                            "openai": "OPENAI_MODEL", "anthropic": "ANTHROPIC_MODEL"}
                           .get(provider, ""), "") or None
    out = {"status": "ok", "director": director, "provider": provider, "model": model,
           "cmudict": cmudict}
    if probe and director:
        # a key being present proved nothing when the model turned out to be paywalled (402)
        try:
            reply = lyrisee_ai._call_llm("Reply with the single word: ok", "ping", 0.0)
            out["probe"] = {"ok": True, "model_used": getattr(lyrisee_ai, "_OLLAMA_MODEL_OK", None) or model,
                            "reply": (reply or "")[:80]}
        except Exception as e:
            out["probe"] = {"ok": False, "error": str(e)[:300]}
    return out

@app.post("/process")
async def process_media(
    file: UploadFile = File(...),
    ai_provider: str = Form("gemini"),
    master_audio: bool = Form(False),
    separate_vocals: bool = Form(False)
):
    if not file.filename:
        return JSONResponse(status_code=400, content={"error": "No file uploaded"})

    fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])
    with os.fdopen(fd, 'wb') as f:
        shutil.copyfileobj(file.file, f)

    file_mb = os.path.getsize(temp_path) / (1024 * 1024)
    out_json = temp_path + "_lyrics.json"
    out_audio = temp_path + "_mastered.wav"

    async def event_stream():
        proc = None
        try:
            yield _sse({"log": f"[upload] {file.filename} ({file_mb:.1f} MB) received"})
            yield _sse({"log": f"[pipeline] provider={ai_provider}"})

            script_dir = os.path.dirname(os.path.abspath(__file__))
            processor_path = os.path.join(script_dir, "audio_processor.py")

            env = os.environ.copy()
            env["LYRISEE_LLM"] = ai_provider
            env["PYTHONUNBUFFERED"] = "1"  # force line-by-line stdout flush

            cmd_args = ["python3", "-u", processor_path, temp_path, "-o", out_json]
            if master_audio:
                cmd_args.append("--master")
            if separate_vocals:
                cmd_args.append("--separate")

            # asyncio subprocess — never blocks the event loop
            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )

            # stream stdout/stderr as they arrive
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    yield _sse({"log": line})

            await proc.wait()

            if proc.returncode != 0:
                yield _sse({"error": f"Processor exited with code {proc.returncode} — see logs above."})
                return

            if not os.path.exists(out_json):
                yield _sse({"error": "Processor exited OK but produced no output file."})
                return

            with open(out_json, "r") as f:
                data = json.load(f)

            word_count = len(data.get("words", []))
            yield _sse({"log": f"[done] {word_count} words · {len(data.get('beats', []))} beats"})
            if master_audio and os.path.exists(out_audio):
                import base64
                with open(out_audio, "rb") as af:
                    b64_audio = base64.b64encode(af.read()).decode("utf-8")
                    data["_mastered_audio"] = f"data:audio/wav;base64,{b64_audio}"
                os.remove(out_audio)
            yield _sse({"done": True, "result": data})

        except Exception as e:
            yield _sse({"error": str(e)})
        finally:
            if proc and proc.returncode is None:
                proc.kill()
            for p in (temp_path, out_json):
                if os.path.exists(p):
                    os.remove(p)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"
