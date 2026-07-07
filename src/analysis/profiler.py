"""Deterministic dataset profiling (pandas only).

`profile_dataframe(path, filename)` computes a JSON-serialisable profile:
per-column type/null/unique stats + numeric summaries or categorical samples,
plus dataset-level data-quality flags (missing values, duplicate rows, numeric
outliers). No data values beyond small sample stats ever leave this module; the
optional LLM narration (see graph.nodes.profile) receives only these computed
stats, never the raw data.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

_TOP_VALUES = 5


def _load(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def _num(value) -> float | None:
    """Coerce a numpy/pandas scalar to a plain float, mapping NaN/inf to None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _outlier_count(series: pd.Series) -> int:
    """Count values beyond 3*IQR of the quartiles (robust outlier flag)."""
    s = series.dropna()
    if len(s) < 4:
        return 0
    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    lower = q1 - 3 * iqr
    upper = q3 + 3 * iqr
    return int(((s < lower) | (s > upper)).sum())


def _profile_column(df: pd.DataFrame, col) -> dict:
    series = df[col]
    non_null = int(series.notna().sum())
    null_count = int(series.isna().sum())
    total = len(df)
    info: dict = {
        "name": str(col),
        "dtype": str(series.dtype),
        "non_null_count": non_null,
        "null_count": null_count,
        "null_pct": round(100.0 * null_count / total, 2) if total else 0.0,
        "unique_count": int(series.nunique(dropna=True)),
    }

    if pd.api.types.is_numeric_dtype(series):
        info["is_numeric"] = True
        info["summary"] = {
            "mean": _num(series.mean()),
            "std": _num(series.std()),
            "min": _num(series.min()),
            "max": _num(series.max()),
        }
        info["outlier_count"] = _outlier_count(series)
    else:
        info["is_numeric"] = False
        top = series.dropna().astype(str).value_counts().head(_TOP_VALUES)
        info["top_values"] = [
            {"value": str(v), "count": int(c)} for v, c in top.items()
        ]
    return info


def profile_dataframe(path: str, filename: str | None = None) -> dict:
    """Compute a deterministic profile for a CSV or Excel file.

    Returns a JSON-serialisable dict: {filename, row_count, column_count,
    columns: [...], quality: {...}}.
    """
    df = _load(path)
    total = len(df)

    columns = [_profile_column(df, c) for c in df.columns]

    missing_cols = [
        {"name": c["name"], "null_count": c["null_count"], "null_pct": c["null_pct"]}
        for c in columns
        if c["null_count"] > 0
    ]
    duplicate_rows = int(df.duplicated().sum())
    outlier_cols = [
        {"name": c["name"], "outlier_count": c["outlier_count"]}
        for c in columns
        if c.get("outlier_count", 0) > 0
    ]

    return {
        "filename": filename or Path(path).name,
        "row_count": total,
        "column_count": len(df.columns),
        "columns": columns,
        "quality": {
            "missing_value_columns": missing_cols,
            "duplicate_row_count": duplicate_rows,
            "outlier_columns": outlier_cols,
        },
    }
