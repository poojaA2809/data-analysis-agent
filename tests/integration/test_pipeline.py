"""Real end-to-end integration — requires a real LLM key (from .env).

These exercise the full analyze_dataset capability against the real Google Gemini
API and a real subprocess pandas executor. They skip ONLY if no key is present.
"""
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from db import session as session_module
from db.models import RunRow

_CSV = Path(__file__).parent.parent / "fixtures" / "sales.csv"


def _create_session_with_dataset(api_client):
    with _CSV.open("rb") as f:
        up = api_client.post(
            "/datasets", files={"file": ("sales.csv", f, "text/csv")}
        ).json()["data"]
    return up["session_id"], up["dataset_id"]


@pytest.mark.usefixtures("_require_llm_key")
def test_happy_path_average(api_client, _isolated_db):
    """Upload CSV, ask a plain question, get a real answer + code + persisted run."""
    session_id, dataset_id = _create_session_with_dataset(api_client)

    r = api_client.post(
        f"/sessions/{session_id}/messages",
        json={"question": "What is the average order_value?", "dataset_ids": [dataset_id]},
    )
    assert r.status_code == 200
    data = r.json()["data"]

    assert data["status"] == "completed"
    assert data["answer_text"] and len(data["answer_text"]) > 0
    assert data["generated_code"] and "result" in data["generated_code"]
    assert data["step_count"] >= 1
    # The real average of order_value in the fixture is 175.
    assert "175" in data["answer_text"] or "175" in (data["generated_code"] or "")

    # Run persisted with completed status.
    with Session(_isolated_db) as s:
        run = s.get(RunRow, data["run_id"])
        assert run is not None
        assert run.status == "completed"
        assert run.answer_text
        assert run.generated_code
        assert json.loads(run.dataset_ids) == [dataset_id]


@pytest.mark.usefixtures("_require_llm_key")
def test_row_count_question(api_client, _isolated_db):
    """Edge-ish: a counting question; assert structure + persisted assistant message."""
    session_id, dataset_id = _create_session_with_dataset(api_client)

    r = api_client.post(
        f"/sessions/{session_id}/messages",
        json={"question": "How many rows are in the dataset?", "dataset_ids": [dataset_id]},
    )
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["answer_text"]

    # Session detail now shows a user + assistant message and the run.
    detail = api_client.get(f"/sessions/{session_id}").json()["data"]
    roles = [m["role"] for m in detail["messages"]]
    assert "user" in roles and "assistant" in roles
    assert len(detail["runs"]) == 1


@pytest.mark.usefixtures("_require_llm_key")
def test_iterating_question_still_finalizes(api_client, _isolated_db):
    """A harder question that may need a code fix — the loop must still finalize.

    Assert on structure (finalized answer within the step budget), not exact prose.
    """
    session_id, dataset_id = _create_session_with_dataset(api_client)

    r = api_client.post(
        f"/sessions/{session_id}/messages",
        json={
            "question": "Which region has the highest total order_value, and what is that total?",
            "dataset_ids": [dataset_id],
        },
    )
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["answer_text"]
    assert data["generated_code"]
    # Loop is bounded: at least one and no more than max_steps generate cycles.
    from config.settings import get_settings
    assert 1 <= data["step_count"] <= get_settings().max_steps
