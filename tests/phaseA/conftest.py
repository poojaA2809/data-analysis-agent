"""Phase A fixtures — an engineered multi-column CSV where a SAMPLED aggregate
(first AGENT_GRID_ROW_CAP rows) differs observably from the FULL-data aggregate.

This proves aggregations run over the full dataframe while the data grid is only
a capped sample.
"""
from datetime import date, timedelta

import pandas as pd
import pytest

_N = 600  # several hundred rows (> the 200 grid cap)


def _build_dataframe() -> pd.DataFrame:
    regions = ["North", "South", "East", "West"]
    categories = ["Hardware", "Software", "Services"]
    rows = []
    start = date(2025, 1, 1)
    for i in range(_N):
        # First 200 rows (the grid sample) are ALL "North" with small amounts.
        # Rows 200+ span every region with much larger amounts, so the full-data
        # groupby/means differ sharply from the first-200 sample.
        if i < 200:
            region = "North"
            amount = 10.0 + (i % 20)          # ~10–29
        else:
            region = regions[i % 4]
            amount = 500.0 + (i % 300)        # ~500–799
        rows.append(
            {
                "order_id": f"O{i:05d}",
                "order_date": (start + timedelta(days=i % 180)).isoformat(),
                "region": region,
                "category": categories[i % 3],
                "amount": round(amount, 2),
                "units": 1 + (i % 9),
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def dashboard_csv(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("phaseA") / "dashboard_sales.csv"
    _build_dataframe().to_csv(path, index=False)
    return str(path)


@pytest.fixture(scope="session")
def dashboard_df() -> pd.DataFrame:
    return _build_dataframe()
