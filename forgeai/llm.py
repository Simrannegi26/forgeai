import hashlib
import json
import os
import re
from pathlib import Path

import requests

OLLAMA = "http://localhost:11434"
GEN_MODEL = os.getenv("FORGE_MODEL", "qwen2.5:3b")
JUDGE_MODEL = os.getenv("FORGE_JUDGE_MODEL", "llama3.2:3b")
EMBED_MODEL = "nomic-embed-text"

CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)


def _key(*parts) -> str:
    return hashlib.sha256("||".join(map(str, parts)).encode()).hexdigest()


def chat(system, user, model=None, json_mode=False, temperature=0.0, timeout=300):
    """Send one request to Ollama. Identical requests are served from disk cache."""
    model = model or GEN_MODEL
    cache_file = CACHE_DIR / f"{_key(model, system, user, json_mode, temperature)}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["text"]

    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": temperature, "seed": 42},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        payload["format"] = "json"

    r = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    text = r.json()["message"]["content"]
    cache_file.write_text(json.dumps({"text": text}), encoding="utf-8")
    return text


def extract_json(text: str):
    """Pull a JSON object out of messy model output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def chat_json(system, user, schema, model=None, retries=3):
    """Ask for JSON, validate it against a Pydantic schema, repair on failure."""
    prompt = user
    last_error = None
    for _ in range(retries):
        text = chat(system, prompt, model=model, json_mode=True)
        try:
            return schema.model_validate(extract_json(text))
        except Exception as e:
            last_error = e
            prompt = (
                f"{user}\n\nYour previous reply was invalid: {str(e)[:300]}\n"
                f"Reply with ONLY valid JSON matching this schema:\n"
                f"{json.dumps(schema.model_json_schema())}"
            )
    raise RuntimeError(f"Model failed to return valid JSON after {retries} tries: {last_error}")


def embed(texts: list[str]) -> list[list[float]]:
    r = requests.post(
        f"{OLLAMA}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["embeddings"]