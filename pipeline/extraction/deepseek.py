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
TIMEOUT = 180


def deepseek_extract(prompt: str, max_tokens: int = 8192) -> dict | None:
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
    """Parse JSON from LLM response, stripping markdown fences if present.

    Attempts to repair truncated JSON from max_tokens cutoff.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to repair truncated JSON (common when max_tokens cuts mid-response)
    repaired = _repair_truncated_json(text)
    if repaired is not None:
        logger.warning("Repaired truncated JSON (%d chars)", len(text))
        return repaired

    logger.error("Failed to parse JSON: %s", text[:200])
    return None


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to close truncated JSON by finding last complete key-value pair."""
    if not text.startswith("{"):
        return None

    # Find the last successfully closed value boundary
    # Look for patterns like: `"value",` or `null,` or `"},`
    import re
    # Find all positions where a complete value ends (before next key or end)
    boundaries = [m.end() for m in re.finditer(r'(?:null|true|false|"|\d)\s*,\s*"', text)]
    # Also try the position after last complete key-value with closing comma
    boundaries.extend(m.start() for m in re.finditer(r',\s*"[^"]*"\s*:\s*"[^"]*$', text))
    boundaries.sort(reverse=True)

    for pos in boundaries:
        candidate = text[:pos].rstrip(" ,\n\r\t")
        open_braces = candidate.count("{") - candidate.count("}")
        attempt = candidate + "}" * max(1, open_braces)
        try:
            result = json.loads(attempt)
            if len(result) >= 1:
                return result
        except json.JSONDecodeError:
            continue

    return None
