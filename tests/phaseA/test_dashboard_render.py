"""Unit tests for the Phase-A render additions (no LLM)."""
import pandas as pd

from analysis.render import (
    _clean_charts,
    build_data_grid,
    clean_insights,
    parse_dashboard,
)


def test_pie_chart_accepted():
    charts = _clean_charts(
        [{"type": "pie", "title": "Share", "x_label": "region", "y_label": "revenue",
          "data": [{"x": "West", "y": 40}, {"x": "East", "y": 60}]}]
    )
    assert len(charts) == 1
    assert charts[0]["type"] == "pie"
    assert charts[0]["data"] == [{"x": "West", "y": 40}, {"x": "East", "y": 60}]


def test_invalid_chart_type_rejected():
    assert _clean_charts([{"type": "bubble", "data": [{"x": 1, "y": 2}]}]) == []


def test_clean_insights_bounds():
    assert clean_insights(["a", "", "  ", "b"]) == ["a", "b"]
    assert len(clean_insights([f"i{n}" for n in range(9)])) == 5
    assert clean_insights("not a list") == []


def test_parse_dashboard_builds_valid_payload():
    raw = {
        "charts": [
            {"type": "bar", "title": "By region", "x_label": "region", "y_label": "amount",
             "data": [{"x": "North", "y": 100}]},
            {"type": "pie", "title": "Share", "x_label": "region", "y_label": "amount",
             "data": [{"x": "North", "y": 100}, {"x": "South", "y": 50}]},
        ],
        "summary_table": {"title": "Totals", "columns": ["region", "amount"],
                          "rows": [["North", 100], ["South", 50]]},
    }
    grid = {"columns": ["order_id", "region"], "rows": [["O1", "North"]], "total_rows": 600}
    payload = parse_dashboard(
        raw, dataset_id="ds1", title="x — overview",
        insights=["North leads at 100."], data_grid=grid,
    )
    assert payload["dataset_id"] == "ds1"
    assert payload["status"] == "completed"
    assert {c["type"] for c in payload["charts"]} == {"bar", "pie"}
    assert payload["summary_table"]["columns"] == ["region", "amount"]
    assert payload["insights"] == ["North leads at 100."]
    assert payload["data_grid"]["total_rows"] == 600


def test_parse_dashboard_degrades_on_garbage():
    payload = parse_dashboard("not json at all")
    assert payload["charts"] == []
    assert payload["summary_table"] == {"title": "", "columns": [], "rows": []}
    assert payload["insights"] == []
    assert payload["status"] == "completed"


def test_data_grid_caps_rows_but_reports_full_total(dashboard_csv, dashboard_df):
    cap = 200
    grid = build_data_grid(dashboard_csv, cap)
    assert grid["total_rows"] == len(dashboard_df) == 600
    assert len(grid["rows"]) == cap  # capped SAMPLE
    assert grid["columns"] == list(dashboard_df.columns)


def test_sampled_aggregate_differs_from_full(dashboard_csv, dashboard_df):
    """The fixture is engineered so the first-200-row aggregate differs sharply
    from the full-data aggregate — the grid is a sample, aggregations are full."""
    full = dashboard_df
    sample = pd.read_csv(dashboard_csv).head(200)
    full_regions = set(full["region"].unique())
    sample_regions = set(sample["region"].unique())
    assert sample_regions == {"North"}
    assert full_regions == {"North", "South", "East", "West"}
    assert full["amount"].mean() > sample["amount"].mean() * 5
