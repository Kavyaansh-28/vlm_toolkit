"""White-box Hugging Face VLM engine (LLaVA family, BLIP-2).

Candidate 1 is greedy decoding (the uncorrected baseline); candidates 2..n are
sampled with ``temperature``.  p_j = exp(mean log-prob of the generated
tokens) from the raw logits, i.e. the length-normalised sequence probability.
"""
from __future__ import annotations

import time
from functools import lru_cache

import torch
from PIL import Image


def _model_class(model_id: str):
    import transformers
    name = model_id.lower()
    if "blip2" in name: return transformers.Blip2ForConditionalGeneration
    if "onevision" in name: return transformers.LlavaOnevisionForConditionalGeneration
    if "llava-v1.6" in name or "llava-next" in name: return transformers.LlavaNextForConditionalGeneration
    return transformers.LlavaForConditionalGeneration


class HFVLMEngine:
    def __init__(self, model_id: str = "llava-hf/llava-1.5-7b-hf", precision: str = "fp16", device: str | None = None):
        from transformers import AutoProcessor
        from utils import get_device
        self.model_id, self.precision = model_id, precision
        self.device = get_device(device or "auto")
        dtype = torch.float16 if self.device in {"cuda", "mps"} else torch.float32
        kwargs: dict = {"torch_dtype": dtype}
        if precision == "4bit" and self.device == "cuda":
            from transformers import BitsAndBytesConfig
            kwargs.update(quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                                 bnb_4bit_compute_dtype=torch.float16), device_map="auto")
        self.model = _model_class(model_id).from_pretrained(model_id, **kwargs).eval()
        if "device_map" not in kwargs:
            self.model.to(self.device)
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.is_blip2 = "blip2" in model_id.lower()

    def _inputs(self, image, query: str):
        if self.is_blip2:
            prompt = f"Question: {query} Answer:"
        else:
            conversation = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": query}]}]
            prompt = self.processor.apply_chat_template(conversation, add_generation_prompt=True)
        return self.processor(images=image, text=prompt, return_tensors="pt").to(self.model.device, self.model.dtype)

    @torch.no_grad()
    def _generate(self, image, query: str, k: int, sample: bool, temperature: float, max_new_tokens: int):
        inputs = self._inputs(image, query)
        options = {"do_sample": True, "temperature": temperature} if sample else {"do_sample": False}
        out = self.model.generate(**inputs, max_new_tokens=max_new_tokens, num_return_sequences=k,
                                  return_dict_in_generate=True, output_logits=True, **options)
        logits = out.logits if getattr(out, "logits", None) is not None else out.scores
        logp = self.model.compute_transition_scores(out.sequences, logits, normalize_logits=True)
        # One log-prob per generation step, so the last steps of `sequences` are the
        # generated tokens whether or not the model echoes the prompt (BLIP-2 vs LLaVA).
        generated = out.sequences[:, -logp.shape[1]:]
        tokenizer = getattr(self.processor, "tokenizer", self.processor)
        pad = tokenizer.pad_token_id
        rows = []
        for i in range(generated.shape[0]):
            mask = generated[i] != pad if pad is not None else torch.ones_like(generated[i], dtype=torch.bool)
            token_logp = logp[i][mask]
            token_logp = token_logp[torch.isfinite(token_logp)]
            text = tokenizer.decode(generated[i][mask], skip_special_tokens=True).strip()
            rows.append((text, float(token_logp.mean().exp()) if token_logp.numel() else None, int(mask.sum())))
        return rows

    def generate_candidates(self, image_path: str, query: str, n: int, temperature: float = .7,
                            max_new_tokens: int = 128, seed: int = 42) -> list[dict]:
        image = Image.open(image_path).convert("RGB")
        torch.manual_seed(seed)
        results = []
        for strategy, k in (("greedy", 1), ("sampled", n - 1)):
            if k <= 0: continue
            started = time.perf_counter()
            try:
                rows = self._generate(image, query, k, strategy == "sampled", temperature, max_new_tokens)
                error = None
            except torch.cuda.OutOfMemoryError as exc:  # report, never crash a benchmark run
                torch.cuda.empty_cache(); rows, error = [("", None, 0)] * k, f"CUDA OOM: {str(exc)[:160]}"
            per = round((time.perf_counter() - started) * 1000 / k)
            results += [{"response": text, "model": self.model_id, "probability": p,
                         "probability_available": p is not None, "num_tokens": tokens, "latency_ms": per,
                         "generation_strategy": strategy, "error": error} for text, p, tokens in rows]
        return results

    def generate(self, image_path: str, query: str, **kwargs) -> dict:
        return self.generate_candidates(image_path, query, 1, **kwargs)[0]

    def get_token_confidence(self, response: dict) -> float | None:
        return response.get("probability") if response.get("probability_available") else None


@lru_cache(maxsize=2)
def load_engine(model_id: str, precision: str = "fp16") -> HFVLMEngine:
    return HFVLMEngine(model_id, precision)
