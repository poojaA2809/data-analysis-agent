"""Proactive assist: follow-ups on a normal question; conservative clarify gate."""
from pathlib import Path

import pytest

_CSV = Path(__file__).parent.parent / "fixtures" / "sales.csv"


def _upload(api_client):
    with _CSV.open("rb") as f:
        up = api_client.post(
            "/datasets", files={"file": ("sales.csv", f, "text/csv")}
        ).json()["data"]
    return up["session_id"], up["dataset_id"]


@pytest.mark.usefixtures("_require_llm_key")
def test_normal_question_returns_followups_and_runs(api_client):
    session_id, dataset_id = _upload(api_client)
    r = api_client.post(
        f"/sessions/{session_id}/messages",
        json={"question": "What is the average order_value by region?",
              "dataset_ids": [dataset_id]},
    )
    data = r.json()["data"]
    # Clear question must NOT trigger clarify — it runs and answers.
    assert data["status"] == "completed"
    assert data["needs_clarification"] is None
    assert data["generated_code"]
    assert data["step_count"] >= 1
    # 2-3 non-empty follow-ups.
    assert isinstance(data["followups"], list)
    assert 2 <= len(data["followups"]) <= 3
    assert all(isinstance(f, str) and f.strip() for f in data["followups"])


@pytest.mark.usefixtures("_require_llm_key")
def test_vague_question_triggers_clarify_and_runs_no_code(api_client):
    session_id, dataset_id = _upload(api_client)
    r = api_client.post(
        f"/sessions/{session_id}/messages",
        json={"question": "tell me stuff", "dataset_ids": [dataset_id]},
    )
    data = r.json()["data"]
    assert data["needs_clarification"] is not None
    assert data["needs_clarification"].strip()
    # No code ran on the clarify early-exit.
    assert not data["generated_code"]
    assert data["step_count"] == 0
    assert data["status"] == "needs_clarification"
