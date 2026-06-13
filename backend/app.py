from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import tempfile
import json
import subprocess
import shutil

app = FastAPI(title="Lyrisee Processing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        # Run the audio processor synchronously
        # We assume audio_processor.py is in the same directory
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

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Lyrisee Backend API is running."}
