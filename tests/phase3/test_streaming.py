"""Live streaming SSE endpoint: real step + token events and a terminal done."""
import json
from pathlib import Path

import pytest

_CSV = Path(__file__).parent.parent / "fixtures" / "sales.csv"


def _upload(api_client):
    with _CSV.open("rb") as f:
        up = api_client.post(
            "/datasets", files={"file": ("sales.csv", f, "text/csv")}
        ).json()["data"]
    return up["session_id"], up["dataset_id"]


def _consume_sse(api_client, session_id, body):
    """Yield (event, data_dict) tuples from the SSE stream."""
    events = []
    with api_client.stream(
        "POST", f"/sessions/{session_id}/messages/stream", json=body
    ) as resp:
        assert resp.status_code == 200
        event = None
        for line in resp.iter_lines():
            if line == "":
                event = None
                continue
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                payload = line.split(":", 1)[1].strip()
                try:
                    events.append((event, json.loads(payload)))
                except json.JSONDecodeError:
                    events.append((event, payload))
    return events


@pytest.mark.usefixtures("_require_llm_key")
def test_stream_emits_steps_tokens_and_done(api_client):
    session_id, dataset_id = _upload(api_client)
    events = _consume_sse(
        api_client,
        session_id,
        {"question": "Show total order_value by region.", "dataset_ids": [dataset_id]},
    )

    kinds = [e for e, _ in events]
    assert kinds.count("step") >= 1
    assert kinds.count("token") >= 1
    assert kinds[-1] == "done"

    # Steps arrive in a sensible order (Planning before Running).
    labels = [d["label"] for e, d in events if e == "step"]
    assert "Planning…" in labels
    assert "Running code…" in labels

    done = [d for e, d in events if e == "done"][-1]
    assert done["status"] == "completed"
    assert done["answer_text"]
    assert done["charts"] or done["key_stats"]
    assert done["cost_usd"] and done["cost_usd"] > 0
    assert done["prompt_tokens"] > 0

    # Concatenated token text reconstructs the answer prose.
    tokens = "".join(d["text"] for e, d in events if e == "token")
    assert tokens.strip()


@pytest.mark.usefixtures("_require_llm_key")
def test_stream_vague_question_emits_clarify(api_client):
    session_id, dataset_id = _upload(api_client)
    events = _consume_sse(
        api_client,
        session_id,
        {"question": "tell me stuff", "dataset_ids": [dataset_id]},
    )
    kinds = [e for e, _ in events]
    assert "clarify" in kinds
    clarify = [d for e, d in events if e == "clarify"][0]
    assert clarify["question"].strip()
    # No code-running step on the clarify path.
    labels = [d.get("label") for e, d in events if e == "step"]
    assert "Running code…" not in labels
