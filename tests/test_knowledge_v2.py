"""Tests for the fail-closed device knowledge exchange."""

import json
from pathlib import Path
from unittest import mock

from pipeline.knowledge_v2.audit import (
    audit_registered_sources,
    inventory_legacy_knowledge,
    parse_catalog_filename,
)
from pipeline.knowledge_v2.export import build_export
from pipeline.knowledge_v2.models import (
    ClaimRecord,
    ClaimSupport,
    EvidenceDepth,
    EvidenceLayer,
    ReviewStatus,
    SourceRecord,
    SourceStatus,
)
from pipeline.knowledge_v2.official import _fetch, scan_watchlist


def test_catalog_filename_parses_stable_device_id():
    parsed = parse_catalog_filename(
        Path("liquid-embolic--medtronic--onyx-les--knowledge.md")
    )
    assert parsed.device_id == "liquid-embolic--medtronic--onyx-les"
    assert parsed.document_type == "knowledge"


def test_legacy_inventory_is_explicitly_unsupported(tmp_path):
    knowledge = tmp_path / "flow-diverter--example--alpha--knowledge.md"
    knowledge.write_text("# Alpha\n\nSource: https://example.invalid\n", encoding="utf-8")

    rows = inventory_legacy_knowledge(tmp_path)

    assert len(rows) == 1
    assert rows[0]["legacy_status"] == "legacy_derived_summary"
    assert rows[0]["review_status"] == "draft"
    assert rows[0]["claim_support"] == "unsupported"


def test_legacy_inventory_finds_relocated_data_by_device_layout(tmp_path):
    relocated = tmp_path / "pipeline" / "data" / "data_by_device"
    relocated.mkdir(parents=True)
    knowledge = relocated / "flow-diverter--example--alpha--knowledge.md"
    knowledge.write_text("# Alpha\n", encoding="utf-8")
    rows = inventory_legacy_knowledge(tmp_path)
    assert rows[0]["filename"].startswith("pipeline/data/data_by_device/")


def test_quarantined_source_requires_reason():
    record = SourceRecord(
        source_id="source:bad",
        device_id="flow-diverter--example--alpha",
        title="Bad document",
        source_type="manufacturer_ifu",
        status=SourceStatus.QUARANTINED,
        evidence_depth=EvidenceDepth.LOCAL_FULL_TEXT,
        local_filename="alpha.pdf",
        sha256="a" * 64,
    )
    assert "quarantined source requires quarantine_reason" in record.validate()


def test_source_record_rejects_absolute_or_traversing_local_filename():
    common = dict(
        source_id="source:path",
        device_id="flow-diverter--example--alpha",
        title="Alpha source",
        source_type="manufacturer_ifu",
        status=SourceStatus.CURRENT,
        evidence_depth=EvidenceDepth.LOCAL_FULL_TEXT,
        sha256="a" * 64,
    )
    absolute = SourceRecord(local_filename="C:\\Users\\Michael\\alpha.pdf", **common)
    traversing = SourceRecord(local_filename="sources/../../alpha.pdf", **common)
    assert "local_filename must be repository-relative" in absolute.validate()
    assert "local_filename must not traverse parent directories" in traversing.validate()


def test_legacy_claim_cannot_be_promoted_without_rewriting_provenance():
    claim = ClaimRecord(
        claim_id="claim:legacy",
        device_id="flow-diverter--example--alpha",
        claim_type="sizing",
        text="Example claim",
        evidence_layer=EvidenceLayer.LEGACY_DERIVED_SUMMARY,
        support=ClaimSupport.DIRECT,
        review_status=ReviewStatus.SOURCE_CHECKED,
        source_ids=("source:one",),
        locators=("page 2",),
    )
    errors = claim.validate()
    assert "legacy-derived claims must remain draft" in errors
    assert "legacy-derived claims must remain unsupported" in errors


def _source(status="current", depth="local_full_text"):
    return {
        "source_id": "source:one",
        "device_id": "flow-diverter--example--alpha",
        "title": "Alpha IFU",
        "source_type": "manufacturer_ifu",
        "status": status,
        "evidence_depth": depth,
        "local_filename": "alpha.pdf",
        "sha256": "a" * 64,
    }


def _claim(**overrides):
    row = {
        "claim_id": "claim:one",
        "device_id": "flow-diverter--example--alpha",
        "claim_type": "sizing",
        "text": "Use the labeled size range.",
        "evidence_layer": "official_labeling",
        "support": "direct",
        "review_status": "source_checked",
        "source_ids": ["source:one"],
        "locators": ["Sizing table, page 4"],
    }
    row.update(overrides)
    return row


def test_export_accepts_only_current_full_text_direct_reviewed_claim(tmp_path):
    manifest = build_export([_source()], [_claim()], tmp_path)
    claims = (tmp_path / "device_claims.v2.jsonl").read_text(encoding="utf-8")

    assert manifest["accepted_claim_count"] == 1
    assert "claim:one" in claims


def test_export_rejects_historical_source(tmp_path):
    manifest = build_export([_source(status="historical")], [_claim()], tmp_path)
    rejected = json.loads(
        (tmp_path / "rejected_claims.v2.jsonl").read_text(encoding="utf-8")
    )

    assert manifest["accepted_claim_count"] == 0
    assert "claim source is not current" in rejected["reasons"]


