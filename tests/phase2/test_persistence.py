"""Persistence + history-read integration tests (real Gemini via .env).

Uploads a CSV, asks a real question, then reloads the session and asserts the
datasets (with a REAL parsed profile), messages, and runs all survive — including
across a fresh DB session handle (a "return next day" restart simulation).
"""
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import DatasetRow, MessageRow, RunRow, SessionRow

_CSV = Path(__file__).parent.parent / "fixtures" / "sales.csv"


@pytest.mark.usefixtures("_require_llm_key")
def test_session_persists_and_lists(api_client, _isolated_db):
    with _CSV.open("rb") as f:
        up = api_client.post(
            "/datasets", files={"file": ("sales.csv", f, "text/csv")}
        ).json()["data"]
    session_id, dataset_id = up["session_id"], up["dataset_id"]

    # The upload response already carries a real deterministic profile.
    assert isinstance(up["profile"], dict)
    assert up["profile"]["row_count"] == 6

    r = api_client.post(
        f"/sessions/{session_id}/messages",
        json={"question": "What is the average order_value?", "dataset_ids": [dataset_id]},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "completed"

    # Reload the session bundle — datasets carry the real profile now, not null.
    detail = api_client.get(f"/sessions/{session_id}").json()["data"]
    assert len(detail["datasets"]) == 1
    ds = detail["datasets"][0]
    assert isinstance(ds["profile"], dict)
    assert ds["profile"]["row_count"] == 6
    assert {c["name"] for c in ds["profile"]["columns"]} == {
        "region", "order_value", "units"
    }
    roles = [m["role"] for m in detail["messages"]]
    assert "user" in roles and "assistant" in roles
    assert len(detail["runs"]) == 1
    assert detail["runs"][0]["status"] == "completed"

    # The sidebar list includes this session with counts.
    listing = api_client.get("/sessions").json()["data"]["sessions"]
    ids = [s["id"] for s in listing]
    assert session_id in ids
    entry = next(s for s in listing if s["id"] == session_id)
    assert entry["dataset_count"] == 1
    assert entry["message_count"] >= 2
    assert entry["updated_at"]

    # "Return next day": a brand-new DB session handle against the SAME file/db
    # still sees everything (nothing was memory-only).
    with Session(_isolated_db) as s:
        sess = s.get(SessionRow, session_id)
        assert sess is not None
        datasets = s.scalars(
            select(DatasetRow).where(DatasetRow.session_id == session_id)
        ).all()
        assert len(datasets) == 1
        assert datasets[0].profile_json  # persisted profile JSON
        messages = s.scalars(
            select(MessageRow).where(MessageRow.session_id == session_id)
        ).all()
        assert len(messages) >= 2
        runs = s.scalars(
            select(RunRow).where(RunRow.session_id == session_id)
        ).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"


@pytest.mark.usefixtures("_require_llm_key")
def test_sessions_ordered_by_updated_at(api_client):
    # Two sessions, each with activity; the most recently active sorts first.
    with _CSV.open("rb") as f:
        up1 = api_client.post(
            "/datasets", files={"file": ("sales.csv", f, "text/csv")}
        ).json()["data"]
    api_client.post(
        f"/sessions/{up1['session_id']}/messages",
        json={"question": "How many rows?", "dataset_ids": [up1["dataset_id"]]},
    )
    with _CSV.open("rb") as f:
        up2 = api_client.post(
            "/datasets", files={"file": ("sales.csv", f, "text/csv")}
        ).json()["data"]
    api_client.post(
        f"/sessions/{up2['session_id']}/messages",
        json={"question": "How many rows?", "dataset_ids": [up2["dataset_id"]]},
    )

    listing = api_client.get("/sessions").json()["data"]["sessions"]
    ids = [s["id"] for s in listing]
    # Session 2 was active last → it appears before session 1.
    assert ids.index(up2["session_id"]) < ids.index(up1["session_id"])
