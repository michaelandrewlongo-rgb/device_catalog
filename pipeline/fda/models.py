"""Pydantic models for FDA device records."""

from pydantic import BaseModel, Field


class FDA510kRecord(BaseModel):
    """Raw record from the openFDA 510(k) endpoint."""
    k_number: str = ""
    applicant: str = ""
    device_name: str = ""
    product_code: str = ""
    decision_date: str = ""
    decision_code: str = ""  # SESE = substantially equivalent
    advisory_committee_description: str = ""
    statement_or_summary: str = ""  # URL to summary PDF, if present


class FDAPMARecord(BaseModel):
    """Raw record from the openFDA PMA endpoint."""
    pma_number: str = ""
    supplement_number: str = ""
    applicant: str = ""
    trade_name: str = ""
    generic_name: str = ""
    product_code: str = ""
    decision_date: str = ""
    decision_code: str = ""  # APPR = approved


class FDADeviceRecord(BaseModel):
    """Normalized device record combining FDA data with catalog metadata."""
    clearance_type: str = ""          # "510k" or "pma"
    clearance_number: str = ""        # K-number or PMA number
    clearance_date: str = ""
    device_class: int = 0             # 1, 2, or 3
    manufacturer_canonical: str = ""  # Normalized manufacturer slug
    manufacturer_raw: str = ""        # Original FDA applicant string
    catalog_category: str = ""        # e.g., "thrombectomy"
    device_name_fda: str = ""         # Device name from FDA
    product_code: str = ""
    product_code_description: str = ""
    already_in_catalog: bool = False
    suggested_filename_stem: str = "" # e.g., "thrombectomy--stryker--trevo-nxt"
    pdf_summary_url: str = ""         # URL to 510(k) summary PDF if available
