---
title: Lyrisee Backend
emoji: 🎶
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
---

# Lyrisee Backend API

This HuggingFace Space runs the heavy audio-processing pipeline for **Lyrisee**. It uses `demucs` for source separation, `stable-ts` for word-level transcription, and a custom LLM pipeline to art-direct kinetic typography logic.

## Usage

You can deploy this Space and configure the frontend (`index.html`) to point its `API_URL` to this Space's endpoint.

### API Endpoints

- **`GET /`**: Health check.
- **`POST /process`**: Accepts a media file (audio or video) as `multipart/form-data` under the key `file`. Processes the media and returns the JSON payload (`lyric_data.json`) suitable for the Lyrisee frontend.

## Configuration

To enable the "Director" AI capabilities, you must configure **Secrets** in your HuggingFace Space settings:

- `OLLAMA_API_KEY`: API key for Ollama Cloud (defaulted model `deepseek-v4-flash`).
- OR `GEMINI_API_KEY`: API key for Google Gemini.
- OR `OPENAI_API_KEY`: API key for OpenAI.
- OR `ANTHROPIC_API_KEY`: API key for Anthropic Claude.
