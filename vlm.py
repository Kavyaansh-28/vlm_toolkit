"""Model-agnostic adapters for API-hosted generator VLMs."""
from __future__ import annotations

import base64
import math
import mimetypes
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

try:  # Verify TLS against the OS certificate store, so API calls work behind corporate TLS-inspecting proxies.
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

DEFAULTS = {
    "openai": "gpt-4.1-mini",
    "groq": "meta-llama/llama-4-scout-17b-16e-instruct",
    "gemini": "gemini-2.5-flash",
    "llama": "meta-llama/llama-4-scout",
    "hf-router": "Qwen/Qwen2.5-VL-7B-Instruct",
}
KEYS = {"openai": "OPENAI_API_KEY", "groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY",
        "llama": "LLAMA_API_KEY", "hf-router": "HF_TOKEN"}
LOCAL_PROVIDERS = ("hf-local",)
ENV_PREFIX = {"hf-router": "HF_ROUTER"}


def _configured_secret(value: str | None) -> bool:
    """Treat copied template placeholders as absent credentials."""
    return bool(value and value.strip() and "your_" not in value.lower() and "api_key_here" not in value.lower())


def _model_env(name: str) -> str:
    return f"{ENV_PREFIX.get(name, name.upper())}_MODEL"


class VLMProvider(ABC):
    """Common image+prompt interface for generator adapters."""

    name: str

    @abstractmethod
    def generate(self, image_path: str, prompt: str, temperature: float | None = None) -> dict[str, Any]:
        """Return text, configured model/provider, and an optional error."""


def _image_payload(image_path: str) -> tuple[str | None, bytes]:
    path = Path(image_path)
    mime = mimetypes.guess_type(path.name)[0]
    return (mime if mime in {"image/jpeg", "image/png", "image/webp", "image/gif"} else None), path.read_bytes()


class OpenAICompatibleProvider(VLMProvider):
    def __init__(self, name: str, model: str, api_key: str, base_url: str | None = None, logprobs: bool = False):
        self.name, self.model, self.api_key, self.base_url, self.logprobs = name, model, api_key, base_url, logprobs

    def generate(self, image_path: str, prompt: str, temperature: float | None = None) -> dict[str, Any]:
        try:
            from openai import OpenAI

            mime, data = _image_payload(image_path)
            if not mime:
                return {"response": "", "model": self.model, "provider": self.name,
                        "error": "Unsupported image type. Upload PNG, JPG, WEBP, or GIF."}
            encoded = base64.b64encode(data).decode("ascii")
            client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=90.0, max_retries=1)
            options: dict[str, Any] = {"max_tokens": 900}
            if temperature is not None: options["temperature"] = temperature
            if self.logprobs: options["logprobs"] = True
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                ]}],
                **options,
            )
            choice = completion.choices[0]
            # Native confidence when the API exposes token log-probs: exp(mean log p).
            tokens = getattr(getattr(choice, "logprobs", None), "content", None) or []
            probability = math.exp(sum(t.logprob for t in tokens) / len(tokens)) if tokens else None
            return {"response": choice.message.content or "", "model": self.model, "provider": self.name,
                    "probability": probability, "probability_available": probability is not None,
                    "num_tokens": len(tokens) or None}
        except ImportError:
            return {"response": "", "model": self.model, "provider": self.name,
                    "error": "The openai package is not installed. Run: python -m pip install openai"}
        except Exception as exc:
            return {"response": "", "model": self.model, "provider": self.name,
                    "error": f"{self.name.title()} vision request failed: {str(exc)[:240]}"}


