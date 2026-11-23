import json
import os
import base64
import httpx
from pathlib import Path
from typing import AsyncGenerator

OLLAMA_URL = "http://localhost:11434"
MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:27b")

# Ollama generation options
OLLAMA_OPTIONS = {
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 64,
    "num_ctx": 8192,
    "repeat_penalty": 1.1,
}


def encode_image_base64(path: str) -> str:
    """Read image file and return base64 string for Ollama multimodal."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def stream_chat(
    messages: list[dict],
    model: str = MODEL,
    base_url: str = OLLAMA_URL,
) -> AsyncGenerator[str, None]:
    """Stream chat completion from Ollama. Yields text chunks.

    Messages can include an 'images' field with a list of base64-encoded images
    for multimodal models like Gemma 3.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        async with client.stream(
            "POST",
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": OLLAMA_OPTIONS,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    break


async def check_health(base_url: str = OLLAMA_URL) -> bool:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            r = await client.get(f"{base_url}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
