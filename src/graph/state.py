from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    session_id: str

    # Input
    question: str
    dataset_paths: list[str]
    dataset_schemas: list[dict]
    messages: list                  # prior chat turns (P2) — [{role, content}]

    # Pipeline data (populated progressively)
    plan: str
    generated_code: str
    execution_stdout: str
    execution_result: str
    execution_error: str | None
    critique: str
    critique_verdict: str           # "ok" | "needs-fix"
    step_count: int

    # Output
    answer_text: str

    # Control
    error: str | None
    status: str                     # completed | failed
