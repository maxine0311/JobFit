"""Hand-written LLM helper: OpenAI-compatible chat with token/cost tracking."""

from __future__ import annotations

import json
import re

from openai import OpenAI

from rag.config import Settings, settings as default_settings


class LLM:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or default_settings
        self.client = OpenAI(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
        )

    def chat(self, system: str, user: str, temperature: float = 0.0) -> dict:
        resp = self.client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        usage = resp.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        s = self.settings
        cost = (prompt_tokens / 1_000_000) * s.input_price_per_m + (
            completion_tokens / 1_000_000
        ) * s.output_price_per_m
        return {
            "text": resp.choices[0].message.content or "",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost,
        }

    def chat_json(self, system: str, user: str, temperature: float = 0.0) -> dict:
        out = self.chat(system, user, temperature=temperature)
        m = re.search(r"\{.*\}", out["text"], re.S)
        try:
            data = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            data = {}
        return {**out, "data": data}
