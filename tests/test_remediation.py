"""Tests for the 2026-08 remediation: validators, correction appliers, exports."""

import json

import pytest

from pipeline.export_devices_nested import build_tree
from pipeline.export_flat_dimensions import derive_source_year, normalize_decimal
from pipeline.knowledge_v2 import apply_extraction_corrections as aec
from pipeline.knowledge_v2 import ingest_manufacturer_catalog as imc
from pipeline.knowledge_v2.validate_dimensions import (
    check_in_mm_consistency,
    check_inner_le_outer,
    check_other_fields_json,
    check_source_year,
    check_vendor_casing,
    find_bleed_candidates,
    find_decimal_commas,
    find_duplicate_catalog_numbers,
)


def _claim(device_id, numbers, manufacturer="example"):
    return {
        "claim_id": f"claim:catalog:{manufacturer}:test_set:{device_id.split('--')[-1]}",
        "device_id": device_id,
        "manufacturer": manufacturer,
        "skus": [{"catalog_number": n} for n in numbers],
    }


def test_duplicate_catalog_numbers_error_without_allowlist():
    claims = [_claim("aspiration--example--alpha", ["A100"]),
              _claim("distal-access--example--beta", ["A100"])]
    findings = find_duplicate_catalog_numbers(claims, allowlist=[])
    assert [f["check"] for f in findings] == ["duplicate_catalog_number"]
    assert findings[0]["severity"] == "error"


def test_duplicate_catalog_numbers_honors_allowlist():
    claims = [_claim("aspiration--example--alpha", ["A100"]),
              _claim("distal-access--example--beta", ["A100"])]
    allow = [{"manufacturer": "example", "catalog_number": "A100",
              "device_ids": ["aspiration--example--alpha", "distal-access--example--beta"],
              "reason": "dual listing verified"}]
    assert find_duplicate_catalog_numbers(claims, allowlist=allow) == []


def _row(family, number, section="Stents", pdf_page=3, fields=None):
    return {"product_family": family, "catalog_number": number, "section": section,
            "pdf_page": pdf_page, "fields": fields or {}}


def test_bleed_shared_catalog_number_is_error():
    rows = {"stryker_catalog_2024": [_row("Alpha Stent", "X1"), _row("Beta Kit", "X1")]}
    checks = {f["check"] for f in find_bleed_candidates(rows, allowlist=[])}
    assert "bleed_shared_catalog_number" in checks


def test_bleed_shared_catalog_number_honors_allowlist():
    rows = {"stryker_catalog_2024": [_row("Alpha Stent", "X1"), _row("Beta Kit", "X1")]}
    allow = [{"manufacturer": "stryker", "catalog_number": "X1",
              "device_ids": [], "reason": "dual listing"}]
    findings = find_bleed_candidates(rows, allowlist=allow)
    assert not [f for f in findings if f["check"] == "bleed_shared_catalog_number"]


def test_bleed_implausible_fields_flags_syringe_columns_on_stent():
    rows = {"s": [_row("Alpha Carotid Stent", "C1",
                       fields={"vaclok_spheres": "20", "diameter_mm": "25"})]}
    findings = find_bleed_candidates(rows, allowlist=[])
    hits = [f for f in findings if f["check"] == "bleed_implausible_fields"]
    assert hits and hits[0]["severity"] == "error"


def test_bleed_shape_outlier_is_warn_only():
    rows = {"s": [_row("Coils", "900017", pdf_page=1),
                  _row("Coils", "900018", pdf_page=1),
                  _row("Coils", "CBL002", pdf_page=1),
                  _row("Cables", "CBL001", pdf_page=2),
                  _row("Cables", "CBL003", pdf_page=2),
                  _row("Cables", "CBL004", pdf_page=2)]}
    outliers = [f for f in find_bleed_candidates(rows, allowlist=[])
                if f["check"] == "bleed_shape_outlier"]
    assert outliers and all(f["severity"] == "warn" for f in outliers)


