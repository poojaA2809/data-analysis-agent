from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    session_id: str

    # Input
    question: str                   # optional on the dashboard path (synthetic objective)
    dataset_paths: list[str]
    dataset_schemas: list[dict]
    messages: list                  # prior chat turns (P2) — [{role, content}]

    # Auto-dashboard path (Phase A)
    dashboard_mode: bool            # selects dashboard prompts + dashboard_finalize
    dataset_id: str                 # the single dataset the dashboard is built for
    dashboard_title: str            # e.g. "sales.csv — overview"
    dashboard: dict                 # the assembled DashboardPayload

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
    charts: list                    # P3: chart specs
    tables: list                    # P3: summary table specs
    key_stats: list                 # P3: highlighted stats
    followups: list                 # P3: 2-3 suggested questions
    needs_clarification: str | None # P3: clarifying question, if unsure

    # Metering (P3)
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float

    # Control
    error: str | None
    status: str                     # completed | failed | needs_clarification
