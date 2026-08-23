"""OpenRouter client for bounded LLM helper tasks."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from ..config import OPENROUTER_API_KEY
from .models import EvidenceInterpretation, ReviewStatus, utc_now_iso
from .storage import LLM_DIR, read_json, write_json

logger = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/auto"


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
        cache_dir: Path = LLM_DIR / "cache",
    ):
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model
        self.timeout = timeout
        self.cache_dir = cache_dir

    def chat_json(
        self,
        task: str,
        messages: list[dict[str, str]],
        source_ids: list[str] | None = None,
        max_tokens: int = 2048,
    ) -> EvidenceInterpretation | None:
        if not self.api_key:
            logger.error("OPENROUTER_API_KEY is not configured")
            return None
        prompt_hash = self._hash_payload(task, messages, max_tokens)
        cached = self._read_cache(prompt_hash)
        if cached is not None:
            return EvidenceInterpretation(
                interpretation_id=f"llm:{prompt_hash}",
                task=task,
                model=self.model,
                prompt_hash=prompt_hash,
                created_at=cached["created_at"],
                source_ids=source_ids or [],
                status=ReviewStatus.DRAFT,
                output=cached["output"],
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(BASE_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        output = _parse_json(content)
        created_at = utc_now_iso()
        self._write_cache(prompt_hash, {"created_at": created_at, "output": output})
        return EvidenceInterpretation(
            interpretation_id=f"llm:{prompt_hash}",
            task=task,
            model=self.model,
            prompt_hash=prompt_hash,
            created_at=created_at,
            source_ids=source_ids or [],
            status=ReviewStatus.DRAFT,
            output=output,
        )

    def _hash_payload(self, task: str, messages: list[dict[str, str]], max_tokens: int) -> str:
        payload = {
            "task": task,
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _cache_path(self, prompt_hash: str) -> Path:
        return self.cache_dir / f"{prompt_hash}.json"

    def _read_cache(self, prompt_hash: str) -> dict[str, Any] | None:
        path = self._cache_path(prompt_hash)
        if not path.exists():
            return None
        return read_json(path)

    def _write_cache(self, prompt_hash: str, payload: dict[str, Any]) -> None:
        write_json(self._cache_path(prompt_hash), payload)


def _parse_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = "\n".join(line for line in stripped.splitlines() if not line.strip().startswith("```"))
    return json.loads(stripped)
