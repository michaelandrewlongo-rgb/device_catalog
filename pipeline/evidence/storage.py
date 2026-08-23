"""Filesystem storage for evidence artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ..config import DATA_DIR

EVIDENCE_DIR = DATA_DIR / "evidence"
REGISTRY_DIR = EVIDENCE_DIR / "registry"
CLAIMS_DIR = EVIDENCE_DIR / "claims"
PUBMED_DIR = EVIDENCE_DIR / "pubmed"
TRIALS_DIR = EVIDENCE_DIR / "trials"
FDA_MAUDE_DIR = EVIDENCE_DIR / "fda_maude"
FDA_RECALLS_DIR = EVIDENCE_DIR / "fda_recalls"
FDA_RAW_DIR = EVIDENCE_DIR / "fda_raw"
GUDID_DIR = EVIDENCE_DIR / "accessgudid"
LLM_DIR = EVIDENCE_DIR / "llm"
HEALTH_DIR = EVIDENCE_DIR / "health"


def ensure_evidence_dirs() -> None:
    for path in [
        EVIDENCE_DIR,
        REGISTRY_DIR,
        CLAIMS_DIR,
        PUBMED_DIR,
        TRIALS_DIR,
        FDA_MAUDE_DIR,
        FDA_RECALLS_DIR,
        FDA_RAW_DIR,
        GUDID_DIR,
        LLM_DIR,
        HEALTH_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return value


def write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
