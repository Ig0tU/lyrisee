# Ollama = Cloud only

In Lyrisee, **Ollama always means [Ollama Cloud](https://ollama.com)**.
Local LLMs go through **LM Studio** (OpenAI-compatible).

## Required secrets / env

```bash
export OLLAMA_API_KEY=your_key_from_https://ollama.com/settings/keys
export OLLAMA_MODEL=deepseek-v3          # or gpt-oss:120b, minimax-m2.7, ...
export LYRISEE_LLM=ollama
# Do NOT set OLLAMA_HOST to localhost — it is forced to https://ollama.com
```

HF Space: Settings → Secrets → add `OLLAMA_API_KEY`, `OLLAMA_MODEL`, `LYRISEE_LLM=ollama`.

## API

```
POST https://ollama.com/api/chat
Authorization: Bearer $OLLAMA_API_KEY
{
  "model": "deepseek-v3",
  "messages": [{"role":"system","content":"..."}, {"role":"user","content":"..."}],
  "stream": false
}
```

## Local LLMs

```bash
export OPENAI_BASE_URL=http://127.0.0.1:1234/v1   # LM Studio
export OPENAI_API_KEY=lm-studio
export OPENAI_MODEL=your-loaded-model
export LYRISEE_LLM=openai
```
