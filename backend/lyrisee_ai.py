#!/usr/bin/env python3
"""
lyrisee_ai.py — Lyrisee Director (CONCEPT + DIRECTION)

Two-stage LLM art-direction that invents a song-specific visual world and then
directs every line inside it. Explicitly hunts dual meanings / double-entendres
and privileges the unsaid (the gap) when it is stronger than the spoken text.

Providers (first available wins):
  GEMINI_API_KEY | OPENAI_API_KEY | ANTHROPIC_API_KEY | OLLAMA_API_KEY

Ollama = Cloud only (https://ollama.com/api/chat + OLLAMA_API_KEY).
Local LLMs = LM Studio via OPENAI_BASE_URL + OPENAI_API_KEY.

Public API used by audio_processor.py:
  have_llm() -> bool
  enrich(words) -> dict with repaired words + concept + metaphors + direction cues
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any


def have_llm() -> bool:
    return bool(
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OLLAMA_API_KEY")
        or os.environ.get("LYRISEE_LLM")
    )


def _provider() -> str:
    pref = (os.environ.get("LYRISEE_LLM") or "").lower().strip()
    if pref in ("gemini", "openai", "anthropic", "ollama", "claude"):
        if pref == "claude":
            return "anthropic"
        return pref
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OLLAMA_API_KEY"):
        return "ollama"
    return "none"
