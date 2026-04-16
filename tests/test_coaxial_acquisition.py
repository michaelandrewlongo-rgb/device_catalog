"""Tests for source-backed coaxial data acquisition."""

from pipeline import coaxial_acquisition


MEDTRONIC_REACT_TEXT = """
Ordering Information
React-68 132 0.083 0.068
React-71 132 0.0855 0.071
"""


PENUMBRA_RED_TEXT = """
Specs & Compatibility
.068" (1.73 mm) Lumen: Delivers powerful aspiration
.084" (2.13 mm) Outer Diameter: Atraumatic tip design
132 cm Length: To reach target vessels
"""


def test_extract_medtronic_react_dimensions():
    records = coaxial_acquisition.extract_medtronic_react(MEDTRONIC_REACT_TEXT)

    assert records == [
        {
            "device_name": "React 68",
            "fields": {"length_cm": [132], "od_inch": 0.083, "id_inch": 0.068},
            "raw_text_snippet": "React-68 132 0.083 0.068",
        },
        {
            "device_name": "React 71",
            "fields": {"length_cm": [132], "od_inch": 0.0855, "id_inch": 0.071},
            "raw_text_snippet": "React-71 132 0.0855 0.071",
        },
    ]


def test_extract_penumbra_red_68_dimensions():
    records = coaxial_acquisition.extract_penumbra_red_68(PENUMBRA_RED_TEXT)

    assert records == [
        {
            "device_name": "Penumbra RED 68",
            "fields": {"id_inch": 0.068, "od_inch": 0.084, "length_cm": [132]},
            "raw_text_snippet": (
                '.068" (1.73 mm) Lumen | .084" (2.13 mm) Outer Diameter | '
                "132 cm Length"
            ),
        }
    ]


def test_build_review_from_supplied_source_texts():
    source_texts = {
        coaxial_acquisition.SOURCE_SPECS[0].source_url: MEDTRONIC_REACT_TEXT,
        coaxial_acquisition.SOURCE_SPECS[1].source_url: PENUMBRA_RED_TEXT,
    }
    records = coaxial_acquisition.build_review(source_texts=source_texts)

    assert [record["device_name"] for record in records] == [
        "Penumbra RED 68",
        "React 68",
        "React 71",
    ]
    assert all(record["accepted"] for record in records)
    assert all(record["source_tier"] == "manufacturer" for record in records)
    assert all(record["source_access_method"] == "supplied_text" for record in records)


def test_apply_review_records_updates_only_accepted_manufacturer_records():
    data = {
        "devices": [
            {
                "name": "React 68",
                "id_inch": None,
                "od_inch": None,
                "length_cm": None,
                "source": "NEEDS_DATA",
            }
        ]
    }
    review_records = [
        {
            "accepted": True,
            "device_name": "React 68",
            "fields": {"id_inch": 0.068, "od_inch": 0.083, "length_cm": [132]},
            "source_name": "Medtronic source",
            "source_tier": "manufacturer",
            "source_url": "https://example.test/manufacturer",
        },
        {
            "accepted": True,
            "device_name": "React 68",
            "fields": {"od_inch": 0.099},
            "source_name": "Seller source",
            "source_tier": "distributor",
            "source_url": "https://example.test/seller",
        },
    ]

    changed = coaxial_acquisition.apply_review_records(data, review_records)
    device = data["devices"][0]

    assert changed == ["React 68: id_inch, od_inch, length_cm"]
    assert device["id_inch"] == 0.068
    assert device["od_inch"] == 0.083
    assert device["length_cm"] == [132]
    assert device["source"] == "manufacturer"
    assert device["source_url"] == "https://example.test/manufacturer"
