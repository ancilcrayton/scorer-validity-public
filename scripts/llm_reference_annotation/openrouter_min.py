"""Minimal OpenRouter chat client for LLM reference annotation."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


class EmptyCompletionError(RuntimeError):
    pass


class OpenRouterMin:
    def __init__(
        self,
        *,
        cache_dir: Path,
        timeout_seconds: float = 180.0,
        cache_responses: bool = False,
    ):
        from openai import OpenAI

        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Add it to the environment or .env before live runs."
            )
        self.cache_dir = cache_dir
        self.cache_responses = cache_responses
        if self.cache_responses:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=timeout_seconds,
        )

    def _cache_file(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_completion_tokens: int,
        seed: int,
        reasoning: dict[str, Any] | None,
        force: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
            "seed": seed,
            "response_format": {"type": "json_object"},
        }
        extra_body: dict[str, Any] = {}
        if reasoning is not None:
            extra_body["reasoning"] = reasoning
        cache_key = hashlib.sha256(
            json.dumps({"payload": payload, "extra_body": extra_body}, sort_keys=True).encode()
        ).hexdigest()
        cache_path = self._cache_file(cache_key)
        if self.cache_responses and cache_path.exists() and not force:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            text = str(cached.get("text", ""))
            if text.strip():
                return text

        kwargs: dict[str, Any] = dict(payload)
        if extra_body:
            kwargs["extra_body"] = extra_body
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                text = (resp.choices[0].message.content or "").strip()
                if not text:
                    raise EmptyCompletionError("empty completion text")
                if self.cache_responses:
                    cache_path.write_text(
                        json.dumps({"text": text, "model": model}, indent=2),
                        encoding="utf-8",
                    )
                return text
            except Exception as exc:  # noqa: BLE001 — retry transient API failures
                last_exc = exc
                time.sleep(1.0 + attempt)
        assert last_exc is not None
        raise last_exc
