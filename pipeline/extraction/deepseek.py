"""DeepSeek API client for structured extraction and enrichment.

OpenAI-compatible endpoint. Shared by Tier 2 (doc extraction) and Tier 3 (enrichment).
"""

from __future__ import annotations

import json
import logging
import time

import httpx

from ..config import DEEPSEEK_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_RETRIES = 3
TIMEOUT = 60


def deepseek_extract(prompt: str, max_tokens: int = 4096) -> dict | None:
    """Send prompt to DeepSeek, parse JSON response. Returns dict or None."""
    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY not set")
        return None

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                resp = client.post(BASE_URL, json=payload, headers=headers)
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = 2 ** attempt
                logger.warning("DeepSeek %d, retry in %ds", resp.status_code, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_json(content)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("DeepSeek error: %s, retry %d", exc, attempt + 1)
            time.sleep(2 ** attempt)

    logger.error("DeepSeek failed after %d retries", MAX_RETRIES)
    return None


def _parse_json(text: str) -> dict | None:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON: %s", text[:200])
        return None
