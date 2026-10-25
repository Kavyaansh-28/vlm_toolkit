"""Model-agnostic adapters for generation and independent visual verification."""
from __future__ import annotations

import base64
import mimetypes
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULTS = {
    "openai": "gpt-4.1-mini",
    "groq": "qwen/qwen3.8-27b",
    "gemini": "gemini-3.8-flash",
    "llama": "meta-llama/llama-4-scout",
}
KEYS = {"openai": "OPENAI_API_KEY", "groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY", "llama": "LLAMA_API_KEY"}


class VLMProvider(ABC):
    """Common image+prompt interface used by both generator and verifier roles."""

    name: str

    @abstractmethod
    def generate(self, image_path: str, prompt: str) -> dict[str, Any]:
        """Return text, configured model/provider, and an optional error."""


class OpenAICompatibleProvider(VLMProvider):
    def __init__(self, name: str, model: str, api_key: str, base_url: str | None = None):
        self.name, self.model, self.api_key, self.base_url = name, model, api_key, base_url

    def generate(self, image_path: str, prompt: str) -> dict[str, Any]:
        try:
            from openai import OpenAI

            path = Path(image_path)
            mime = mimetypes.guess_type(path.name)[0]
            if mime not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
                return {"response": "", "model": self.model, "provider": self.name,
                        "error": "Unsupported image type. Upload PNG, JPG, WEBP, or GIF."}
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=90.0, max_retries=1)
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                ]}],
                max_tokens=900,
            )
            return {"response": completion.choices[0].message.content or "", "model": self.model,
                    "provider": self.name, "probability": None, "probability_available": False}
        except ImportError:
            return {"response": "", "model": self.model, "provider": self.name,
                    "error": "The openai package is not installed. Run: python3 -m pip install openai"}
        except Exception as exc:
            return {"response": "", "model": self.model, "provider": self.name,
                    "error": f"{self.name.title()} vision request failed: {str(exc)[:240]}"}


class GeminiProvider(VLMProvider):
    def __init__(self, model: str, api_key: str):
        self.name, self.model, self.api_key = "gemini", model, api_key

    def generate(self, image_path: str, prompt: str) -> dict[str, Any]:
        try:
            from google import genai

            path = Path(image_path)
            mime = mimetypes.guess_type(path.name)[0]
            if mime not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
                return {"response": "", "model": self.model, "provider": self.name,
                        "error": "Unsupported image type. Upload PNG, JPG, WEBP, or GIF."}
            data = path.read_bytes()
            client = genai.Client(api_key=self.api_key, http_options={"timeout": 600000})
            if hasattr(client, "interactions"):
                response = client.interactions.create(
                    model=self.model,
                    input=[{"type": "text", "text": prompt},
                           {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": mime}],
                )
                text = response.output_text
            else:
                from google.genai import types
                response = client.models.generate_content(
                    model=self.model, contents=[prompt, types.Part.from_bytes(data=data, mime_type=mime)],
                )
                text = response.text
            return {"response": text or "", "model": self.model, "provider": self.name,
                    "probability": None, "probability_available": False}
        except ImportError:
            return {"response": "", "model": self.model, "provider": self.name,
                    "error": "The google-genai package is not installed. Run: python3 -m pip install google-genai"}
        except Exception as exc:
            return {"response": "", "model": self.model, "provider": self.name,
                    "error": f"Gemini vision request failed: {str(exc)[:240]}"}


def providers() -> list[str]:
    return list(DEFAULTS)


def get_provider(name: str) -> VLMProvider | None:
    """Resolve a configured provider adapter; credentials are read only server-side."""
    name = name.lower()
    if name not in DEFAULTS:
        return None
    model = os.getenv(f"{name.upper()}_MODEL", DEFAULTS[name])
    key = os.getenv(KEYS[name])
    if name == "llama":
        base_url = os.getenv("LLAMA_BASE_URL")
        if not base_url:
            return None
        return OpenAICompatibleProvider(name, model, key or "local", base_url)
    if not key:
        return None
    if name == "gemini":
        return GeminiProvider(model, key)
    base_url = "https://api.groq.com/openai/v1" if name == "groq" else None
    return OpenAICompatibleProvider(name, model, key, base_url)


def _missing_config(provider: str) -> dict[str, Any]:
    key_name = KEYS.get(provider.lower())
    if key_name:
        model = os.getenv(f"{provider.upper()}_MODEL", DEFAULTS[provider.lower()])
        if provider.lower() == "llama" and not os.getenv("LLAMA_BASE_URL"):
            return {"response": "", "model": model, "provider": provider,
                    "error": "LLAMA_BASE_URL is not configured. Add your OpenAI-compatible Llama vision endpoint to .env."}
        if not os.getenv(key_name):
            return {"response": "", "model": model, "provider": provider,
                    "error": f"{key_name} is not configured. Add it to .env or choose another provider."}
    return {"response": "", "model": "", "provider": provider, "error": f"Unknown provider: {provider}."}


def run_vlm_task(image_path: str, prompt: str, provider: str) -> dict[str, Any]:
    adapter = get_provider(provider)
    return adapter.generate(image_path, prompt) if adapter else _missing_config(provider)


def generate_vlm_response(image_path: str, query: str, provider: str = "openai") -> dict[str, Any]:
    prompt = (
        "Answer the user's question concisely using only visible image content. "
        "Avoid unsupported details and speculation.\n\n"
        f"USER QUESTION:\n{query}"
    )
    return run_vlm_task(image_path, prompt, provider)
