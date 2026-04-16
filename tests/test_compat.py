"""Tests for thrombectomy coaxial compatibility data and query logic."""

import json
from pathlib import Path

import pytest

from pipeline import compat_query


DATA_PATH = (
    Path(__file__).parent.parent
    / "pipeline"
    / "data"
    / "compatibility"
    / "thrombectomy_stack.json"
)


@pytest.fixture
def compatibility_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def devices(compatibility_data):
    return [d for d in compatibility_data["devices"] if "_section" not in d]


def test_json_loads_without_error(compatibility_data):
    assert "devices" in compatibility_data
    assert "_meta" in compatibility_data


def test_no_duplicate_names(devices):
    names = [d["name"] for d in devices]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert dupes == []


def test_required_fields_present(devices):
    required = ["name", "manufacturer", "category", "role", "source"]
    for device in devices:
        for field in required:
            assert device.get(field), f"{device.get('name', '?')} missing {field}"


def test_id_less_than_od_where_both_present(devices):
    for device in devices:
        id_val = device.get("id_inch")
        od_val = device.get("od_inch")
        if id_val is not None and od_val is not None:
            assert id_val < od_val, (
                f"{device['name']}: ID ({id_val}) >= OD ({od_val}); "
                "dimensions may be swapped"
            )


def test_od_prox_gte_distal_od_where_both_present(devices):
    for device in devices:
        distal_od = device.get("od_inch")
        proximal_od = device.get("od_prox_inch")
        if distal_od is not None and proximal_od is not None:
            assert proximal_od >= distal_od, (
                f"{device['name']}: proximal OD ({proximal_od}) < "
                f"distal OD ({distal_od})"
            )


def test_dimensions_in_reasonable_inch_range(devices):
    for device in devices:
        for field in ["id_inch", "od_inch", "od_prox_inch", "min_guide_id_inch"]:
            value = device.get(field)
            if value is not None:
                assert 0.010 < value < 0.200, (
                    f"{device['name']}.{field} = {value}; expected inches"
                )


def test_lengths_are_positive(devices):
    for device in devices:
        lengths = device.get("length_cm")
        if lengths:
            for length in lengths:
                assert length > 0, f"{device['name']} has non-positive length"


def test_all_stack_categories_represented(devices):
    categories = {d["category"] for d in devices}
    expected = {
        "guide_catheter",
        "intermediate",
        "aspiration",
        "microcatheter",
        "stent_retriever",
    }
    assert expected.issubset(categories)


def test_at_least_current_device_count(devices):
    assert len(devices) >= 34


def test_fits_through_true_false_and_unknown():
    inner = {"name": "inner", "od_inch": 0.021}
    tapered_inner = {"name": "tapered", "od_inch": 0.021, "od_prox_inch": 0.035}
    outer = {"name": "outer", "id_inch": 0.070}
    too_small = {"name": "small", "id_inch": 0.021}
    unknown = {"name": "unknown", "id_inch": None}

    assert compat_query.fits_through(inner, outer) is True
    assert compat_query.fits_through(tapered_inner, too_small) is False
    assert compat_query.fits_through(inner, unknown) is None


def test_find_device_allows_fuzzy_name(devices):
    match = compat_query.find_device("sofia6", devices)
    assert match["name"] == "SOFIA 6F"


def test_verification_status_is_derived_from_source():
    assert compat_query.verification_status({"source": "catalog"}) == "verified"
    assert compat_query.verification_status({"source": "catalog-partial"}) == "partial"
    assert compat_query.verification_status({"source": "catalog-inferred"}) == "inferred_existing"
    assert compat_query.verification_status({"source": "NEEDS_DATA"}) == "needs_source"


def test_gap_kind_marks_missing_aspiration_od_as_critical():
    device = {"role": "aspiration_catheter"}
    assert compat_query.gap_kind(device, "od_inch") == "critical"


def test_case_output_includes_source_and_unknown_counts(devices, capsys):
    compat_query.build_case("SOFIA 6F", devices)
    output = capsys.readouterr().out

    assert "Case device: SOFIA 6F" in output
    assert "Source:" in output
    assert "Inner devices that fit through it:" in output


def test_gaps_output_groups_unresolved_sources(devices, capsys):
    compat_query.show_gaps(devices)
    output = capsys.readouterr().out

    assert "CRITICAL" in output
    assert "UNRESOLVED" in output
    assert "AXS Catalyst 6" in output


def test_manufacturer_acquired_dimensions_are_present(devices):
    by_name = {device["name"]: device for device in devices}

    assert by_name["React 68"]["id_inch"] == 0.068
    assert by_name["React 68"]["od_inch"] == 0.083
    assert by_name["React 68"]["length_cm"] == [132]
    assert by_name["React 68"]["source"] == "manufacturer"

    assert by_name["React 71"]["id_inch"] == 0.071
    assert by_name["React 71"]["od_inch"] == 0.0855
    assert by_name["React 71"]["length_cm"] == [132]
    assert by_name["React 71"]["source"] == "manufacturer"

    assert by_name["Penumbra RED 68"]["id_inch"] == 0.068
    assert by_name["Penumbra RED 68"]["od_inch"] == 0.084
    assert by_name["Penumbra RED 68"]["length_cm"] == [132]
    assert by_name["Penumbra RED 68"]["source"] == "manufacturer"
