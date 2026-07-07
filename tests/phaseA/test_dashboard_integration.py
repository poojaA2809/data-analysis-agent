"""Real end-to-end auto-dashboard integration (real Google Gemini + real
subprocess executor). Skips ONLY if no LLM key is present in .env."""
import pytest

from config.settings import get_settings

_VALID_TYPES = {"bar", "line", "pie", "scatter"}


def _upload(api_client, csv_path: str):
    with open(csv_path, "rb") as f:
        up = api_client.post(
            "/datasets", files={"file": ("dashboard_sales.csv", f, "text/csv")}
        ).json()["data"]
    return up["session_id"], up["dataset_id"]


@pytest.mark.usefixtures("_require_llm_key")
def test_auto_dashboard_happy_path(api_client, dashboard_csv, dashboard_df):
    _session_id, dataset_id = _upload(api_client, dashboard_csv)

    r = api_client.post(f"/datasets/{dataset_id}/dashboard")
    assert r.status_code == 200, r.text
    d = r.json()["data"]

    assert d["status"] == "completed"
    assert d["dataset_id"] == dataset_id
    assert d["title"]

    # >= 2 charts, all valid types, with a non-bar type present (a temporal
    # column and part-of-whole shares warrant a line/pie/scatter).
    charts = d["charts"]
    assert isinstance(charts, list) and len(charts) >= 2
    types = {c["type"] for c in charts}
    assert types.issubset(_VALID_TYPES)
    assert len(types) >= 2 or any(t != "bar" for t in types)
    for c in charts:
        assert isinstance(c["data"], list) and c["data"]
        assert "x" in c["data"][0] and "y" in c["data"][0]

    # Non-empty grouped summary table.
    st = d["summary_table"]
    assert st["columns"] and st["rows"]

    # 2–5 grounded insights.
    assert 2 <= len(d["insights"]) <= 5
    assert all(isinstance(s, str) and s.strip() for s in d["insights"])

    # Data grid: capped SAMPLE, but the TRUE full row count.
    grid = d["data_grid"]
    cap = get_settings().grid_row_cap
    assert grid["total_rows"] == len(dashboard_df) == 600
    assert len(grid["rows"]) <= cap
    assert grid["columns"] == list(dashboard_df.columns)


def test_auto_dashboard_unknown_dataset_404(api_client):
    r = api_client.post("/datasets/does-not-exist/dashboard")
    assert r.status_code == 404
