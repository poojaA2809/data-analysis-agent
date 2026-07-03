"""Conversation-memory integration test (real Gemini via .env).

A two-turn conversation where the 2nd question is a follow-up that only makes
sense with prior context ("and which is the highest?"). Asserts the follow-up
completes coherently AND spies that the prior turns were injected into the
prompt sent to the model.
"""
from pathlib import Path

import pytest

import llm.client as llm_client

_CSV = Path(__file__).parent.parent / "fixtures" / "sales.csv"


@pytest.mark.usefixtures("_require_llm_key")
def test_followup_uses_prior_conversation(api_client, monkeypatch):
    with _CSV.open("rb") as f:
        up = api_client.post(
            "/datasets", files={"file": ("sales.csv", f, "text/csv")}
        ).json()["data"]
    session_id, dataset_id = up["session_id"], up["dataset_id"]

    # Turn 1: establish context.
    r1 = api_client.post(
        f"/sessions/{session_id}/messages",
        json={
            "question": "What is the total order_value per region?",
            "dataset_ids": [dataset_id],
        },
    )
    assert r1.json()["data"]["status"] == "completed"

    # Spy on the prompts sent to the model during turn 2 (delegating to the real API).
    captured: list[str] = []
    real_call = llm_client.LLMClient.call_model

    def _spy(self, prompt, *, system=None):
        captured.append(prompt)
        return real_call(self, prompt, system=system)

    monkeypatch.setattr(llm_client.LLMClient, "call_model", _spy)

    # Turn 2: a follow-up that relies on the prior turn.
    r2 = api_client.post(
        f"/sessions/{session_id}/messages",
        json={"question": "And which region is the highest?", "dataset_ids": [dataset_id]},
    )
    data = r2.json()["data"]
    assert data["status"] == "completed"
    assert data["answer_text"]
    assert data["generated_code"]

    # The prior conversation must have been injected into at least one prompt.
    joined = "\n".join(captured)
    assert "Prior conversation" in joined
    assert "total order_value per region" in joined
