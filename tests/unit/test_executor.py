"""Executor tests — no LLM key required. Runs a real subprocess against pandas."""
from pathlib import Path

from analysis.executor import execute_python

_CSV = str(Path(__file__).parent.parent / "fixtures" / "sales.csv")


def test_executor_returns_result():
    out = execute_python("result = len(df)", [_CSV])
    assert out["error"] is None
    assert out["result"] == 6


def test_executor_computes_aggregate():
    out = execute_python("result = df['order_value'].mean()", [_CSV])
    assert out["error"] is None
    assert abs(float(out["result"]) - 175.0) < 1e-6


def test_executor_captures_bad_code_without_crashing():
    out = execute_python("result = df['nonexistent_column'].sum()", [_CSV])
    assert out["error"]  # error captured, not raised
    assert out["result"] is None


def test_executor_captures_stdout():
    out = execute_python("print('hello'); result = 1", [_CSV])
    assert "hello" in out["stdout"]
    assert out["result"] == 1


def test_executor_dfs_dict_available():
    out = execute_python("result = list(dfs.keys())", [_CSV])
    assert out["error"] is None
    assert out["result"] == ["sales"]
