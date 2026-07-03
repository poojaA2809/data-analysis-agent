"""Data-locality guarantee: only the column schema + a few sample rows are ever
sent to the LLM — never the full dataset.

This is a payload-assertion (prompt-spy) test, so the LLM call itself is stubbed:
we capture exactly what would be sent and assert that rows beyond the sample cap
never appear, while column names and the sampled rows do.
"""
import pandas as pd

import graph.nodes as nodes
from analysis.schema import derive_schema, _SAMPLE_ROWS

_SENTINEL = "ZZZSENTINEL_LATE_ROW_9999"


class _SpyLLM:
    """Drop-in for LLMClient that records every (prompt, system) it is handed."""

    calls: list[tuple[str, str | None]] = []

    def __init__(self) -> None:
        pass

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        _SpyLLM.calls.append((prompt, system))
        return "print('result', 1)"


def _make_wide_csv(tmp_path):
    rows = _SAMPLE_ROWS + 15  # comfortably more than the sample cap
    data = {
        "order_value": list(range(100, 100 + rows)),
        "region": [f"region_{i}" for i in range(rows)],
    }
    # Plant a sentinel that only exists well past the sample cap.
    data["region"][rows - 3] = _SENTINEL
    df = pd.DataFrame(data)
    path = tmp_path / "big.csv"
    df.to_csv(path, index=False)
    return str(path), rows


def test_only_schema_and_sample_rows_reach_llm(tmp_path, monkeypatch):
    csv_path, total_rows = _make_wide_csv(tmp_path)
    schema = derive_schema(csv_path, name="big")

    # Sanity: the fixture really is larger than the sample cap and the sentinel
    # lives beyond it.
    assert total_rows > _SAMPLE_ROWS
    assert len(schema["sample_rows"]) == _SAMPLE_ROWS
    assert schema["row_count"] == total_rows

    _SpyLLM.calls = []
    monkeypatch.setattr(nodes, "LLMClient", _SpyLLM)

    state = {
        "run_id": "loc-test",
        "question": "What is the average order_value?",
        "dataset_schemas": [schema],
        "dataset_paths": [csv_path],
        "step_count": 0,
    }

    state = nodes.plan(state)
    assert "error" not in state, state.get("error")
    nodes.generate_code(state)

    assert _SpyLLM.calls, "expected the LLM to be invoked by plan/generate_code"
    blob = "".join(p + (s or "") for p, s in _SpyLLM.calls)

    # Full dataset never leaves the box: the late-row sentinel is absent.
    assert _SENTINEL not in blob, "full dataset (late row) leaked to the LLM"

    # But the schema IS present: column names and the sampled rows.
    assert "order_value" in blob and "region" in blob
    assert "region_0" in blob  # a first-page sample value
    assert str(schema["sample_rows"][0]["order_value"]) in blob