class GeminiProvider(VLMProvider):
    def __init__(self, model: str, api_key: str):
        self.name, self.model, self.api_key = "gemini", model, api_key

    def generate(self, image_path: str, prompt: str, temperature: float | None = None) -> dict[str, Any]:
        try:
            from google import genai
            from google.genai import types

            mime, data = _image_payload(image_path)
            if not mime:
                return {"response": "", "model": self.model, "provider": self.name,
                        "error": "Unsupported image type. Upload PNG, JPG, WEBP, or GIF."}
            client = genai.Client(api_key=self.api_key, http_options={"timeout": 600000})
            config = types.GenerateContentConfig(temperature=temperature) if temperature is not None else None
            response = client.models.generate_content(
                model=self.model, contents=[prompt, types.Part.from_bytes(data=data, mime_type=mime)], config=config,
            )
            return {"response": response.text or "", "model": self.model, "provider": self.name,
                    "probability": None, "probability_available": False}
        except ImportError:
            return {"response": "", "model": self.model, "provider": self.name,
                    "error": "The google-genai package is not installed. Run: python -m pip install google-genai"}
        except Exception as exc:
            return {"response": "", "model": self.model, "provider": self.name,
                    "error": f"Gemini vision request failed: {str(exc)[:240]}"}


def providers() -> list[str]:
    return list(DEFAULTS) + list(LOCAL_PROVIDERS)


def provider_models() -> list[dict[str, str]]:
    """Public configuration safe for the UI: IDs for routing, model IDs for display.

    API keys are deliberately never included in this payload.
    """
    rows = [{"id": name, "model": os.getenv(_model_env(name)) or DEFAULTS[name]} for name in DEFAULTS]
    try:
        from core.config import raw_config
        local = raw_config().get("vlm", {}).get("hf_model", "llava-hf/llava-1.5-7b-hf")
    except Exception:
        local = "llava-hf/llava-1.5-7b-hf"
    return rows + [{"id": "hf-local", "model": f"{local} (local)"}]


def get_provider(name: str) -> VLMProvider | None:
    """Resolve a configured provider adapter; credentials are read only server-side."""
    name = name.lower()
    if name not in DEFAULTS:
        return None
    model = os.getenv(_model_env(name), DEFAULTS[name])
    key = os.getenv(KEYS[name])
    if name == "llama":
        base_url = os.getenv("LLAMA_BASE_URL")
        if not base_url:
            return None
        return OpenAICompatibleProvider(name, model, key or "local", base_url)
    if not _configured_secret(key):
        return None
    if name == "gemini":
        return GeminiProvider(model, key)
    if name == "hf-router":
        return OpenAICompatibleProvider(name, model, key, "https://router.huggingface.co/v1")
    base_url = "https://api.groq.com/openai/v1" if name == "groq" else None
    return OpenAICompatibleProvider(name, model, key, base_url, logprobs=name == "openai")


def _missing_config(provider: str) -> dict[str, Any]:
    key_name = KEYS.get(provider.lower())
    if key_name:
        model = os.getenv(_model_env(provider.lower()), DEFAULTS[provider.lower()])
        if provider.lower() == "llama" and not os.getenv("LLAMA_BASE_URL"):
            return {"response": "", "model": model, "provider": provider,
                    "error": "LLAMA_BASE_URL is not configured. Add your OpenAI-compatible Llama vision endpoint to .env."}
        if not _configured_secret(os.getenv(key_name)):
            return {"response": "", "model": model, "provider": provider,
                    "error": f"{key_name} is not configured. Add it to .env or choose another provider."}
    return {"response": "", "model": "", "provider": provider, "error": f"Unknown provider: {provider}."}


def run_vlm_task(image_path: str, prompt: str, provider: str, temperature: float | None = None) -> dict[str, Any]:
    adapter = get_provider(provider)
    return adapter.generate(image_path, prompt, temperature) if adapter else _missing_config(provider)


def generate_vlm_response(image_path: str, query: str, provider: str = "openai", temperature: float | None = None) -> dict[str, Any]:
    prompt = (
        "Answer the user's question concisely using only visible image content. "
        "Avoid unsupported details and speculation.\n\n"
        f"USER QUESTION:\n{query}"
    )
    return run_vlm_task(image_path, prompt, provider, temperature)
