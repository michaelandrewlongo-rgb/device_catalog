"""Bounded official-source availability and revision scan.

This scanner is deliberately non-promotional: a healthy page or newly detected
document identifier becomes a review finding, never an automatically approved
clinical claim.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .io import read_json, write_json

ALLOWED_OFFICIAL_DOMAINS = {
    "medtronic.com",
    "www.medtronic.com",
    "stryker.com",
    "www.stryker.com",
    "terumoneuro.com",
    "www.terumoneuro.com",
    "accessdata.fda.gov",
    "www.accessdata.fda.gov",
    "fda.gov",
    "www.fda.gov",
}


def _fetch(url: str, timeout: float) -> tuple[int, bytes, str]:
    host = (urllib.parse.urlparse(url).hostname or "").casefold()
    if host not in ALLOWED_OFFICIAL_DOMAINS:
        raise ValueError(f"non-official domain is not allowed: {host}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "agent-textbooks-device-watch/2.0 (private source verification)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read(), response.headers.get_content_type()


def _body_text(body: bytes) -> str:
    """Decode a fetched body for identity checks; PDF bodies are text-extracted.

    A 510(k) summary is a PDF. Matching expected terms against its raw bytes would
    always fail (content streams are compressed), which would quarantine every
    correct regulatory source. Falls back to raw decoding when PyMuPDF is absent.
    """
    if body.startswith(b"%PDF"):
        try:
            import fitz  # PyMuPDF

            with fitz.open(stream=body, filetype="pdf") as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception:  # pragma: no cover - extraction fallback
            pass
    return body.decode("utf-8", errors="replace")


def scan_watchlist(watchlist_path: Path, output_path: Path, timeout: float = 20.0) -> dict[str, Any]:
    config = read_json(watchlist_path)
    findings: list[dict[str, Any]] = []
    for index, entry in enumerate(config["sources"]):
        if index:
            time.sleep(0.15)
        finding: dict[str, Any] = {
            "source_id": entry["source_id"],
            "device_id": entry["device_id"],
            "official_url": entry["official_url"],
            "checked_at": datetime.now(UTC).isoformat(),
            "status": "unavailable",
            "identity_match": False,
            "detected_document_ids": [],
        }
        try:
            status, body, content_type = _fetch(entry["official_url"], timeout)
            text = _body_text(body)
            folded = text.casefold()
            expected = entry.get("expected_terms", [])
            blocked = any(
                marker in folded
                for marker in ("incorrect browser", "access denied", "enable javascript and cookies")
            )
            finding.update(
                {
                    "http_status": status,
                    "content_type": content_type,
                    "content_sha256": hashlib.sha256(body).hexdigest(),
                    "identity_match": all(term.casefold() in folded for term in expected),
                    "detected_document_ids": sorted(
                        {
                            match.group(0)
                            for pattern in entry.get("document_id_patterns", [])
                            for match in re.finditer(pattern, text, flags=re.IGNORECASE)
                        }
                    ),
                }
            )
            if blocked:
                finding["status"] = "blocked"
                finding["error"] = "Official page rejected the non-browser scanner."
            else:
                finding["status"] = "reviewable" if finding["identity_match"] else "identity_mismatch"
        except (ValueError, urllib.error.URLError, TimeoutError, OSError) as exc:
            finding["error"] = f"{type(exc).__name__}: {exc}"
        findings.append(finding)

    report = {
        "schema_version": "2.0.0",
        "policy": "official_domains_only_no_automatic_claim_promotion",
        "generated_at": datetime.now(UTC).isoformat(),
        "findings": findings,
    }
    write_json(output_path, report)
    return report
