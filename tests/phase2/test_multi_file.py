"""Multi-file + Excel integration tests (real Gemini via .env).

- Upload two related CSVs (customers + orders sharing customer_id) into one
  session and ask a question that requires joining them; assert a completed,
  non-empty answer and that the generated code references both via `dfs[...]`.
- Upload an Excel file; assert it is profiled and successfully analysed.
"""
from pathlib import Path

import pytest

_FX = Path(__file__).parent.parent / "fixtures"


def _upload(api_client, name, session_id=None):
    data = {}
    if session_id:
        data["session_id"] = session_id
    with (_FX / name).open("rb") as f:
        return api_client.post(
            "/datasets", data=data, files={"file": (name, f)}
        ).json()["data"]


@pytest.mark.usefixtures("_require_llm_key")
def test_join_two_csv_files(api_client):
    up1 = _upload(api_client, "customers.csv")
    session_id = up1["session_id"]
    up2 = _upload(api_client, "orders.csv", session_id=session_id)

    r = api_client.post(
        f"/sessions/{session_id}/messages",
        json={
            "question": (
                "Join customers and orders on customer_id and tell me the total "
                "order amount for each customer name."
            ),
            "dataset_ids": [up1["dataset_id"], up2["dataset_id"]],
        },
    )
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["answer_text"]
    code = data["generated_code"] or ""
    # The generated code must reach into the multi-file namespace.
    assert "dfs[" in code


@pytest.mark.usefixtures("_require_llm_key")
def test_excel_upload_profile_and_analysis(api_client):
    up = _upload(api_client, "sample.xlsx")
    assert up["file_type"] == "xlsx"
    assert isinstance(up["profile"], dict)
    assert up["profile"]["row_count"] == 5
    assert {c["name"] for c in up["profile"]["columns"]} == {"product", "price", "qty"}

    r = api_client.post(
        f"/sessions/{up['session_id']}/messages",
        json={"question": "What is the total qty across all rows?",
              "dataset_ids": [up["dataset_id"]]},
    )
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["answer_text"]
