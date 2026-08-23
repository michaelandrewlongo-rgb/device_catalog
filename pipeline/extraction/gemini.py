"""Gemini Flash 2.5 client via OpenRouter (OpenAI-compatible endpoint).

Drop-in replacement for deepseek_extract() in enrichment/competitor-fill flows.
"""

from __future__ import annotations

import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"
MAX_RETRIES = 3
TIMEOUT = 180


def _load_openrouter_key() -> str | None:
    """Load OPENROUTER_API_KEY: env var first, then first match in master_env.txt.

    Uses first-match (not last-match) so the primary key takes precedence over
    project-specific entries lower in the file.
    """
    import os
    from pathlib import Path

    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"].strip()
    path = Path.home() / "Desktop" / "master_env.txt"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    return None


OPENROUTER_API_KEY = _load_openrouter_key()


def gemini_extract(prompt: str, max_tokens: int = 8192) -> dict | None:
    """Send prompt to Gemini Flash 2.5 via OpenRouter, parse JSON response.

    Returns dict or None. Interface mirrors deepseek_extract().
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not set")
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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
                logger.warning("OpenRouter %d, retry in %ds", resp.status_code, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_json(content)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("Gemini/OpenRouter error: %s, retry %d", exc, attempt + 1)
            time.sleep(2 ** attempt)

    logger.error("Gemini extract failed after %d retries", MAX_RETRIES)
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
        pass

    # Attempt to extract a JSON object from prose response
    import re
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse JSON from Gemini response: %s", text[:200])
    return None