def test_in_mm_consistency_accepts_printed_precision_rounding():
    rows = {"s": [_row("F", "N1", fields={"id": "0.070in (1.8mm)"})]}
    assert check_in_mm_consistency(rows, allowlist=[]) == []


def test_in_mm_consistency_flags_truncated_conversion():
    rows = {"s": [_row("F", "N1", fields={"id": "0.078in (1.9mm)"})]}
    findings = check_in_mm_consistency(rows, allowlist=[])
    assert [f["check"] for f in findings] == ["in_mm_mismatch"]


def test_in_mm_consistency_honors_allowlist():
    rows = {"s": [_row("F", "N1", fields={"id": "0.078in (1.9mm)"})]}
    allow = [{"set": "s", "catalog_number": "N1", "field": "id", "reason": "printed"}]
    assert check_in_mm_consistency(rows, allowlist=allow) == []


def test_csv_checks_cover_json_year_diameter_comma_and_casing():
    rows = [
        {"claim_id": "c1", "other_fields": "not json", "evidence_layer": "manufacturer_catalog",
         "source_year": "", "inner_diameter": "2.4 mm", "outer_diameter": "2.0 mm",
         "length": "1,5 cm", "manufacturer": "Stryker"},
    ]
    assert [f["check"] for f in check_other_fields_json(rows)] == ["other_fields_json"]
    assert [f["check"] for f in check_source_year(rows)] == ["source_year_missing"]
    assert check_source_year(rows)[0]["severity"] == "warn"
    assert [f["check"] for f in check_inner_le_outer(rows)] == ["inner_gt_outer"]
    assert [f["check"] for f in find_decimal_commas(rows)] == ["decimal_comma"]
    assert [f["check"] for f in check_vendor_casing(rows)] == ["vendor_casing"]


def test_normalize_decimal_handles_lists_and_mixed_units():
    assert normalize_decimal("5,0/4,0 mm") == "5.0/4.0 mm"
    assert normalize_decimal("1,02 mm (.040'') mm/in") == "1.02 mm (.040'') mm/in"
    assert normalize_decimal("2.4 mm") == "2.4 mm"


def test_derive_source_year_falls_back_through_revision_and_checked_at():
    assert derive_source_year({"catalog_year": "2019"}, {}) == "2019"
    assert derive_source_year({}, {"revision": "website as captured 2026-08-23"}) == "2026"
    assert derive_source_year({"checked_at": "2025-01-02"}, {}) == "2025"
    assert derive_source_year({}, {}) == ""


