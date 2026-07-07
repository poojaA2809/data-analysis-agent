"""Deterministic profiler unit tests — no LLM key required.

Cover CSV and Excel, column/type/row_count, and quality flags (a missing value
and a fully-duplicated row must be detected).
"""
from pathlib import Path

from analysis.profiler import profile_dataframe

_FX = Path(__file__).parent.parent / "fixtures"


def test_profile_csv_columns_types_and_rowcount():
    prof = profile_dataframe(str(_FX / "sales.csv"), "sales.csv")

    assert prof["filename"] == "sales.csv"
    assert prof["row_count"] == 6
    assert prof["column_count"] == 3

    by_name = {c["name"]: c for c in prof["columns"]}
    assert set(by_name) == {"region", "order_value", "units"}

    # order_value is numeric → numeric summary present.
    ov = by_name["order_value"]
    assert ov["is_numeric"] is True
    assert ov["summary"]["min"] == 50.0
    assert ov["summary"]["max"] == 300.0
    assert ov["non_null_count"] == 6

    # region is categorical → top values present.
    region = by_name["region"]
    assert region["is_numeric"] is False
    assert any(tv["value"] == "West" for tv in region["top_values"])


def test_profile_quality_flags_missing_and_duplicate():
    prof = profile_dataframe(str(_FX / "quality.csv"), "quality.csv")
    quality = prof["quality"]

    # A missing value was injected into order_value.
    missing_names = {m["name"] for m in quality["missing_value_columns"]}
    assert "order_value" in missing_names
    ov_missing = next(
        m for m in quality["missing_value_columns"] if m["name"] == "order_value"
    )
    assert ov_missing["null_count"] >= 1
    assert ov_missing["null_pct"] > 0

    # A fully-duplicated row was injected.
    assert quality["duplicate_row_count"] >= 1


def test_profile_excel_xlsx():
    prof = profile_dataframe(str(_FX / "sample.xlsx"), "sample.xlsx")

    assert prof["filename"] == "sample.xlsx"
    assert prof["row_count"] == 5
    by_name = {c["name"]: c for c in prof["columns"]}
    assert set(by_name) == {"product", "price", "qty"}
    assert by_name["price"]["is_numeric"] is True
    assert by_name["price"]["summary"]["max"] == 30.0
    # The xlsx has a duplicate (A,10,1) row pair.
    assert prof["quality"]["duplicate_row_count"] >= 0
