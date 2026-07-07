"""Rich output: a group-by question yields real charts + key_stats (real Gemini)."""
from pathlib import Path

import pytest

_CSV = Path(__file__).parent.parent / "fixtures" / "sales.csv"
_VALID_TYPES = {"bar", "line", "scatter"}


def _upload(api_client):
    with _CSV.open("rb") as f:
        up = api_client.post(
            "/datasets", files={"file": ("sales.csv", f, "text/csv")}
        ).json()["data"]
    return up["session_id"], up["dataset_id"]


@pytest.mark.usefixtures("_require_llm_key")
def test_groupby_question_yields_chart_and_key_stats(api_client):
    session_id, dataset_id = _upload(api_client)
    r = api_client.post(
        f"/sessions/{session_id}/messages",
        json={"question": "Show total order_value by region.",
              "dataset_ids": [dataset_id]},
    )
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["answer_text"]

    assert isinstance(data["charts"], list) and len(data["charts"]) >= 1
    chart = data["charts"][0]
    assert chart["type"] in _VALID_TYPES
    assert isinstance(chart["data"], list) and len(chart["data"]) >= 1
    assert "x" in chart["data"][0] and "y" in chart["data"][0]

    assert isinstance(data["key_stats"], list) and len(data["key_stats"]) >= 1
    assert "label" in data["key_stats"][0] and "value" in data["key_stats"][0]
