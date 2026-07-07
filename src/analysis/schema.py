"""Derive a compact schema (columns + dtypes + a few sample rows) from a dataset file.

Only a handful of sample rows are ever produced — never the full dataset — so the
result is safe to send to the LLM.
"""
import json
from pathlib import Path

import pandas as pd

_SAMPLE_ROWS = 5


def _load(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def derive_schema(path: str, name: str | None = None) -> dict:
    """Return {name, columns: {col: dtype}, sample_rows: [...], row_count}."""
    df = _load(path)
    columns = {str(c): str(df[c].dtype) for c in df.columns}
    sample = json.loads(
        df.head(_SAMPLE_ROWS).to_json(orient="records", date_format="iso")
    )
    return {
        "name": name or Path(path).stem,
        "columns": columns,
        "sample_rows": sample,
        "row_count": int(len(df)),
    }
