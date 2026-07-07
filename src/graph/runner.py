"""Runner: create the run row, invoke the graph, persist results + assistant message.

Exposes helpers reused by both the synchronous ask endpoint and the SSE stream
endpoint so both persist runs identically and return the same enriched payload.
"""
import json
import time
from datetime import datetime, timezone

from db.models import RunRow, MessageRow, SessionRow
from db.session import create_db_session
from graph.agent import agentic_ai, dashboard_ai
from graph.state import AgentState
from observability.cost import compute_cost
from observability.events import get_logger

_log = get_logger("graph.runner")


def create_run_row(
    session_id: str, question: str, dataset_ids: list[str] | None
) -> str:
    """Insert a pending run row; return its id."""
    with create_db_session() as session:
        run = RunRow(
            session_id=session_id,
            question=question,
            dataset_ids=json.dumps(dataset_ids or []),
            status="pending",
            step_count=0,
        )
        session.add(run)
        session.flush()
        return run.id


def build_initial_state(
    run_id: str,
    session_id: str,
    question: str,
    dataset_paths: list[str],
    dataset_schemas: list[dict],
    messages: list[dict] | None,
) -> AgentState:
    return {
        "run_id": run_id,
        "session_id": session_id,
        "question": question,
        "dataset_paths": dataset_paths,
        "dataset_schemas": dataset_schemas,
        "messages": messages or [],
        "step_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "error": None,
    }


def result_payload(run_id: str, final: dict) -> dict:
    """Build the enriched AskResponse payload from a final graph state."""
    status = final.get("status") or ("failed" if final.get("error") else "completed")
    pt = final.get("prompt_tokens") or 0
    ct = final.get("completion_tokens") or 0
    cost = compute_cost(pt, ct) if (pt or ct) else None
    return {
        "run_id": run_id,
        "status": status,
        "answer_text": final.get("answer_text"),
        "generated_code": final.get("generated_code"),
        "step_count": final.get("step_count", 0),
        "needs_clarification": final.get("needs_clarification"),
        "charts": final.get("charts") or [],
        "tables": final.get("tables") or [],
        "key_stats": final.get("key_stats") or [],
        "followups": final.get("followups") or [],
        "prompt_tokens": pt or None,
        "completion_tokens": ct or None,
        "cost_usd": cost,
        "error": final.get("error"),
    }


def persist_run(session_id: str, run_id: str, final: dict) -> dict:
    """Persist the run row + assistant message; return the enriched payload."""
    payload = result_payload(run_id, final)
    status = payload["status"]
    answer = payload["answer_text"]
    now = datetime.now(timezone.utc)

    message_id = None
    with create_db_session() as session:
        if status == "completed" and answer:
            msg = MessageRow(session_id=session_id, role="assistant", content=answer)
            session.add(msg)
            session.flush()
            message_id = msg.id

        run = session.get(RunRow, run_id)
        run.status = status
        run.message_id = message_id
        run.plan_json = final.get("plan")
        run.generated_code = final.get("generated_code")
        run.execution_stdout = final.get("execution_stdout")
        run.result_json = final.get("execution_result")
        run.answer_text = answer
        run.step_count = final.get("step_count", 0)
        run.prompt_tokens = payload["prompt_tokens"]
        run.completion_tokens = payload["completion_tokens"]
        run.cost_usd = payload["cost_usd"]
        run.error_message = final.get("error")
        run.completed_at = now

        sess = session.get(SessionRow, session_id)
        if sess is not None:
            sess.updated_at = now

    return payload


def run_agent(
    session_id: str,
    question: str,
    dataset_paths: list[str],
    dataset_schemas: list[dict],
    *,
    dataset_ids: list[str] | None = None,
    messages: list[dict] | None = None,
) -> dict:
    """Run the analyze_dataset agent synchronously. Returns the enriched payload."""
    started = time.monotonic()
    run_id = create_run_row(session_id, question, dataset_ids)
    _log.info("run.start", run_id=run_id, session_id=session_id, question=question[:120])

    initial = build_initial_state(
        run_id, session_id, question, dataset_paths, dataset_schemas, messages
    )

    try:
        final = agentic_ai.invoke(initial)
    except Exception as exc:  # noqa: BLE001 — never crash the request
        final = {"status": "failed", "error": str(exc)}

    payload = persist_run(session_id, run_id, final)
    _log.info(
        "run.done",
        run_id=run_id,
        status=payload["status"],
        step_count=payload["step_count"],
        prompt_tokens=payload["prompt_tokens"],
        completion_tokens=payload["completion_tokens"],
        cost_usd=payload["cost_usd"],
        latency_ms=int((time.monotonic() - started) * 1000),
        error=payload["error"],
    )
    return payload


_DASHBOARD_QUESTION = "[auto-dashboard]"


def run_dashboard(
    session_id: str,
    dataset_id: str,
    dataset_path: str,
    dataset_schema: dict,
    *,
    title: str = "",
) -> dict:
    """Run the auto-dashboard flow synchronously for ONE dataset. Reuses the
    plan→generate_code→execute_code→observe loop in dashboard mode, persists a
    `runs` row exactly like the ask path, and returns a DashboardPayload dict.

    Never raises — on any failure returns a payload with status="failed" + error.
    """
    started = time.monotonic()
    run_id = create_run_row(session_id, _DASHBOARD_QUESTION, [dataset_id])
    _log.info("dashboard.start", run_id=run_id, session_id=session_id, dataset_id=dataset_id)

    initial: AgentState = {
        "run_id": run_id,
        "session_id": session_id,
        "question": _DASHBOARD_QUESTION,
        "dataset_paths": [dataset_path],
        "dataset_schemas": [dataset_schema],
        "dataset_id": dataset_id,
        "dashboard_title": title,
        "dashboard_mode": True,
        "messages": [],
        "step_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "error": None,
    }

    try:
        final = dashboard_ai.invoke(initial)
    except Exception as exc:  # noqa: BLE001 — never crash the request
        final = {"status": "failed", "error": str(exc)}

    # Persist the run row (tokens/cost/status/step_count) like the ask path.
    persist_run(session_id, run_id, final)

    dashboard = final.get("dashboard")
    if not isinstance(dashboard, dict):
        dashboard = {
            "dataset_id": dataset_id,
            "title": title,
            "charts": [],
            "summary_table": {"title": "", "columns": [], "rows": []},
            "insights": [],
            "data_grid": {"columns": [], "rows": [], "total_rows": 0},
            "status": "failed",
            "error": final.get("error") or "dashboard generation failed",
        }
    _log.info(
        "dashboard.done",
        run_id=run_id,
        status=dashboard.get("status"),
        charts=len(dashboard.get("charts", [])),
        insights=len(dashboard.get("insights", [])),
        latency_ms=int((time.monotonic() - started) * 1000),
        error=dashboard.get("error"),
    )
    return dashboard
