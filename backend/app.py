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
def health():
    return {"status": "ok"}

@app.post("/process")
async def process_media(
    file: UploadFile = File(...),
    ai_provider: str = Form("gemini")
):
    if not file.filename:
        return JSONResponse(status_code=400, content={"error": "No file uploaded"})

    fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])
    with os.fdopen(fd, 'wb') as f:
        shutil.copyfileobj(file.file, f)

    file_mb = os.path.getsize(temp_path) / (1024 * 1024)
    out_json = temp_path + "_lyrics.json"

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

            # asyncio subprocess — never blocks the event loop
            proc = await asyncio.create_subprocess_exec(
                "python3", "-u", processor_path, temp_path, "-o", out_json,
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
