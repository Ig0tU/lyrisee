# ðŸ¦Ž Lyric Weaver: Finalization Roadmap (Agent-Oriented)

This document serves as the strategic map for elevating **Lyric Weaver** to its ultimate state of "Typographic Embodiment" and production-grade robustness.

## 1. Architectural Consolidation
- **Core Library Extraction:** Move `SceneDirector`, `VisualConfigController`, and the `audio_intelligence_pipeline` into a unified `lyrisee` Python package.
- **Service Decoupling:** Separate the Flask API from the processing workers. Use a message queue (e.g., Celery + Redis) to handle rendering, as it is computationally expensive and memory-intensive.
- **Configuration Standardization:** Ensure all constructs (styles) are fully defined in `visual_configs.json`, moving all "hard-coded" logic out of `app.py`.

## 2. Advanced "Word-Form" Engine (Phase 3)
- **Letter-Level Control:** Refactor the renderer to handle individual glyphs within words. This is required for complex animations where letters separate or morph.
- **Semantic-Visual Action Library:**
    - Implement the `Build_Form` action for nouns (e.g., `cage`, `bird`, `peace`).
    - Implement the `Semantic_Motion` action for verbs (e.g., `running`, `falling`, `searching`).
- **Procedural Rigging Prototype:** Develop a utility that uses `ttf2mesh` to rig glyphs, allowing for the "humanized" word movements described in the vision.

## 3. Robustness & Production Readiness
- **Dependency Isolation:** Strict `requirements.txt` locking.
- **Font Fallback System:** Improve the `TextClip` wrapper to automatically find valid system fonts across Darwin, Linux, and Windows.
- **Resource Management:** Implement a cleanup task for `uploads/` and `static/results/` to prevent disk bloat.
- **Hardware Acceleration:** Ensure `demucs` and `whisper` automatically detect and use `CUDA` (NVIDIA) or `MPS` (Apple Silicon) if available.

## 4. UI/UX Evolution
- **Human-in-the-Loop Editor:** Create a lightweight web interface for correcting Whisper's transcript and adjusting word-level timestamps before the final render.
- **Style Previewer:** Allow users to see a "Storyboard" preview (static frames) before committing to a full video render.
- **Telemetry & Logging:** Integrated structured JSON logging for every processing step.

## 5. Deployment
- **Dockerization:** Complete the `Dockerfile` to include all system dependencies (FFmpeg, ImageMagick, Ghostscript, specific fonts).
- **GPU Cloud Support:** Documentation for deploying on GPU-enabled instances (AWS G4/G5, Lambda Labs).

---
*Status: Architecture Verified. Pipeline Functional. Awaiting Creative Expansion.*
