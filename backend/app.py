from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
import tempfile
import json
import subprocess
import shutil

app = FastAPI(title="Lyrisee Processing API")

# This CORS block is what allows Vercel to talk to Hugging Face
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def serve_index_or_health():
    # If index.html is in the folder above, serve it (for Hugging Face)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(script_dir, "../index.html") 
    
    if os.path.exists(index_path):
        return FileResponse(index_path)
    
    # Fallback health check if index.html isn't there
    return {"status": "ok", "message": "Lyrisee Backend API is running."}

@app.post("/process")
async def process_media(file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse(status_code=400, content={"error": "No file uploaded"})

    # Save the uploaded file to a temporary location
    fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])
    with os.fdopen(fd, 'wb') as f:
        shutil.copyfileobj(file.file, f)

    out_json = temp_path + "_lyrics.json"

    try:
        # Run your exact original audio processor synchronously
        script_dir = os.path.dirname(os.path.abspath(__file__))
        processor_path = os.path.join(script_dir, "audio_processor.py")

        env = os.environ.copy()

        result = subprocess.run(
            ["python3", processor_path, temp_path, "-o", out_json],
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode != 0:
            return JSONResponse(status_code=500, content={"error": "Processing failed", "details": result.stderr})

        with open(out_json, "r") as f:
            data = json.load(f)

        return JSONResponse(content=data)

    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(out_json):
            os.remove(out_json)
