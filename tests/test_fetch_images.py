# tests/test_fetch_images.py
"""Unit tests for pipeline.fetch_images — all HTTP calls are mocked."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
import pipeline.fetch_images as fi
from pipeline.fetch_images import (
    extract_fallback_image,
    extract_og_image,
    image_ext_from_content_type,
    image_ext_from_url,
)

# --- Helpers ----------------------------------------------------------------

def _make_response(text: str = "", status: int = 200):
    mock = MagicMock()
    mock.text = text
    mock.status_code = status
    mock.raise_for_status = MagicMock()
    mock.iter_content = MagicMock(return_value=[b"IMGDATA"])
    mock.headers = {"content-type": "image/jpeg"}
    return mock


PAGE_OG = '<html><head><meta property="og:image" content="https://cdn.example.com/prod.jpg"></head></html>'
PAGE_FALLBACK = '<html><body><div class="product-image"><img src="/images/prod.png"></div></body></html>'
PAGE_WIDE_IMG = '<html><body><img src="/images/big.jpg" width="300"></body></html>'
PAGE_EMPTY = "<html><body><p>nothing here</p></body></html>"


# --- extract_og_image -------------------------------------------------------

def test_extract_og_image_property():
    soup = BeautifulSoup(PAGE_OG, "html.parser")
    assert extract_og_image(soup) == "https://cdn.example.com/prod.jpg"


def test_extract_og_image_name_fallback():
    html = '<html><head><meta name="og:image" content="https://example.com/img.png"></head></html>'
    assert extract_og_image(BeautifulSoup(html, "html.parser")) == "https://example.com/img.png"


def test_extract_og_image_missing():
    assert extract_og_image(BeautifulSoup("<html></html>", "html.parser")) is None


def test_extract_og_image_empty_content():
    html = '<html><head><meta property="og:image" content=""></head></html>'
    assert extract_og_image(BeautifulSoup(html, "html.parser")) is None


# --- extract_fallback_image -------------------------------------------------

def test_extract_fallback_image_product_container():
    soup = BeautifulSoup(PAGE_FALLBACK, "html.parser")
    assert extract_fallback_image(soup, "https://example.com") == "https://example.com/images/prod.png"


def test_extract_fallback_image_wide_img():
    soup = BeautifulSoup(PAGE_WIDE_IMG, "html.parser")
    assert extract_fallback_image(soup, "https://example.com") == "https://example.com/images/big.jpg"


def test_extract_fallback_image_none_for_small_img():
    html = '<html><body><img src="/icon.gif" width="16"></body></html>'
    assert extract_fallback_image(BeautifulSoup(html, "html.parser"), "https://example.com") is None


def test_extract_fallback_image_data_src():
    html = '<html><body><div class="product-media"><img data-src="/lazy.webp"></div></body></html>'
    result = extract_fallback_image(BeautifulSoup(html, "html.parser"), "https://example.com")
    assert result == "https://example.com/lazy.webp"


# --- ext helpers ------------------------------------------------------------

def test_ext_from_url_jpg():
    assert image_ext_from_url("https://cdn.example.com/prod.jpg") == ".jpg"


def test_ext_from_url_jpeg_normalized():
    assert image_ext_from_url("https://cdn.example.com/prod.jpeg") == ".jpg"


def test_ext_from_url_webp():
    assert image_ext_from_url("https://cdn.example.com/prod.webp") == ".webp"


def test_ext_from_url_unknown():
    assert image_ext_from_url("https://cdn.example.com/image?size=lg") is None


def test_ext_from_content_type_jpeg():
    assert image_ext_from_content_type("image/jpeg; charset=utf-8") == ".jpg"


def test_ext_from_content_type_png():
    assert image_ext_from_content_type("image/png") == ".png"


def test_ext_from_content_type_unknown():
    assert image_ext_from_content_type("text/html") is None


# --- get_source_url ---------------------------------------------------------

def test_get_source_url_found(tmp_path, monkeypatch):
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    (enriched / "cat--mfr--dev.json").write_text(
        json.dumps({"source_url": "https://example.com/products/dev"}), encoding="utf-8"
    )
    monkeypatch.setattr(fi, "ENRICHED_DIR", enriched)
    assert fi.get_source_url("cat--mfr--dev") == "https://example.com/products/dev"


def test_get_source_url_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(fi, "ENRICHED_DIR", tmp_path)
    assert fi.get_source_url("no--such--device") is None


def test_get_source_url_null_field(tmp_path, monkeypatch):
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    (enriched / "cat--mfr--dev.json").write_text(json.dumps({"source_url": None}), encoding="utf-8")
    monkeypatch.setattr(fi, "ENRICHED_DIR", enriched)
    assert fi.get_source_url("cat--mfr--dev") is None


# --- find_existing_image ----------------------------------------------------

def test_find_existing_image_found(tmp_path, monkeypatch):
    images = tmp_path / "images"
    images.mkdir()
    img = images / "cat--mfr--dev.jpg"
    img.write_bytes(b"x")
    monkeypatch.setattr(fi, "IMAGES_DIR", images)
    assert fi.find_existing_image("cat--mfr--dev") == img


def test_find_existing_image_not_found(tmp_path, monkeypatch):
    images = tmp_path / "images"
    images.mkdir()
    monkeypatch.setattr(fi, "IMAGES_DIR", images)
    assert fi.find_existing_image("cat--mfr--dev") is None


# --- fetch_image_for_device -------------------------------------------------

def test_fetch_image_for_device_happy_path(tmp_path, monkeypatch):
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    images = tmp_path / "images"
    images.mkdir()
    monkeypatch.setattr(fi, "ENRICHED_DIR", enriched)
    monkeypatch.setattr(fi, "IMAGES_DIR", images)
    (enriched / "cat--mfr--dev.json").write_text(
        json.dumps({"source_url": "https://example.com/prod"}), encoding="utf-8"
    )
    page_resp = _make_response(PAGE_OG)
    img_resp = _make_response()

    with patch("pipeline.fetch_images.requests.get", side_effect=[page_resp, img_resp]):
        result = fi.fetch_image_for_device("cat--mfr--dev")

    assert result == "fetched"
    assert (images / "cat--mfr--dev.jpg").read_bytes() == b"IMGDATA"


def test_fetch_image_for_device_skipped_existing(tmp_path, monkeypatch):
    images = tmp_path / "images"
    images.mkdir()
    (images / "cat--mfr--dev.jpg").write_bytes(b"existing")
    monkeypatch.setattr(fi, "IMAGES_DIR", images)

    with patch("pipeline.fetch_images.requests.get") as mock_get:
        result = fi.fetch_image_for_device("cat--mfr--dev")

    assert result == "skipped"
    mock_get.assert_not_called()


def test_fetch_image_for_device_no_enriched(tmp_path, monkeypatch):
    monkeypatch.setattr(fi, "ENRICHED_DIR", tmp_path)
    monkeypatch.setattr(fi, "IMAGES_DIR", tmp_path / "images")
    (tmp_path / "images").mkdir()
    assert fi.fetch_image_for_device("no--such--device") == "no_enriched"


def test_fetch_image_for_device_no_url(tmp_path, monkeypatch):
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    images = tmp_path / "images"
    images.mkdir()
    monkeypatch.setattr(fi, "ENRICHED_DIR", enriched)
    monkeypatch.setattr(fi, "IMAGES_DIR", images)
    (enriched / "cat--mfr--dev.json").write_text(json.dumps({"source_url": None}), encoding="utf-8")
    assert fi.fetch_image_for_device("cat--mfr--dev") == "no_url"


def test_fetch_image_for_device_page_error(tmp_path, monkeypatch):
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    images = tmp_path / "images"
    images.mkdir()
    monkeypatch.setattr(fi, "ENRICHED_DIR", enriched)
    monkeypatch.setattr(fi, "IMAGES_DIR", images)
    (enriched / "cat--mfr--dev.json").write_text(
        json.dumps({"source_url": "https://example.com/prod"}), encoding="utf-8"
    )
    with patch("pipeline.fetch_images.requests.get", side_effect=Exception("timeout")):
        assert fi.fetch_image_for_device("cat--mfr--dev") == "failed"


def test_fetch_image_for_device_no_image_on_page(tmp_path, monkeypatch):
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    images = tmp_path / "images"
    images.mkdir()
    monkeypatch.setattr(fi, "ENRICHED_DIR", enriched)
    monkeypatch.setattr(fi, "IMAGES_DIR", images)
    (enriched / "cat--mfr--dev.json").write_text(
        json.dumps({"source_url": "https://example.com/prod"}), encoding="utf-8"
    )
    with patch("pipeline.fetch_images.requests.get", return_value=_make_response(PAGE_EMPTY)):
        assert fi.fetch_image_for_device("cat--mfr--dev") == "failed"


def test_fetch_image_for_device_dry_run(tmp_path, monkeypatch, capsys):
    enriched = tmp_path / "enriched"
    enriched.mkdir()
    images = tmp_path / "images"
    images.mkdir()
    monkeypatch.setattr(fi, "ENRICHED_DIR", enriched)
    monkeypatch.setattr(fi, "IMAGES_DIR", images)
    (enriched / "cat--mfr--dev.json").write_text(
        json.dumps({"source_url": "https://example.com/prod"}), encoding="utf-8"
    )
    with patch("pipeline.fetch_images.requests.get", return_value=_make_response(PAGE_OG)):
        result = fi.fetch_image_for_device("cat--mfr--dev", dry_run=True)

    assert result == "fetched"
    assert not (images / "cat--mfr--dev.jpg").exists()
    assert "DRY-RUN" in capsys.readouterr().out
