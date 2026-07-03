"""Unit tests for the finalize JSON parser (no LLM)."""
from analysis.render import parse_finalize


def test_parse_full_structured():
    raw = """```json
    {"answer": "West leads with 400.",
     "charts": [{"type": "bar", "title": "Sales by region", "x_label": "region",
                 "y_label": "total", "data": [{"x": "West", "y": 400}, {"x": "East", "y": 350}]}],
     "tables": [{"title": "Totals", "columns": ["region", "total"], "rows": [["West", 400]]}],
     "key_stats": [{"label": "Top region", "value": "West", "delta": "+50"}],
     "followups": ["What about units?", "Trend over time?"]}
    ```"""
    out = parse_finalize(raw)
    assert out["answer"].startswith("West leads")
    assert out["charts"][0]["type"] == "bar"
    assert out["charts"][0]["data"][0] == {"x": "West", "y": 400}
    assert out["tables"][0]["columns"] == ["region", "total"]
    assert out["key_stats"][0]["label"] == "Top region"
    assert len(out["followups"]) == 2


def test_parse_tolerates_prose_around_json():
    raw = 'Here is the result:\n{"answer": "42 rows.", "charts": [], "key_stats": [{"label":"Rows","value":42}]}\nHope that helps!'
    out = parse_finalize(raw)
    assert "42" in out["answer"]
    assert out["charts"] == []
    assert out["key_stats"][0]["value"] == 42


def test_parse_fallback_on_non_json():
    raw = "The average order value is 175 dollars."
    out = parse_finalize(raw)
    assert out["answer"] == raw
    assert out["charts"] == [] and out["tables"] == [] and out["key_stats"] == []


def test_invalid_chart_type_dropped():
    raw = '{"answer": "x", "charts": [{"type": "pie", "data": [{"x": 1, "y": 2}]}]}'
    assert parse_finalize(raw)["charts"] == []


def test_chart_rows_capped():
    pts = ",".join(f'{{"x": {i}, "y": {i}}}' for i in range(500))
    raw = f'{{"answer": "x", "charts": [{{"type": "line", "data": [{pts}]}}]}}'
    out = parse_finalize(raw)
    assert len(out["charts"][0]["data"]) == 200


def test_followups_capped_to_three():
    raw = '{"answer": "x", "followups": ["a", "b", "c", "d", "e"]}'
    assert len(parse_finalize(raw)["followups"]) == 3
