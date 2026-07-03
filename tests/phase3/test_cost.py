"""Cost metering: compute_cost unit + daily aggregation, plus a real integration."""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from db.models import RunRow, SessionRow
from observability.cost import compute_cost, daily_usage

_CSV = Path(__file__).parent.parent / "fixtures" / "sales.csv"


def test_compute_cost_uses_price_constants():
    # defaults: input 0.30 / output 2.50 per Mtok
    cost = compute_cost(1_000_000, 1_000_000)
    assert cost == pytest.approx(0.30 + 2.50)


def test_daily_usage_sums_todays_runs(_isolated_db):
    with Session(_isolated_db) as s:
        sess = SessionRow(title="t")
        s.add(sess)
        s.flush()
        s.add(
            RunRow(
                session_id=sess.id,
                question="q",
                status="completed",
                prompt_tokens=100,
                completion_tokens=50,
                cost_usd=0.01,
                created_at=datetime.now(timezone.utc),
            )
        )
        s.commit()
        out = daily_usage(s)
    assert out["prompt_tokens"] == 100
    assert out["completion_tokens"] == 50
    assert out["cost_usd"] == pytest.approx(0.01)


def _upload(api_client):
    with _CSV.open("rb") as f:
        up = api_client.post(
            "/datasets", files={"file": ("sales.csv", f, "text/csv")}
        ).json()["data"]
    return up["session_id"], up["dataset_id"]


@pytest.mark.usefixtures("_require_llm_key")
def test_real_run_records_tokens_and_cost(api_client):
    session_id, dataset_id = _upload(api_client)
    r = api_client.post(
        f"/sessions/{session_id}/messages",
        json={"question": "What is the total order_value by region?",
              "dataset_ids": [dataset_id]},
    )
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["prompt_tokens"] and data["prompt_tokens"] > 0
    assert data["completion_tokens"] and data["completion_tokens"] > 0
    assert data["cost_usd"] and data["cost_usd"] > 0

    daily = api_client.get("/usage/daily").json()["data"]
    assert "date" in daily
    assert daily["prompt_tokens"] >= data["prompt_tokens"]
    assert daily["completion_tokens"] >= data["completion_tokens"]
    assert daily["cost_usd"] >= data["cost_usd"]