def test_build_tree_groups_by_device_id_and_suffixes_collisions():
    rows = [
        {"device_id": "microcatheter--acme--alpha", "device_name": "Alpha",
         "manufacturer": "acme", "category": "microcatheter"},
        {"device_id": "microcatheter--acme--alpha", "device_name": "Alpha",
         "manufacturer": "acme", "category": "microcatheter"},
        {"device_id": "microcatheter--other--alpha", "device_name": "Alpha O",
         "manufacturer": "other", "category": "microcatheter"},
    ]
    tree = build_tree(rows)
    assert ("microcatheter", "alpha--acme") in tree
    assert ("microcatheter", "alpha--other") in tree
    assert len(tree[("microcatheter", "alpha--acme")]["rows"]) == 2


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_extraction_corrections_exclude_and_update_are_idempotent(tmp_path, monkeypatch):
    extracted = tmp_path / "extracted"
    corrections = extracted / "corrections"
    corrections.mkdir(parents=True)
    monkeypatch.setattr(aec, "EXTRACTED_DIR", extracted)
    monkeypatch.setattr(aec, "CORRECTIONS_DIR", corrections)
    _write_jsonl(extracted / "demo.rows.jsonl", [
        _row("Bad Family", "B1"),
        _row("Good Family", "G1", fields={"id": "wrong"}),
    ])
    _write_jsonl(corrections / "demo.corrections.jsonl", [
        {"action": "exclude_family", "product_family": "Bad Family",
         "evidence": "page defect", "date": "2026-08-24"},
        {"action": "update_fields", "match": {"catalog_number": "G1"},
         "set": {"catalog_number": "G2"}, "evidence": "page prints G2", "date": "2026-08-24"},
    ])
    first = aec.apply_set("demo")
    assert len(first["applied"]) == 2
    rows = [json.loads(l) for l in (extracted / "demo.rows.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["catalog_number"] for r in rows] == ["G2"]
    assert "Corrected:" in rows[0]["notes"]
    excluded = [json.loads(l) for l in (extracted / "demo.excluded.jsonl").read_text(encoding="utf-8").splitlines()]
    assert excluded[0]["excluded_row"]["catalog_number"] == "B1"
    second = aec.apply_set("demo")
    assert second["applied"] == [] and len(second["skipped"]) == 2


def test_extraction_corrections_refuse_ambiguous_match(tmp_path, monkeypatch):
    extracted = tmp_path / "extracted"
    corrections = extracted / "corrections"
    corrections.mkdir(parents=True)
    monkeypatch.setattr(aec, "EXTRACTED_DIR", extracted)
    monkeypatch.setattr(aec, "CORRECTIONS_DIR", corrections)
    _write_jsonl(extracted / "demo.rows.jsonl", [_row("F", "A1"), _row("F", "A1")])
    _write_jsonl(corrections / "demo.corrections.jsonl", [
        {"action": "update_fields", "match": {"catalog_number": "A1"},
         "set": {"catalog_number": "A2"}, "evidence": "x"},
    ])
    with pytest.raises(ValueError, match="matched 2 rows"):
        aec.apply_set("demo")


def test_ingest_rebuild_purges_only_its_own_set(tmp_path, monkeypatch):
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    registry = data / "source_registry.json"
    claims = data / "reviewed_claims.v2.jsonl"
    monkeypatch.setattr(imc, "EXTRACTED_DIR", extracted)
    monkeypatch.setattr(imc, "REGISTRY", registry)
    monkeypatch.setattr(imc, "CLAIMS", claims)
    monkeypatch.setattr(imc, "CATALOG_ROOT", tmp_path)
    (tmp_path / "cat.pdf").write_bytes(b"%PDF-1.4")
    _write_jsonl(extracted / "demo_set.rows.jsonl", [
        {"product_family": "Alpha Stent", "product_name": "Alpha", "section": "Stents",
         "catalog_number": "A1", "pdf_page": 3, "printed_page": 3,
         "fields": {"length": "10"}, "units": {}, "headers": {}},
    ])
    (extracted / "demo_set.summary.json").write_text(json.dumps(
        {"pdf_sha256": "0" * 64, "title": "Demo", "catalog_year": "2024"}), encoding="utf-8")
    other_source = {"source_id": "catalog:other:other_set:x", "device_id": "x"}
    other_claim = {"claim_id": "claim:catalog:other:other_set:x", "device_id": "x"}
    registry.write_text(json.dumps({"sources": [other_source]}), encoding="utf-8")
    _write_jsonl(claims, [other_claim])

    result = imc.ingest("demo_set", "example", "cat.pdf", rebuild=True)
    assert result["new_claims"] == 1 and result["purged_claims"] == 0

    result = imc.ingest("demo_set", "example", "cat.pdf", rebuild=True,
                        review_note="rebuilt after re-verification")
    assert result["purged_claims"] == 1 and result["new_claims"] == 1

    kept = [json.loads(l) for l in claims.read_text(encoding="utf-8").splitlines()]
    assert other_claim["claim_id"] in {c["claim_id"] for c in kept}
    rebuilt = [c for c in kept if c["claim_id"].startswith("claim:catalog:example:demo_set:")]
    assert rebuilt and rebuilt[0]["review_note"] == "rebuilt after re-verification"