def test_export_rejects_metadata_only_source(tmp_path):
    manifest = build_export([_source(depth="metadata_only")], [_claim()], tmp_path)
    assert manifest["accepted_claim_count"] == 0


def test_export_rejects_draft_adjacent_or_unlocated_claims(tmp_path):
    claims = [
        _claim(claim_id="draft", review_status="draft"),
        _claim(claim_id="adjacent", support="adjacent"),
        _claim(claim_id="unlocated", locators=[]),
    ]
    manifest = build_export([_source()], claims, tmp_path)
    assert manifest["accepted_claim_count"] == 0
    assert manifest["rejected_claim_count"] == 3


def test_export_rejects_legacy_or_malformed_claims(tmp_path):
    claims = [
        _claim(claim_id="legacy", evidence_layer="legacy_derived_summary"),
        _claim(claim_id="bad-sources", source_ids="source:one"),
        _claim(claim_id="missing-layer", evidence_layer=None),
        _claim(claim_id="bogus-layer", evidence_layer="bogus"),
    ]
    manifest = build_export([_source()], claims, tmp_path)
    assert manifest["accepted_claim_count"] == 0
    assert manifest["rejected_claim_count"] == 4


def test_export_rejects_cross_device_claim(tmp_path):
    claim = _claim(device_id="flow-diverter--example--different")
    manifest = build_export([_source()], [claim], tmp_path)
    assert manifest["accepted_claim_count"] == 0


def test_export_rejects_unsafe_source_path(tmp_path):
    source = _source()
    source["local_filename"] = "/etc/passwd"
    try:
        build_export([source], [], tmp_path)
    except ValueError as exc:
        assert "safe repository-relative path" in str(exc)
    else:
        raise AssertionError("unsafe source path was exported")


def test_export_does_not_include_absolute_paths(tmp_path):
    source = _source()
    source["internal_path"] = "/home/michael/private/alpha.pdf"
    build_export([source], [_claim()], tmp_path)
    exported = (tmp_path / "device_sources.v2.jsonl").read_text(encoding="utf-8")
    assert "/home/michael" not in exported
    assert "internal_path" not in exported


def test_official_scan_rejects_non_allowlisted_domains():
    try:
        _fetch("https://example.com/device", 0.1)
    except ValueError as exc:
        assert "non-official domain" in str(exc)
    else:
        raise AssertionError("non-official source was accepted")


def test_official_scan_reports_identity_and_document_ids(tmp_path):
    watchlist = tmp_path / "watchlist.json"
    output = tmp_path / "report.json"
    watchlist.write_text(json.dumps({"sources": [{
        "source_id": "official:test",
        "device_id": "flow-diverter--example--alpha",
        "official_url": "https://www.fda.gov/example",
        "expected_terms": ["Alpha", "IFU"],
        "document_id_patterns": ["IFU[0-9]+ Rev\\. [A-Z]"],
    }]}), encoding="utf-8")
    body = b"Alpha IFU IFU12345 Rev. C"
    with mock.patch("pipeline.knowledge_v2.official._fetch", return_value=(200, body, "text/html")):
        report = scan_watchlist(watchlist, output)
    finding = report["findings"][0]
    assert finding["status"] == "reviewable"
    assert finding["detected_document_ids"] == ["IFU12345 Rev. C"]
    assert output.exists()


def test_latest_official_identity_mismatch_quarantines_current_metadata(tmp_path):
    registry = tmp_path / "registry.json"
    report = tmp_path / "report.json"
    registry.write_text(json.dumps({
        "checked_at": "2026-08-01",
        "sources": [{
            "source_id": "official:test",
            "device_id": "flow-diverter--example--alpha",
            "title": "Alpha official page",
            "source_type": "manufacturer_product_page",
            "status": "current",
            "evidence_depth": "metadata_only",
            "official_url": "https://www.fda.gov/example",
        }],
    }), encoding="utf-8")
    report.write_text(json.dumps({"findings": [{
        "source_id": "official:test",
        "status": "identity_mismatch",
    }]}), encoding="utf-8")
    records, _ = audit_registered_sources(tmp_path, registry, report)
    assert records[0].status == SourceStatus.QUARANTINED


def test_source_audit_resolves_relocated_catalog_artifact_and_pins_hash(tmp_path):
    relocated = tmp_path / "pipeline" / "data" / "data_by_device"
    relocated.mkdir(parents=True)
    filename = "flow-diverter--example--alpha--ifu.pdf"
    artifact = relocated / filename
    artifact.write_bytes(b"fake-pdf")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "checked_at": "2026-08-22",
        "sources": [{
            "source_id": "ifu:test:alpha",
            "device_id": "flow-diverter--example--alpha",
            "title": "Alpha IFU",
            "source_type": "manufacturer_ifu",
            "status": "current",
            "local_filename": filename,
            "expected_sha256": "0" * 64,
            "identity": {"required_all": ["Alpha", "REV A"]},
        }],
    }), encoding="utf-8")
    with mock.patch(
        "pipeline.knowledge_v2.audit.extract_pdf_text",
        return_value=("Alpha REV A", None),
    ):
        records, _ = audit_registered_sources(tmp_path, registry)
    assert records[0].local_filename.startswith("pipeline/data/data_by_device/")
    assert records[0].status == SourceStatus.QUARANTINED
    assert "pinned reviewed hash" in (records[0].quarantine_reason or "")
